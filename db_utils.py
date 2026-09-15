import sqlite3
from pathlib import Path
from datetime import datetime
import secrets
import hashlib
import streamlit as st


def get_db_connection(db_path: Path) -> sqlite3.Connection:
	conn = sqlite3.connect(str(db_path), check_same_thread=False)
	conn.execute("PRAGMA journal_mode=WAL;")
	return conn


def get_cached_db_connection(db_path: Path) -> sqlite3.Connection:
	"""Streamlit session_state에 DB 커넥션을 캐싱하여 재사용합니다.

	- db_path가 바뀌면 기존 커넥션을 안전하게 닫고 새로 엽니다.
	- 동일 경로에서는 같은 커넥션을 재사용합니다.
	"""
	db_key = "db_conn"
	path_key = "db_conn_path"
	if db_key in st.session_state:
		try:
			cached_path = st.session_state.get(path_key)
			if cached_path == str(db_path):
				return st.session_state[db_key]
			# 경로가 바뀌면 이전 커넥션 닫기
			try:
				st.session_state[db_key].close()
			except Exception:
				pass
		finally:
			st.session_state.pop(db_key, None)
			st.session_state.pop(path_key, None)

	conn = get_db_connection(db_path)
	st.session_state[db_key] = conn
	st.session_state[path_key] = str(db_path)
	return conn


def close_cached_db_connection() -> None:
	"""세션에 보관된 커넥션을 닫고 제거합니다."""
	db_key = "db_conn"
	path_key = "db_conn_path"
	if db_key in st.session_state:
		try:
			st.session_state[db_key].close()
		except Exception:
			pass
		finally:
			st.session_state.pop(db_key, None)
			st.session_state.pop(path_key, None)


def initialize_database(db_path: Path) -> None:
	conn = get_db_connection(db_path)
	cur = conn.cursor()
	# Projects
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS "PROJECT" (
			"projectid"	INTEGER NOT NULL,
			"userid"	INTEGER NOT NULL,
			"projectname"	TEXT NOT NULL,
			"projectexpl"	TEXT,
			"vectorpath"	TEXT,
			"completed"	INTEGER NOT NULL DEFAULT 0,
			PRIMARY KEY("projectid" AUTOINCREMENT),
			CONSTRAINT "fk_project_user" FOREIGN KEY("userid") REFERENCES "USER"("userid") ON DELETE CASCADE
		);
		"""
	)
	# Backfill: add completed column if missing (for existing DBs)
	cur.execute("PRAGMA table_info('PROJECT')")
	cols = [r[1] for r in cur.fetchall()]
	if "completed" not in cols:
		cur.execute("ALTER TABLE PROJECT ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")
	if "vectorpath" not in cols:
		cur.execute("ALTER TABLE PROJECT ADD COLUMN vectorpath TEXT")
	# Chat
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS "CHATLOG" (
			"chatid"	INTEGER NOT NULL,
			"userid"	INTEGER NOT NULL,
			"path"	TEXT NOT NULL,
			"projectid"	INTEGER NOT NULL,
			PRIMARY KEY("chatid" AUTOINCREMENT),
			CONSTRAINT "fk_chatlog_project" FOREIGN KEY("projectid") REFERENCES "PROJECT"("projectid") ON DELETE CASCADE,
			CONSTRAINT "fk_chatlog_user" FOREIGN KEY("userid") REFERENCES "USER"("userid") ON DELETE CASCADE
		);
		"""
	)
	# Archive
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS "ARCHIVE" (
			"archiveid"	INTEGER NOT NULL,
			"userid"	INTEGER NOT NULL,
			"path"	TEXT NOT NULL,
			"archivename"	TEXT NOT NULL,
			"archivetype"	TEXT NOT NULL,
			"archiveexpl"	TEXT,
			"projectid"	INTEGER NOT NULL,
			PRIMARY KEY("archiveid" AUTOINCREMENT),
			CONSTRAINT "fk_archive_project" FOREIGN KEY("projectid") REFERENCES "PROJECT"("projectid") ON DELETE CASCADE,
			CONSTRAINT "fk_archive_user" FOREIGN KEY("userid") REFERENCES "USER"("userid") ON DELETE CASCADE
		);
		"""
	)
	# Users
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS "USER" (
			"userid"	INTEGER NOT NULL,
			"name"	TEXT NOT NULL,
			"email"	TEXT NOT NULL,
			"password"	TEXT NOT NULL,
			PRIMARY KEY("userid")
		);
		"""
	)
	conn.commit()
	conn.close()


