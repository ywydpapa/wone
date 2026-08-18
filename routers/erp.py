from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from typing import Optional
from datetime import datetime
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, get_current_user, templates
from core.constants import ERP_DOC_TYPES, ERP_REDIRECTS, ERP_DOC_TYPE_LABELS

router = APIRouter()


def _erp_docs_for(dtype: str):
    conn = get_sqlite()
    try:
        rows = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type=? ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 WHEN 'wait' THEN 2 ELSE 3 END, id DESC",
            (dtype,)
        ).fetchall())
    finally:
        conn.close()
    return rows


@router.get("/erp_dash", response_class=HTMLResponse)
async def erp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    from datetime import date
    uname = get_current_user(request)["user_name"]
    uid = get_current_user(request)["user_id"]
    today = date.today().isoformat()
    conn = get_sqlite()
    try:
        counts = {r["doc_type"]: r["cnt"] for r in [
            dict(r) for r in conn.execute(
                "SELECT doc_type, COUNT(*) AS cnt FROM erp_docs GROUP BY doc_type"
            ).fetchall()
        ]}
        recent = with_status_meta(conn.execute("SELECT * FROM erp_docs ORDER BY id DESC LIMIT 5").fetchall())
        today_jobs = with_status_meta(conn.execute(
            "SELECT * FROM jobs WHERE user_id=? AND work_date=? AND status != 'trash' ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id",
            (uid, today)
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/erp/erp_dash.html", context={
            "request": request, "page_title": "업무 대시보드",
            "doc_counts": counts, "recent_docs": recent,
            "user_name": uname,
            "today_jobs": today_jobs,
        }
    )


