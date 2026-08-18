import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import dotenv

from core.db import run_migrations
from routers import auth, dashboard, jobs, community, erp, resume, contact, profile, info, apps

dotenv.load_dotenv()


def _ensure_db():
    """신규 클론 등 users 테이블이 없으면 init_db로 자동 초기화."""
    from core.db import get_sqlite
    conn = get_sqlite()
    try:
        conn.execute("SELECT 1 FROM users LIMIT 1")
    except Exception:
        conn.close()
        from init_db import init
        init()
        return
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_db()
    run_migrations()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "wone-sample-dev-key-change-in-production"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "https://www.wno1.kr"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 신규 클론에는 static/이 없을 수 있음(업로드 파일은 git 미추적) — 기동 전 보장
os.makedirs("static/uploads/erp", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(jobs.router)
app.include_router(community.router)
app.include_router(erp.router)
app.include_router(resume.router)
app.include_router(contact.router)
app.include_router(profile.router)
app.include_router(info.router)
app.include_router(apps.router)
