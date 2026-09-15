from pathlib import Path
import streamlit as st
from db_utils import get_cached_db_connection, get_projects_by_completed, count_projects_by_completed, create_project, set_project_completed, insert_chatlog
from utils import (
	archive_text_and_vectorize,
	archive_audio_and_vectorize,
	archive_image_and_vectorize,
    chat_generate_response,
)
from ui import header, quick_actions, page_header


def _list_card(assets_dir: Path, db_path: Path, name: str, expl: str | None, index: int, show_actions: bool = True, allow_revert: bool = False) -> None:
	with st.container(border=True):
		left, center, right = st.columns([1, 3, 1])
		with left:
			st.image(assets_dir / "img/project.png", width=60)
		with center:
			st.markdown(f"**{name}**")
			st.caption(f"{expl or ''}")
		with right:
			with st.container(border=False):
				if allow_revert:
					# 버튼을 중앙 정렬하기 위한 CSS 스타일 적용
					st.markdown(
						"""
						<style>
						[data-testid=\"stButton\"] {
							display: flex;
							align-items: center;
							justify-content: center;
							height: 50%;
						}
						</style>
						""",
						unsafe_allow_html=True,
					)
					if st.button("되돌리기", key=f"revert_btn_{index}", type="secondary", icon=":material/undo:", use_container_width=True):
						conn = get_cached_db_connection(db_path)
						ok, msg = set_project_completed(conn, project_name=name, completed=0)
						if ok:
							st.success("프로젝트가 진행 중으로 변경되었습니다.")
							st.rerun()
						else:
							st.error(msg)
				elif show_actions:
					# 버튼을 중앙 정렬하기 위한 CSS 스타일 적용
					st.markdown(
						"""
						<style>
						[data-testid=\"stButton\"] {
							display: flex;
							align-items: center;
							justify-content: center;
							height: 50%;
						}
						</style>
						""",
						unsafe_allow_html=True,
					)
					if st.button("기록하기", key=f"more_btn_{index}", type="secondary", icon=":material/arrow_forward:", use_container_width=True):
						st.session_state["page_state"].append("record")
						st.session_state["selected_project"] = name
						st.rerun()
					if st.button("완료하기", key=f"complete_btn_{index}", type="secondary", icon=":material/check:", use_container_width=True):
						conn = get_cached_db_connection(db_path)
						ok, msg = set_project_completed(conn, project_name=name, completed=1)
						if ok:
							st.success("프로젝트가 완료로 변경되었습니다.")
							st.rerun()
						else:
							st.error(msg)


def render_project_list_screen(assets_dir: Path, db_path: Path) -> None:
	page_header(assets_dir, "프로젝트 리스트")
	st.subheader("진행 중 프로젝트")
	st.caption("Ongoing Projects")
	ongoing = get_projects_by_completed(get_cached_db_connection(db_path), completed=0, limit=None)
	if not ongoing:
		st.info("진행 중 프로젝트가 없습니다.")
	for i, (pid, name, expl) in enumerate(ongoing):
		_list_card(assets_dir, db_path, name, expl, index=f"ongoing_{i}", show_actions=True, allow_revert=False)
	st.divider()
	st.subheader("완료된 프로젝트")
	st.caption("Completed Projects")
	show_completed = st.checkbox("완료된 프로젝트 보기", value=True)
	if show_completed:
		completed = get_projects_by_completed(get_cached_db_connection(db_path), completed=1, limit=None)
		if not completed:
			st.info("완료된 프로젝트가 없습니다.")
		for i, (pid, name, expl) in enumerate(completed):
			_list_card(assets_dir, db_path, name, expl, index=f"completed_{i}", show_actions=False, allow_revert=True)