@router.get("/erp_hr", response_class=HTMLResponse)
async def erp_hr(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_hr.html", context={
        "request": request, "page_title": "인사관리 대시보드",
        "docs": _erp_docs_for("hr_task"),
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_fa", response_class=HTMLResponse)
async def erp_fa(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        # Main doc list: expense docs ordered by urgency
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='expense' ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 WHEN 'wait' THEN 2 WHEN 'pending' THEN 3 ELSE 4 END, id DESC",
        ).fetchall())

        # Alerts: urgent/wait/pending expense + po docs for the alert panel
        alert_rows = with_status_meta(conn.execute(
            """SELECT * FROM erp_docs
               WHERE doc_type IN ('expense', 'po')
               AND status IN ('urgent', 'wait', 'pending', 'progress')
               ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'pending' THEN 1 WHEN 'wait' THEN 2 ELSE 3 END,
                        id DESC
               LIMIT 6""",
        ).fetchall())

        # Stat counts
        expense_done_count = conn.execute(
            "SELECT COUNT(*) FROM erp_docs WHERE doc_type='expense' AND status IN ('done','approved')"
        ).fetchone()[0]
        expense_pending_count = conn.execute(
            "SELECT COUNT(*) FROM erp_docs WHERE doc_type='expense' AND status IN ('wait','pending','urgent')"
        ).fetchone()[0]
        po_pending_count = conn.execute(
            "SELECT COUNT(*) FROM erp_docs WHERE doc_type='po' AND status IN ('wait','pending','urgent','progress')"
        ).fetchone()[0]
    finally:
        conn.close()

    return templates.TemplateResponse(request=request, name="/erp/erp_fa.html", context={
        "request": request, "page_title": "자금관리 대시보드",
        "docs": docs,
        "alerts": alert_rows,
        "expense_done_count": expense_done_count,
        "expense_pending_count": expense_pending_count,
        "po_pending_count": po_pending_count,
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_scrm", response_class=HTMLResponse)
async def erp_scrm(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_scrm.html", context={
        "request": request, "page_title": "영업/고객관리 대시보드",
        "docs": _erp_docs_for("activity"),
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_purch", response_class=HTMLResponse)
async def erp_purch(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_purch.html", context={
        "request": request, "page_title": "구매관리 대시보드",
        "docs": _erp_docs_for("po"),
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_inventory", response_class=HTMLResponse)
async def erp_inventory(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_inventory.html", context={
        "request": request, "page_title": "재고관리 대시보드",
        "docs": _erp_docs_for("stock_move"),
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_product", response_class=HTMLResponse)
async def erp_product(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_product.html", context={
        "request": request, "page_title": "생산관리 대시보드",
        "docs": _erp_docs_for("work_order"),
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/erp_groupware", response_class=HTMLResponse)
async def erp_groupware(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    from datetime import date
    uname = get_current_user(request)["user_name"]
    conn = get_sqlite()
    today = date.today().isoformat()
    try:
        unread_mail = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE is_read=0 AND direction='in'"
        ).fetchone()[0]
        today_jobs = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE work_date=?", (today,)
        ).fetchone()[0]
        pending_docs = conn.execute(
            "SELECT COUNT(*) FROM erp_docs WHERE status='wait'"
        ).fetchone()[0]
        notices = [dict(r) for r in conn.execute(
            "SELECT id, category, title, author, dept, created_at FROM posts "
            "WHERE category IN ('notice', 'general') ORDER BY id DESC LIMIT 5"
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="/erp/erp_groupware.html", context={
        "request": request, "page_title": "사내 그룹웨어",
        "docs": _erp_docs_for("draft"),
        "user_name": uname,
        "unread_mail": unread_mail,
        "today_jobs": today_jobs,
        "pending_docs": pending_docs,
        "notices": notices,
    })


# ERP 문서 작성 폼 (동적 라우트)
for _route_name, (_dtype, _dlabel) in ERP_DOC_TYPES.items():
    def _make_handler(__dtype=_dtype, __dlabel=_dlabel):
        async def handler(request: Request):
            if not check_login(request):
                return RedirectResponse(url="/login", status_code=303)
            uid = get_current_user(request)["user_id"]
            conn = get_sqlite()
            try:
                users = conn.execute(
                    "SELECT id, name, dept, position FROM users WHERE id != ? ORDER BY dept, name",
                    (uid,)
                ).fetchall()
                users = [dict(u) for u in users]
            finally:
                conn.close()
            return templates.TemplateResponse(
                request=request, name="erp/erp_form.html", context={
                    "request": request, "page_title": __dlabel,
                    "doc_type": __dtype, "back_url": ERP_REDIRECTS[__dtype],
                    "user_name": get_current_user(request)["user_name"],
                    "users": users,
                }
            )
        return handler
    router.add_api_route(f"/{_route_name}", _make_handler(), methods=["GET"], response_class=HTMLResponse)


@router.get("/erp_doc/{doc_id}", response_class=HTMLResponse)
async def erp_doc_detail(request: Request, doc_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        row = conn.execute(
            """SELECT e.*,
                   u.name AS author_name, u.dept AS author_dept,
                   u.position AS author_position, u.phone AS author_phone,
                   u2.name AS approver_name
               FROM erp_docs e
               LEFT JOIN users u ON e.user_id = u.id
               LEFT JOIN users u2 ON e.approved_by = u2.id
               WHERE e.id=?""",
            (doc_id,)
        ).fetchone()
        if not row:
            return HTMLResponse("<h2>문서를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
        lines = conn.execute("""
    SELECT al.*, u.name as user_name, u.dept as user_dept, u.position as user_position
    FROM approval_lines al
    LEFT JOIN users u ON al.approver_id = u.id
    WHERE al.doc_id=?
    ORDER BY al.step
""", (doc_id,)).fetchall()
        approval_lines = [dict(l) for l in lines]
        history = conn.execute("""
    SELECT * FROM doc_history WHERE doc_id=? ORDER BY created_at
""", (doc_id,)).fetchall()
        history = [dict(h) for h in history]
    finally:
        conn.close()
    doc = with_status_meta([row])[0]
    doc["doc_type_label"] = ERP_DOC_TYPE_LABELS.get(doc["doc_type"], doc["doc_type"])
    back_url = ERP_REDIRECTS.get(doc["doc_type"], "/erp_groupware")
    print_mode = request.query_params.get("print", "") == "1"
    uid = get_current_user(request)["user_id"]
    active_line = next((l for l in approval_lines if l["status"] == "pending"), None)
    can_approve = False
    if active_line:
        can_approve = (active_line["approver_id"] == uid)
    role = request.session.get("role", "")
    if role in ("admin", "manager"):
        can_approve = True
    if doc.get("status") in ("done", "approved", "resolved", "rejected"):
        can_approve = False
    return templates.TemplateResponse(
        request=request, name="erp/erp_doc_detail.html", context={
            "request": request, "page_title": doc["title"],
            "doc": doc, "back_url": back_url,
            "user_name": get_current_user(request)["user_name"],
            "approval_lines": approval_lines,
            "history": history,
            "print_mode": print_mode,
            "can_approve": can_approve,
            "current_user_id": uid,
        }
    )


@router.get("/leave_approvals", response_class=HTMLResponse)
async def leave_approvals(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='hr_task' AND title LIKE '%휴가%' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/leave_approvals.html", context={
        "request": request, "page_title": "휴가 승인",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
    })


@router.get("/recruitment_status", response_class=HTMLResponse)
async def recruitment_status(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        postings = [dict(r) for r in conn.execute("SELECT * FROM job_postings ORDER BY id DESC").fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/recruitment_status.html", context={
        "request": request, "page_title": "채용 현황",
        "user_name": get_current_user(request)["user_name"], "postings": postings,
    })


@router.get("/outflow_list", response_class=HTMLResponse)
async def outflow_list(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('done','approved') ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "출금 완료 내역",
        "subtitle": "처리 완료된 지출 내역입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
    })


@router.get("/pending_payments", response_class=HTMLResponse)
async def pending_payments(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('wait','pending','urgent') ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "미결제 내역",
        "subtitle": "처리 대기 중인 지출 요청입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
    })


@router.get("/production_status", response_class=HTMLResponse)
async def production_status(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='work_order' AND status IN ('progress','wait') ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "작업 진행 현황",
        "subtitle": "진행 중이거나 대기 중인 작업 지시입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_product", "back_label": "생산관리",
    })


@router.get("/equipment_alerts", response_class=HTMLResponse)
async def equipment_alerts(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='work_order' AND status='urgent' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "생산 긴급 알림",
        "subtitle": "긴급 처리가 필요한 작업 지시입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_product", "back_label": "생산관리",
    })


@router.get("/po_status", response_class=HTMLResponse)
async def po_status(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='po' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "발주 현황",
        "subtitle": "전체 발주서 목록입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_purch", "back_label": "구매관리",
    })


@router.get("/delayed_delivery", response_class=HTMLResponse)
async def delayed_delivery(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='po' AND status='urgent' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "납기 지연",
        "subtitle": "납기가 지연되어 긴급 확인이 필요한 발주입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_purch", "back_label": "구매관리",
    })


@router.get("/outbound_status", response_class=HTMLResponse)
async def outbound_status(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='stock_move' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "입출고 현황",
        "subtitle": "전체 입출고 등록 내역입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_inventory", "back_label": "재고관리",
    })