def _hash_password(password: str) -> str:
	return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(conn: sqlite3.Connection, name: str, email: str, password: str) -> tuple[bool, str]:
	try:
		pwd_hash = _hash_password(password)
		conn.execute(
			"INSERT INTO USER (name, email, password) VALUES (?, ?, ?)",
			(name, email, pwd_hash),
		)
		conn.commit()
		return True, "가입이 완료되었습니다."
	except sqlite3.IntegrityError:
		return False, "이미 등록된 이메일입니다."
	except Exception as e:
		return False, f"오류: {e}"


def authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> bool:
	cur = conn.cursor()
	cur.execute("SELECT password FROM USER WHERE email = ?", (email,))
	row = cur.fetchone()
	if not row:
		return False
	stored_hash = row[0]
	return stored_hash == _hash_password(password)


def get_project_names(conn: sqlite3.Connection) -> list[str]:
	cur = conn.cursor()
	cur.execute("SELECT projectname FROM PROJECT ORDER BY projectname ASC")
	rows = cur.fetchall()
	return [r[0] for r in rows]


def get_user_id_by_email(conn: sqlite3.Connection, email: str) -> int | None:
	cur = conn.cursor()
	cur.execute("SELECT userid FROM USER WHERE email = ?", (email,))
	row = cur.fetchone()
	return int(row[0]) if row and row[0] is not None else None


def create_project(
	conn: sqlite3.Connection,
	user_id: int,
	project_name: str,
	project_expl: str | None,
) -> tuple[bool, str, int | None]:
	try:
		cur = conn.cursor()
		cur.execute(
			"INSERT INTO PROJECT (userid, projectname, projectexpl) VALUES (?, ?, ?)",
			(user_id, project_name, project_expl),
		)
		conn.commit()
		project_id = cur.lastrowid
		return True, "프로젝트가 추가되었습니다.", int(project_id) if project_id is not None else None
	except Exception as e:
		return False, f"오류: {e}", None


def get_projects_by_completed(
	conn: sqlite3.Connection,
	user_id: int,
	completed: int,
	limit: int | None = None,
) -> list[tuple[int, str, str | None]]:
	cur = conn.cursor()
	query = "SELECT projectid, projectname, projectexpl FROM PROJECT WHERE userid = ? AND completed = ? ORDER BY projectid DESC"
	params: tuple = (user_id, completed)
	if limit is not None:
		query += " LIMIT ?"
		params = (user_id, completed, limit)
	cur.execute(query, params)
	return [(int(r[0]), str(r[1]), r[2] if r[2] is not None else None) for r in cur.fetchall()]


def count_projects_by_completed(conn: sqlite3.Connection, user_id: int, completed: int) -> int:
	cur = conn.cursor()
	cur.execute("SELECT COUNT(*) FROM PROJECT WHERE userid = ? AND completed = ?", (user_id, completed))
	row = cur.fetchone()
	return int(row[0]) if row and row[0] is not None else 0


def set_project_completed(conn: sqlite3.Connection, user_id: int, project_name: str, completed: int = 1) -> tuple[bool, str]:
	"""프로젝트 완료 여부를 업데이트합니다.

	user_id 소유의 프로젝트 중 project_name과 일치하는 것만 갱신합니다.
	"""
	try:
		cur = conn.cursor()
		cur.execute(
			"UPDATE PROJECT SET completed = ? WHERE projectname = ? AND userid = ?",
			(completed, project_name, user_id),
		)
		conn.commit()
		if cur.rowcount == 0:
			return False, "해당 프로젝트를 찾을 수 없습니다."
		return True, "프로젝트 상태가 업데이트되었습니다."
	except Exception as e:
		return False, f"오류: {e}"


def get_project_id_by_name(conn: sqlite3.Connection, user_id: int, project_name: str) -> int | None:
	"""user_id 소유의 프로젝트 중 이름이 일치하는 projectid를 반환합니다.

	프로젝트명은 사용자 간에 유일하지 않을 수 있으므로 반드시 userid로 함께 스코핑합니다.
	"""
	cur = conn.cursor()
	cur.execute(
		"SELECT projectid FROM PROJECT WHERE projectname = ? AND userid = ?",
		(project_name, user_id),
	)
	row = cur.fetchone()
	return int(row[0]) if row and row[0] is not None else None


def insert_chatlog(conn: sqlite3.Connection, user_id: int, project_id: int, path: str) -> tuple[bool, str, int | None]:
	"""CHATLOG에 한 건을 삽입한다."""
	try:
		cur = conn.cursor()
		cur.execute(
			"INSERT INTO CHATLOG (userid, path, projectid) VALUES (?, ?, ?)",
			(user_id, path, project_id),
		)
		conn.commit()
		return True, "채팅 로그가 저장되었습니다.", int(cur.lastrowid) if cur.lastrowid is not None else None
	except Exception as e:
		return False, f"오류: {e}", None