def ask_bot(assets_dir: Path, db_path: Path) -> None:
	st.subheader("아카이봇에게 물어보세요!")
	st.caption("I'm here to help you!")
	col_proj, col_input, col_send = st.columns([1.2, 3.2, 0.6])
	with col_proj:
		# Load project names from DB; if none, show '없음'
		conn = get_cached_db_connection(db_path)
		cur = conn.cursor()
		# 최신 생성 순으로 정렬
		cur.execute("SELECT projectname FROM PROJECT ORDER BY projectid DESC")
		rows = cur.fetchall()
		project_options = [r[0] for r in rows] if rows else ["없음"]
		project = st.selectbox("프로젝트", project_options, label_visibility="collapsed")
	with col_input:
		question = st.text_input("메인 컬러 어떻게 정하기로 했어?", label_visibility="collapsed")
	with col_send:
		# st.write("\n")
		img_path = assets_dir / "img/send.png"
		# Use Streamlit's icon support instead of injecting HTML into the label
		send = st.button("", use_container_width=True, type="secondary", icon=":material/send:")
		st.write("\n")
	if send and question:
		# 선택된 프로젝트 ID 조회
		conn = get_cached_db_connection(db_path)
		cur = conn.cursor()
		cur.execute("SELECT projectid FROM PROJECT WHERE projectname = ?", (project,))
		row = cur.fetchone()
		if not row:
			st.error("선택한 프로젝트를 찾을 수 없습니다.")
			return
		project_id = int(row[0])
		user_id = st.session_state.get("user_id")
		if not user_id:
			st.error("로그인 후 다시 시도하세요.")
			return
		# 챗 화면으로 이동: 초기 질문과 프로젝트 정보를 세션에 저장
		st.session_state["chat_project_id"] = project_id
		st.session_state["chat_project_name"] = project
		st.session_state["chat_initial_question"] = question
		st.session_state["page_state"].append("chat")
		st.rerun()


def project_archive(img1: Path, img2: Path, processing: int, completed: int) -> None:
	col_subheader, _, col_more = st.columns([3, 3, 1.5])
	with col_subheader:
		st.subheader("프로젝트 아카이브")
		st.caption("Current status and insights")
	with col_more:
		# 버튼을 중앙 정렬하기 위한 CSS 스타일 적용
		st.markdown(
			"""
			<style>
			[data-testid="stButton"] {
				display: flex;
				align-items: center;
				justify-content: center;
				height: 100%;
			}
			</style>
			""",
			unsafe_allow_html=True,
		)
		if st.button("더보기", type="secondary", icon=":material/arrow_forward:", use_container_width=True):
			st.session_state["page_state"].append("list")
			st.rerun()
	quick_actions(img1, img2, text1=f"진행 중 프로젝트 {processing}", text2=f"완료된 프로젝트 {completed}", page_name1="list", page_name2="list")


def project_form(db_path: Path) -> None:
	with st.form("project_form"):
		name = st.text_input("프로젝트명", placeholder="Enter the title of the record")
		expl = st.text_area("프로젝트 개요 (선택)", placeholder="Provide additional details")
		submitted = st.form_submit_button("새로운 프로젝트 추가하기")
	if submitted:
		if not name:
			st.error("프로젝트명을 입력하세요")
			return
		user_id = st.session_state.get("user_id")
		if not user_id:
			st.error("로그인 후 다시 시도하세요")
			return
		conn = get_cached_db_connection(db_path)
		ok, msg, new_id = create_project(conn, user_id, name, expl or None)
		if ok:
			st.success(f"프로젝트가 저장되었습니다 (프로젝트명: {name})")
			# 2초 후 메인 화면으로 이동
			try:
				import time as _t
				_t.sleep(2)
			except Exception:
				pass
			st.session_state["page_state"] = ["main"]
			st.rerun()
		else:
			st.error(msg)


def tips(assets_dir: Path) -> None:
	st.subheader("아카이봇이 궁금하다면?")
	st.caption("Guidelines and tips")
	quick_actions(img1=assets_dir/"img/question.png", img2=assets_dir/"img/upload.png", text1="아카이봇에게 질문하는 방법(준비중)", text2="아카이브 업데이트하는 방법(준비중)", page_name1="tip1", page_name2="tip2")


def spacer(px: int = 16) -> None:
	"""Render vertical space between sections."""
	st.markdown(f"<div style='height:{px}px'></div>", unsafe_allow_html=True)


def render_main_screen(assets_dir: Path, db_path: Path) -> None:
	header(assets_dir)
	# Top quick cards
	img1 = assets_dir / "img/folder.png"
	img2 = assets_dir / "img/avocabot-removebg-preview.png"
	quick_actions(img1=img1, img2=img2, text1="프로젝트 기록하기", text2="아카이봇", page_name1="record", page_name2="chat_list")

	spacer(16)
	ask_bot(assets_dir, db_path)
	# 채팅 화면 네비게이션
	if st.session_state.get("page_state")[-1] == "chat":
		render_chat_screen(assets_dir, db_path)
	# 진행/완료 프로젝트 개수 집계
	conn_cnt = get_cached_db_connection(db_path)
	processing_cnt = count_projects_by_completed(conn_cnt, 0)
	completed_cnt = count_projects_by_completed(conn_cnt, 1)
	img3 = assets_dir / "img/loading.png"
	img4 = assets_dir / "img/check.png"
	project_archive(img1=img3, img2=img4, processing=processing_cnt, completed=completed_cnt)
	st.divider()
	project_form(db_path)
	st.divider()
	tips(assets_dir)


