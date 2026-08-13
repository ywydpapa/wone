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
async def resume(request: Request, q: str = "", region: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    sql = "SELECT * FROM job_postings WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE '%'||?||'%' OR company LIKE '%'||?||'%')"
        params += [q, q]
    if region:
        sql += " AND region LIKE '%'||?||'%'"
        params.append(region)
    sql += " ORDER BY id DESC"
    postings = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/resume.html", context={
            "request": request,
            "page_title": "채용/인재",
            "postings": postings,
            "q": q,
            "region": region,
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
            "request": request,
            "page_title": "AS 접수",
            "user_info": user_info,
            "my_requests": my_requests,
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

ERP_PAGE_DOCTYPE = {
    "erp_hr":         "hr_task",
    "erp_fa":         "expense",
    "erp_inventory":  "stock_move",
    "erp_product":    "work_order",
    "erp_purch":      "po",
    "erp_scrm":       "activity",
    "erp_groupware":  "draft",
}

_ERP_ROUTE_MAP = {
    "erp_hr":        ("/erp/erp_hr.html",         "인사관리 대시보드"),
    "erp_fa":        ("/erp/erp_fa.html",          "자금관리 대시보드"),
    "erp_inventory": ("/erp/erp_inventory.html",   "재고관리 대시보드"),
    "erp_product":   ("/erp/erp_product.html",     "생산관리 대시보드"),
    "erp_purch":     ("/erp/erp_purch.html",       "구매관리 대시보드"),
    "erp_scrm":      ("/erp/erp_scrm.html",        "영업/고객관리 대시보드"),
    "erp_groupware": ("/erp/erp_groupware.html",   "사내 그룹웨어"),
}


def _erp_docs_for(dtype: str):
    conn = get_sqlite()
    rows = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type=? ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 WHEN 'wait' THEN 2 ELSE 3 END, id DESC",
        (dtype,)
    ).fetchall())
    conn.close()
    return rows


