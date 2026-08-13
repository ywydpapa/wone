from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import check_login, templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/login/login.html", context={
            "request": request, "page_title": "로그인", "error": error,
        }
    )


@router.post("/login_check")
async def login_check(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_sqlite()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?", (username, password)
    ).fetchone()
    conn.close()
    if row:
        request.session["logined"] = True
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        request.session["user_name"] = row["name"]
        request.session["role"] = row["role"]
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        request=request, name="/login/signup.html", context={
            "request": request, "page_title": "회원가입", "error": error,
        }
    )


@router.post("/signup")
async def signup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    dept: str = Form("경영지원팀"),
):
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO users (username, password, name, dept) VALUES (?,?,?,?)",
            (username, password, name, dept)
        )
        conn.commit()
    except Exception:
        conn.close()
        return RedirectResponse(url="/signup?error=dup", status_code=303)
    conn.close()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/forgot_password")
async def forgot_password():
    return RedirectResponse(url="/signup", status_code=303)
