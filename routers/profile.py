from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite
from core.deps import check_login, templates

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, success: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    user = dict(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    my_post_count = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
    my_comment_count = conn.execute("SELECT COUNT(*) FROM comments WHERE user_id=?", (uid,)).fetchone()[0]
    my_done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="top/profile.html", context={
            "request": request, "page_title": "내 프로필",
            "user": user, "my_post_count": my_post_count,
            "my_comment_count": my_comment_count, "my_done_count": my_done_count,
            "success": success,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.post("/api/profile")
async def update_profile(request: Request, name: str = Form(...), dept: str = Form(""), phone: str = Form("")):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE users SET name=?, dept=?, phone=? WHERE id=?", (name, dept, phone, uid))
    conn.commit()
    conn.close()
    request.session["user_name"] = name
    return RedirectResponse(url="/profile?success=1", status_code=303)


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    notifs = [dict(r) for r in conn.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC", (uid,)
    ).fetchall()]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="top/notifications.html", context={
            "request": request, "page_title": "알림",
            "notifications": notifs,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.post("/api/notifications/read_all")
async def notifications_read_all(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/accessibility", response_class=HTMLResponse)
async def accessibility_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="top/accessibility.html", context={
            "request": request, "page_title": "접근성 설정",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )
