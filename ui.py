from pathlib import Path
import base64
import streamlit as st


def inject_responsive_styles() -> None:
	"""Inject CSS so that:
	- On desktop: content width is constrained to a mobile-sized column
	- On small screens (mobile): content uses full available width
	"""
	st.markdown(
		"""
		<style>
		@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/pretendard.css');
		html, body, .main, .block-container, .stMarkdown, .stTextInput input, .stTextArea textarea, .stSelectbox div, .stButton>button, .stMetric, label {
			font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif !important;
		}
		/* Base: center content */
		.main .block-container {
			margin-left: auto;
			margin-right: auto;
		}

		/* Desktop and tablets wider than 480px: emulate mobile-width column */
		@media (min-width: 481px) {
			.main .block-container {
				max-width: 430px; /* mobile-like width */
				padding-left: 16px;
				padding-right: 16px;
			}
		}

		/* Phones and narrow viewports: occupy full width */
		@media (max-width: 480px) {
			.main .block-container {
				max-width: 100%;
				padding-left: 12px;
				padding-right: 12px;
			}
		}

		/* Simple card-like boxes */
		.av-card {
			border: 1px solid #efefef;
			border-radius: 12px;
			padding: 18px 16px;
			background: #ffffff;
			box-shadow: 0 1px 2px rgba(0,0,0,0.04);
			transition: transform 120ms ease, box-shadow 120ms ease;
		}

		/* Clickable card styles */
		.av-link, .av-link:link, .av-link:visited, .av-link:hover, .av-link:active {
			text-decoration: none !important;
			color: inherit !important;
			display: block;
			cursor: pointer;
		}
		.av-link:hover .av-card, .av-link:focus .av-card {
			transform: translateY(-2px);
			box-shadow: 0 6px 12px rgba(0,0,0,0.08);
		}
		.av-link:active .av-card {
			transform: translateY(0);
			box-shadow: 0 2px 4px rgba(0,0,0,0.06);
		}

		/* Two-column grid that never collapses on mobile */
		.av-grid {
			display: grid;
			grid-template-columns: repeat(2, 1fr);
			gap: 12px;
		}

		.av-card img { height: 44px; width: auto; border-radius: 10px; display: block; margin: 0 auto; }

		.av-card p {
			margin: 8px 0 0 0;
			font-size: 14px;
			font-weight: 600;
			text-align: center;
		}

		/* Primary action button full-width */
		.stButton>button.av-primary {
			width: 100%;
			background: #111111;
			color: #ffffff;
			border: 0;
			border-radius: 12px;
			padding: 14px 18px;
			font-weight: 700;
		}

		/* Tiny helper for right-aligned small button */
		.stButton>button.av-ghost {
			background: #f5f5f5;
			color: #111111;
			border: 0;
			border-radius: 10px;
			padding: 8px 12px;
			font-weight: 600;
		}

		/* Header separator */
		.av-sep {
			height: 1px;
			background: #e9e9e9;
			box-shadow: 0 2px 6px -2px rgba(0,0,0,0.5);
			border: 0;
			margin: -4px 0 6px 0;
		}

		/* Header: force two columns side-by-side even on mobile */
		.av-header { display: grid; grid-template-columns: auto 1fr; align-items: center; column-gap: 10px; }
		.av-header-logo { height: 44px; width: auto; display: block; }
		.av-header-title { margin: 0; }
		</style>
		""",
		unsafe_allow_html=True,
	)


def to_b64(p: Path) -> str:
	if not p.exists():
		return ""
	return base64.b64encode(p.read_bytes()).decode("utf-8")


def header(assets_dir: Path) -> None:
	logo_path = assets_dir / "img/archiv-bot.png"
	logo_html = f"<img class='av-header-logo' src='data:image/png;base64,{to_b64(logo_path)}' alt='logo'/>" if logo_path.exists() else "<div class='av-header-logo'>🥑</div>"
	title_html = "<h3 class='av-header-title'>Archiv-bot</h3>"
	st.markdown(f"<div class='av-header'>{logo_html}{title_html}</div>", unsafe_allow_html=True)
	st.markdown("<div class='av-sep'></div>", unsafe_allow_html=True)


def page_header(assets_dir: Path, page_name: str) -> None:
	with st.container():
		st.markdown("""
	<style>
	/* av-col-center 내부의 버튼에만 적용 */
	.av-col-center div.stButton > button {
		font-size: 80px !important;        /* 폰트 크기 */
		line-height: 1 !important;          /* 줄간격 보정 */
		padding: 0 !important;              /* 세로 여백 제거 */
		min-height: 0 !important;           /* 스트림릿 기본 최소높이 무력화 */
		height: 30px !important;             /* 원하는 버튼 높이 */
		display: inline-flex !important;     /* 텍스트 수직정렬을 위해 */
		align-items: center !important;
		justify-content: center !important;
		box-shadow: none !important;        /* 기본 그림자 제거 */
	}

	/* 버튼이 들어있는 컬럼 래퍼를 세로 가운데 정렬 */
	.block-container .av-col-center {
		display: flex !important;
		align-items: center !important;
		height: 70% !important;
	}
	</style>
	""", unsafe_allow_html=True)
		col1, col2 = st.columns([1,10])
		with col1:
			st.markdown('<div class="av-col-center">', unsafe_allow_html=True)
			if st.button("⮜", use_container_width=True):
				st.session_state["page_state"] = st.session_state["page_state"][:-1]
				st.rerun()
			st.markdown("</div>", unsafe_allow_html=True)
		with col2:
			title_html = f"<h3 class='av-header-title'>{page_name}</h3>"
			st.markdown(f"<div class='av-header'>{title_html}</div>", unsafe_allow_html=True)
		st.markdown("<div class='av-sep'></div>", unsafe_allow_html=True)



def quick_actions(img1: Path, img2: Path, text1: str, text2: str, page_name1: str, page_name2: str) -> None:
	st.write("")
	
	col1, col2 = st.columns(2)
	with col1:
		# 이미지 base64 인코딩
		img1_tag = f'<img src="data:image/png;base64,{to_b64(img1)}" style="width: 44px; height: auto; display: block; margin: 0 auto;" />' if img1.exists() else ''
		
		# 카드 스타일 적용 (이미지 포함)
		st.markdown(f"""
		<div style="
			border: 1px solid #efefef;
			border-radius: 12px;
			padding: 18px 16px;
			background: #ffffff;
			box-shadow: 0 1px 2px rgba(0,0,0,0.04);
			text-align: center;
		">
			{img1_tag}
		""", unsafe_allow_html=True)
		
		# 버튼만 별도로 배치
		if st.button(text1, use_container_width=True):
			st.session_state["page_state"].append(f"{page_name1}")
			st.rerun()
		
		st.markdown("</div>", unsafe_allow_html=True)
		
	with col2:
		# 이미지 base64 인코딩
		img2_tag = f'<img src="data:image/png;base64,{to_b64(img2)}" style="width: 44px; height: auto; display: block; margin: 0 auto;" />' if img2.exists() else ''
		
		# 카드 스타일 적용 (이미지 포함)
		st.markdown(f"""
		<div style="
			border: 1px solid #efefef;
			border-radius: 12px;
			padding: 18px 16px;
			background: #ffffff;
			box-shadow: 0 1px 2px rgba(0,0,0,0.04);
			text-align: center;
		">
			{img2_tag}
		""", unsafe_allow_html=True)
		
		# 버튼만 별도로 배치
		if st.button(text2, use_container_width=True):
			st.session_state["page_state"].append(f"{page_name2}")
			st.rerun()
		
		st.markdown("</div>", unsafe_allow_html=True)


