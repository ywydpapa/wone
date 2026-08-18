from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.deps import check_login, get_current_user, templates
from core.constants import FAQ_ITEMS, TERMS_ARTICLES, PRIVACY_ARTICLES, UPDATES_LIST

router = APIRouter()


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/faq.html", context={
        "request": request, "page_title": "자주 묻는 질문",
        "faq_items": FAQ_ITEMS,
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/guide.html", context={
        "request": request, "page_title": "가이드 문서",
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/inquiry", response_class=HTMLResponse)
async def inquiry_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/inquiry.html", context={
        "request": request, "page_title": "1:1 문의하기",
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/policy.html", context={
        "request": request, "page_title": "이용약관",
        "subtitle": "서비스 이용 전 반드시 읽어주세요.",
        "effective_date": "2026-01-01", "articles": TERMS_ARTICLES,
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/policy.html", context={
        "request": request, "page_title": "개인정보처리방침",
        "subtitle": "임직원 개인정보 보호에 관한 방침입니다.",
        "effective_date": "2026-01-01", "articles": PRIVACY_ARTICLES,
        "user_name": get_current_user(request)["user_name"],
    })


@router.get("/updates", response_class=HTMLResponse)
async def updates_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="info/updates.html", context={
        "request": request, "page_title": "업데이트 내역",
        "updates": UPDATES_LIST,
        "user_name": get_current_user(request)["user_name"],
    })