@router.get("/low_stock_alerts", response_class=HTMLResponse)
async def low_stock_alerts(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='stock_move' AND status='urgent' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "재고 부족 알림",
        "subtitle": "긴급 보충이 필요한 재고 항목입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_inventory", "back_label": "재고관리",
    })


@router.get("/sales_leads", response_class=HTMLResponse)
async def sales_leads(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='activity' AND status IN ('progress','wait') ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "영업 기회",
        "subtitle": "진행 중인 영업 활동입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_scrm", "back_label": "영업/고객관리",
    })


@router.get("/voc_list", response_class=HTMLResponse)
async def voc_list(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE doc_type='activity' AND status='urgent' ORDER BY id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "고객 VOC",
        "subtitle": "긴급 대응이 필요한 고객 요청입니다.",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
        "back_url": "/erp_scrm", "back_label": "영업/고객관리",
    })


@router.get("/approval_pending", response_class=HTMLResponse)
async def approval_pending(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        docs = with_status_meta(conn.execute(
            "SELECT * FROM erp_docs WHERE status IN ('wait','pending','urgent') ORDER BY CASE status WHEN 'urgent' THEN 0 ELSE 1 END, id DESC"
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="erp/approval_pending.html", context={
        "request": request, "page_title": "결재 대기",
        "user_name": get_current_user(request)["user_name"], "docs": docs,
    })


# --- API ---

@router.post("/api/erp_docs")
async def create_erp_doc(
    request: Request,
    doc_type: str = Form(""), title: str = Form(""), content: str = Form(""),
    visibility: str = Form("공개"),
    retention_period: str = Form("3년"),
    effective_date: str = Form(""),
    dept: str = Form(""),
    reviewer_id: int = Form(...),
    approver_id: int = Form(...),
    attachment: Optional[UploadFile] = File(None),
    save_mode: str = Form("submit"),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    import uuid, pathlib
    uid = get_current_user(request)["user_id"]
    saved_name = ""
    if attachment and attachment.filename:
        ext = pathlib.Path(attachment.filename).suffix
        content_bytes = await attachment.read()
        ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".hwp", ".txt", ".zip"}
        MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return JSONResponse({"error": "허용되지 않는 파일 형식입니다."}, status_code=400)
        if len(content_bytes) > MAX_UPLOAD_SIZE:
            return JSONResponse({"error": "파일 크기가 10MB를 초과합니다."}, status_code=413)
        safe_name = f"{uuid.uuid4().hex}{ext}"
        upload_dir = pathlib.Path("static/uploads/erp")
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / safe_name
        dest.write_bytes(content_bytes)
        # DB에는 "원본파일명|저장파일명" 형식으로 저장
        saved_name = f"{attachment.filename}|{safe_name}"
    DOC_NUM_PREFIXES = {"draft": "GW", "hr_task": "HR", "stock_move": "INV", "work_order": "WO", "po": "PO", "activity": "CRM", "expense": "EXP"}
    prefix = DOC_NUM_PREFIXES.get(doc_type, "DOC")
    year = datetime.now().year
    uname = get_current_user(request)["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_draft = (save_mode == "draft")
    doc_status = "draft" if is_draft else "wait"
    conn = get_sqlite()
    try:
        cur = conn.execute(
            "INSERT INTO erp_docs (user_id, doc_type, title, content, attachment, status, visibility, retention_period, effective_date, dept) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, doc_type, title, content, saved_name, doc_status, visibility, retention_period, effective_date, dept),
        )
        new_doc_id = cur.lastrowid
        seq = conn.execute("SELECT COUNT(*) FROM erp_docs WHERE doc_type=?", (doc_type,)).fetchone()[0]
        doc_number = f"{prefix}-{year}-{seq:04d}"
        conn.execute("UPDATE erp_docs SET doc_number=? WHERE id=?", (doc_number, new_doc_id))
        # Create 3 approval lines: step 0 = 기안, step 1 = 검토, step 2 = 승인
        if is_draft:
            # Draft: all lines pending, step 0 not yet approved
            conn.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
                (new_doc_id, 0, uid, "기안", "pending")
            )
        else:
            # Submit: step 0 auto-approved by drafter
            conn.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, acted_at) VALUES (?,?,?,?,?,?)",
                (new_doc_id, 0, uid, "기안", "approved", now)
            )
        conn.execute(
            "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
            (new_doc_id, 1, reviewer_id, "검토", "pending")
        )
        conn.execute(
            "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
            (new_doc_id, 2, approver_id, "승인", "pending")
        )
        history_action = "임시저장" if is_draft else "기안"
        conn.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment) VALUES (?,?,?,?,?)",
            (new_doc_id, uid, uname, history_action, "")
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=ERP_REDIRECTS.get(doc_type, "/"), status_code=303)


