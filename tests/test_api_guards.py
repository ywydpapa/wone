"""
test_api_guards.py

API 보안 가드 테스트:
1. 비로그인 API 호출 -> 401
2. 권한 없는 status 변경 -> 403
3. 허용 안 된 확장자 업로드 -> 400
4. 존재하지 않는 문서 -> 404
"""
import io

import pytest


# ---------------------------------------------------------------------------
# 1. 비로그인 API 호출 -> 401
# ---------------------------------------------------------------------------

def test_unauthenticated_list_erp_docs(client):
    """비로그인 GET /api/erp_docs -> 401."""
    resp = client.get("/api/erp_docs", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_list_jobs(client):
    """비로그인 GET /api/jobs -> 401."""
    resp = client.get("/api/jobs", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_list_posts(client):
    """비로그인 GET /api/posts -> 401."""
    resp = client.get("/api/posts", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_list_as_requests(client):
    """비로그인 GET /api/as_requests -> 401."""
    resp = client.get("/api/as_requests", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_toggle_job(client, first_job_id):
    """비로그인 POST /api/jobs/{id}/toggle -> 401."""
    resp = client.post(f"/api/jobs/{first_job_id}/toggle", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_approve_doc(client, first_erp_doc_id):
    """비로그인 POST /api/erp_docs/{id}/approve -> 401."""
    resp = client.post(
        f"/api/erp_docs/{first_erp_doc_id}/approve",
        data={"comment": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_unauthenticated_reject_doc(client, first_erp_doc_id):
    """비로그인 POST /api/erp_docs/{id}/reject -> 401."""
    resp = client.post(
        f"/api/erp_docs/{first_erp_doc_id}/reject",
        data={"comment": "test"},
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_unauthenticated_withdraw_doc(client, first_erp_doc_id):
    """비로그인 POST /api/erp_docs/{id}/withdraw -> 401."""
    resp = client.post(
        f"/api/erp_docs/{first_erp_doc_id}/withdraw",
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_unauthenticated_submit_doc(client, first_erp_doc_id):
    """비로그인 POST /api/erp_docs/{id}/submit -> 401."""
    resp = client.post(
        f"/api/erp_docs/{first_erp_doc_id}/submit",
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_unauthenticated_dept_members(client):
    """비로그인 GET /api/dept/members -> 401."""
    resp = client.get("/api/dept/members?dept=경영지원팀", follow_redirects=False)
    assert resp.status_code == 401


def test_unauthenticated_send_message(client):
    """비로그인 POST /api/messages/send -> 401."""
    resp = client.post(
        "/api/messages/send",
        data={"to_name": "김민수", "body": "hello"},
        follow_redirects=False,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. 권한 없는 status 변경 -> 403
#    (update_erp_doc_status: role이 admin/manager가 아닌 경우)
# ---------------------------------------------------------------------------

def test_status_update_forbidden_for_regular_user(app, first_erp_doc_id):
    """일반 사용자(role=employee)가 /api/erp_docs/{id}/status 호출 -> 403."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=True) as c:
        c.post(
            "/login_check",
            data={"username": "user1", "password": "1234"},
            follow_redirects=False,
        )
        resp = c.post(
            f"/api/erp_docs/{first_erp_doc_id}/status",
            data={"status": "done", "reason": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 403, f"expected 403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 3. 허용 안 된 확장자 업로드 -> 400
# ---------------------------------------------------------------------------

def test_upload_disallowed_extension(admin_client):
    """허용되지 않는 확장자(.exe) 첨부 -> 400."""
    fake_file = io.BytesIO(b"fake executable content")
    resp = admin_client.post(
        "/api/erp_docs",
        data={
            "doc_type": "draft",
            "title": "첨부파일 테스트",
            "content": "내용",
            "reviewer_id": "2",
            "approver_id": "3",
            "save_mode": "submit",
        },
        files={"attachment": ("malicious.exe", fake_file, "application/octet-stream")},
        follow_redirects=False,
    )
    assert resp.status_code == 400, f"expected 400 for .exe upload, got {resp.status_code}"


def test_upload_allowed_extension_pdf(admin_client, db, reviewer_id, approver_id):
    """허용된 확장자(.pdf)는 정상 처리(303 리다이렉트)."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
    resp = admin_client.post(
        "/api/erp_docs",
        data={
            "doc_type": "draft",
            "title": "PDF 첨부 테스트",
            "content": "내용",
            "reviewer_id": str(reviewer_id),
            "approver_id": str(approver_id),
            "save_mode": "submit",
        },
        files={"attachment": ("document.pdf", fake_pdf, "application/pdf")},
        follow_redirects=False,
    )
    assert resp.status_code == 303, f"expected 303 for .pdf upload, got {resp.status_code}"


def test_upload_disallowed_extension_sh(admin_client):
    """허용되지 않는 확장자(.sh) 첨부 -> 400."""
    fake_file = io.BytesIO(b"#!/bin/bash\nrm -rf /")
    resp = admin_client.post(
        "/api/erp_docs",
        data={
            "doc_type": "draft",
            "title": "쉘 스크립트 첨부 테스트",
            "content": "내용",
            "reviewer_id": "2",
            "approver_id": "3",
            "save_mode": "submit",
        },
        files={"attachment": ("script.sh", fake_file, "application/x-sh")},
        follow_redirects=False,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 4. 존재하지 않는 문서/리소스 -> 404
# ---------------------------------------------------------------------------

def test_erp_doc_nonexistent_returns_404(admin_client):
    """/erp_doc/999999 -> 404."""
    resp = admin_client.get("/erp_doc/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_job_nonexistent_returns_404(admin_client):
    """/job/999999 -> 404."""
    resp = admin_client.get("/job/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_post_nonexistent_returns_404(admin_client):
    """/post/999999 -> 404."""
    resp = admin_client.get("/post/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_resume_nonexistent_returns_404(admin_client):
    """/resume/999999 -> 404."""
    resp = admin_client.get("/resume/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_talent_nonexistent_returns_404(admin_client):
    """/talent/999999 -> 404."""
    resp = admin_client.get("/talent/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_withdraw_nonexistent_doc_returns_404(admin_client):
    """/api/erp_docs/999999/withdraw -> 404."""
    resp = admin_client.post(
        "/api/erp_docs/999999/withdraw",
        follow_redirects=False,
    )
    assert resp.status_code == 404


def test_submit_nonexistent_doc_returns_404(admin_client):
    """/api/erp_docs/999999/submit -> 404."""
    resp = admin_client.post(
        "/api/erp_docs/999999/submit",
        follow_redirects=False,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 추가: 인증된 API 정상 동작 확인
# ---------------------------------------------------------------------------

def test_authenticated_list_erp_docs_ok(admin_client):
    """로그인 후 GET /api/erp_docs -> 200 + 리스트."""
    resp = admin_client.get("/api/erp_docs", follow_redirects=False)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_authenticated_list_jobs_ok(admin_client):
    """로그인 후 GET /api/jobs -> 200 + 리스트."""
    resp = admin_client.get("/api/jobs", follow_redirects=False)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
