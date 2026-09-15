import streamlit as st
from pathlib import Path
from db_utils import get_db_connection, get_cached_db_connection, initialize_database, create_project, count_projects_by_completed, get_user_id_by_email, create_user, get_projects_by_completed
from ui import inject_responsive_styles, header, quick_actions
from auth import auth_page
from views import render_project_list_screen, render_main_screen, render_record_screen, render_chat_screen, render_chat_list_screen


def main() -> None:
	if "page_state" not in st.session_state:
		st.session_state["page_state"] = ["main"]	
	# 세션 상태로 렌더링 결정
	main_page = st.session_state.get("page_state")[-1] == "main"
	list_page = st.session_state.get("page_state")[-1] == "list"
	record_page = st.session_state.get("page_state")[-1] == "record"
	chat_page = st.session_state.get("page_state")[-1] == "chat"
	chat_list_page = st.session_state.get("page_state")[-1] == "chat_list"
	# bot_page = st.session_state.get("page_state")[-1] == "bot"
	tip1_page = st.session_state.get("page_state")[-1] == "tip1"
	tip2_page = st.session_state.get("page_state")[-1] == "tip2"
	
	st.set_page_config(
		page_title="Archiv-bot",
		page_icon="🥑",
		layout="centered",
		initial_sidebar_state="collapsed",
	)

	inject_responsive_styles()

	assets_dir = Path(__file__).parent
	db_path = assets_dir / "db.db"
	initialize_database(db_path)

	# # 자동 로그인: 세션이 없으면 테스트 계정으로 로그인
	# if not st.session_state.get("auth_user"):
	# 	conn_boot = get_cached_db_connection(db_path)
	# 	try:
	# 		email = "test@test.com"
	# 		name = "test"
	# 		password = "test1234"
	# 		uid = get_user_id_by_email(conn_boot, email)
	# 		if uid is None:
	# 			create_user(conn_boot, name, email, password)
	# 			uid = get_user_id_by_email(conn_boot, email)
	# 		st.session_state["auth_user"] = email
	# 		st.session_state["user_id"] = uid
	# 	finally:
	# 		pass

	# 인증 가드
	if not st.session_state.get("auth_user"):
		auth_page(db_path)
		return

	# 조건에 따라 서로 다른 화면 렌더
	if main_page:
		render_main_screen(assets_dir, db_path)
		return
	elif record_page:
		render_record_screen(assets_dir, db_path)
	elif chat_page:
		render_chat_screen(assets_dir, db_path)
	elif chat_list_page:
		render_chat_list_screen(assets_dir, db_path)
	# elif bot_page:
	# 	# 메인의 '아카이봇' 클릭 시 채팅 리스트로 이동
	# 	st.session_state["page_state"][-1] = "chat_list"
	# 	st.rerun()
	elif list_page:
		render_project_list_screen(assets_dir, db_path)


if __name__ == "__main__":
	main()


