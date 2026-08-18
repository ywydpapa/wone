"""
test_erp_workflow.py

ERP 문서 결재 워크플로우 테스트:
1. 문서 생성 (POST /api/erp_docs) -> status=wait
2. 승인 2회 -> status=done
3. 이력(doc_history) 기록 확인
4. 반려 플로우
5. draft 저장 -> 상신 (submit)
6. 철회 (withdraw)
7. 기안자 아닌 계정 철회 시 403
"""
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit", doc_type="draft"):
    """ERP 문서 1건 생성, 생성된 doc id 반환."""
    resp = admin_client.post(
        "/api/erp_docs",
        data={
            "doc_type": doc_type,
            "title": f"테스트 문서 [{save_mode}]",
            "content": "테스트 내용입니다.",
            "reviewer_id": str(reviewer_id),
            "approver_id": str(approver_id),
            "save_mode": save_mode,
        },
        follow_redirects=False,
    )
    # 성공 시 303 리다이렉트
    assert resp.status_code == 303, f"create_doc returned {resp.status_code}: {resp.text}"
    return resp


def _get_latest_doc_id(db):
    """임시 DB에서 가장 최근에 삽입된 erp_doc id."""
    row = db.execute("SELECT id FROM erp_docs ORDER BY id DESC LIMIT 1").fetchone()
    assert row, "erp_docs 가 비어 있음"
    return row[0]


# ---------------------------------------------------------------------------
# 1. 문서 생성 후 status = wait
# ---------------------------------------------------------------------------

def test_create_erp_doc_status_wait(admin_client, db, reviewer_id, approver_id):
    """문서를 submit 모드로 생성하면 status='wait'."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)
    row = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row["status"] == "wait", f"expected 'wait', got '{row['status']}'"


def test_create_erp_doc_approval_lines_created(admin_client, db, reviewer_id, approver_id):
    """문서 생성 후 approval_lines 3건(기안/검토/승인) 생성."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)
    count = db.execute(
        "SELECT COUNT(*) FROM approval_lines WHERE doc_id=?", (doc_id,)
    ).fetchone()[0]
    assert count == 3, f"expected 3 approval_lines, got {count}"


