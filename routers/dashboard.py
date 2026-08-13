from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/top/index.html", context={
            "request": request, "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/emp_dash", response_class=HTMLResponse)
async def emp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    todos = with_status_meta(conn.execute(
        "SELECT * FROM jobs WHERE user_id=? AND status!='done' ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id",
        (uid,)).fetchall())
    done_recent = with_status_meta(conn.execute(
        "SELECT * FROM jobs WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 1", (uid,)).fetchall())
    done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
    unread_msgs = conn.execute(
        "SELECT * FROM messages WHERE user_id=? AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/emp_dash.html", context={
            "request": request, "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수"),
            "todos": todos, "done_recent": done_recent, "done_count": done_count,
            "progress_count": len(todos),
            "messages": [dict(m) for m in unread_msgs],
            "unread_count": len(unread_msgs),
        }
    )


@router.get("/manage_dash", response_class=HTMLResponse)
async def manage_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/top/manage_dash.html", context={
            "request": request, "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )
