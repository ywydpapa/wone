from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, get_current_user, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request, name="/top/index.html", context={
            "request": request, "page_title": "업무 대시보드",
            "user_name": get_current_user(request)["user_name"],
        }
    )


@router.get("/emp_dash", response_class=HTMLResponse)
async def emp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    uid = u["user_id"]
    conn = get_sqlite()
    try:
        todos = with_status_meta(conn.execute(
            "SELECT * FROM jobs WHERE user_id=? AND status NOT IN ('done','trash') ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id",
            (uid,)).fetchall())
        done_recent = with_status_meta(conn.execute(
            "SELECT * FROM jobs WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 1", (uid,)).fetchall())
        done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
        unread_msgs = conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/emp_dash.html", context={
            "request": request, "page_title": "업무 대시보드",
            "user_name": u["user_name"],
            "todos": todos, "done_recent": done_recent, "done_count": done_count,
            "progress_count": len(todos),
            "messages": [dict(m) for m in unread_msgs],
            "unread_count": len(unread_msgs),
        }
    )


@router.get("/manage_dash", response_class=HTMLResponse)
async def manage_dash(request: Request, q: str = "", status_filter: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    conn = get_sqlite()
    try:
        worker_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        progress_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status NOT IN ('done','trash')"
        ).fetchone()[0]
        review_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='done'"
        ).fetchone()[0]
        pending_as_count = conn.execute(
            "SELECT COUNT(*) FROM as_requests WHERE status IN ('pending','in_progress')"
        ).fetchone()[0]
        urgent_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='urgent'"
        ).fetchone()[0]
        week_done_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='done' AND work_date >= date('now','-7 days')"
        ).fetchone()[0]

        dept_stats_raw = conn.execute(
            """SELECT dept,
                      COUNT(*) as cnt,
                      SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done_cnt
               FROM jobs
               GROUP BY dept
               ORDER BY cnt DESC"""
        ).fetchall()
        dept_stats = []
        for row in dept_stats_raw:
            total = row[1]
            done = row[2] or 0
            in_progress = total - done
            rate = round(done / total * 100) if total > 0 else 0
            dept_stats.append({
                "dept": row[0],
                "total": total,
                "in_progress": in_progress,
                "done": done,
                "rate": rate,
            })

        sql = """SELECT j.*, u.name AS worker_name, u.dept AS worker_dept
                 FROM jobs j JOIN users u ON u.id=j.user_id
                 WHERE j.status NOT IN ('done','trash')"""
        params: list = []
        if q:
            sql += " AND (j.title LIKE '%'||?||'%' OR u.name LIKE '%'||?||'%')"
            params += [q, q]
        if status_filter:
            sql += " AND j.status=?"
            params.append(status_filter)
        sql += " ORDER BY CASE j.status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, j.id DESC LIMIT 10"
        recent_jobs = with_status_meta(conn.execute(sql, params).fetchall())

        pending_requests = with_status_meta(conn.execute(
            """SELECT r.*, u.name AS requester_name, u.dept AS requester_dept
               FROM as_requests r JOIN users u ON u.id=r.user_id
               WHERE r.status IN ('pending','in_progress')
               ORDER BY CASE r.urgency WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, r.id DESC LIMIT 5"""
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/manage_dash.html", context={
            "request": request, "page_title": "관리자 대시보드",
            "user_name": u["user_name"],
            "worker_count": worker_count,
            "progress_count": progress_count,
            "review_count": review_count,
            "pending_as_count": pending_as_count,
            "urgent_count": urgent_count,
            "week_done_count": week_done_count,
            "dept_stats": dept_stats,
            "recent_jobs": recent_jobs,
            "pending_requests": pending_requests,
            "q": q,
            "status_filter": status_filter,
        }
    )


@router.get("/workers", response_class=HTMLResponse)
async def workers_page(request: Request, dept: str = "", q: str = ""):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    conn = get_sqlite()
    try:
        sql = """SELECT u.*,
                    (SELECT COUNT(*) FROM jobs WHERE user_id=u.id AND status NOT IN ('done','trash')) as active_jobs,
                    (SELECT COUNT(*) FROM jobs WHERE user_id=u.id AND status='done') as done_jobs
                 FROM users u WHERE 1=1"""
        params: list = []
        if dept:
            sql += " AND u.dept=?"
            params.append(dept)
        if q:
            sql += " AND u.name LIKE '%'||?||'%'"
            params.append(q)
        sql += " ORDER BY u.dept, u.name"
        workers = conn.execute(sql, params).fetchall()
        workers = [dict(w) for w in workers]

        depts = [row[0] for row in conn.execute(
            "SELECT DISTINCT dept FROM users ORDER BY dept"
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/workers.html", context={
            "request": request, "page_title": "근로자 관리",
            "user_name": u["user_name"],
            "workers": workers,
            "depts": depts,
            "dept": dept,
            "q": q,
        }
    )


@router.get("/worker/{user_id}", response_class=HTMLResponse)
async def worker_detail(request: Request, user_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    u = get_current_user(request)
    conn = get_sqlite()
    try:
        worker = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not worker:
            conn.close()
            return RedirectResponse(url="/workers", status_code=303)
        worker = dict(worker)

        active_jobs = with_status_meta(conn.execute(
            """SELECT * FROM jobs WHERE user_id=? AND status NOT IN ('done','trash')
               ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id DESC""",
            (user_id,)
        ).fetchall())

        done_jobs = with_status_meta(conn.execute(
            "SELECT * FROM jobs WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 5",
            (user_id,)
        ).fetchall())

        urgent_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='urgent'", (user_id,)
        ).fetchone()[0]
        done_count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (user_id,)
        ).fetchone()[0]

        as_requests = with_status_meta(conn.execute(
            "SELECT * FROM as_requests WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (user_id,)
        ).fetchall())
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="/top/worker_detail.html", context={
            "request": request, "page_title": f"{worker['name']} 근로자 상세",
            "user_name": u["user_name"],
            "worker": worker,
            "active_jobs": active_jobs,
            "done_jobs": done_jobs,
            "active_count": len(active_jobs),
            "done_count": done_count,
            "urgent_count": urgent_count,
            "as_requests": as_requests,
        }
    )


@router.post("/api/jobs/assign")
async def assign_job(
    request: Request,
    user_id: int = Form(...),
    title: str = Form(...),
    category: str = Form("사무"),
    details: str = Form(""),
    dept: str = Form(""),
    due_label: str = Form(""),
    work_date: str = Form(""),
):
    if not check_login(request):
        return JSONResponse({"error": "로그인 필요"}, status_code=401)
    conn = get_sqlite()
    try:
        import datetime
        date_val = work_date or datetime.date.today().isoformat()
        conn.execute(
            """INSERT INTO jobs (user_id, work_date, category, title, details, dept, due_label, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'progress')""",
            (user_id, date_val, category, title, details, dept, due_label)
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/worker/{user_id}", status_code=303)
