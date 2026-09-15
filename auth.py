import streamlit as st
from pathlib import Path
from db_utils import get_cached_db_connection, authenticate_user, create_user


def auth_page(db_path: Path) -> None:
	st.header("로그인 / 회원가입")
	mode = st.tabs(["로그인", "회원가입"]) if hasattr(st, "tabs") else None

	if mode:
		login_tab, signup_tab = mode
		with login_tab:
			_login_form(db_path)
		with signup_tab:
			_signup_form(db_path)
	else:
		st.subheader("로그인")
		_login_form(db_path)
		st.subheader("회원가입")
		_signup_form(db_path)


def _login_form(db_path: Path) -> None:
	with st.form("login_form"):
		email = st.text_input("이메일")
		password = st.text_input("비밀번호", type="password")
		submit = st.form_submit_button("로그인")
	if submit:
		conn = get_cached_db_connection(db_path)
		ok = authenticate_user(conn, email, password)
		if ok:
			# Get userid for session storage
			cur = conn.cursor()
			cur.execute("SELECT userid FROM USER WHERE email = ?", (email,))
			user_id = cur.fetchone()[0]
			# keep cached connection open
			st.success("로그인 성공")
			st.session_state["auth_user"] = email
			st.session_state["user_id"] = user_id
			# Force rerun to navigate to main content
			try:
				st.rerun()
			except Exception:
				st.experimental_rerun()
		else:
			# keep cached connection open
			st.error("이메일 또는 비밀번호를 확인하세요")


def _signup_form(db_path: Path) -> None:
	with st.form("signup_form"):
		name = st.text_input("이름")
		email = st.text_input("이메일")
		password = st.text_input("비밀번호", type="password")
		password2 = st.text_input("비밀번호 확인", type="password")
		submit = st.form_submit_button("회원가입")
	if submit:
		if not name or not email or not password:
			st.error("이름, 이메일과 비밀번호를 입력하세요")
			return
		if password != password2:
			st.error("비밀번호가 일치하지 않습니다")
			return
		conn = get_cached_db_connection(db_path)
		success, msg = create_user(conn, name, email, password)
		# keep cached connection open
		if success:
			st.success(msg)
		else:
			st.error(msg)


