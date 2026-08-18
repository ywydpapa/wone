"""
test_auth.py

인증 관련 테스트:
- 정상 로그인 (303 + 세션쿠키)
- 잘못된 비밀번호 거부
- 로그아웃 후 보호 페이지 접근 -> /login 리다이렉트
- 회원가입 후 신규 계정 로그인
"""
import uuid

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 정상 로그인
# ---------------------------------------------------------------------------

def test_login_success_status(app):
    """admin/1234 로그인 -> 303 리다이렉트."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.status_code == 303


def test_login_success_redirects_to_root(app):
    """로그인 성공 시 / 로 리다이렉트."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.headers.get("location") in ("/", "http://testserver/")


def test_login_success_sets_cookie(app):
    """로그인 성공 후 세션 쿠키가 발급된다."""
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        # starlette session cookie 이름은 'session'
        assert "session" in c.cookies


# ---------------------------------------------------------------------------
# 잘못된 비밀번호
# ---------------------------------------------------------------------------

def test_login_wrong_password(app):
    """잘못된 비밀번호 -> /login?error=1 로 리다이렉트."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert "error" in loc or "login" in loc


def test_login_nonexistent_user(app):
    """존재하지 않는 사용자 -> 로그인 실패."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/login_check",
            data={"username": "no_such_user_xyz", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert "error" in loc or "login" in loc


# ---------------------------------------------------------------------------
# 로그아웃 후 보호 페이지 접근
# ---------------------------------------------------------------------------

def test_logout_then_protected_redirect(app):
    """로그아웃 후 보호 페이지(/) 접근 시 /login 리다이렉트."""
    with TestClient(app, raise_server_exceptions=True) as c:
        # 로그인
        c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        # 로그아웃
        c.get("/logout", follow_redirects=False)
        # 보호 페이지 접근
        resp = c.get("/", follow_redirects=False)
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert "login" in loc


def test_logout_redirects_to_login(app):
    """로그아웃 자체가 /login 으로 리다이렉트한다."""
    with TestClient(app, raise_server_exceptions=True) as c:
        c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        resp = c.get("/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert "login" in resp.headers.get("location", "")


# ---------------------------------------------------------------------------
# 회원가입 후 로그인
# ---------------------------------------------------------------------------

def test_signup_then_login(app):
    """신규 회원가입 후 해당 계정으로 로그인 성공."""
    unique = uuid.uuid4().hex[:8]
    username = f"testuser_{unique}"
    password = "test1234"

    with TestClient(app, raise_server_exceptions=True) as c:
        # 회원가입
        resp = c.post(
            "/signup",
            data={"username": username, "password": password, "name": "테스트유저", "dept": "개발팀"},
            follow_redirects=False,
        )
        # 성공 시 /login 으로 리다이렉트
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert "login" in loc

        # 신규 계정 로그인
        resp2 = c.post(
            "/login_check",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert resp2.status_code == 303
        assert resp2.headers.get("location") in ("/", "http://testserver/")


def test_signup_duplicate_username(app):
    """중복 username 회원가입 -> error 파라미터 포함 리다이렉트."""
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.post(
            "/signup",
            data={"username": "admin", "password": "1234", "name": "중복테스트", "dept": "테스트팀"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert "error" in loc


def test_login_page_accessible_without_auth(client):
    """로그인 페이지는 비로그인 상태에서 200 반환."""
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 200


def test_signup_page_accessible(client):
    """회원가입 페이지는 비로그인 상태에서 200 반환."""
    resp = client.get("/signup", follow_redirects=False)
    assert resp.status_code == 200
