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
from typing import Optional
import shutil
import uvicorn

dotenv.load_dotenv()
DATABASE_URL = os.getenv("dburl")
if not DATABASE_URL:
    raise RuntimeError("환경변수 dburl 이 설정되어 있지 않습니다.")

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=1800,
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "supersecretkey"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            "user_name": request.session.get("username", "관리자")
        }
    )


@app.get("/resume", response_class=HTMLResponse)
async def resume(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/resume.html", context={
            "request": request,
            "page_title": "채용/인재",
            "user_name": request.session.get("username", "관리자")
        }
    )


@app.get("/emp_dash", response_class=HTMLResponse)
async def emp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/emp_dash.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
        }
    )


@app.get("/completed_jobs", response_class=HTMLResponse)
async def cedjob(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/apps/complete_job.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("username", "관리자")
        }
    )


@app.get("/newarrived_jobs", response_class=HTMLResponse)
async def newarrived_jobs(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/apps/new_arrived_job.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
        }
    )

@app.get("/community", response_class=HTMLResponse)
async def communi(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/top/community.html", context={
            "request": request,
            "page_title": "관리자 대시보드",
            "user_name": request.session.get("username", "관리자")
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
            "user_name": request.session.get("username", "관리자")
        }
    )


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    # 이미 로그인된 상태라면 메인 페이지(/)로 리다이렉트
    if check_login(request):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request, name="/login/login.html", context={
            "request": request,
            "page_title": "로그인",
        }
    )


@app.post("/login_check")
async def login_check(request: Request, username: str = Form(...), password: str = Form(...)):
    # TODO: 실제 DB를 조회하여 username과 password가 맞는지 검증하는 로직 추가 필요
    # 여기서는 임시로 값이 들어오기만 하면 로그인 성공으로 간주합니다.
    if username and password:
        # 세션에 로그인 상태 저장
        request.session["logined"] = True
        request.session["username"] = username

        # 로그인 성공 시 메인 페이지로 리다이렉트
        return RedirectResponse(url="/", status_code=303)
    else:
        # 실패 시 다시 로그인 페이지로
        return RedirectResponse(url="/login", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    # 세션 데이터 전체 삭제 (로그아웃)
    request.session.clear()
    # 로그아웃 후 로그인 페이지로 리다이렉트
    return RedirectResponse(url="/login", status_code=303)