@app.get("/erp_dash", response_class=HTMLResponse)
async def erp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    counts = {r["doc_type"]: r["cnt"] for r in [
        dict(r) for r in conn.execute(
            "SELECT doc_type, COUNT(*) AS cnt FROM erp_docs GROUP BY doc_type"
        ).fetchall()
    ]}
    recent = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs ORDER BY id DESC LIMIT 5"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/erp/erp_dash.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "doc_counts": counts,
            "recent_docs": recent,
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_hr", response_class=HTMLResponse)
async def erp_hr(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_hr.html", context={
            "request": request, "page_title": "인사관리 대시보드",
            "docs": _erp_docs_for("hr_task"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_fa", response_class=HTMLResponse)
async def erp_fa(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_fa.html", context={
            "request": request, "page_title": "자금관리 대시보드",
            "docs": _erp_docs_for("expense"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_scrm", response_class=HTMLResponse)
async def erp_scrm(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_scrm.html", context={
            "request": request, "page_title": "영업/고객관리 대시보드",
            "docs": _erp_docs_for("activity"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_purch", response_class=HTMLResponse)
async def erp_purch(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_purch.html", context={
            "request": request, "page_title": "구매관리 대시보드",
            "docs": _erp_docs_for("po"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_inventory", response_class=HTMLResponse)
async def erp_invent(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_inventory.html", context={
            "request": request, "page_title": "재고관리 대시보드",
            "docs": _erp_docs_for("stock_move"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_product", response_class=HTMLResponse)
async def erp_product(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_product.html", context={
            "request": request, "page_title": "생산관리 대시보드",
            "docs": _erp_docs_for("work_order"),
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.get("/erp_groupware", response_class=HTMLResponse)
async def erp_groupware(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/erp/erp_groupware.html", context={
            "request": request, "page_title": "사내 그룹웨어",
            "docs": _erp_docs_for("draft"),
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
        (request.session.get("user_id", 1), workDate, workCategory, workTitle, workDetails, workIssues, progressStatus),
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
        (request.session.get("user_id", 1), asCategory, asUrgency, asTitle, asDetails, attachment_name, "pending"),
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
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
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
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT p.* FROM posts p JOIN bookmarks b ON b.post_id=p.id AND b.user_id=? ORDER BY p.created_at DESC",
        (uid,)
    ).fetchall()
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
    "expense": "/erp_fa",
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
        (request.session.get("user_id", 1), doc_type, title, content, "wait"),
    )
    conn.commit()
    conn.close()
    redirect_to = ERP_REDIRECTS.get(doc_type, "/")
    return RedirectResponse(url=redirect_to, status_code=303)


@app.get("/profile", response_class=HTMLResponse)
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
            "user": user,
            "my_post_count": my_post_count,
            "my_comment_count": my_comment_count,
            "my_done_count": my_done_count,
            "success": success,
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/profile")
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


@app.get("/notifications", response_class=HTMLResponse)
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
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/notifications/read_all")
async def notifications_read_all(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/accessibility", response_class=HTMLResponse)
async def accessibility_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="top/accessibility.html", context={
            "request": request, "page_title": "접근성 설정",
            "user_name": request.session.get("user_name", "김민수")
        }
    )


# ============================================================
# 정보성 페이지 (Task 11)
# ============================================================
FAQ_ITEMS = [
    {"q": "로그인이 안됩니다.", "a": "아이디와 비밀번호를 다시 확인해 주세요. 비밀번호를 잊으셨다면 시스템 관리자(내선 119)에게 초기화를 요청하세요."},
    {"q": "업무일지는 어떻게 등록하나요?", "a": "상단 메뉴 > 업무관리 > 새 업무 등록을 클릭하면 업무일지 작성 폼이 열립니다. 분류, 제목, 내용을 입력 후 저장하면 대시보드에 바로 반영됩니다."},
    {"q": "AS 접수는 어디서 하나요?", "a": "상단 메뉴 > 고객지원 > AS 접수에서 신청할 수 있습니다. 접수 후 나의 AS 내역에서 처리 상태를 확인하세요."},
    {"q": "접근성 도구는 어떻게 사용하나요?", "a": "상단 메뉴 > 접근성 설정에서 글자 크기(보통/크게/아주 크게)와 고대비 모드를 설정할 수 있습니다. 설정은 브라우저에 저장되어 유지됩니다."},
    {"q": "수어통역 지원을 신청하려면?", "a": "AS 접수 메뉴에서 분류를 '접근성 지원 요청'으로 선택하고 수어통역 필요 상황을 상세히 기재해 주세요. 영업일 기준 1일 이내 담당자가 연락드립니다."},
    {"q": "급여명세서는 어디서 확인하나요?", "a": "ERP > 자금관리 메뉴에서 월별 급여 명세서를 확인할 수 있습니다. 열람 권한이 없는 경우 경영지원팀에 문의하세요."},
    {"q": "연차 신청은 어떻게 하나요?", "a": "ERP > 인사관리 메뉴에서 휴가 신청서를 작성해 상신합니다. 직속 상관이 결재하면 연차가 차감됩니다."},
    {"q": "비밀번호를 변경하고 싶어요.", "a": "현재 비밀번호 변경은 시스템 관리자(내선 119)를 통해서만 가능합니다. 본인 확인 후 초기화해 드립니다."},
]

TERMS_ARTICLES = [
    {"title": "서비스 이용 목적", "body": "본 시스템은 임직원 업무 효율화를 위해 제공됩니다. 업무 외 목적으로 사용하거나 허가받지 않은 제3자에게 접근 권한을 제공하는 행위는 금지됩니다."},
    {"title": "계정 관리 책임", "body": "임직원은 본인 계정의 아이디와 비밀번호를 안전하게 관리할 책임이 있습니다. 계정 공유 및 양도는 금지되며, 도용 의심 시 즉시 관리자에게 신고해야 합니다."},
    {"title": "금지 행위", "body": "시스템 및 데이터의 무단 복사, 배포, 변조 행위는 금지됩니다. 타 직원을 비방하거나 허위 정보를 유포하는 행위도 사규에 따라 징계 대상이 될 수 있습니다."},
    {"title": "서비스 제공 및 중단", "body": "회사는 시스템 점검, 긴급 상황 등의 사유로 사전 고지 없이 서비스를 일시 중단할 수 있습니다. 정기 점검은 매주 토요일 새벽 2~4시에 진행됩니다."},
    {"title": "면책 조항", "body": "사용자 귀책 사유로 인한 데이터 손실, 계정 도용 피해에 대해 회사는 책임을 지지 않습니다. 시스템 오류로 인한 피해는 IT지원팀을 통해 접수해 주세요."},
    {"title": "약관 변경", "body": "본 약관은 회사 사정에 따라 변경될 수 있으며, 변경 시 사내 공지 및 시스템 팝업으로 안내합니다."},
]

PRIVACY_ARTICLES = [
    {"title": "수집 항목", "body": "로그인 아이디, 이름, 부서, 직급, 연락처, 업무 활동 로그(게시글, 댓글, ERP 처리 내역 등)를 수집합니다."},
    {"title": "수집 목적", "body": "업무 시스템 운영, 본인 확인, 서비스 이용 통계 분석을 목적으로 개인정보를 활용합니다."},
    {"title": "보유 및 이용 기간", "body": "재직 기간 동안 보관하며, 퇴직 후 관련 법령이 정하는 기간(최대 5년)이 경과한 후 파기합니다."},
    {"title": "제3자 제공", "body": "법령에 정해진 경우를 제외하고 임직원 개인정보를 외부에 제공하지 않습니다."},
    {"title": "개인정보 보호 책임자", "body": "개인정보 관련 문의는 경영지원팀 개인정보 보호 담당자(내선 119)에게 연락해 주세요."},
]

UPDATES_LIST = [
    {
        "version": "v2.3.0",
        "date": "2026-08-13",
        "title": "전체 샘플 기능 구현 및 스텁 페이지 제거",
        "changes": [
            "프로필, 알림, 접근성 설정 페이지 실데이터 전환",
            "FAQ, 가이드, 1:1문의, 이용약관, 개인정보처리방침, 업데이트 내역 콘텐츠 추가",
            "일정관리(캘린더), 휴가승인, 채용현황, 출금/미결제 내역, 결재대기 페이지 구현",
            "준비 중 스텁 페이지 시스템 완전 제거",
        ],
    },
    {
        "version": "v2.2.0",
        "date": "2026-08-12",
        "title": "ERP 결재/채용/AS 연동 완료",
        "changes": [
            "ERP 7개 모듈 DB 연동 및 문서 승인/반려 결재 기능",
            "채용 공고 목록/상세 DB 연동 (장애인 친화 채용 정보 포함)",
            "AS 접수 내역 세션 유저 기준 조회",
            "게시글 상세: 조회수·댓글·좋아요·스크랩 DB 연동",
        ],
    },
    {
        "version": "v2.1.0",
        "date": "2026-08-11",
        "title": "로그인/회원가입 DB 연동 및 커뮤니티 기능",
        "changes": [
            "로그인 DB 검증, 회원가입, topbar 개인화",
            "커뮤니티 목록 필터/검색/페이지네이션 구현",
            "업무 대시보드 체크박스 완료 토글, 메시지 읽음 처리",
            "SQLite 스키마 전면 개편 및 샘플 데이터 시드",
        ],
    },
]


@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/faq.html", context={
            "request": request, "page_title": "자주 묻는 질문",
            "faq_items": FAQ_ITEMS,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/guide.html", context={
            "request": request, "page_title": "가이드 문서",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@app.get("/inquiry", response_class=HTMLResponse)
async def inquiry_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/inquiry.html", context={
            "request": request, "page_title": "1:1 문의하기",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/policy.html", context={
            "request": request, "page_title": "이용약관",
            "subtitle": "서비스 이용 전 반드시 읽어주세요.",
            "effective_date": "2026-01-01",
            "articles": TERMS_ARTICLES,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/policy.html", context={
            "request": request, "page_title": "개인정보처리방침",
            "subtitle": "임직원 개인정보 보호에 관한 방침입니다.",
            "effective_date": "2026-01-01",
            "articles": PRIVACY_ARTICLES,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@app.get("/updates", response_class=HTMLResponse)
async def updates_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="info/updates.html", context={
            "request": request, "page_title": "업데이트 내역",
            "updates": UPDATES_LIST,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


# ============================================================
# 업무성 페이지 (Task 12)
# ============================================================

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT work_date, title, status FROM jobs WHERE user_id=? AND work_date LIKE '2026-08%'",
        (uid,)
    ).fetchall()
    conn.close()
    events = [dict(r) for r in rows]
    events_by_date = {}
    for ev in events:
        d = ev["work_date"]
        if d not in events_by_date:
            events_by_date[d] = []
        events_by_date[d].append(ev)
    # Build weekly grid for August 2026 (starts Saturday=6, so offset=6)
    import calendar as cal_mod
    weeks = cal_mod.monthcalendar(2026, 8)
    return templates.TemplateResponse(
        request=request, name="apps/calendar.html", context={
            "request": request, "page_title": "일정 관리",
            "user_name": request.session.get("user_name", "김민수"),
            "weeks": weeks,
            "events": events,
            "events_by_date": events_by_date,
        }
    )


@app.get("/leave_approvals", response_class=HTMLResponse)
async def leave_approvals_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='hr_task' AND title LIKE '%휴가%' ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="erp/leave_approvals.html", context={
            "request": request, "page_title": "휴가 승인",
            "user_name": request.session.get("user_name", "김민수"),
            "docs": docs,
        }
    )


@app.get("/recruitment_status", response_class=HTMLResponse)
async def recruitment_status_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    postings = [dict(r) for r in conn.execute("SELECT * FROM job_postings ORDER BY id DESC").fetchall()]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="erp/recruitment_status.html", context={
            "request": request, "page_title": "채용 현황",
            "user_name": request.session.get("user_name", "김민수"),
            "postings": postings,
        }
    )


@app.get("/outflow_list", response_class=HTMLResponse)
async def outflow_list_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('done','approved') ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="erp/fa_list.html", context={
            "request": request, "page_title": "출금 완료 내역",
            "subtitle": "처리 완료된 지출 내역입니다.",
            "user_name": request.session.get("user_name", "김민수"),
            "docs": docs,
        }
    )


@app.get("/pending_payments", response_class=HTMLResponse)
async def pending_payments_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('wait','pending','urgent') ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="erp/fa_list.html", context={
            "request": request, "page_title": "미결제 내역",
            "subtitle": "처리 대기 중인 지출 요청입니다.",
            "user_name": request.session.get("user_name", "김민수"),
            "docs": docs,
        }
    )


@app.get("/approval_pending", response_class=HTMLResponse)
async def approval_pending_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE status IN ('wait','pending','urgent') ORDER BY CASE status WHEN 'urgent' THEN 0 ELSE 1 END, id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="erp/approval_pending.html", context={
            "request": request, "page_title": "결재 대기",
            "user_name": request.session.get("user_name", "김민수"),
            "docs": docs,
        }
    )


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
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE posts SET views=views+1 WHERE id=?", (post_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    if not row:
        conn.close()
        return HTMLResponse("<h2>게시글을 찾을 수 없습니다</h2><a href='/community'>돌아가기</a>", status_code=404)
    comments = [dict(c) for c in conn.execute(
        "SELECT * FROM comments WHERE post_id=? ORDER BY id ASC", (post_id,)).fetchall()]
    like_count = conn.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (post_id,)).fetchone()[0]
    liked = conn.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (post_id, uid)).fetchone() is not None
    bookmarked = conn.execute("SELECT 1 FROM bookmarks WHERE post_id=? AND user_id=?", (post_id, uid)).fetchone() is not None
    conn.close()
    return templates.TemplateResponse(
        request=request, name="top/post_detail.html", context={
            "request": request,
            "page_title": dict(row)['title'],
            "post": dict(row),
            "comments": comments,
            "like_count": like_count,
            "liked": liked,
            "bookmarked": bookmarked,
            "categories": POST_CATEGORIES,
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/posts/{post_id}/comments")
async def add_comment(request: Request, post_id: int, content: str = Form(...)):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    author = request.session.get("user_name", "익명")
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO comments (post_id, user_id, author, content) VALUES (?, ?, ?, ?)",
        (post_id, uid, author, content)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


@app.post("/api/posts/{post_id}/like")
async def toggle_like(request: Request, post_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    existing = conn.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (post_id, uid)).fetchone()
    if existing:
        conn.execute("DELETE FROM post_likes WHERE post_id=? AND user_id=?", (post_id, uid))
        liked = False
    else:
        conn.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, uid))
        liked = True
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (post_id,)).fetchone()[0]
    conn.close()
    return {"liked": liked, "count": count}


@app.post("/api/posts/{post_id}/bookmark")
async def toggle_bookmark(request: Request, post_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    existing = conn.execute("SELECT 1 FROM bookmarks WHERE post_id=? AND user_id=?", (post_id, uid)).fetchone()
    if existing:
        conn.execute("DELETE FROM bookmarks WHERE post_id=? AND user_id=?", (post_id, uid))
        bookmarked = False
    else:
        conn.execute("INSERT INTO bookmarks (post_id, user_id) VALUES (?, ?)", (post_id, uid))
        bookmarked = True
    conn.commit()
    conn.close()
    return {"bookmarked": bookmarked}


ERP_DOC_TYPE_LABELS = {
    "draft":      "결재 기안",
    "hr_task":    "HR 업무",
    "stock_move": "입출고",
    "work_order": "작업 지시",
    "po":         "구매 발주",
    "activity":   "영업 활동",
    "expense":    "자금관리",
}


@app.get("/erp_doc/{doc_id}", response_class=HTMLResponse)
async def erp_doc_detail(request: Request, doc_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>문서를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
    doc = with_status_meta([row])[0]
    doc["doc_type_label"] = ERP_DOC_TYPE_LABELS.get(doc["doc_type"], doc["doc_type"])
    back_url = ERP_REDIRECTS.get(doc["doc_type"], "/erp_dash")
    return templates.TemplateResponse(
        request=request, name="erp/erp_doc_detail.html", context={
            "request": request,
            "page_title": doc['title'],
            "doc": doc,
            "back_url": back_url,
            "user_name": request.session.get("user_name", "김민수")
        }
    )


@app.post("/api/erp_docs/{doc_id}/status")
async def update_erp_doc_status(request: Request, doc_id: int, status: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    if status not in ("approved", "rejected", "done"):
        return JSONResponse({"error": "invalid status"}, status_code=400)
    conn = get_sqlite()
    row = conn.execute("SELECT doc_type FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    if row:
        conn.execute("UPDATE erp_docs SET status=? WHERE id=?", (status, doc_id))
        conn.commit()
    conn.close()
    back = ERP_REDIRECTS.get(row["doc_type"], "/erp_dash") if row else "/erp_dash"
    return RedirectResponse(url=back, status_code=303)


@app.get("/resume/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM job_postings WHERE id=?", (resume_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>공고를 찾을 수 없습니다</h2><a href='/resume'>목록으로</a>", status_code=404)
    return templates.TemplateResponse(
        request=request, name="top/resume_detail.html", context={
            "request": request,
            "page_title": dict(row)["title"],
            "jp": dict(row),
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