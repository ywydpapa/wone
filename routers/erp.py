from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse
from typing import Optional
from core.db import get_sqlite, with_status_meta
from core.deps import check_login, templates
from core.constants import ERP_DOC_TYPES, ERP_REDIRECTS, ERP_DOC_TYPE_LABELS

router = APIRouter()


def _erp_docs_for(dtype: str):
    conn = get_sqlite()
    rows = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type=? ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 WHEN 'wait' THEN 2 ELSE 3 END, id DESC",
        (dtype,)
    ).fetchall())
    conn.close()
    return rows


@router.get("/erp_dash", response_class=HTMLResponse)
async def erp_dash(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    counts = {r["doc_type"]: r["cnt"] for r in [
        dict(r) for r in conn.execute(
            "SELECT doc_type, COUNT(*) AS cnt FROM erp_docs GROUP BY doc_type"
        ).fetchall()
    ]}
    recent = with_status_meta(conn.execute("SELECT * FROM erp_docs ORDER BY id DESC LIMIT 5").fetchall())
    conn.close()
    return templates.TemplateResponse(
        request=request, name="/erp/erp_dash.html", context={
            "request": request, "page_title": "업무 대시보드",
            "doc_counts": counts, "recent_docs": recent,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/erp_hr", response_class=HTMLResponse)
async def erp_hr(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_hr.html", context={
        "request": request, "page_title": "인사관리 대시보드",
        "docs": _erp_docs_for("hr_task"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_fa", response_class=HTMLResponse)
async def erp_fa(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_fa.html", context={
        "request": request, "page_title": "자금관리 대시보드",
        "docs": _erp_docs_for("expense"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_scrm", response_class=HTMLResponse)
async def erp_scrm(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_scrm.html", context={
        "request": request, "page_title": "영업/고객관리 대시보드",
        "docs": _erp_docs_for("activity"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_purch", response_class=HTMLResponse)
async def erp_purch(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_purch.html", context={
        "request": request, "page_title": "구매관리 대시보드",
        "docs": _erp_docs_for("po"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_inventory", response_class=HTMLResponse)
async def erp_inventory(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_inventory.html", context={
        "request": request, "page_title": "재고관리 대시보드",
        "docs": _erp_docs_for("stock_move"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_product", response_class=HTMLResponse)
async def erp_product(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_product.html", context={
        "request": request, "page_title": "생산관리 대시보드",
        "docs": _erp_docs_for("work_order"),
        "user_name": request.session.get("user_name", "김민수"),
    })


@router.get("/erp_groupware", response_class=HTMLResponse)
async def erp_groupware(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="/erp/erp_groupware.html", context={
        "request": request, "page_title": "사내 그룹웨어",
        "docs": _erp_docs_for("draft"),
        "user_name": request.session.get("user_name", "김민수"),
    })


# ERP 문서 작성 폼 (동적 라우트)
for _route_name, (_dtype, _dlabel) in ERP_DOC_TYPES.items():
    def _make_handler(__dtype=_dtype, __dlabel=_dlabel):
        async def handler(request: Request):
            if not check_login(request):
                return RedirectResponse(url="/login", status_code=303)
            return templates.TemplateResponse(
                request=request, name="erp/erp_form.html", context={
                    "request": request, "page_title": __dlabel,
                    "doc_type": __dtype, "back_url": ERP_REDIRECTS[__dtype],
                    "user_name": request.session.get("user_name", "김민수"),
                }
            )
        return handler
    router.add_api_route(f"/{_route_name}", _make_handler(), methods=["GET"], response_class=HTMLResponse)


@router.get("/erp_doc/{doc_id}", response_class=HTMLResponse)
async def erp_doc_detail(request: Request, doc_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    row = conn.execute("SELECT * FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("<h2>문서를 찾을 수 없습니다</h2><a href='/'>홈으로</a>", status_code=404)
    doc = with_status_meta([row])[0]
    doc["doc_type_label"] = ERP_DOC_TYPE_LABELS.get(doc["doc_type"], doc["doc_type"])
    back_url = ERP_REDIRECTS.get(doc["doc_type"], "/erp_dash")
    return templates.TemplateResponse(
        request=request, name="erp/erp_doc_detail.html", context={
            "request": request, "page_title": doc["title"],
            "doc": doc, "back_url": back_url,
            "user_name": request.session.get("user_name", "김민수"),
        }
    )


@router.get("/leave_approvals", response_class=HTMLResponse)
async def leave_approvals(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='hr_task' AND title LIKE '%휴가%' ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(request=request, name="erp/leave_approvals.html", context={
        "request": request, "page_title": "휴가 승인",
        "user_name": request.session.get("user_name", "김민수"), "docs": docs,
    })


@router.get("/recruitment_status", response_class=HTMLResponse)
async def recruitment_status(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    postings = [dict(r) for r in conn.execute("SELECT * FROM job_postings ORDER BY id DESC").fetchall()]
    conn.close()
    return templates.TemplateResponse(request=request, name="erp/recruitment_status.html", context={
        "request": request, "page_title": "채용 현황",
        "user_name": request.session.get("user_name", "김민수"), "postings": postings,
    })


@router.get("/outflow_list", response_class=HTMLResponse)
async def outflow_list(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('done','approved') ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "출금 완료 내역",
        "subtitle": "처리 완료된 지출 내역입니다.",
        "user_name": request.session.get("user_name", "김민수"), "docs": docs,
    })


@router.get("/pending_payments", response_class=HTMLResponse)
async def pending_payments(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE doc_type='expense' AND status IN ('wait','pending','urgent') ORDER BY id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(request=request, name="erp/fa_list.html", context={
        "request": request, "page_title": "미결제 내역",
        "subtitle": "처리 대기 중인 지출 요청입니다.",
        "user_name": request.session.get("user_name", "김민수"), "docs": docs,
    })


@router.get("/approval_pending", response_class=HTMLResponse)
async def approval_pending(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    docs = with_status_meta(conn.execute(
        "SELECT * FROM erp_docs WHERE status IN ('wait','pending','urgent') ORDER BY CASE status WHEN 'urgent' THEN 0 ELSE 1 END, id DESC"
    ).fetchall())
    conn.close()
    return templates.TemplateResponse(request=request, name="erp/approval_pending.html", context={
        "request": request, "page_title": "결재 대기",
        "user_name": request.session.get("user_name", "김민수"), "docs": docs,
    })


# --- API ---

@router.post("/api/erp_docs")
async def create_erp_doc(
    request: Request,
    doc_type: str = Form(""), title: str = Form(""), content: str = Form(""),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_sqlite()
    conn.execute(
        "INSERT INTO erp_docs (user_id, doc_type, title, content, status) VALUES (?,?,?,?,?)",
        (request.session.get("user_id", 1), doc_type, title, content, "wait"),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=ERP_REDIRECTS.get(doc_type, "/"), status_code=303)


@router.post("/api/erp_docs/{doc_id}/status")
async def update_erp_doc_status(request: Request, doc_id: int, status: str = Form(...)):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    if status not in ("approved", "rejected", "done"):
        return JSONResponse({"error": "invalid status"}, status_code=400)
    conn = get_sqlite()
    row = conn.execute("SELECT doc_type FROM erp_docs WHERE id=?", (doc_id,)).fetchone()
    if row:
        conn.execute("UPDATE erp_docs SET status=? WHERE id=?", (status, doc_id))
        conn.commit()
    conn.close()
    back = ERP_REDIRECTS.get(row["doc_type"], "/erp_dash") if row else "/erp_dash"
    return RedirectResponse(url=back, status_code=303)


@router.get("/api/erp_docs")
async def list_erp_docs(request: Request, doc_type: Optional[str] = None):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    if doc_type:
        rows = conn.execute("SELECT * FROM erp_docs WHERE doc_type=? ORDER BY created_at DESC", (doc_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM erp_docs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
