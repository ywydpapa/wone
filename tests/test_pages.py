"""
test_pages.py

- 로그인 상태에서 전 GET HTML 라우트 200 확인 (30개 이상)
- 비로그인 상태에서 보호 라우트들이 303 /login 리다이렉트인지 확인 (대표 5개)
"""
import pytest


# ---------------------------------------------------------------------------
# 라우트 목록
# ---------------------------------------------------------------------------
# 파라미터 없는 라우트
SIMPLE_ROUTES = [
    "/",
    "/emp_dash",
    "/manage_dash",
    "/workers",
    "/job_diary",
    "/completed_jobs",
    "/newarrived_jobs",
    "/new_job",
    "/trash",
    "/calendar",
    "/community",
    "/write_post",
    "/my_posts",
    "/my_bookmarks",
    "/erp_dash",
    "/erp_hr",
    "/erp_fa",
    "/erp_scrm",
    "/erp_purch",
    "/erp_inventory",
    "/erp_product",
    "/erp_groupware",
    "/leave_approvals",
    "/recruitment_status",
    "/outflow_list",
    "/pending_payments",
    "/production_status",
    "/equipment_alerts",
    "/po_status",
    "/delayed_delivery",
    "/outbound_status",
    "/low_stock_alerts",
    "/sales_leads",
    "/voc_list",
    "/approval_pending",
    # ERP form routes (동적 등록)
    "/draft_doc",
    "/new_hr_task",
    "/new_stock_move",
    "/new_work_order",
    "/new_po",
    "/new_activity",
    "/new_slip",
    # 기타
    "/contact",
    "/as_manage",
    "/profile",
    "/notifications",
    "/accessibility",
    "/resume",
    "/voice",
    "/eyemouse",
    "/real_trans",
    "/youtube_edit",
    "/faq",
    "/guide",
    "/inquiry",
    "/terms",
    "/privacy",
    "/updates",
]

# 비로그인 시 리다이렉트를 확인할 대표 라우트
GUARDED_ROUTES_SAMPLE = [
    "/",
    "/emp_dash",
    "/erp_dash",
    "/community",
    "/profile",
]


# ---------------------------------------------------------------------------
# 로그인 상태에서 전 페이지 200
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", SIMPLE_ROUTES)
def test_page_200_when_logged_in(admin_client, path):
    """로그인 상태에서 GET 라우트가 200을 반환한다."""
    resp = admin_client.get(path, follow_redirects=True)
    assert resp.status_code == 200, f"GET {path} returned {resp.status_code}"


def test_erp_doc_detail_200(admin_client, first_erp_doc_id):
    """로그인 상태에서 /erp_doc/{id} 200."""
    resp = admin_client.get(f"/erp_doc/{first_erp_doc_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_job_detail_200(admin_client, first_job_id):
    """로그인 상태에서 /job/{id} 200."""
    resp = admin_client.get(f"/job/{first_job_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_post_detail_200(admin_client, first_post_id):
    """로그인 상태에서 /post/{id} 200."""
    resp = admin_client.get(f"/post/{first_post_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_resume_detail_200(admin_client, first_job_posting_id):
    """로그인 상태에서 /resume/{id} 200."""
    resp = admin_client.get(f"/resume/{first_job_posting_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_talent_detail_200(admin_client):
    """로그인 상태에서 /talent/1 200 (talent_profiles DB에 id=1 존재)."""
    resp = admin_client.get("/talent/1", follow_redirects=True)
    assert resp.status_code == 200


def test_worker_detail_200(admin_client, db):
    """로그인 상태에서 /worker/{id} 200."""
    row = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    resp = admin_client.get(f"/worker/{row[0]}", follow_redirects=True)
    assert resp.status_code == 200


def test_job_apply_form_200(admin_client, first_job_posting_id):
    """로그인 상태에서 /job_apply/{id} 200 (미지원 공고)."""
    resp = admin_client.get(f"/job_apply/{first_job_posting_id}", follow_redirects=True)
    # 이미 지원했으면 303 리다이렉트 가능 -> 200 or 200 after redirect
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 비로그인 상태에서 보호 라우트 303 리다이렉트
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", GUARDED_ROUTES_SAMPLE)
def test_guarded_route_redirects_when_not_logged_in(client, path):
    """비로그인 상태에서 보호 라우트는 303 + /login 리다이렉트."""
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 303, f"GET {path} expected 303, got {resp.status_code}"
    loc = resp.headers.get("location", "")
    assert "login" in loc, f"GET {path} did not redirect to /login (got: {loc})"


# ---------------------------------------------------------------------------
# 404 동작 확인
# ---------------------------------------------------------------------------

def test_erp_doc_not_found_404(admin_client):
    """/erp_doc/999999 는 404 응답."""
    resp = admin_client.get("/erp_doc/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_job_not_found_404(admin_client):
    """/job/999999 는 404 응답."""
    resp = admin_client.get("/job/999999", follow_redirects=False)
    assert resp.status_code == 404


def test_talent_not_found_404(admin_client):
    """/talent/999999 는 404 응답 (talent_profiles DB에 없음)."""
    resp = admin_client.get("/talent/999999", follow_redirects=False)
    assert resp.status_code == 404
