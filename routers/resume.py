from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates
from core.constants import TALENT_PROFILES

router = APIRouter()


@router.get("/resume", response_class=HTMLResponse)
async def resume_list(request: Request, q: str = "", region: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    sql = "SELECT * FROM job_postings WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE '%'||?||'%' OR company LIKE '%'||?||'%')"; params += [q, q]
    if region:
        sql += " AND region LIKE '%'||?||'%'"; params.append(region)
    sql += " ORDER BY id DESC"
    try:
        postings = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/resume.html", context={
            "request": request, "page_title": "채용/인재",
            "postings": postings, "q": q, "region": region,
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/resume/{resume_id}", response_class=HTMLResponse)
async def resume_detail(request: Request, resume_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM job_postings WHERE id=?", (resume_id,)).fetchone()
        already_applied = conn.execute(
            "SELECT 1 FROM job_applications WHERE job_id=? AND user_id=?", (resume_id, uid)
        ).fetchone() is not None
    finally:
        conn.close()
    if not row:
        return HTMLResponse("<h2>공고를 찾을 수 없습니다</h2><a href='/resume'>목록으로</a>", status_code=404)
    return templates.TemplateResponse(
        request=request, name="top/resume_detail.html", context={
            "request": request, "page_title": dict(row)["title"],
            "jp": dict(row), "already_applied": already_applied,
            "user_name": u["user_name"],
        }
    )


@router.get("/talent/{talent_id}", response_class=HTMLResponse)
async def talent_detail(request: Request, talent_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    profile = TALENT_PROFILES.get(talent_id)
    if not profile:
        return HTMLResponse("<h2>인재 정보를 찾을 수 없습니다</h2><a href='/resume'>목록으로</a>", status_code=404)
    return templates.TemplateResponse(
        request=request, name="top/talent_detail.html", context={
            "request": request, "page_title": f"{profile['name']} 이력서",
            "talent": profile,
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/job_apply/{job_id}", response_class=HTMLResponse)
async def job_apply_form(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        jp = conn.execute("SELECT * FROM job_postings WHERE id=?", (job_id,)).fetchone()
        user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        already = conn.execute(
            "SELECT 1 FROM job_applications WHERE job_id=? AND user_id=?", (job_id, uid)
        ).fetchone()
    finally:
        conn.close()
    if not jp:
        return HTMLResponse("<h2>공고를 찾을 수 없습니다</h2><a href='/resume'>목록으로</a>", status_code=404)
    if already:
        return RedirectResponse(url=f"/resume/{job_id}?applied=1", status_code=303)
    u = dict(user) if user else {}
    return templates.TemplateResponse(
        request=request, name="top/job_apply.html", context={
            "request": request, "page_title": "지원서 작성",
            "jp": dict(jp),
            "user_name": u.get("name", ""),
            "user_phone": u.get("phone", ""),
        }
    )


@router.post("/api/job_apply/{job_id}")
async def job_apply_submit(
    request: Request, job_id: int,
    name: str = Form(...), email: str = Form(...),
    phone: str = Form(...), cover_letter: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO job_applications (job_id, user_id, name, email, phone, cover_letter) VALUES (?,?,?,?,?,?)",
            (job_id, uid, name, email, phone, cover_letter)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    return RedirectResponse(url=f"/resume/{job_id}?applied=1", status_code=303)
