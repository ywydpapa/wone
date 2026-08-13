from pathlib import Path
import os
from PIL import Image
import jwt
from fastapi import (
    FastAPI,
    Depends,
    Request,
    Form,
    Response,
    HTTPException,
    Body, File, UploadFile
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware
import dotenv
from starlette.responses import JSONResponse
from datetime import datetime, timedelta
import funchub
from typing import Optional, List
import shutil
import sqlite3
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")


def get_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


STATUS_META = {
    "urgent":      ("긴급",  "status-urgent",   ""),
    "progress":    ("진행중", "status-progress", ""),
    "in_progress": ("진행중", "status-progress", ""),
    "wait":        ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "pending":     ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "draft":       ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "done":        ("완료",  "status-done",     ""),
    "approved":    ("완료",  "status-done",     ""),
    "resolved":    ("완료",  "status-done",     ""),
    "rejected":    ("반려",  "status-urgent",   ""),
}


def with_status_meta(rows):
    """sqlite Row 리스트 → dict 리스트 + status_label/status_class/status_style 부여"""
    out = []
    for r in rows:
        d = dict(r)
        label, cls, style = STATUS_META.get(d.get("status", ""), (d.get("status", ""), "status-progress", ""))
        d["status_label"], d["status_class"], d["status_style"] = label, cls, style
        out.append(d)
    return out


dotenv.load_dotenv()
DATABASE_URL = os.getenv("dburl", "sqlite+aiosqlite:///./test.db")

_engine_kwargs = {}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_pre_ping=True, pool_timeout=10, pool_recycle=1800)

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)


async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "supersecretkey"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://www.wno1.kr"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
PHOTO_DIR = Path("./static/photo/event_photos")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
security = HTTPBearer()

class VoiceInput(BaseModel):
    text: str


async def get_db():
    async with async_session() as session:
        yield session


# --- 세션 체크용 헬퍼 함수 ---
def check_login(request: Request):
    """세션에 logined 값이 없으면 False 반환"""
    return request.session.get("logined", False)


@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    # 로그인 상태가 아니면 로그인 페이지로 리다이렉트
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/index.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/text")
async def receive_voice_text(data: VoiceInput):
    print(f"인식된 텍스트: {data.text}")
    return {"status": "success", "received_text": data.text}


@app.get("/resume", response_class=HTMLResponse)
async def resume(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/resume.html", context={
            "request": request,
            "page_title": "채용/인재",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/voice", response_class=HTMLResponse)
async def voice(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/voice.html", context={
            "request": request,
            "page_title": "채용/인재",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/eyemouse", response_class=HTMLResponse)
async def eyemouse(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/apps/eyemouse.html", context={
            "request": request,
            "page_title": "채용/인재",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/emp_dash", response_class=HTMLResponse)
async def emp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    todos = with_status_meta(conn.execute(
        "SELECT * FROM jobs WHERE user_id=? AND status!='done' ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id",
        (uid,)).fetchall())
    done_recent = with_status_meta(conn.execute(
        "SELECT * FROM jobs WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 1",
        (uid,)).fetchall())
    done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
    unread_msgs = conn.execute(
        "SELECT * FROM messages WHERE user_id=? AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/emp_dash.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수"),
            "todos": todos,
            "done_recent": done_recent,
            "done_count": done_count,
            "progress_count": len(todos),
            "messages": [dict(m) for m in unread_msgs],
            "unread_count": len(unread_msgs),
        }
    )


@app.get("/manage_dash", response_class=HTMLResponse)
async def manage_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/manage_dash.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/youtube_edit", response_class=HTMLResponse)
async def yt_edit(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/youtube_edit.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

@app.get("/real_trans", response_class=HTMLResponse)
async def real_trans(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/apps/realtime_trans.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/job_diary", response_class=HTMLResponse)
async def jobdiary(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/apps/job_diary.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/completed_jobs", response_class=HTMLResponse)
async def cedjob(request: Request, q: str = "", page: int = 1):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    per_page = 10
    params: list = [uid]
    sql = "SELECT * FROM jobs WHERE user_id=? AND status='done'"
    if q:
        sql += " AND title LIKE '%'||?||'%'"
        params.append(q)
    total = conn.execute(sql.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [per_page, (page - 1) * per_page]
    done_jobs = with_status_meta(conn.execute(sql, params).fetchall())
    progress_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status!='done'", (uid,)).fetchone()[0]
    conn.close()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        request=request, name="/apps/complete_job.html", context={
            "request": request,
            "page_title": "완료 업무",
            "user_name": request.session.get("user_name", "김민수"),
            "done_jobs": done_jobs,
            "done_count": total,
            "progress_count": progress_count,
            "q": q,
            "page": page,
            "total_pages": total_pages,
        }
    )


@app.get("/newarrived_jobs", response_class=HTMLResponse)
async def newarrived_jobs(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    unread_msgs = [dict(m) for m in conn.execute(
        "SELECT * FROM messages WHERE user_id=? AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()]
    read_msgs = [dict(m) for m in conn.execute(
        "SELECT * FROM messages WHERE user_id=? AND is_read=1 ORDER BY id DESC", (uid,)).fetchall()]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/apps/new_arrived_job.html", context={
            "request": request,
            "page_title": "메시지함",
            "user_name": request.session.get("user_name", "김민수"),
            "unread_msgs": unread_msgs,
            "read_msgs": read_msgs,
            "unread_count": len(unread_msgs),
            "read_count": len(read_msgs),
        }
    )

@app.get("/new_job", response_class=HTMLResponse)
async def new_job(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/new_job.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

POST_CATEGORIES = {
    "it":      ("💻 IT/개발",      "primary"),
    "biz":     ("📊 경영/사무",    "success"),
    "design":  ("🎨 디자인",       "warning"),
    "sales":   ("📢 영업/마케팅",  "danger"),
    "notice":  ("📌 공지",         "dark"),
    "general": ("💬 자유",         "secondary"),
    "qna":     ("❓ Q&A",          "info"),
}


@app.get("/community", response_class=HTMLResponse)
async def communi(request: Request, category: str = "all", q: str = "", page: int = 1):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    per_page = 10
    sql = """SELECT p.*,
        (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count,
        (SELECT COUNT(*) FROM post_likes l WHERE l.post_id=p.id) AS like_count
        FROM posts p WHERE 1=1"""
    params: list = []
    if category != "all":
        sql += " AND p.category=?"; params.append(category)
    if q:
        sql += " AND (p.title LIKE '%'||?||'%' OR p.content LIKE '%'||?||'%')"; params += [q, q]
    count_sql = sql.replace("SELECT p.*,\n        (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count,\n        (SELECT COUNT(*) FROM post_likes l WHERE l.post_id=p.id) AS like_count\n        FROM posts p WHERE 1=1", "SELECT COUNT(*) FROM posts p WHERE 1=1")
    total = conn.execute(count_sql, params).fetchone()[0]
    sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"; params += [per_page, (page - 1) * per_page]
    posts = [dict(r) for r in conn.execute(sql, params).fetchall()]
    my_post_count = conn.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,)).fetchone()[0]
    my_comment_count = conn.execute("SELECT COUNT(*) FROM comments WHERE user_id=?", (uid,)).fetchone()[0]
    my_like_received = conn.execute(
        "SELECT COUNT(*) FROM post_likes l JOIN posts p ON p.id=l.post_id WHERE p.user_id=?", (uid,)
    ).fetchone()[0]
    conn.close()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        request=request, name="/top/community.html", context={
            "request": request,
            "page_title": "커뮤니티",
            "user_name": request.session.get("user_name", "김민수"),
            "posts": posts,
            "categories": POST_CATEGORIES,
            "current_category": category,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "my_post_count": my_post_count,
            "my_comment_count": my_comment_count,
            "my_like_received": my_like_received,
        }
    )

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/contact.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, error: str = ""):
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/login/login.html", context={
            "request": request,
            "page_title": "로그인",
            "error": error,
        }
    )


@app.post("/login_check")
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


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        request=request, name="/login/signup.html", context={
            "request": request,
            "page_title": "회원가입",
            "error": error,
        }
    )


@app.post("/signup")
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


@app.get("/forgot_password")
async def forgot_password(request: Request):
    return RedirectResponse(url="/signup", status_code=303)

@app.get("/erp_dash", response_class=HTMLResponse)
async def erp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_dash.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_hr", response_class=HTMLResponse)
async def erp_hr(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_hr.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

@app.get("/erp_fa", response_class=HTMLResponse)
async def erp_fa(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_fa.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_scrm", response_class=HTMLResponse)
async def erp_scrm(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_scrm.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

@app.get("/erp_purch", response_class=HTMLResponse)
async def erp_purch(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_purch.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

@app.get("/erp_inventory", response_class=HTMLResponse)
async def erp_invent(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_inventory.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_product", response_class=HTMLResponse)
async def erp_product(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_product.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )

@app.get("/erp_groupware", response_class=HTMLResponse)
async def erp_groupware(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_groupware.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


# ============================================================
# API: 업무 저장 (업무일지 + 새 업무)
# ============================================================
@app.post("/api/jobs")
async def create_job(
    request: Request,
    workDate: str = Form(""),
    workCategory: str = Form(""),
    workTitle: str = Form(""),
    workDetails: str = Form(""),
    workIssues: str = Form(""),
    progressStatus: str = Form("progress"),
    workAttachment: Optional[UploadFile] = File(None),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO jobs (user_id, work_date, category, title, details, issues, status) VALUES (?,?,?,?,?,?,?)",
        (1, workDate, workCategory, workTitle, workDetails, workIssues, progressStatus),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/emp_dash", status_code=303)


@app.get("/api/jobs")
async def list_jobs(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/jobs/{job_id}/toggle")
async def toggle_job(request: Request, job_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        conn.close()
        return JSONResponse({"error": "not found"}, status_code=404)
    new_status = "progress" if row["status"] == "done" else "done"
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
    conn.commit()
    conn.close()
    return {"status": new_status}


@app.post("/api/messages/{msg_id}/read")
async def read_message(request: Request, msg_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/messages/read_all")
async def read_all_messages(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ============================================================
# API: AS 요청 접수
# ============================================================
@app.post("/submit_as_request")
async def submit_as_request(
    request: Request,
    asCategory: str = Form(""),
    asUrgency: str = Form(""),
    asTitle: str = Form(""),
    asDetails: str = Form(""),
    asAttachment: Optional[UploadFile] = File(None),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    attachment_name = ""
    if asAttachment and asAttachment.filename:
        attachment_name = asAttachment.filename
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO as_requests (user_id, category, urgency, title, details, attachment, status) VALUES (?,?,?,?,?,?,?)",
        (1, asCategory, asUrgency, asTitle, asDetails, attachment_name, "pending"),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/contact", status_code=303)


@app.get("/api/as_requests")
async def list_as_requests(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM as_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# API: 커뮤니티 게시글
# ============================================================
@app.get("/write_post", response_class=HTMLResponse)
async def write_post_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="top/write_post.html", context={
            "request": request,
            "page_title": "새 글 작성",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/posts")
async def create_post(
    request: Request,
    category: str = Form("general"),
    title: str = Form(""),
    content: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    user = conn.execute("SELECT name, dept FROM users WHERE id=?", (uid,)).fetchone()
    author = user["name"] if user else ""
    dept = user["dept"] if user else ""
    conn.execute(
        "INSERT INTO posts (user_id, category, title, content, author, dept) VALUES (?,?,?,?,?,?)",
        (uid, category, title, content, author, dept),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/community", status_code=303)


@app.get("/api/posts")
async def list_posts(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/my_posts", response_class=HTMLResponse)
async def my_posts(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM posts WHERE user_id=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request, name="top/my_posts.html", context={
            "request": request,
            "page_title": "내가 쓴 글",
            "posts": [dict(r) for r in rows],
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/my_bookmarks", response_class=HTMLResponse)
async def my_bookmarks(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM posts WHERE bookmarked=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request, name="top/my_bookmarks.html", context={
            "request": request,
            "page_title": "북마크",
            "posts": [dict(r) for r in rows],
            "user_name": request.session.get("user_name", "김민수")
        }
    )


# ============================================================
# API: ERP 문서 (공통 생성/조회)
# ============================================================
ERP_DOC_TYPES = {
    "draft_doc": ("draft", "결재 기안"),
    "new_hr_task": ("hr_task", "HR 업무"),
    "new_stock_move": ("stock_move", "입출고 등록"),
    "new_work_order": ("work_order", "작업 지시"),
    "new_po": ("po", "발주서"),
    "new_activity": ("activity", "활동 등록"),
}

ERP_REDIRECTS = {
    "draft": "/erp_groupware",
    "hr_task": "/erp_hr",
    "stock_move": "/erp_inventory",
    "work_order": "/erp_product",
    "po": "/erp_purch",
    "activity": "/erp_scrm",
}


for route_name, (dtype, dlabel) in ERP_DOC_TYPES.items():
    def _make_handler(_dtype=dtype, _dlabel=dlabel):
        async def handler(request: Request):
            if not check_login(request):
                return RedirectResponse(url="/login", status_code=303)
            return templates.TemplateResponse(
                request=request, name="erp/erp_form.html", context={
                    "request": request,
                    "page_title": _dlabel,
                    "doc_type": _dtype,
                    "back_url": ERP_REDIRECTS[_dtype],
                    "user_name": request.session.get("user_name", "김민수")
                }
            )
        return handler
    app.add_api_route(f"/{route_name}", _make_handler(), methods=["GET"], response_class=HTMLResponse)


@app.post("/api/erp_docs")
async def create_erp_doc(
    request: Request,
    doc_type: str = Form(""),
    title: str = Form(""),
    content: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO erp_docs (user_id, doc_type, title, content, status) VALUES (?,?,?,?,?)",
        (1, doc_type, title, content, "draft"),
    )
    conn.commit()
    conn.close()
    redirect_to = ERP_REDIRECTS.get(doc_type, "/")
    return RedirectResponse(url=redirect_to, status_code=303)


# ============================================================
# 스텁 페이지들 (href="#" 연결용)
# ============================================================
STUB_PAGES = {
    "/profile": "내 프로필",
    "/notifications": "알림",
    "/accessibility": "접근성 설정",
    "/guide": "가이드 문서",
    "/faq": "자주 묻는 질문",
    "/inquiry": "1:1 문의하기",
    "/terms": "이용약관",
    "/privacy": "개인정보처리방침",
    "/updates": "업데이트 내역",
    "/calendar": "일정 관리",
    "/leave_approvals": "휴가 승인",
    "/recruitment_status": "채용 현황",
    "/outflow_list": "출금 내역",
    "/pending_payments": "미결제 내역",
    "/approval_pending": "결재 대기",
}

for _path, _title in STUB_PAGES.items():
    def _make_stub(_t=_title):
        async def _handler(request: Request):
            if not check_login(request):
                return RedirectResponse(url="/login", status_code=303)
            return templates.TemplateResponse(
                request=request, name="common/stub.html", context={
                    "request": request,
                    "page_title": _t,
                    "user_name": request.session.get("user_name", "김민수")
                }
            )
        return _handler
    app.add_api_route(_path, _make_stub(), methods=["GET"], response_class=HTMLResponse)


# 상세보기 동적 라우트들
@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>업무를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
    r = dict(row)
    return templates.TemplateResponse(
        request=request, name="common/detail.html", context={
            "request": request,
            "page_title": "업무 상세",
            "badges": [{"text": r['status'], "color": "primary"}, {"text": r['category'], "color": "secondary"}],
            "detail_title": r['title'],
            "detail_date": r['work_date'],
            "detail_content": r['details'] or '-',
            "extra_content": r['issues'] or '',
            "extra_label": "이슈/특이사항",
            "back_url": "/emp_dash",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/post/{post_id}", response_class=HTMLResponse)
async def post_detail(request: Request, post_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>게시글을 찾을 수 없습니다</h2><a href='/community'>돌아가기</a>", status_code=404)
    r = dict(row)
    return templates.TemplateResponse(
        request=request, name="common/detail.html", context={
            "request": request,
            "page_title": r['title'],
            "badges": [{"text": r['category'], "color": "info"}],
            "detail_title": r['title'],
            "detail_date": r['created_at'],
            "detail_content": r['content'],
            "author": r.get('author', ''),
            "dept": r.get('dept', ''),
            "views": r.get('views', ''),
            "comments": r.get('comments', ''),
            "likes": r.get('likes', ''),
            "extra_content": '',
            "extra_label": '',
            "back_url": "/community",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_doc/{doc_id}", response_class=HTMLResponse)
async def erp_doc_detail(request: Request, doc_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>문서를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
    r = dict(row)
    return templates.TemplateResponse(
        request=request, name="common/detail.html", context={
            "request": request,
            "page_title": r['title'],
            "badges": [{"text": r['doc_type'], "color": "primary"}, {"text": r['status'], "color": "secondary"}],
            "detail_title": r['title'],
            "detail_date": r['created_at'],
            "detail_content": r['content'],
            "extra_content": '',
            "extra_label": '',
            "back_url": "/",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/resume/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="common/stub.html", context={
            "request": request,
            "page_title": f"이력서 상세 (#{resume_id})",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/as_request/{req_id}", response_class=HTMLResponse)
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
            "request": request,
            "page_title": "AS 요청 상세",
            "badges": [{"text": r['urgency'], "color": "warning"}, {"text": r['status'], "color": "info"}],
            "detail_title": r['title'],
            "detail_date": r['created_at'],
            "detail_content": r['details'],
            "extra_content": '',
            "extra_label": '',
            "back_url": "/contact",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/api/erp_docs")
async def list_erp_docs(request: Request, doc_type: Optional[str] = None):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    if doc_type:
        rows = conn.execute("SELECT * FROM erp_docs WHERE doc_type=? ORDER BY created_at DESC", (doc_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM erp_docs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]