from __future__ import annotations

from pathlib import Path
from datetime import datetime
import sqlite3
from typing import Tuple, Optional
import base64, docx, pytesseract
from PIL import Image

from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers import OpenAIWhisperParser

import streamlit as st


def _ensure_dir(path: Path) -> None:
	"""디렉토리 보장 생성."""
	path.mkdir(parents=True, exist_ok=True)


def _now_stamp() -> str:
	"""YYYYMMDD_HHMMSS 포맷 타임스탬프 반환."""
	return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_text_from_file(file_path: Path) -> str:
	"""PDF, DOCX, TXT에서 텍스트 추출. 불가 시 빈 문자열.

	- PDF: PyPDFLoader 사용
	- DOCX: python-docx 사용
	- TXT: UTF-8 기본, 실패 시 cp949 재시도
	"""
	suffix = file_path.suffix.lower()
	text = ""
	if suffix == ".txt":
		try:
			text = file_path.read_text(encoding="utf-8")
		except Exception:
			try:
				text = file_path.read_text(encoding="cp949")
			except Exception:
				text = ""
	elif suffix == ".docx" and docx is not None:
		try:
			d = docx.Document(str(file_path))
			text = "\n".join(p.text for p in d.paragraphs)
		except Exception:
			text = ""
	elif suffix == ".pdf" and PyPDFLoader is not None:
		try:
			reader = PyPDFLoader(str(file_path))
			pages = []
			for p in reader.pages:
				try:
					pages.append(p.extract_text() or "")
				except Exception:
					pages.append("")
			text = "\n".join(pages)
		except Exception:
			text = ""
	return text.strip()


def _get_embeddings():
	"""임베딩 모델 로더. session state에서 관리하여 재사용.
	
	필요 패키지가 없으면 예외를 던진다.
	"""
	# Streamlit session state에서 임베딩 모델 관리
	if "embeddings_model" not in st.session_state:
		st.session_state.embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
	return st.session_state.embeddings_model


def _get_text_splitter():
	"""텍스트 분할기를 session state에서 관리하여 재사용."""
	if "text_splitter" not in st.session_state:
		st.session_state.text_splitter = RecursiveCharacterTextSplitter(
			chunk_size=700,
			chunk_overlap=120,
			separators=["\n\n", "\n", " ", ""],
		)
	return st.session_state.text_splitter


def _get_chat_llm() -> ChatOpenAI:
	"""ChatOpenAI 모델을 session state에서 관리하여 재사용.

	기본 모델은 gpt-5, 필요 시 환경에 맞게 교체 가능.
	"""
	if "chat_llm" not in st.session_state:
		try:
			st.session_state.chat_llm = ChatOpenAI(model="gpt-5", temperature=0.2)
		except Exception:
			# 폴백: 배포 환경에서 gpt-5 미지원 시 대체 모델 사용
			st.session_state.chat_llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
	return st.session_state.chat_llm


