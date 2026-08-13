from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, templates

router = APIRouter()


@router.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    user_row = conn.execute("SELECT name, dept, phone FROM users WHERE id=?", (uid,)).fetchone()
    my_requests = with_status_meta(conn.execute(
        "SELECT * FROM as_requests WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,)
    ).fetchall())
    conn.close()
    user_info = dict(user_row) if user_row else {"name": "김민수", "dept": "경영지원팀", "phone": "070-1234-5678"}
    return templates.TemplateResponse(
        request=request, name="/top/contact.html", context={
            "request": request, "page_title": "AS 접수",
            "user_info": user_info, "my_requests": my_requests,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/as_request/{req_id}", response_class=HTMLResponse)
async def as_request_detail(request: Request, req_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM as_requests WHERE id=?", (req_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>요청을 찾을 수 없습니다</h2><a href='/contact'>돌아가기</a>", status_code=404)
    r = dict(row)
    return templates.TemplateResponse(
        request=request, name="common/detail.html", context={
            "request": request, "page_title": "AS 요청 상세",
            "badges": [{"text": r["urgency"], "color": "warning"}, {"text": r["status"], "color": "info"}],
            "detail_title": r["title"], "detail_date": r["created_at"],
            "detail_content": r["details"], "extra_content": "", "extra_label": "",
            "back_url": "/contact",
            "user_name": request.session.get("user_name", "김민수"),
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
    attachment_name = asAttachment.filename if asAttachment and asAttachment.filename else ""
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO as_requests (user_id, category, urgency, title, details, attachment, status) VALUES (?,?,?,?,?,?,?)",
        (request.session.get("user_id", 1), asCategory, asUrgency, asTitle, asDetails, attachment_name, "pending"),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/contact", status_code=303)


@router.get("/api/as_requests")
async def list_as_requests(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM as_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
