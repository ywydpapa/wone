from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from core.deps import check_login, get_current_user, templates

router = APIRouter()


class VoiceInput(BaseModel):
    text: str


@router.post("/api/text")
async def receive_voice_text(data: VoiceInput):
    print(f"인식된 텍스트: {data.text}")
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
async def real_trans(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/apps/realtime_trans.html", context={
        "request": request, "page_title": "실시간 자막",
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/youtube_edit", response_class=HTMLResponse)
async def youtube_edit(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/top/youtube_edit.html", context={
        "request": request, "page_title": "유튜브 편집",
        "user_name": get_current_user(request)["user_name"],
    })