def render_record_screen(assets_dir: Path, db_path: Path) -> None:
	"""프로젝트 기록하기 화면을 렌더링합니다."""
	page_header(assets_dir, "프로젝트 기록하기")
	
	# 프로젝트 선택
	st.markdown("**프로젝트 선택**")
	
	# 현재 진행 중인 프로젝트들을 가져오기
	conn = get_cached_db_connection(db_path)
	ongoing_projects = get_projects_by_completed(conn, completed=0, limit=None)
	
	# 프로젝트 이름 리스트 생성
	project_names = [name for _, name, _ in ongoing_projects]
	
	# 선택된 프로젝트가 있으면 기본값으로 설정, 없으면 첫 번째 프로젝트를 기본값으로
	selected_project = st.session_state.get("selected_project", "")
	default_index = 0
	if selected_project in project_names:
		default_index = project_names.index(selected_project)
	
	if project_names:
		project_name = st.selectbox(
			"저장할 프로젝트를 선택하세요.",
			options=project_names,
			index=default_index,
			label_visibility="collapsed"
		)
		st.caption("저장할 프로젝트를 선택하세요.")
	else:
		st.warning("진행 중인 프로젝트가 없습니다. 먼저 프로젝트를 생성해주세요.")
		st.caption("저장할 프로젝트를 선택하세요.")
		project_name = None
	
	# 종류 선택
	st.markdown("**종류 선택**")
	st.caption("Add relevant tags to your record")

	col1, col2 = st.columns(2)

	# 현재 선택 상태
	selected_type = st.session_state.get("selected_type")

	with col1:
		btn_type = "primary" if selected_type == "messages" else "secondary"
		if st.button("💬 카톡 메시지", key="btn_messages", use_container_width=True, type=btn_type):
			st.session_state["selected_type"] = "messages"
		btn_type = "primary" if selected_type == "call" else "secondary"
		if st.button("📱 통화 녹음", key="btn_call", use_container_width=True, type=btn_type):
			st.session_state["selected_type"] = "call"

	with col2:
		btn_type = "primary" if selected_type == "image" else "secondary"
		if st.button("🖼️ 이미지", key="btn_image", use_container_width=True, type=btn_type):
			st.session_state["selected_type"] = "image"
		btn_type = "primary" if selected_type == "meeting" else "secondary"
		if st.button("📝 회의록", key="btn_meeting", use_container_width=True, type=btn_type):
			st.session_state["selected_type"] = "meeting"
	
	# 선택된 종류 표시
	selected_type = st.session_state.get("selected_type")
	
	# 제목
	st.markdown("**제목**")
	title = st.text_input("아카이빙할 기록의 제목을 작성해주세요.", label_visibility="collapsed")
	st.caption("기록을 간단하게 설명해주세요.")
	
	# 설명 (선택)
	st.markdown("**설명 (선택)**")
	description = st.text_area("상세 설명을 추가해주세요.", label_visibility="collapsed")
	st.caption("기록의 내용을 자세하게 설명해주세요.")
	
	# 업로드
	st.markdown("**업로드**")
	uploaded_file = st.file_uploader("파일을 선택해주세요.", label_visibility="collapsed")
	st.caption("지원하는 파일 형식: PDF, DOCX, TXT, JPG, PNG, MP3")
	
	# 하단 버튼들
	st.divider()
	col_cancel, col_upload = st.columns(2)
	
	with col_cancel:
		if st.button("Cancel", type="secondary", use_container_width=True):
			st.session_state["page_state"] = st.session_state["page_state"][:-1]
			st.rerun()
	
	with col_upload:
		if st.button("Upload", type="primary", use_container_width=True):
			if not (title and selected_type and project_name):
				st.error("제목, 종류, 프로젝트를 모두 선택해주세요.")
				return
			if uploaded_file is None:
				st.error("업로드할 파일을 선택하세요.")
				return
			with st.spinner("업로드 중입니다… 잠시만 기다려주세요"):
				# DB 조회: 선택한 프로젝트의 ID 찾기
				conn = get_cached_db_connection(db_path)
				try:
					cur = conn.cursor()
					cur.execute("SELECT projectid FROM PROJECT WHERE projectname = ?", (project_name,))
					row = cur.fetchone()
					if not row:
						st.error("선택한 프로젝트를 찾을 수 없습니다.")
						return
					project_id = int(row[0])
					user_id = st.session_state.get("user_id")
					if not user_id:
						st.error("로그인 후 다시 시도하세요.")
						return
					# 저장 루트 경로 준비
					data_root = assets_dir / "data"
					vdb_root = assets_dir / "faiss"
					file_bytes = uploaded_file.getvalue()
					uploaded_filename = uploaded_file.name
					# 종류에 따라 처리 분기
					if selected_type == "image":
						ok, msg, saved_path = archive_image_and_vectorize(
							conn=conn,
							user_id=user_id,
							project_id=project_id,
							title=title,
							description=description or None,
							selected_type=selected_type,
							uploaded_filename=uploaded_filename,
							file_bytes=file_bytes,
							data_root=data_root,
							vdb_root=vdb_root,
						)
					elif selected_type == "call":
						ok, msg, saved_path = archive_audio_and_vectorize(
							conn=conn,
							user_id=user_id,
							project_id=project_id,
							title=title,
							description=description or None,
							selected_type=selected_type,
							uploaded_filename=uploaded_filename,
							file_bytes=file_bytes,
							data_root=data_root,
							vdb_root=vdb_root,
						)
					else:
						ok, msg, saved_path = archive_text_and_vectorize(
							conn=conn,
							user_id=user_id,
							project_id=project_id,
							title=title,
							description=description or None,
							selected_type=selected_type,
							uploaded_filename=uploaded_filename,
							file_bytes=file_bytes,
							data_root=data_root,
							vdb_root=vdb_root,
						)
					# 결과 표기
					if ok:
						st.success(msg)
						if saved_path:
							st.caption(f"저장 경로: {saved_path}")
					else:
						st.error(msg)
				finally:
					pass


