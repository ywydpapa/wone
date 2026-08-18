"""
conftest.py

1. 임시 디렉토리에 test.db 복사
2. DATABASE_URL 환경변수를 sys.modules import 전에 설정
3. importlib 으로 core.db 재로드 -> 앱 로드
4. client (비로그인) / admin_client (admin 로그인) 픽스처 제공
"""
import importlib
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# 프로젝트 루트를 sys.path에 추가
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Session-scoped: 임시 DB 복사 + 모듈 재로드 + TestClient 생성
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    """실제 test.db를 임시 디렉토리에 복사한 경로를 반환."""
    src = os.path.join(ROOT, "test.db")
    tmp_dir = tmp_path_factory.mktemp("db")
    dst = str(tmp_dir / "test_copy.db")
    shutil.copy2(src, dst)
    return dst


@pytest.fixture(scope="session")
def app(tmp_db_path):
    """
    DATABASE_URL을 임시 DB로 설정한 뒤 앱을 로드.
    core.db는 모듈 로드 시점에 URL을 읽으므로 import 전에 env를 설정해야 한다.
    """
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db_path}"

    # core.db / main 이 이미 import 돼 있으면 캐시를 지우고 재로드
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("core") or mod_name == "main" or mod_name.startswith("routers"):
            del sys.modules[mod_name]

    # 이제 임시 DB URL을 가진 상태로 import
    import core.db  # noqa: F401  -- _DATABASE_URL 갱신
    importlib.reload(core.db)

    import main as app_module
    importlib.reload(app_module)

    return app_module.app


@pytest.fixture(scope="session")
def client(app):
    """비로그인 TestClient."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="session")
def admin_client(app, tmp_db_path):
    """admin/1234로 로그인된 TestClient."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.status_code == 303, f"admin login failed: {resp.status_code}"
        yield c


# ---------------------------------------------------------------------------
# 헬퍼: 임시 DB에서 직접 데이터 조회
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db(tmp_db_path):
    """임시 DB sqlite3 연결 (읽기/쓰기 가능, 세션 스코프)."""
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def first_erp_doc_id(db):
    """임시 DB에 존재하는 첫 번째 erp_doc id."""
    row = db.execute("SELECT id FROM erp_docs ORDER BY id LIMIT 1").fetchone()
    assert row, "erp_docs 테이블에 데이터가 없습니다"
    return row[0]


@pytest.fixture(scope="session")
def first_post_id(db):
    """임시 DB에 존재하는 첫 번째 post id."""
    row = db.execute("SELECT id FROM posts ORDER BY id LIMIT 1").fetchone()
    assert row, "posts 테이블에 데이터가 없습니다"
    return row[0]


@pytest.fixture(scope="session")
def first_job_id(db):
    """임시 DB에 존재하는 첫 번째 job id."""
    row = db.execute("SELECT id FROM jobs ORDER BY id LIMIT 1").fetchone()
    assert row, "jobs 테이블에 데이터가 없습니다"
    return row[0]


@pytest.fixture(scope="session")
def first_job_posting_id(db):
    """임시 DB에 존재하는 첫 번째 job_posting id."""
    row = db.execute("SELECT id FROM job_postings ORDER BY id LIMIT 1").fetchone()
    assert row, "job_postings 테이블에 데이터가 없습니다"
    return row[0]


@pytest.fixture(scope="session")
def reviewer_id(db):
    """admin(id=1)과 다른 사용자 id (reviewer 역할)."""
    row = db.execute("SELECT id FROM users WHERE id != 1 ORDER BY id LIMIT 1").fetchone()
    assert row, "users 테이블에 admin 외 사용자가 없습니다"
    return row[0]


@pytest.fixture(scope="session")
def approver_id(db):
    """admin, reviewer와 다른 사용자 id (approver 역할)."""
    row = db.execute("SELECT id FROM users WHERE id NOT IN (1) ORDER BY id DESC LIMIT 1").fetchone()
    assert row, "users 테이블에 충분한 사용자가 없습니다"
    return row[0]
