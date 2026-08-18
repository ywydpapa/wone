from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, success: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        user = dict(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        my_post_count = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
        my_comment_count = conn.execute("SELECT COUNT(*) FROM comments WHERE user_id=?", (uid,)).fetchone()[0]
        my_done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="top/profile.html", context={
            "request": request, "page_title": "내 프로필",
            "user": user, "my_post_count": my_post_count,
            "my_comment_count": my_comment_count, "my_done_count": my_done_count,
            "success": success,
            "user_name": u["user_name"],
        }
    )


@router.post("/api/profile")
async def update_profile(request: Request, name: str = Form(...), dept: str = Form(""), phone: str = Form("")):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        conn.execute("UPDATE users SET name=?, dept=?, phone=? WHERE id=?", (name, dept, phone, uid))
        conn.commit()
    finally:
        conn.close()
    request.session["user_name"] = name
    return RedirectResponse(url="/profile?success=1", status_code=303)


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        notifs = [dict(r) for r in conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC", (uid,)
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="top/notifications.html", context={
            "request": request, "page_title": "알림",
            "notifications": notifs,
            "user_name": u["user_name"],
        }
    )


@router.post("/api/notifications/read_all")
async def notifications_read_all(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/accessibility", response_class=HTMLResponse)
async def accessibility_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="top/accessibility.html", context={
            "request": request, "page_title": "접근성 설정",
            "user_name": get_current_user(request)["user_name"],
        }
    )