def chat_generate_response(
	user_input: str,
	conn: sqlite3.Connection,
	project_id: int,
	vdb_root: Path,
	history: list[tuple[str, str]] | None = None,
	system_prompt: str | None = None,
	k: int = 4,
) -> str:
	"""대화 이력과 사용자 입력을 받아 RAG 기반 응답을 생성합니다.

	- history: [(role, content)] where role in ("user", "bot")
	- system_prompt: 대화 지침이 필요한 경우 전달
	- 프로젝트의 FAISS 벡터스토어에서 상위 k개 유사 문맥을 검색하여 프롬프트에 주입
	"""
	# 1) 프로젝트 벡터스토어에서 컨텍스트 검색
	context_text = ""
	try:
		embeddings = _get_embeddings()
		proj_dir = _get_or_create_project_vector_dir(conn, project_id, vdb_root)
		index_faiss = proj_dir / "index.faiss"
		index_pkl = proj_dir / "index.pkl"
		if index_faiss.exists() and index_pkl.exists():
			vs = FAISS.load_local(str(proj_dir), embeddings, allow_dangerous_deserialization=True)
			docs = vs.similarity_search(user_input, k=k)
			context_chunks: list[str] = []
			for d in docs:
				meta = d.metadata or {}
				src = meta.get("source", "")
				title = meta.get("title", "")
				context_chunks.append(f"[Title:{title}] [Source:{src}]\n{d.page_content}")
			context_text = "\n\n---\n".join(context_chunks)
	except Exception:
		context_text = ""

	# 2) 메시지 구성
	messages: list = []
	sys_prompt_default = (
		"당신은 프로젝트 컨텍스트를 활용하여 정확하고 간결한 답변을 제공하는 어시스턴트입니다.\n"
		"근거가 되는 문맥이 충분치 않다면 추측하지 말고 추가 질문을 하세요."
	)
	messages.append(SystemMessage(content=system_prompt or sys_prompt_default))
	if context_text:
		messages.append(SystemMessage(content=f"프로젝트 관련 참고 문맥:\n{context_text}"))
	if history:
		for role, content in history:
			if role == "user":
				messages.append(HumanMessage(content=content))
			else:
				messages.append(AIMessage(content=content))
	messages.append(HumanMessage(content=user_input))

	# 3) 모델 호출
	llm = _get_chat_llm()
	resp = llm.invoke(messages)
	return getattr(resp, "content", "") or ""


def clear_embedding_cache():
	"""session state의 임베딩 모델 캐시를 정리합니다."""
	if "embeddings_model" in st.session_state:
		del st.session_state.embeddings_model
	if "text_splitter" in st.session_state:
		del st.session_state.text_splitter


def get_embedding_model_info():
	"""현재 사용 중인 임베딩 모델 정보를 반환합니다."""
	if "embeddings_model" in st.session_state:
		model = st.session_state.embeddings_model
		return {
			"model_name": getattr(model, "model", "unknown"),
			"cached": True,
			"type": type(model).__name__
		}
	else:
		return {
			"model_name": "text-embedding-ada-002",
			"cached": False,
			"type": "OpenAIEmbeddings"
		}


def _get_or_create_project_vector_dir(conn: sqlite3.Connection, project_id: int, vdb_root: Path) -> Path:
	"""프로젝트별 벡터스토어 디렉토리를 반환하고, 없으면 생성.

	- DB PROJECT.vectorpath 값이 있으면 그대로 사용
	- 값이 없으면 vdb_root/project_{id} 경로를 생성 후 DB에 저장
	"""
	cur = conn.cursor()
	cur.execute("SELECT vectorpath FROM PROJECT WHERE projectid = ?", (project_id,))
	row = cur.fetchone()
	# 1) DB에 경로가 있으면 그대로 사용
	if row and row[0]:
		proj_dir = Path(row[0])
		_ensure_dir(proj_dir)
		return proj_dir
	# 2) 없으면 기본 규칙 경로를 생성하고 DB 업데이트
	proj_dir = vdb_root / f"project_{project_id}"
	_ensure_dir(proj_dir)
	cur.execute("UPDATE PROJECT SET vectorpath = ? WHERE projectid = ?", (str(proj_dir), project_id))
	conn.commit()
	return proj_dir


def _save_uploaded_file_bytes(data_dir: Path, filename: str, file_bytes: bytes) -> Path:
	"""원본 파일을 data 디렉토리에 저장하고 경로 반환."""
	_ensure_dir(data_dir)
	path = data_dir / filename
	path.write_bytes(file_bytes)
	return path


def vectorize_and_store_text(
	conn: sqlite3.Connection,
	project_id: int,
	text: str,
	source_path: Path,
	title: str,
	selected_type: str,
	vdb_root: Path,
) -> None:
	"""주어진 텍스트를 분할→임베딩→FAISS에 병합/저장까지 수행.

	- 프로젝트별 디렉토리를 생성/확인하고, 기존 인덱스가 있으면 병합 저장
	- 텍스트가 비어 있으면 아무 작업도 하지 않음
	"""
	if not text:
		return
	embeddings = _get_embeddings()
	splitter = _get_text_splitter()
	chunks = splitter.split_text(text)
	if not chunks:
		return
	metadatas = [
		{"source": str(source_path), "title": title, "type": selected_type, "project_id": project_id}
	] * len(chunks)
	proj_dir = _get_or_create_project_vector_dir(conn, project_id, vdb_root)
	index_faiss = proj_dir / "index.faiss"
	index_pkl = proj_dir / "index.pkl"
	if index_faiss.exists() and index_pkl.exists():
		vs = FAISS.load_local(str(proj_dir), embeddings, allow_dangerous_deserialization=True)
		vs.add_texts(chunks, metadatas=metadatas)
		vs.save_local(str(proj_dir))
	else:
		vs = FAISS.from_texts(texts=chunks, embedding=embeddings, metadatas=metadatas)
		vs.save_local(str(proj_dir))


