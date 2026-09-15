# 🥑 Archiv-bot

**RAG 기반 프로젝트 이력 관리 서비스**

여러 사람이 참여하는 프로젝트에서 정기회의뿐 아니라 내부 논의 과정에서 오간 기록(통화, 카카오톡 메시지, 이미지 등)을 모아두고, 필요할 때 챗봇에게 물어보면 근거와 출처를 붙여 바로 찾아주는 서비스입니다.

## 배경

다수가 참여하는 프로젝트 특성상 정기회의뿐 아니라 내부 논의 과정에서 수정된 내용에 대한 이력 관리가 어렵습니다. Archiv-bot은 다양한 형태의 기록을 수집하고 일자별로 요약·정리해, 최종 결정 사항을 빠르게 확인하고 팀원/클라이언트와의 논쟁에도 빠르게 대처할 수 있도록 돕습니다.

## 핵심 기능

1. **통화 기록 전사** — 한국어 전문 전사 모델로 음성 데이터를 텍스트화
2. **이미지 분석** — 멀티모달 LLM으로 이미지를 분석해 텍스트 생성
3. **벡터 저장소 저장** — 원본 메타데이터·텍스트·벡터를 연결한 프로젝트별 저장소 구축
4. **RAG 챗봇 응답** — 프로젝트 이력 관련 질의에 근거 기반 답변과 출처 제공

## 기술 스택

- **App**: Streamlit
- **RAG / LLM**: LangChain (`langchain-openai`, `langchain-community`)
- **모델**: 멀티모달 `gpt-4o`(오디오/이미지/텍스트 분석·요약), 임베딩 `text-embedding-ada-002`, 응답 `gpt-5`
- **벡터 저장소**: FAISS
- **문서/이미지 처리**: `pytesseract`, `python-docx`, `Pillow`
- **DB**: SQLite

## 프로젝트 구조

```
project/
├── main.py           # Streamlit 엔트리포인트, 화면 라우팅
├── auth.py           # 로그인/회원가입
├── views.py          # 화면별 렌더링 로직
├── ui.py             # 공통 UI 컴포넌트/스타일
├── db_utils.py       # SQLite 연결 및 쿼리
├── utils.py          # 전사/이미지 분석/임베딩/RAG 유틸
├── img/              # UI 에셋
├── README/           # 발표 슬라이드
├── db.db*            # (gitignore) SQLite DB — 계정 비밀번호 해시 포함
├── data/             # (gitignore) 카카오톡 대화 원본 텍스트
├── chat/             # (gitignore) 저장된 챗봇 대화 로그
├── test_data/        # (gitignore) 테스트용 카카오톡 대화 원본
└── faiss/            # (gitignore) 프로젝트별 벡터 인덱스 (대화 원문 포함)
```

> 위 트리에서 `(gitignore)` 표시된 항목은 개인정보(카카오톡 대화 원문, 계정 비밀번호 해시 등)가 포함되어 있어 `.gitignore`로 저장소에서 제외했습니다. 로컬에는 존재하지만 이 저장소에는 올라가지 않습니다.

## 시작하기

### 사전 준비

- Python 3.10
- OpenAI API Key (임베딩 / gpt-4o / gpt-5 / Whisper API 호출에 사용)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — 이미지 텍스트 추출(`pytesseract`)에 필요한 시스템 바이너리로, `pip install`과 별개로 OS에 직접 설치해야 합니다. 한국어 인식을 위해 한국어 언어팩(`kor`)도 함께 설치하고, PATH에 잡히지 않으면 `pytesseract.pytesseract.tesseract_cmd`에 설치 경로를 지정하세요.

### 설치

```bash
git clone https://github.com/EYZ27/archiv-bot.git
cd archiv-bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 환경 변수

`.env.example`을 복사해 `.env`를 만들고 값을 채우세요 (`.env`는 `.gitignore`에 포함되어 저장소에 올라가지 않습니다).

```bash
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY=sk-... 형태로 채워주세요
```

### 실행

```bash
streamlit run main.py
```

첫 실행 시 `db.db`가 자동으로 생성되며, 회원가입 후 로그인하면 바로 사용할 수 있습니다.

## 발표 슬라이드

<img src="README/Slide 16_9 - 00.png" width="800" />
<img src="README/Slide 16_9 - 01.png" width="800" />
<img src="README/Slide 16_9 - 02.png" width="800" />
<img src="README/Slide 16_9 - 03.png" width="800" />
<img src="README/Slide 16_9 - 04.png" width="800" />
<img src="README/Slide 16_9 - 05.png" width="800" />
<img src="README/Slide 16_9 - 06.png" width="800" />
<img src="README/Slide 16_9 - 07.png" width="800" />
<img src="README/Slide 16_9 - 08.png" width="800" />
<img src="README/Slide 16_9 - 09.png" width="800" />
<img src="README/Slide 16_9 - 10.png" width="800" />
