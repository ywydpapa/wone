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
    Body,File, UploadFile
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
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s != "" else None

def _clean_int(value: object) -> int | None:
    s = _clean_str(value)
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"Invalid integer input: {s!r}")

def to_int(s, default=0):
    try:
        return int(s)
    except Exception:
        return default


@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="/top/index.html", context={
            "request": request,
            "page_title": "업무 대시보드",
            "user_name": "관리자"
        }
    )