def render_chat_screen(assets_dir: Path, db_path: Path) -> None:
	"""프로젝트별 챗봇 화면을 렌더링하고, 대화를 chat 폴더의 txt로 자동 저장합니다."""
	project_id = st.session_state.get("chat_project_id")
	project_name = st.session_state.get("chat_project_name")
	initial_question = st.session_state.pop("chat_initial_question", None)
	if not project_id or not project_name:
		st.error("프로젝트 정보가 없습니다.")
		return
	page_header(assets_dir, f"{project_name}")
	# 채팅 세션 상태
	if "chat_messages" not in st.session_state:
		st.session_state["chat_messages"] = []  # list of (role, content)
	# 세션용 로그 파일 경로 준비(최초 1회)
	if "chat_log_path" not in st.session_state:
		chat_dir = assets_dir / "chat"
		chat_dir.mkdir(parents=True, exist_ok=True)
		from datetime import datetime as _dt
		file_name = f"project_{project_id}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.txt"
		st.session_state["chat_log_path"] = str(chat_dir / file_name)
		# DB CHATLOG에 1회 기록
		try:
			user_id = st.session_state.get("user_id")
			if user_id:
				conn0 = get_cached_db_connection(db_path)
				insert_chatlog(conn0, user_id=int(user_id), project_id=int(project_id), path=st.session_state["chat_log_path"]) 
		except Exception:
			pass
	# 로컬 파일로 저장하는 함수
	def _autosave() -> None:
		try:
			path = Path(st.session_state["chat_log_path"])
			lines = []
			for role, content in st.session_state["chat_messages"]:
				prefix = "User" if role == "user" else "Bot"
				lines.append(f"[{prefix}] {content}")
			path.write_text("\n".join(lines), encoding="utf-8")
		except Exception:
			pass
	# 초기 질문이 있으면 메시지에 추가하고, pending 플래그 설정
	if initial_question:
		st.session_state["chat_messages"].append(("user", initial_question))
		_autosave()
		st.session_state["chat_pending"] = initial_question
	# 메시지 렌더 (선 렌더링)
	for role, content in st.session_state["chat_messages"]:
		if role == "bot":
			st.chat_message("assistant").markdown(content)
		else:
			st.chat_message("user").markdown(content)
	# 만약 응답 대기 중이면 스피너를 보여주며 RAG 응답 생성
	pending = st.session_state.get("chat_pending")
	if pending:
		with st.spinner("아카이봇이 답변을 작성 중입니다…"):
			try:
				conn = get_cached_db_connection(db_path)
				vdb_root = assets_dir / "faiss"
				reply = chat_generate_response(
					user_input=pending,
					conn=conn,
					project_id=int(project_id),
					vdb_root=vdb_root,
					history=[m for m in st.session_state["chat_messages"] if m[0] != "bot"],
				)
			except Exception as e:
				# 임시: 상세 오류와 스택트레이스를 화면과 콘솔에 노출
				try:
					st.exception(e)
				except Exception:
					st.error(f"모델 호출 오류: {e}")
				# 콘솔 출력
				try:
					import traceback
					print("[render_chat_screen] Chat RAG error:", e)
					print(traceback.format_exc())
				except Exception:
					pass
				reply = "죄송해요, 답변 생성 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요."
			st.session_state["chat_messages"].append(("bot", reply))
			_autosave()
			st.session_state.pop("chat_pending", None)
			st.rerun()
	# 입력 박스
	prompt = st.chat_input("질문을 입력하세요…")
	if prompt:
		# 우선 사용자 메시지를 렌더링 큐에 추가하고, 응답 대기 플래그만 세팅
		st.session_state["chat_messages"].append(("user", prompt))
		_autosave()
		st.session_state["chat_pending"] = prompt
		st.rerun()