def test_create_erp_doc_step0_auto_approved(admin_client, db, reviewer_id, approver_id):
    """submit 모드: step 0(기안) approval_line은 자동 approved."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)
    line = db.execute(
        "SELECT status FROM approval_lines WHERE doc_id=? AND step=0", (doc_id,)
    ).fetchone()
    assert line["status"] == "approved"


# ---------------------------------------------------------------------------
# 2. 승인 2회 -> status = done
# ---------------------------------------------------------------------------

def test_approve_twice_reaches_done(admin_client, db, reviewer_id, approver_id):
    """승인 2회(검토+승인) 후 doc status = done."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)

    # 1차 승인 (검토 - admin role=admin이므로 pending 첫 번째 line 처리)
    r1 = admin_client.post(
        f"/api/erp_docs/{doc_id}/approve",
        data={"comment": "검토 완료"},
        follow_redirects=False,
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1.get("ok") is True

    # 2차 승인 (승인)
    r2 = admin_client.post(
        f"/api/erp_docs/{doc_id}/approve",
        data={"comment": "최종 승인"},
        follow_redirects=False,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("ok") is True
    assert body2.get("new_status") == "done"

    # DB 확인
    row = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row["status"] == "done"


# ---------------------------------------------------------------------------
# 3. 이력(doc_history) 기록 확인
# ---------------------------------------------------------------------------

def test_doc_history_recorded_on_create(admin_client, db, reviewer_id, approver_id):
    """문서 생성 시 doc_history에 '기안' 이력이 기록된다."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)
    row = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='기안'", (doc_id,)
    ).fetchone()
    assert row is not None, "doc_history에 기안 이력이 없습니다"


def test_doc_history_recorded_on_approve(admin_client, db, reviewer_id, approver_id):
    """승인 시 doc_history에 '승인' 이력이 기록된다."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)

    admin_client.post(
        f"/api/erp_docs/{doc_id}/approve",
        data={"comment": "이력 확인용 승인"},
        follow_redirects=False,
    )

    row = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='승인'", (doc_id,)
    ).fetchone()
    assert row is not None, "doc_history에 승인 이력이 없습니다"


# ---------------------------------------------------------------------------
# 4. 반려 플로우
# ---------------------------------------------------------------------------

def test_reject_flow(admin_client, db, reviewer_id, approver_id):
    """반려 후 doc status = rejected, doc_history에 반려 이력."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)

    resp = admin_client.post(
        f"/api/erp_docs/{doc_id}/reject",
        data={"comment": "반려 사유입니다"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    row = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row["status"] == "rejected"

    hist = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='반려'", (doc_id,)
    ).fetchone()
    assert hist is not None


# ---------------------------------------------------------------------------
# 5. draft 저장 -> 상신 (submit)
# ---------------------------------------------------------------------------

def test_draft_then_submit(admin_client, db, reviewer_id, approver_id):
    """draft 모드로 저장 후 /api/erp_docs/{id}/submit 로 상신 -> status=wait."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="draft")
    doc_id = _get_latest_doc_id(db)

    # draft 상태 확인
    row = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row["status"] == "draft", f"expected draft, got {row['status']}"

    # 상신
    resp = admin_client.post(
        f"/api/erp_docs/{doc_id}/submit",
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    row2 = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row2["status"] == "wait"

    hist = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='상신'", (doc_id,)
    ).fetchone()
    assert hist is not None


def test_draft_history_recorded(admin_client, db, reviewer_id, approver_id):
    """draft 저장 시 doc_history에 '임시저장' 이력."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="draft")
    doc_id = _get_latest_doc_id(db)
    row = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='임시저장'", (doc_id,)
    ).fetchone()
    assert row is not None


# ---------------------------------------------------------------------------
# 6. 철회 (withdraw) - 기안자가 wait 상태에서
# ---------------------------------------------------------------------------

def test_withdraw_flow(admin_client, db, reviewer_id, approver_id):
    """기안자(admin)가 wait 상태 문서 철회 -> status=draft."""
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)

    resp = admin_client.post(
        f"/api/erp_docs/{doc_id}/withdraw",
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    row = db.execute("SELECT status FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    assert row["status"] == "draft"

    hist = db.execute(
        "SELECT action FROM doc_history WHERE doc_id=? AND action='철회'", (doc_id,)
    ).fetchone()
    assert hist is not None


# ---------------------------------------------------------------------------
# 7. 기안자 아닌 계정 철회 시 403
# ---------------------------------------------------------------------------

def test_withdraw_by_non_drafter_returns_403(app, db, reviewer_id, approver_id):
    """admin이 기안한 문서를 user1이 철회하려 하면 403."""
    # admin 클라이언트로 문서 생성
    with TestClient(app, raise_server_exceptions=True) as admin_c:
        admin_c.post(
            "/login_check",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        admin_c.post(
            "/api/erp_docs",
            data={
                "doc_type": "draft",
                "title": "철회 403 테스트 문서",
                "content": "내용",
                "reviewer_id": str(reviewer_id),
                "approver_id": str(approver_id),
                "save_mode": "submit",
            },
            follow_redirects=False,
        )
        doc_id = db.execute(
            "SELECT id FROM erp_docs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]

    # user1 클라이언트로 철회 시도
    with TestClient(app, raise_server_exceptions=True) as user_c:
        user_c.post(
            "/login_check",
            data={"username": "user1", "password": "1234"},
            follow_redirects=False,
        )
        resp = user_c.post(
            f"/api/erp_docs/{doc_id}/withdraw",
            follow_redirects=False,
        )
        assert resp.status_code == 403, f"expected 403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 추가: approve API 비로그인 -> 401
# ---------------------------------------------------------------------------

def test_approve_without_login_returns_401(client, first_erp_doc_id):
    """비로그인으로 approve -> 401."""
    resp = client.post(
        f"/api/erp_docs/{first_erp_doc_id}/approve",
        data={"comment": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 401


def test_no_pending_line_approve_returns_400(admin_client, db, reviewer_id, approver_id):
    """이미 모두 승인된 문서에 approve -> 400 (승인할 항목 없음)."""
    # 문서 생성
    _create_doc(admin_client, reviewer_id, approver_id, save_mode="submit")
    doc_id = _get_latest_doc_id(db)

    # 두 번 승인해서 done 상태로 만들기
    admin_client.post(f"/api/erp_docs/{doc_id}/approve", data={"comment": ""})
    admin_client.post(f"/api/erp_docs/{doc_id}/approve", data={"comment": ""})

    # 세 번째 승인 시도 -> 400
    resp = admin_client.post(
        f"/api/erp_docs/{doc_id}/approve",
        data={"comment": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 400
