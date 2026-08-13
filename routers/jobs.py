import calendar as cal_mod
from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, templates

router = APIRouter()


@router.get("/job_diary", response_class=HTMLResponse)
async def job_diary(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/apps/job_diary.html", context={
            "request": request, "page_title": "업무일지",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/completed_jobs", response_class=HTMLResponse)
async def completed_jobs(request: Request, q: str = "", page: int = 1):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    per_page = 10
    params: list = [uid]
    sql = "SELECT * FROM jobs WHERE user_id=? AND status='done'"
    if q:
        sql += " AND title LIKE '%'||?||'%'"; params.append(q)
    total = conn.execute(sql.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"; params += [per_page, (page - 1) * per_page]
    done_jobs = with_status_meta(conn.execute(sql, params).fetchall())
    progress_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status!='done'", (uid,)).fetchone()[0]
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/apps/complete_job.html", context={
            "request": request, "page_title": "완료 업무",
            "user_name": request.session.get("user_name", "김민수"),
            "done_jobs": done_jobs, "done_count": total, "progress_count": progress_count,
            "q": q, "page": page, "total_pages": max(1, (total + per_page - 1) // per_page),
        }
    )


@router.get("/newarrived_jobs", response_class=HTMLResponse)
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
            "request": request, "page_title": "메시지함",
            "user_name": request.session.get("user_name", "김민수"),
            "unread_msgs": unread_msgs, "read_msgs": read_msgs,
            "unread_count": len(unread_msgs), "read_count": len(read_msgs),
        }
    )


@router.get("/new_job", response_class=HTMLResponse)
async def new_job(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/top/new_job.html", context={
            "request": request, "page_title": "새 업무 등록",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/job/{job_id}", response_class=HTMLResponse)
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
            "request": request, "page_title": "업무 상세",
            "badges": [{"text": r["status"], "color": "primary"}, {"text": r["category"], "color": "secondary"}],
            "detail_title": r["title"], "detail_date": r["work_date"],
            "detail_content": r["details"] or "-",
            "extra_content": r["issues"] or "", "extra_label": "이슈/특이사항",
            "back_url": "/emp_dash",
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    rows = conn.execute(
        "SELECT work_date, title, status FROM jobs WHERE user_id=? AND work_date LIKE '2026-08%'", (uid,)
    ).fetchall()
    conn.close()
    events = [dict(r) for r in rows]
    events_by_date: dict = {}
    for ev in events:
        d = ev["work_date"]
        events_by_date.setdefault(d, []).append(ev)
    weeks = cal_mod.monthcalendar(2026, 8)
    return templates.TemplateResponse(
        request=request, name="apps/calendar.html", context={
            "request": request, "page_title": "일정 관리",
            "user_name": request.session.get("user_name", "김민수"),
            "weeks": weeks, "events": events, "events_by_date": events_by_date,
        }
    )


# --- API ---

@router.post("/api/jobs")
async def create_job(
    request: Request,
    workDate: str = Form(""), workCategory: str = Form(""),
    workTitle: str = Form(""), workDetails: str = Form(""),
    workIssues: str = Form(""), progressStatus: str = Form("progress"),
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


@router.get("/api/jobs")
async def list_jobs(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/jobs/{job_id}/toggle")
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


@router.post("/api/messages/{msg_id}/read")
async def read_message(request: Request, msg_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/api/messages/read_all")
async def read_all_messages(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return {"ok": True}