@router.post("/api/erp_docs/{doc_id}/status")
async def update_erp_doc_status(request: Request, doc_id: int, status: str = Form(...), reason: str = Form("")):
    role = request.session.get("role", "")
    if role not in ("admin", "manager"):
        return JSONResponse({"error": "권한이 없습니다."}, status_code=403)

    u = get_current_user(request)
    uid = u["user_id"]
    uname = u["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sqlite()
    try:
        conn.execute(
            "UPDATE erp_docs SET status=?, approved_by=?, approved_at=? WHERE id=?",
            (status, uid, now, doc_id)
        )
        if status == "rejected" and reason:
            conn.execute("UPDATE erp_docs SET reject_reason=? WHERE id=?", (reason, doc_id))

        # Update the first pending approval line (admin/manager acts on behalf)
        conn.execute(
            """UPDATE approval_lines SET status=?, comment=?, acted_at=?
               WHERE id = (SELECT id FROM approval_lines
                           WHERE doc_id=? AND status='pending' ORDER BY step LIMIT 1)""",
            (status, reason, now, doc_id)
        )

        # Insert history entry
        action = "승인" if status in ("done", "approved") else "반려"
        conn.execute(
            "INSERT INTO doc_history (doc_id, action, user_id, user_name, comment) VALUES (?,?,?,?,?)",
            (doc_id, action, uid, uname, reason)
        )

        conn.commit()
    finally:
        conn.close()

    return JSONResponse({"ok": True})


@router.post("/api/erp_docs/{doc_id}/approve")
async def approve_erp_doc(request: Request, doc_id: int, comment: str = Form("")):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    u = get_current_user(request)
    uid, uname = u["user_id"], u["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sqlite()
    try:
        role = request.session.get("role", "")
        if role in ("admin", "manager"):
            line = conn.execute(
                "SELECT * FROM approval_lines WHERE doc_id=? AND status='pending' ORDER BY step LIMIT 1",
                (doc_id,)
            ).fetchone()
        else:
            line = conn.execute(
                "SELECT * FROM approval_lines WHERE doc_id=? AND approver_id=? AND status='pending'",
                (doc_id, uid)
            ).fetchone()

        if not line:
            return JSONResponse({"error": "승인할 항목이 없습니다."}, status_code=400)

        conn.execute(
            "UPDATE approval_lines SET status='approved', comment=?, acted_at=? WHERE id=?",
            (comment, now, line["id"])
        )

        total = conn.execute("SELECT COUNT(*) FROM approval_lines WHERE doc_id=?", (doc_id,)).fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM approval_lines WHERE doc_id=? AND status='approved'", (doc_id,)).fetchone()[0]
        new_status = "done" if approved >= total else "progress"

        conn.execute("UPDATE erp_docs SET status=?, approved_by=?, approved_at=? WHERE id=?",
                     (new_status, uid, now, doc_id))

        conn.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment) VALUES (?,?,?,?,?)",
            (doc_id, uid, uname, "승인", comment)
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True, "new_status": new_status})