def render_chat_list_screen(assets_dir: Path, db_path: Path) -> None:
	"""사용자의 채팅 로그 목록을 보여주고, 선택 시 해당 채팅으로 이동합니다."""
	page_header(assets_dir, "아카이봇")
	# 상단 빠른 질문 영역 (메인과 동일 UX)
	ask_bot(assets_dir, db_path)
	st.divider()
	user_id = st.session_state.get("user_id")
	if not user_id:
		st.error("로그인 후 다시 시도하세요.")
		return
	conn = get_cached_db_connection(db_path)
	cur = conn.cursor()
	cur.execute(
		"""
		SELECT c.chatid, c.path, c.projectid, p.projectname
		FROM CHATLOG c
		JOIN PROJECT p ON p.projectid = c.projectid
		WHERE c.userid = ?
		ORDER BY c.chatid DESC
		""",
		(user_id,),
	)
	rows = cur.fetchall()
	if not rows:
		st.info("저장된 채팅이 없습니다. 먼저 질문을 시작해 보세요.")
		return
	for chatid, path, projectid, projectname in rows:
		with st.container(border=True):
			col1, col2 = st.columns([4, 1.5])
			with col1:
				st.markdown(f"**{projectname}**")
				# 미리보기: 최근 사용자 메시지
				preview = "(기록 없음)"
				try:
					from pathlib import Path as _P
					p = _P(str(path))
					if p.exists():
						lines = p.read_text(encoding="utf-8").splitlines()
						for line in reversed(lines):
							if line.startswith("[User]"):
								preview = line[len("[User]"):].strip()
								break
				except Exception:
					preview = "(미리보기 로드 실패)"
				st.caption(preview)
			with col2:
				open_clicked = st.button("열기", key=f"open_chat_{chatid}", type="secondary", use_container_width=True)
				delete_clicked = st.button("삭제", key=f"delete_chat_{chatid}", type="secondary", use_container_width=True)
				if open_clicked:
					# 세션에 프로젝트 정보 설정 후 채팅 화면으로 이동
					st.session_state["chat_project_id"] = int(projectid)
					st.session_state["chat_project_name"] = str(projectname)
					# 가능하면 기존 로그도 불러오기
					try:
						from pathlib import Path as _P
						p = _P(str(path))
						if p.exists():
							lines = p.read_text(encoding="utf-8").splitlines()
							msgs: list[tuple[str, str]] = []
							for line in lines:
								if line.startswith("[User]"):
									msgs.append(("user", line[len("[User]"):].strip()))
								elif line.startswith("[Bot]"):
									msgs.append(("bot", line[len("[Bot]"):].strip()))
							st.session_state["chat_messages"] = msgs
							st.session_state["chat_log_path"] = str(p)
					except Exception:
						pass
					st.session_state["page_state"].append("chat")
					st.rerun()

				if delete_clicked:
					# 파일 삭제 및 DB 레코드 삭제
					try:
						from pathlib import Path as _P
						p = _P(str(path))
						if p.exists():
							p.unlink(missing_ok=True)
						conn_del = get_cached_db_connection(db_path)
						curd = conn_del.cursor()
						curd.execute("DELETE FROM CHATLOG WHERE chatid = ?", (int(chatid),))
						conn_del.commit()
						st.success("채팅 기록이 삭제되었습니다.")
						st.rerun()
					except Exception as e:
						st.error(f"삭제 중 오류: {e}")