def archive_text_and_vectorize(
	conn: sqlite3.Connection,
	user_id: int,
	project_id: int,
	title: str,
	description: Optional[str],
	selected_type: str,
	uploaded_filename: str,
	file_bytes: bytes,
	data_root: Path,
	vdb_root: Path,
) -> Tuple[bool, str, Optional[Path]]:
	"""텍스트 파일(PDF/DOCX/TXT)을 저장하고, 텍스트를 벡터화하여 프로젝트 벡터스토어에 추가.

	반환: (성공여부, 메시지, 저장된 data 파일 경로)
	"""
	try:
		# 1) 파일명 규칙: title_날짜(연월일)_시간(시분초)_selected_type.원본확장자
		now = _now_stamp()  # YYYYMMDD_HHMMSS
		suffix = Path(uploaded_filename).suffix.lower()
		clean_title = title.replace("/", "-").replace("\\", "-").strip()
		final_name = f"{clean_title}_{now}_{selected_type}{suffix}"
		data_dir = data_root
		data_path = _save_uploaded_file_bytes(data_dir, final_name, file_bytes)

		# 2) 텍스트 추출
		text = _read_text_from_file(data_path)
		if not text:
			return False, "텍스트를 추출할 수 없습니다. 지원되지 않는 형식이거나 내용이 비어 있습니다.", data_path

		# 3) 텍스트 벡터화 및 저장 (공용 모듈 사용)
		vectorize_and_store_text(
			conn=conn,
			project_id=project_id,
			text=text,
			source_path=data_path,
			title=title,
			selected_type=selected_type,
			vdb_root=vdb_root,
		)

		# 4) ARCHIVE 테이블에 저장
		cur = conn.cursor()
		cur.execute(
			"""
			INSERT INTO ARCHIVE (userid, path, archivename, archivetype, archiveexpl, projectid)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(user_id, str(data_path), title, selected_type, description or None, project_id),
		)
		conn.commit()
		return True, "아카이브 저장 및 벡터화가 완료되었습니다.", data_path
	except Exception as e:
		return False, f"오류: {e}", None


# 향후 확장용: 오디오/이미지의 경우에도 원본 저장 및 ARCHIVE 입력은 동일하게 처리하고
# 벡터화는 전사(whisper) 또는 OCR(pytesseract) 성공 시에만 수행한다.

def archive_audio_and_vectorize(
	conn: sqlite3.Connection,
	user_id: int,
	project_id: int,
	title: str,
	description: Optional[str],
	selected_type: str,
	uploaded_filename: str,
	file_bytes: bytes,
	data_root: Path,
	vdb_root: Path,
) -> Tuple[bool, str, Optional[Path]]:
	"""오디오 원본 저장 및(선택적으로) 전사 후 텍스트 벡터화.

	의존성/환경에 따라 전사를 건너뛸 수 있으며, 그 경우에도 ARCHIVE 저장은 수행한다.
	"""
	try:
		now = _now_stamp()
		suffix = Path(uploaded_filename).suffix.lower()
		clean_title = title.replace("/", "-").replace("\\", "-").strip()
		final_name = f"{clean_title}_{now}_{selected_type}{suffix}"
		data_path = _save_uploaded_file_bytes(data_root, final_name, file_bytes)

		# ARCHIVE 저장 선반영
		cur = conn.cursor()
		cur.execute(
			"""
			INSERT INTO ARCHIVE (userid, path, archivename, archivetype, archiveexpl, projectid)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(user_id, str(data_path), title, selected_type, description or None, project_id),
		)
		conn.commit()

		# 전사 시도: LangChain OpenAI Whisper 파서 사용
		text = ""
		try:
			loader = GenericLoader.from_filesystem(str(data_path), parser=OpenAIWhisperParser())
			docs = loader.load()
			text = "\n\n".join(d.page_content for d in docs).strip()
		except Exception:
			text = ""

			# 텍스트 벡터화 (공용 모듈 사용)
			vectorize_and_store_text(
				conn=conn,
				project_id=project_id,
				text=text,
				source_path=data_path,
				title=title,
				selected_type=selected_type,
				vdb_root=vdb_root,
			)
			return True, "오디오 저장 및 전사/벡터화가 완료되었습니다.", data_path

		# 텍스트가 없으면 저장만 하고 종료
		if not text:
			return True, "오디오는 아카이브에 저장되었고, 전사에 실패했습니다.", data_path

	except Exception as e:
			return False, f"오류: {e}", None


