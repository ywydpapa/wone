from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, get_current_user, templates

router = APIRouter()

AS_CATEGORIES = {
    "hardware": "하드웨어",
    "software": "소프트웨어",
    "network": "네트워크",
    "access": "접근성 지원",
    "facility": "시설/환경",
    "other": "기타",
}


@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        user_row = conn.execute("SELECT name, dept, phone FROM users WHERE id=?", (uid,)).fetchone()
        my_requests = with_status_meta(conn.execute(
            "SELECT * FROM as_requests WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)
        ).fetchall())
    finally:
        conn.close()
    user_info = dict(user_row) if user_row else {"name": "김민수", "dept": "경영지원팀", "phone": "070-1234-5678"}
    return templates.TemplateResponse(
        request=request, name="/top/contact.html", context={
            "request": request, "page_title": "AS 접수",
            "user_info": user_info, "my_requests": my_requests,
            "user_name": u["user_name"],
        }
    )


@router.get("/as_manage", response_class=HTMLResponse)
async def as_manage(
    request: Request,
    status_filter: str = "",
    urgency_filter: str = "",
    category_filter: str = "",
    q: str = "",
    page: int = 1,
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    per_page = 15
    offset = (page - 1) * per_page

    conn = get_sqlite()
    try:
        # Build WHERE clause
        conditions = ["1=1"]
        params: list = []
        if status_filter:
            conditions.append("r.status = ?")
            params.append(status_filter)
        if urgency_filter:
            conditions.append("r.urgency = ?")
            params.append(urgency_filter)
        if category_filter:
            conditions.append("r.category = ?")
            params.append(category_filter)
        if q:
            conditions.append("(r.title LIKE '%'||?||'%' OR u.name LIKE '%'||?||'%')")
            params.extend([q, q])

        where = " AND ".join(conditions)

        base_sql = (
            "SELECT r.*, u.name AS requester_name, u.dept AS requester_dept, u.phone AS requester_phone"
            " FROM as_requests r JOIN users u ON u.id = r.user_id"
            " WHERE " + where
        )
        order_sql = (
            " ORDER BY CASE r.urgency WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, r.id DESC "
        )

        count_sql = (
            "SELECT COUNT(*) FROM as_requests r JOIN users u ON u.id = r.user_id WHERE " + where
        )
        total_row = conn.execute(count_sql, params).fetchone()
        total = total_row[0] if total_row else 0
        total_pages = max(1, (total + per_page - 1) // per_page)

        rows = conn.execute(
            base_sql + order_sql + "LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()
        requests_list = with_status_meta(rows)

        # Category label enrichment
        for r in requests_list:
            r["category_label"] = AS_CATEGORIES.get(r.get("category", ""), r.get("category", ""))

        # Stats
        stat_total = conn.execute("SELECT COUNT(*) FROM as_requests").fetchone()[0]
        stat_pending = conn.execute("SELECT COUNT(*) FROM as_requests WHERE status='pending'").fetchone()[0]
        stat_in_progress = conn.execute("SELECT COUNT(*) FROM as_requests WHERE status='in_progress'").fetchone()[0]
        stat_resolved = conn.execute("SELECT COUNT(*) FROM as_requests WHERE status='resolved'").fetchone()[0]
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="top/as_manage.html", context={
            "request": request,
            "page_title": "지원요청 관리",
            "user_name": u["user_name"],
            "requests_list": requests_list,
            "status_filter": status_filter,
            "urgency_filter": urgency_filter,
            "category_filter": category_filter,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "stat_total": stat_total,
            "stat_pending": stat_pending,
            "stat_in_progress": stat_in_progress,
            "stat_resolved": stat_resolved,
            "AS_CATEGORIES": AS_CATEGORIES,
        }
    )


@router.get("/as_request/{req_id}", response_class=HTMLResponse)
async def as_request_detail(request: Request, req_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    conn = get_sqlite()
    try:
        row = conn.execute(
            """SELECT r.*, u.name AS requester_name, u.dept AS requester_dept, u.phone AS requester_phone
               FROM as_requests r JOIN users u ON u.id = r.user_id
               WHERE r.id=?""",
            (req_id,),
        ).fetchone()
        if not row:
            return HTMLResponse("<h2>요청을 찾을 수 없습니다</h2><a href='/as_manage'>돌아가기</a>", status_code=404)
        r = dict(row)

        # Status meta
        from core.db import STATUS_META
        label, cls, style = STATUS_META.get(r.get("status", ""), (r.get("status", ""), "status-progress", ""))
        r["status_label"], r["status_class"], r["status_style"] = label, cls, style
        r["category_label"] = AS_CATEGORIES.get(r.get("category", ""), r.get("category", ""))

        comments_rows = conn.execute(
            """SELECT c.*, u.name AS commenter_name
               FROM as_comments c JOIN users u ON u.id = c.user_id
               WHERE c.request_id=? ORDER BY c.id ASC""",
            (req_id,),
        ).fetchall()
        comments = [dict(c) for c in comments_rows]

        all_users = conn.execute(
            "SELECT id, name, dept FROM users ORDER BY name"
        ).fetchall()
        employees = [dict(emp) for emp in all_users]
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request, name="top/as_detail.html", context={
            "request": request,
            "page_title": "지원요청 상세",
            "user_name": u["user_name"],
            "r": r,
            "comments": comments,
            "employees": employees,
            "AS_CATEGORIES": AS_CATEGORIES,
        }
    )


@router.post("/submit_as_request")
async def submit_as_request(
    request: Request,
    asCategory: str = Form(""), asUrgency: str = Form(""),
    asTitle: str = Form(""), asDetails: str = Form(""),
    asAttachment: Optional[UploadFile] = File(None),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    attachment_name = asAttachment.filename if asAttachment and asAttachment.filename else ""
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO as_requests (user_id, category, urgency, title, details, attachment, status) VALUES (?,?,?,?,?,?,?)",
            (uid, asCategory, asUrgency, asTitle, asDetails, attachment_name, "pending"),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/contact", status_code=303)


@router.post("/api/as_requests/{req_id}/status")
async def update_as_status(request: Request, req_id: int, status: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        if status == "resolved":
            conn.execute(
                "UPDATE as_requests SET status=?, resolved_at=datetime('now','localtime') WHERE id=?",
                (status, req_id),
            )
        else:
            conn.execute(
                "UPDATE as_requests SET status=?, resolved_at=NULL WHERE id=?",
                (status, req_id),
            )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/as_request/{req_id}", status_code=303)


@router.post("/api/as_requests/{req_id}/assign")
async def assign_as_request(request: Request, req_id: int, assigned_to: int = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        name_row = conn.execute("SELECT name FROM users WHERE id=?", (assigned_to,)).fetchone()
        assigned_name = name_row["name"] if name_row else ""
        conn.execute(
            "UPDATE as_requests SET assigned_to=?, assigned_name=? WHERE id=?",
            (assigned_to, assigned_name, req_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/as_request/{req_id}", status_code=303)


@router.post("/api/as_requests/{req_id}/memo")
async def update_as_memo(request: Request, req_id: int, memo: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        conn.execute("UPDATE as_requests SET admin_memo=? WHERE id=?", (memo, req_id))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/as_request/{req_id}", status_code=303)


@router.post("/api/as_requests/{req_id}/comment")
async def add_as_comment(request: Request, req_id: int, content: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        name_row = conn.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
        user_name = name_row["name"] if name_row else u["user_name"]
        conn.execute(
            "INSERT INTO as_comments (request_id, user_id, user_name, content, created_at) VALUES (?,?,?,?,datetime('now','localtime'))",
            (req_id, uid, user_name, content),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/as_request/{req_id}", status_code=303)


@router.get("/api/as_requests")
async def list_as_requests(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        rows = conn.execute("SELECT * FROM as_requests ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
