import calendar as cal_mod
from typing import Optional
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, get_current_user, templates

router = APIRouter()


@router.get("/job_diary", response_class=HTMLResponse)
async def job_diary(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/apps/job_diary.html", context={
            "request": request, "page_title": "업무일지",
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/completed_jobs", response_class=HTMLResponse)
async def completed_jobs(request: Request, q: str = "", page: int = 1):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    per_page = 10
    count_params: list = [uid]
    count_sql = "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'"
    params: list = [uid]
    sql = "SELECT * FROM jobs WHERE user_id=? AND status='done'"
    if q:
        sql += " AND title LIKE '%'||?||'%'"; params.append(q)
        count_sql += " AND title LIKE '%'||?||'%'"; count_params.append(q)
    try:
        total = conn.execute(count_sql, count_params).fetchone()[0]
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"; params += [per_page, (page - 1) * per_page]
        done_jobs = with_status_meta(conn.execute(sql, params).fetchall())
        progress_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status!='done'", (uid,)).fetchone()[0]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/apps/complete_job.html", context={
            "request": request, "page_title": "완료 업무",
            "user_name": u["user_name"],
            "done_jobs": done_jobs, "done_count": total, "progress_count": progress_count,
            "q": q, "page": page, "total_pages": max(1, (total + per_page - 1) // per_page),
        }
    )


@router.get("/newarrived_jobs", response_class=HTMLResponse)
async def newarrived_jobs(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        unread_msgs = [dict(m) for m in conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND direction='in' AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()]
        read_msgs = [dict(m) for m in conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND direction='in' AND is_read=1 ORDER BY id DESC", (uid,)).fetchall()]
        sent_msgs = [dict(m) for m in conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND direction='out' ORDER BY id DESC", (uid,)).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/apps/new_arrived_job.html", context={
            "request": request, "page_title": "메시지함",
            "user_name": u["user_name"],
            "unread_msgs": unread_msgs, "read_msgs": read_msgs, "sent_msgs": sent_msgs,
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
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return HTMLResponse("<h2>업무를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
    job = with_status_meta([row])[0]
    return templates.TemplateResponse(
        request=request, name="apps/job_detail.html", context={
            "request": request, "page_title": "업무 상세",
            "job": job,
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/job/{job_id}/edit", response_class=HTMLResponse)
async def job_edit(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        owner = conn.execute("SELECT user_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not owner or owner["user_id"] != uid:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return HTMLResponse("<h2>업무를 찾을 수 없습니다</h2><a href='/emp_dash'>돌아가기</a>", status_code=404)
    return templates.TemplateResponse(
        request=request, name="apps/job_edit.html", context={
            "request": request, "page_title": "업무 수정",
            "job": dict(row),
            "user_name": u["user_name"],
        }
    )


@router.post("/api/jobs/{job_id}")
async def update_job(
    request: Request, job_id: int,
    workDate: str = Form(""), workCategory: str = Form(""),
    workTitle: str = Form(""), workDetails: str = Form(""),
    workIssues: str = Form(""), progressStatus: str = Form("progress"),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        owner = conn.execute("SELECT user_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not owner or owner["user_id"] != uid:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        conn.execute(
            "UPDATE jobs SET work_date=?, category=?, title=?, details=?, issues=?, status=? WHERE id=?",
            (workDate, workCategory, workTitle, workDetails, workIssues, progressStatus, job_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/job/{job_id}", status_code=303)


@router.post("/api/jobs/{job_id}/delete")
async def delete_job(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        owner = conn.execute("SELECT user_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not owner or owner["user_id"] != uid:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        conn.execute("UPDATE jobs SET status='trash' WHERE id=?", (job_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/emp_dash", status_code=303)


@router.post("/api/jobs/{job_id}/restore")
async def restore_job(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        owner = conn.execute("SELECT user_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not owner or owner["user_id"] != uid:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        conn.execute("UPDATE jobs SET status='progress' WHERE id=? AND status='trash'", (job_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/trash", status_code=303)


@router.post("/api/jobs/{job_id}/permanent_delete")
async def permanent_delete_job(request: Request, job_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        owner = conn.execute("SELECT user_id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not owner or owner["user_id"] != uid:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        conn.execute("DELETE FROM jobs WHERE id=? AND status='trash'", (job_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/trash", status_code=303)


@router.get("/trash", response_class=HTMLResponse)
async def trash_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id=? AND status='trash' ORDER BY id DESC", (uid,)
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="apps/trash.html", context={
            "request": request, "page_title": "휴지통",
            "user_name": u["user_name"],
            "trashed_jobs": [dict(r) for r in rows],
        }
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    from datetime import date
    u = get_current_user(request)
    uid = u["user_id"]
    today = date.today()
    year, month = today.year, today.month
    month_prefix = f"{year}-{month:02d}"
    conn = get_sqlite()
    try:
        rows = conn.execute(
            "SELECT id, work_date, title, status FROM jobs WHERE user_id=? AND work_date LIKE ?",
            (uid, f"{month_prefix}%")
        ).fetchall()
    finally:
        conn.close()
    events = [dict(r) for r in rows]
    events_by_date: dict = {}
    for ev in events:
        events_by_date.setdefault(ev["work_date"], []).append(ev)
    weeks = cal_mod.monthcalendar(year, month)
    return templates.TemplateResponse(
        request=request, name="apps/calendar.html", context={
            "request": request, "page_title": "일정 관리",
            "user_name": u["user_name"],
            "weeks": weeks, "events": events, "events_by_date": events_by_date,
            "year": year, "month": month, "month_prefix": month_prefix,
            "today_str": today.isoformat(),
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
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO jobs (user_id, work_date, category, title, details, issues, status) VALUES (?,?,?,?,?,?,?)",
            (uid, workDate, workCategory, workTitle, workDetails, workIssues, progressStatus),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/emp_dash", status_code=303)


@router.get("/api/jobs")
async def list_jobs(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/api/jobs/{job_id}/toggle")
async def toggle_job(request: Request, job_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return JSONResponse({"error": "not found"}, status_code=404)
        new_status = "progress" if row["status"] == "done" else "done"
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
        conn.commit()
    finally:
        conn.close()
    return {"status": new_status}


@router.get("/message/{msg_id}", response_class=HTMLResponse)
async def message_detail(request: Request, msg_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT * FROM messages WHERE id=? AND user_id=?", (msg_id, uid)).fetchone()
        if not row:
            return HTMLResponse("<h2>메시지를 찾을 수 없습니다</h2><a href='/newarrived_jobs'>돌아가기</a>", status_code=404)
        conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
        conn.commit()
    finally:
        conn.close()
    return templates.TemplateResponse(request=request, name="apps/message_detail.html", context={
        "request": request, "page_title": "메시지 상세",
        "user_name": u["user_name"],
        "msg": dict(row),
    })


@router.post("/api/messages/{msg_id}/reply")
async def reply_message(request: Request, msg_id: int, body: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        row = conn.execute("SELECT sender FROM messages WHERE id=? AND user_id=?", (msg_id, uid)).fetchone()
        if row:
            recipient = row["sender"]
            conn.execute(
                "INSERT INTO messages (user_id, sender, recipient, body, time_label, is_read, direction) VALUES (?,?,?,?,datetime('now','localtime'),1,'out')",
                (uid, u["user_name"], recipient, body),
            )
            conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/newarrived_jobs", status_code=303)


@router.post("/api/messages/{msg_id}/read")
async def read_message(request: Request, msg_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/report_export", response_class=HTMLResponse)
async def report_export(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/completed_jobs", status_code=303)


@router.get("/api/dept/members")
async def dept_members(request: Request, dept: str):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    try:
        rows = conn.execute(
            "SELECT name, position FROM users WHERE dept=? ORDER BY id", (dept,)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/api/messages/thread")
async def message_thread(request: Request, with_name: str):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        rows = conn.execute(
            """SELECT sender, recipient, body, time_label, direction FROM messages
               WHERE user_id=? AND (
                   (direction='out' AND recipient=?) OR
                   (direction='in'  AND sender=?)
               )
               ORDER BY id DESC LIMIT 20""",
            (uid, with_name, with_name)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in reversed(rows)]


@router.post("/api/messages/send")
async def send_message(request: Request, to_name: str = Form(...), body: str = Form(...)):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    u = get_current_user(request)
    uid = u["user_id"]
    if not body.strip():
        return JSONResponse({"error": "내용을 입력해 주세요."}, status_code=400)
    conn = get_sqlite()
    try:
        # 수신자 user_id 조회
        recipient_row = conn.execute("SELECT id FROM users WHERE name=?", (to_name,)).fetchone()
        # 발신자 발신함 기록
        conn.execute(
            "INSERT INTO messages (user_id, sender, recipient, body, time_label, is_read, direction) VALUES (?,?,?,?,datetime('now','localtime'),1,'out')",
            (uid, u["user_name"], to_name, body.strip())
        )
        # 수신자 수신함 기록
        if recipient_row:
            conn.execute(
                "INSERT INTO messages (user_id, sender, recipient, body, time_label, is_read, direction) VALUES (?,?,?,?,datetime('now','localtime'),0,'in')",
                (recipient_row["id"], u["user_name"], to_name, body.strip())
            )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.post("/api/messages/read_all")
async def read_all_messages(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = get_current_user(request)["user_id"]
    conn = get_sqlite()
    try:
        conn.execute("UPDATE messages SET is_read=1 WHERE user_id=?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