def archive_image_and_vectorize(
	conn: sqlite3.Connection,
	user_id: int,
	project_id: int,
	title: str,
	description: Optional[str],
	selected_type: str,
	uploaded_filename: str,
	file_bytes: bytes,
	data_root: Path,
	vdb_root: Path,
) -> Tuple[bool, str, Optional[Path]]:
	"""이미지 원본 저장 후 텍스트화(멀티모달 우선, 실패 시 OCR)하여 벡터화.

	- 1순위: OpenAI 비전 모델로 이미지 캡셔닝/텍스트화
	- 실패 시: pytesseract OCR 폴백
	- 어느 쪽이든 텍스트가 생성되면 프로젝트 벡터스토어에 반영
	"""
	try:
		now = _now_stamp()
		suffix = Path(uploaded_filename).suffix.lower()
		clean_title = title.replace("/", "-").replace("\\", "-").strip()
		final_name = f"{clean_title}_{now}_{selected_type}{suffix}"
		data_path = _save_uploaded_file_bytes(data_root, final_name, file_bytes)

		# ARCHIVE 저장 선반영
		cur = conn.cursor()
		cur.execute(
			"""
			INSERT INTO ARCHIVE (userid, path, archivename, archivetype, archiveexpl, projectid)
			VALUES (?, ?, ?, ?, ?, ?)
			""",
			(user_id, str(data_path), title, selected_type, description or None, project_id),
		)
		conn.commit()

		# 1) OpenAI 비전 모델 시도 (LangChain ChatOpenAI, base64 data URL)
		text = ""
		try:
			mime = "image/png" if suffix in (".png",) else "image/jpeg"
			b64 = base64.b64encode(Path(data_path).read_bytes()).decode("utf-8")
			image_url = f"data:{mime};base64,{b64}"
			llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
			message = HumanMessage(
				content=[
					{"type": "text", "text": "이미지의 핵심 텍스트와 의미를 한국어로 추출/요약해 주세요."},
					{"type": "image_url", "image_url": {"url": image_url}},
				]
			)
			resp = llm.invoke([message])
			text = (getattr(resp, "content", "") or "").strip()
		except Exception:
			text = ""

		# 2) OCR 폴백 (pytesseract 사용 가능 시)
		if not text and pytesseract is not None and Image is not None:
			try:
				img = Image.open(str(data_path))
				text = pytesseract.image_to_string(img, lang="eng+kor")
				text = (text or "").strip()
			except Exception:
				text = ""

		# 텍스트 벡터화 (공용 모듈 사용)
		vectorize_and_store_text(
			conn=conn,
			project_id=project_id,
			text=text,
			source_path=data_path,
			title=title,
			selected_type=selected_type,
			vdb_root=vdb_root,
		)

		if not text:
			return True, "이미지는 아카이브에 저장되었고, 텍스트화에 실패했습니다.", data_path

		return True, "이미지 저장 및 텍스트화/벡터화가 완료되었습니다.", data_path
	except Exception as e:
		return False, f"오류: {e}", None


