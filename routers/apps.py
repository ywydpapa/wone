from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from core.deps import check_login, get_current_user, templates
from core.db import get_sqlite

router = APIRouter()


class VoiceInput(BaseModel):
    text: str


@router.post("/api/text")
async def receive_voice_text(request: Request, data: VoiceInput):
    if not check_login(request):
        return {"error": "not logged in"}
    return {"status": "success", "received_text": data.text}


@router.get("/voice", response_class=HTMLResponse)
async def voice(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/top/voice.html", context={
        "request": request, "page_title": "음성 지원",
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/eyemouse", response_class=HTMLResponse)
async def eyemouse(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/apps/eyemouse.html", context={
        "request": request, "page_title": "아이 마우스",
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/real_trans", response_class=HTMLResponse)
async def real_trans(request: Request, requested: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/apps/realtime_trans.html", context={
        "request": request, "page_title": "실시간 자막",
        "user_name": get_current_user(request)["user_name"],
        "requested": requested == "1",
    })


@router.post("/api/trans_request")
async def trans_request(
    request: Request,
    translator_name: str = Form(...),
    service_type: str = Form(""),
    request_date: str = Form(""),
    request_time: str = Form(""),
    duration: str = Form(""),
    meeting_link: str = Form(""),
    details: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = get_current_user(request)
    user_id = user["user_id"]
    conn = get_sqlite()
    try:
        conn.execute(
            """INSERT INTO trans_requests
               (user_id, translator_name, service_type, request_date, request_time, duration, meeting_link, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, translator_name, service_type, request_date, request_time, duration, meeting_link, details),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/real_trans?requested=1", status_code=303)


@router.get("/youtube_edit", response_class=HTMLResponse)
async def youtube_edit(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/top/youtube_edit.html", context={
        "request": request, "page_title": "유튜브 편집",
        "user_name": get_current_user(request)["user_name"],
    })