@router.post("/api/erp_docs/{doc_id}/reject")
async def reject_erp_doc(request: Request, doc_id: int, comment: str = Form(...)):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    u = get_current_user(request)
    uid, uname = u["user_id"], u["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sqlite()
    try:
        role = request.session.get("role", "")
        if role in ("admin", "manager"):
            line = conn.execute(
                "SELECT * FROM approval_lines WHERE doc_id=? AND status='pending' ORDER BY step LIMIT 1",
                (doc_id,)
            ).fetchone()
        else:
            line = conn.execute(
                "SELECT * FROM approval_lines WHERE doc_id=? AND approver_id=? AND status='pending'",
                (doc_id, uid)
            ).fetchone()

        if not line:
            return JSONResponse({"error": "반려할 항목이 없습니다."}, status_code=400)

        conn.execute(
            "UPDATE approval_lines SET status='rejected', comment=?, acted_at=? WHERE id=?",
            (comment, now, line["id"])
        )
        conn.execute(
            "UPDATE erp_docs SET status='rejected', reject_reason=?, approved_by=?, approved_at=? WHERE id=?",
            (comment, uid, now, doc_id)
        )
        conn.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment) VALUES (?,?,?,?,?)",
            (doc_id, uid, uname, "반려", comment)
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.post("/api/erp_docs/{doc_id}/submit")
async def submit_erp_doc(request: Request, doc_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    u = get_current_user(request)
    uid, uname = u["user_id"], u["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sqlite()
    try:
        doc = conn.execute("SELECT * FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
        if doc["user_id"] != uid:
            return JSONResponse({"error": "기안자만 상신할 수 있습니다."}, status_code=403)
        if doc["status"] != "draft":
            return JSONResponse({"error": "임시저장 상태의 문서만 상신할 수 있습니다."}, status_code=400)

        # Mark status → wait and approve step 0 (기안)
        conn.execute("UPDATE erp_docs SET status='wait' WHERE id=?", (doc_id,))
        conn.execute(
            "UPDATE approval_lines SET status='approved', acted_at=? WHERE doc_id=? AND step=0",
            (now, doc_id)
        )
        conn.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment) VALUES (?,?,?,?,?)",
            (doc_id, uid, uname, "상신", "")
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.post("/api/erp_docs/{doc_id}/withdraw")
async def withdraw_erp_doc(request: Request, doc_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    u = get_current_user(request)
    uid, uname = u["user_id"], u["user_name"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_sqlite()
    try:
        doc = conn.execute("SELECT * FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            return JSONResponse({"error": "문서를 찾을 수 없습니다."}, status_code=404)
        if doc["user_id"] != uid:
            return JSONResponse({"error": "기안자만 철회할 수 있습니다."}, status_code=403)
        if doc["status"] in ("done", "approved", "resolved", "rejected"):
            return JSONResponse({"error": "완료 또는 반려된 문서는 철회할 수 없습니다."}, status_code=400)

        # Check that the final approver (last step) has not approved yet
        last_line = conn.execute(
            "SELECT * FROM approval_lines WHERE doc_id=? ORDER BY step DESC LIMIT 1",
            (doc_id,)
        ).fetchone()
        if last_line and last_line["status"] == "approved":
            return JSONResponse({"error": "최종 결재가 완료된 문서는 철회할 수 없습니다."}, status_code=400)

        # Reset status to draft
        conn.execute("UPDATE erp_docs SET status='draft' WHERE id=?", (doc_id,))
        # Reset ALL approval lines (including step 0) to pending, clear comment and acted_at
        conn.execute(
            "UPDATE approval_lines SET status='pending', comment=NULL, acted_at=NULL WHERE doc_id=?",
            (doc_id,)
        )
        conn.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment) VALUES (?,?,?,?,?)",
            (doc_id, uid, uname, "철회", "기안자 철회")
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.get("/erp_doc/{doc_id}/print", response_class=HTMLResponse)
async def erp_doc_print(request: Request, doc_id: int):
    return RedirectResponse(url=f"/erp_doc/{doc_id}?print=1", status_code=303)


@router.get("/api/erp_docs")
async def list_erp_docs(request: Request, doc_type: Optional[str] = None):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        if doc_type:
            rows = conn.execute("SELECT * FROM erp_docs WHERE doc_type=? ORDER BY created_at DESC", (doc_type,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM erp_docs ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
