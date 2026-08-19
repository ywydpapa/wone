import json
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import check_login, get_current_user, templates

router = APIRouter()


@router.get("/resume", response_class=HTMLResponse)
async def resume_list(request: Request, q: str = "", region: str = "", work_area: str = "", disability_type: str = ""):
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
    talents_sql = "SELECT * FROM talent_profiles WHERE 1=1"
    talent_params = []
    if work_area:
        talents_sql += " AND category LIKE '%'||?||'%'"; talent_params.append(work_area)
    if disability_type:
        talents_sql += " AND disability_type = ?"; talent_params.append(disability_type)
    if q:
        talents_sql += " AND (name LIKE '%'||?||'%' OR summary LIKE '%'||?||'%')"; talent_params += [q, q]
    talents_sql += " ORDER BY id DESC"
    try:
        postings = [dict(r) for r in conn.execute(sql, params).fetchall()]
        talents = [dict(r) for r in conn.execute(talents_sql, talent_params).fetchall()]
    finally:
        conn.close()
    for t in talents:
        t['skills'] = json.loads(t['skills']) if t.get('skills') else []
        t['experience'] = json.loads(t['experience']) if t.get('experience') else []
    return templates.TemplateResponse(
        request=request, name="/top/resume.html", context={
            "request": request, "page_title": "채용/인재",
            "postings": postings, "q": q, "region": region,
            "talents": talents, "work_area": work_area,
            "disability_type": disability_type,
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
async def talent_detail(request: Request, talent_id: int, offered: int = 0):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM talent_profiles WHERE id=?", (talent_id,)).fetchone()
        already_offered = conn.execute(
            "SELECT 1 FROM talent_offers WHERE talent_id=? AND sender_id=?", (talent_id, uid)
        ).fetchone() is not None
    finally:
        conn.close()
    if not row:
        return HTMLResponse("<h2>인재 정보를 찾을 수 없습니다</h2><a href='/resume'>목록으로</a>", status_code=404)
    profile = dict(row)
    profile['skills'] = json.loads(profile['skills']) if profile.get('skills') else []
    profile['experience'] = json.loads(profile['experience']) if profile.get('experience') else []
    return templates.TemplateResponse(
        request=request, name="top/talent_detail.html", context={
            "request": request, "page_title": f"{profile['name']} 이력서",
            "talent": profile,
            "user_name": u["user_name"],
            "offered": bool(offered) or already_offered,
        }
    )


@router.post("/api/talent_offer/{talent_id}")
async def talent_offer_submit(
    request: Request, talent_id: int,
    title: str = Form(...), message: str = Form(...), contact: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    sender_name = u.get("user_name", "")
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO talent_offers (talent_id, sender_id, sender_name, title, message, contact) VALUES (?,?,?,?,?,?)",
            (talent_id, uid, sender_name, title, message, contact)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
    return RedirectResponse(url=f"/talent/{talent_id}?offered=1", status_code=303)


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
