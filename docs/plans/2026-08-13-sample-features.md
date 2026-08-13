# Wone 전체 샘플 기능 구현 플랜 (소넷 위임서)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (또는 subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하드코딩된 정적 화면 전부를 DB 샘플 데이터 기반의 실제 동작 기능(댓글, 좋아요, 결재, 읽음 처리 등 업계 표준 CRUD)으로 전환하고, 스텁 17개 페이지를 샘플 콘텐츠 페이지로 교체한다.

**Architecture:** FastAPI + Jinja2 + SQLite(`test.db`). 기존 패턴 유지 — 페이지 라우트는 `templates.TemplateResponse`, 데이터 조작은 `get_sqlite()` (sqlite3 동기 커넥션), 폼 POST 후 303 리다이렉트. JS fetch는 체크박스/좋아요 같은 인플레이스 토글에만 사용.

**Tech Stack:** Python 3.9+, FastAPI, Jinja2, Bootstrap 5, FontAwesome 6, SQLite

## Global Constraints (반드시 지킬 것)

- **디자인 시스템 유지**: 모든 페이지는 `{% include 'common/header.html' %}` + `{% include 'common/topbar.html' %}` 구조. 기존 CSS 클래스 재사용: `dash-header`, `content-card`, `stat-card`, `task-item`, `task-title`, `task-meta`, `badge-status status-urgent|status-progress|status-done`, `msg-item`, `tool-btn`, `post-item`
- **UI 텍스트는 전부 한국어**, 이모지는 기존 템플릿에 이미 있는 스타일만 유지 (새로 추가 금지 아님, 기존 톤 유지)
- **하드코딩된 "김민수"는 전부 `{{ user_name }}`으로 치환** (topbar 포함)
- 모든 페이지 라우트 첫 줄: `if not check_login(request): return RedirectResponse(url="/login", status_code=303)` — JSON API는 `JSONResponse({"error": "not logged in"}, status_code=401)`
- SQL은 반드시 파라미터 바인딩(`?`) 사용. f-string으로 SQL 조립 금지
- 템플릿에 사용자 입력 출력 시 Jinja 기본 이스케이프 신뢰 (`|safe` 사용 금지)
- 현재 로그인 유저 id는 세션 `request.session.get("user_id", 1)` 사용 (Task 2에서 세션에 저장함)
- 커밋: 태스크 단위로 `git add <구체적 파일>` 후 커밋. 메시지는 한국어 요약 + `Co-Authored-By: Claude` 푸터
- **test.db는 언제든 `python init_db.py`로 재생성 가능한 목업**. 스키마 바뀌면 삭제 후 재생성이 정상 절차
- 테스트: pytest 인프라 없음. 각 태스크 검증은 `python init_db.py` + `uvicorn main:app --port 8001` 백그라운드 + `curl` 스모크 (쿠키 로그인 절차 아래 참고)

### curl 스모크 공통 절차

```bash
# 서버 기동 (백그라운드)
cd /Users/chessy/Documents/wone && python init_db.py && (uvicorn main:app --port 8001 &) && sleep 2
# 로그인 세션 쿠키 획득
curl -s -c /tmp/wone_cookie -X POST http://127.0.0.1:8001/login_check -d "username=admin&password=1234" -o /dev/null
# 이후 페이지 확인
curl -s -b /tmp/wone_cookie http://127.0.0.1:8001/community | grep -c "post-item"
```

### 상태 매핑 (전 태스크 공통)

| DB status | 라벨 | CSS 클래스 |
|---|---|---|
| urgent | 긴급 | status-urgent |
| progress | 진행중 | status-progress |
| wait / pending / draft | 대기 | status-progress (style="background-color:#e2e3e5; color:#383d41;") |
| done / approved / resolved | 완료 | status-done |
| rejected | 반려 | status-urgent |

이 매핑은 main.py에 헬퍼로 1회 정의해서 재사용:

```python
STATUS_META = {
    "urgent":   ("긴급",  "status-urgent",   ""),
    "progress": ("진행중", "status-progress", ""),
    "wait":     ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "pending":  ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "draft":    ("대기",  "status-progress", "background-color:#e2e3e5; color:#383d41;"),
    "done":     ("완료",  "status-done",     ""),
    "approved": ("완료",  "status-done",     ""),
    "resolved": ("완료",  "status-done",     ""),
    "rejected": ("반려",  "status-urgent",   ""),
    "in_progress": ("진행중", "status-progress", ""),
}

def with_status_meta(rows):
    """sqlite Row 리스트 → dict 리스트 + status_label/status_class/status_style 부여"""
    out = []
    for r in rows:
        d = dict(r)
        label, cls, style = STATUS_META.get(d.get("status", ""), (d.get("status", ""), "status-progress", ""))
        d["status_label"], d["status_class"], d["status_style"] = label, cls, style
        out.append(d)
    return out
```

---

## Phase 1 — 기반 (DB, 로그인, 업무)

### Task 1: init_db.py 전면 개편 (스키마 + 샘플 데이터)

**Files:**
- Modify: `init_db.py` (전체 재작성)
- 실행 산출물: `test.db` 재생성

**Interfaces:**
- Produces: 아래 테이블 스키마. 이후 모든 태스크가 이 컬럼명을 그대로 사용한다.

**스키마 (전체):**

```python
"""SQLite 테스트 DB 초기화 - 테이블 생성 + mock 데이터 삽입.
실행 시 기존 테이블 DROP 후 재생성 (test.db는 목업 전용)."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "test.db")

TABLES = ["users", "jobs", "as_requests", "posts", "comments", "post_likes",
          "bookmarks", "messages", "erp_docs", "job_postings", "notifications"]

def init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for t in TABLES:
        c.execute(f"DROP TABLE IF EXISTS {t}")

    c.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        dept TEXT DEFAULT '경영지원팀',
        position TEXT DEFAULT '사원',
        phone TEXT DEFAULT '070-1234-5678',
        role TEXT DEFAULT 'employee'
    )""")

    c.execute("""CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        work_date TEXT,
        category TEXT,
        title TEXT NOT NULL,
        details TEXT,
        issues TEXT,
        dept TEXT DEFAULT '공통 업무',
        due_label TEXT DEFAULT '',
        status TEXT DEFAULT 'progress',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE as_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        urgency TEXT,
        title TEXT NOT NULL,
        details TEXT,
        attachment TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT DEFAULT 'general',
        title TEXT NOT NULL,
        content TEXT,
        author TEXT DEFAULT '',
        dept TEXT DEFAULT '',
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER,
        author TEXT DEFAULT '',
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE post_likes (
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (post_id, user_id)
    )""")

    c.execute("""CREATE TABLE bookmarks (
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (post_id, user_id)
    )""")

    c.execute("""CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sender TEXT NOT NULL,
        body TEXT NOT NULL,
        time_label TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE erp_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doc_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        dept TEXT DEFAULT '',
        due_label TEXT DEFAULT '',
        status TEXT DEFAULT 'wait',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE job_postings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        region TEXT DEFAULT '서울',
        employment_type TEXT DEFAULT '정규직',
        disability_friendly TEXT DEFAULT '',
        salary TEXT DEFAULT '회사내규',
        deadline TEXT DEFAULT '',
        description TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    c.execute("""CREATE TABLE notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        icon TEXT DEFAULT 'far fa-bell',
        title TEXT NOT NULL,
        body TEXT DEFAULT '',
        time_label TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0
    )""")
```

**샘플 데이터 요구사항 (executemany로 삽입):**

- `users` 3명: `("admin","1234","김민수","경영지원팀","사원","070-1234-5678","admin")`, `("user1","1234","이영희","디자인팀","대리","070-1234-5679","employee")`, `("user2","1234","박철수","개발팀","과장","070-1234-5680","employee")`
- `jobs`: user_id=1 기준 **progress 3건 + urgent 1건** (emp_dash "오늘의 할 일"용 — 기존 하드코딩 내용 재사용: "웹 접근성 모니터링 결과 보고서 작성"(urgent, IT 지원팀, "오늘 18:00 까지"), "고객사 영수증 데이터 엑셀 입력 (200건)"(progress, 경영지원팀, "내일 12:00 까지"), "주간 팀 화상 회의 참석"(wait, 공통 업무, "오늘 14:00 (Zoom)") 등) + **done 12건** (complete_job.html의 하드코딩 12건 제목/부서/완료시각을 due_label에 그대로 옮김)
- `messages`: user_id=1에 **미읽음 2건** ("이매니저"/"박팀장" — new_arrived_job.html 하드코딩 본문 그대로) + **읽음 2건** ("최사원", "시스템 알림")
- `posts`: community.html 하드코딩 4건을 그대로 시드 — category는 `it`/`biz`/`design`/`sales`, author/dept 채움 (예: "김개발","프론트엔드"), views는 124/342/210/156. 추가로 `notice`/`general` 4건 (기존 init_db 데이터 재사용, author는 users 이름으로)
- `comments`: post 1~4에 각 1~3개 (예: post_id=1에 "aria-live 처리 부분 정말 유용하네요!" — author "이사무")
- `post_likes`: 임의 분포 (post 1에 user 2,3 / post 2에 user 1,2,3 등). community 카드의 좋아요 숫자는 이 테이블 COUNT로 계산한다
- `bookmarks`: user_id=1이 post 2, 3 스크랩
- `erp_docs`: doc_type별 3~4건씩, **7종**: `draft`(결재기안), `hr_task`, `stock_move`, `work_order`, `po`, `activity`, `expense`(자금관리용 신규). 각 모듈 페이지 하드코딩 항목을 시드로 재사용 (예: hr_task — "[휴가승인] 개발팀 이대리 연차 휴가 신청 (8/10 ~ 8/12)" status=urgent dept="개발1팀" due_label="오늘 18:00 마감"). status는 urgent/progress/wait/done 골고루
- `job_postings`: 8건 — 장애인 친화 채용 샘플 (예: company "한국장애인고용공단 협력사", title "웹 접근성 QA 담당자", disability_friendly "재택근무 가능, 수어통역 지원" 등 현실적인 8건 창작)
- `notifications`: user_id=1에 5건 (아이콘/제목/본문/시간라벨, 미읽음 2건)

**Steps:**

- [ ] **Step 1:** 위 스키마로 `init_db.py` 재작성 + 샘플 데이터 삽입 코드 작성
- [ ] **Step 2:** 실행: `cd /Users/chessy/Documents/wone && python init_db.py` → `DB initialized` 출력 확인
- [ ] **Step 3:** 검증: `sqlite3 test.db "SELECT COUNT(*) FROM jobs WHERE status='done'"` → `12`. `sqlite3 test.db "SELECT COUNT(*) FROM erp_docs"` → 21 이상. `sqlite3 test.db "SELECT COUNT(*) FROM job_postings"` → `8`
- [ ] **Step 4:** 커밋: `git add init_db.py && git commit` ("DB 스키마 확장 및 전체 샘플 데이터 시드")

### Task 2: 로그인 DB 검증 + 회원가입 + topbar 개인화

**Files:**
- Modify: `main.py` (`login_check`, `/login` 라우트, 신규 `/signup` GET/POST — STUB_PAGES 딕셔너리에서 `/signup`, `/forgot_password` 제거)
- Modify: `templates/login/login.html` (에러 메시지 표시 + 회원가입 링크. 먼저 Read 할 것)
- Create: `templates/login/signup.html`
- Modify: `templates/common/topbar.html` ("김민수" → `{{ user_name }}`, 아바타 URL의 `김+민수` → `{{ user_name }}`)

**Interfaces:**
- Produces: 세션 키 `logined`(bool), `user_id`(int), `username`(str=로그인ID), `user_name`(str=표시이름), `role`(str). **이후 모든 태스크는 표시 이름으로 `request.session.get("user_name", "김민수")`를 컨텍스트 `user_name`에 넣는다** (기존 라우트들의 `request.session.get("username", ...)` 호출도 일괄 `user_name`으로 교체)

**Steps:**

- [ ] **Step 1:** `login_check` 재작성:

```python
@app.post("/login_check")
async def login_check(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_sqlite()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?", (username, password)
    ).fetchone()
    conn.close()
    if row:
        request.session["logined"] = True
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        request.session["user_name"] = row["name"]
        request.session["role"] = row["role"]
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)
```

(참고: 목업이라 평문 비교. 실서비스 전환 시 해시 필요 — README에 이미 명시돼 있음)

- [ ] **Step 2:** `/login` 라우트에 `error: str = ""` 쿼리 파라미터 받아 컨텍스트로 전달. `login.html`의 폼 위에 추가:

```html
{% if error %}
<div class="alert alert-danger py-2 small">아이디 또는 비밀번호가 올바르지 않습니다.</div>
{% endif %}
```

또한 login.html에 안내 박스 추가: "테스트 계정: admin / 1234"

- [ ] **Step 3:** `/signup` GET(폼 렌더) + POST(`users` INSERT, username 중복 시 `?error=dup`로 리다이렉트) 구현. `signup.html`은 login.html 레이아웃 복제 후 필드: username, password, name, dept(select: 경영지원팀/개발팀/디자인팀/영업팀), 가입 성공 시 `/login`으로
- [ ] **Step 4:** topbar.html 개인화 치환, main.py 전 라우트의 `user_name` 컨텍스트 값 통일
- [ ] **Step 5:** 스모크: 잘못된 비번 → 302 to `/login?error=1`. `admin/1234` → `/` 200. `curl -s -b /tmp/wone_cookie http://127.0.0.1:8001/ | grep "김민수"` 매치
- [ ] **Step 6:** 커밋 ("로그인 DB 검증, 회원가입, topbar 개인화")

### Task 3: 업무 페이지 DB 연동 + 체크박스 완료 토글 + 메시지 읽음 처리

**Files:**
- Modify: `main.py` (`emp_dash`, `cedjob`, `newarrived_jobs` 라우트에 DB 조회 추가, 신규 API 3개)
- Modify: `templates/top/emp_dash.html`, `templates/apps/complete_job.html`, `templates/apps/new_arrived_job.html`

**Interfaces:**
- Produces: `POST /api/jobs/{job_id}/toggle` → `{"status": "done"|"progress"}`, `POST /api/messages/{msg_id}/read`, `POST /api/messages/read_all` → `{"ok": true}`

**Steps:**

- [ ] **Step 1:** `emp_dash` 라우트에서 조회 후 컨텍스트 전달:

```python
uid = request.session.get("user_id", 1)
conn = get_sqlite()
todos = with_status_meta(conn.execute(
    "SELECT * FROM jobs WHERE user_id=? AND status!='done' ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 ELSE 2 END, id", (uid,)).fetchall())
done_recent = with_status_meta(conn.execute(
    "SELECT * FROM jobs WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 1", (uid,)).fetchall())
done_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='done'", (uid,)).fetchone()[0]
unread_msgs = conn.execute("SELECT * FROM messages WHERE user_id=? AND is_read=0 ORDER BY id DESC", (uid,)).fetchall()
conn.close()
```

컨텍스트: `todos`, `done_recent`, `done_count`, `progress_count=len(todos)`, `messages=[dict(m) for m in unread_msgs]`, `unread_count=len(unread_msgs)`

- [ ] **Step 2:** `emp_dash.html` 수정 — 통계 3칸 숫자를 `{{ progress_count }}`/`{{ done_count }}`/`{{ unread_count }}`로, 헤더 문구의 "3건"→`{{ progress_count }}건`, "김민수"→`{{ user_name }}`. task-list를 루프로 교체:

```html
<div class="task-list">
    {% for t in todos %}
    <div class="task-item">
        <input class="form-check-input task-checkbox" type="checkbox" id="task{{ t.id }}"
               onchange="toggleJob({{ t.id }}, this)">
        <div class="task-content">
            <label class="task-title" for="task{{ t.id }}">{{ t.title }}</label>
            <div class="task-meta d-flex align-items-center gap-3">
                <span class="badge-status {{ t.status_class }}" {% if t.status_style %}style="{{ t.status_style }}"{% endif %}>{{ t.status_label }}</span>
                {% if t.due_label %}<span><i class="far fa-clock"></i> {{ t.due_label }}</span>{% endif %}
                <span><i class="far fa-folder-open"></i> {{ t.dept }}</span>
            </div>
        </div>
        <a href="/job/{{ t.id }}" class="btn btn-light btn-sm"><i class="fas fa-ellipsis-v"></i></a>
    </div>
    {% endfor %}
    {% for t in done_recent %}
    <div class="task-item opacity-50">
        <input class="form-check-input task-checkbox" type="checkbox" id="task{{ t.id }}" checked
               onchange="toggleJob({{ t.id }}, this)">
        <div class="task-content">
            <label class="task-title text-decoration-line-through" for="task{{ t.id }}">{{ t.title }}</label>
            <div class="task-meta d-flex align-items-center gap-3">
                <span class="badge-status status-done">완료</span>
                {% if t.due_label %}<span><i class="fas fa-check"></i> {{ t.due_label }}</span>{% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
</div>
```

body 하단 스크립트 추가:

```html
<script>
function toggleJob(id, el) {
    fetch('/api/jobs/' + id + '/toggle', {method: 'POST'})
        .then(r => r.json())
        .then(() => location.reload())
        .catch(() => { el.checked = !el.checked; });
}
</script>
```

담당자 메시지 카드도 `{% for m in messages %}` 루프로 (msg-item 구조 유지, `m.sender`/`m.time_label`/`m.body`)

- [ ] **Step 3:** main.py에 토글/읽음 API 추가:

```python
@app.post("/api/jobs/{job_id}/toggle")
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


@app.post("/api/messages/{msg_id}/read")
async def read_message(request: Request, msg_id: int):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/messages/read_all")
async def read_all_messages(request: Request):
    if not check_login(request):
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = request.session.get("user_id", 1)
    conn = get_sqlite()
    conn.execute("UPDATE messages SET is_read=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return {"ok": True}
```

- [ ] **Step 4:** `complete_job.html` — done 12건 루프 렌더 (라우트에서 `done_jobs`, `done_count`, `progress_count` 전달, 헤더 "12건" 치환). 검색 input은 `<form method="get">` + `q` 파라미터로 `WHERE title LIKE '%'||?||'%'` 필터. 페이지네이션은 페이지당 10건 (`page` 쿼리 파라미터, 기존 링크 구조 재사용)
- [ ] **Step 5:** `new_arrived_job.html` — 미읽음/읽음 메시지 루프 렌더. "읽음" 버튼 → `fetch('/api/messages/{id}/read').then(()=>location.reload())`, "모두 읽음 처리" 버튼 → `read_all`. 요약 카드 숫자 실데이터 (`unread_count`, `read_count`). "답장하기" 버튼은 `alert('샘플 데모입니다')` 대신 `/new_job`으로 이동
- [ ] **Step 6:** 스모크: emp_dash에 DB 제목 노출 확인, 토글 API로 done 처리 후 `/completed_jobs`에 이동 확인, read_all 후 unread 0 확인
- [ ] **Step 7:** 커밋 ("업무 대시보드/완료/메시지함 DB 연동 및 토글 기능")

---

## Phase 2 — 커뮤니티 · ERP · 채용 · AS

### Task 4: 커뮤니티 목록 (필터/검색/페이지네이션/프로필 통계)

**Files:**
- Modify: `main.py` (`communi` 라우트)
- Modify: `templates/top/community.html`

**Interfaces:**
- Consumes: posts/comments/post_likes 테이블 (Task 1)
- Produces: `GET /community?category=it|biz|design|sales|all&q=검색어&page=1`

**카테고리 메타 (main.py 상수):**

```python
POST_CATEGORIES = {
    "it":     ("💻 IT/개발",   "primary"),
    "biz":    ("📊 경영/사무", "success"),
    "design": ("🎨 디자인",   "warning"),
    "sales":  ("📢 영업/마케팅", "danger"),
    "notice": ("📌 공지",     "dark"),
    "general": ("💬 자유",    "secondary"),
    "qna":    ("❓ Q&A",      "info"),
}
```

**Steps:**

- [ ] **Step 1:** `communi` 라우트 재작성 — `category: str = "all"`, `q: str = ""`, `page: int = 1` 파라미터. 쿼리:

```python
sql = """SELECT p.*,
    (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count,
    (SELECT COUNT(*) FROM post_likes l WHERE l.post_id=p.id) AS like_count
    FROM posts p WHERE 1=1"""
params = []
if category != "all":
    sql += " AND p.category=?"; params.append(category)
if q:
    sql += " AND (p.title LIKE '%'||?||'%' OR p.content LIKE '%'||?||'%')"; params += [q, q]
sql += " ORDER BY p.id DESC LIMIT 10 OFFSET ?"; params.append((page-1)*10)
```

프로필 통계: `my_post_count`(내 글 수), `my_comment_count`, `my_like_received`(내 글이 받은 좋아요 합) 각각 COUNT 쿼리. 컨텍스트에 `posts`, `categories=POST_CATEGORIES`, `current_category`, `q`, `page`, `total_pages` 전달

- [ ] **Step 2:** community.html — 탭을 `{% for code, (label, color) in categories.items() %}` 대신 고정 5개 탭(전체보기+it/biz/design/sales)을 `href="/community?category=..."`로, 현재 탭에 `active` 클래스 조건부. 게시글 4개 하드코딩 블록 → 루프 1개로:

```html
{% for p in posts %}
<div class="p-3 mb-3 border rounded bg-white post-item shadow-sm">
    <div class="d-flex justify-content-between mb-2">
        {% set meta = categories.get(p.category, ('💬 자유', 'secondary')) %}
        <span class="badge bg-{{ meta[1] }} bg-opacity-10 text-{{ meta[1] }} border border-{{ meta[1] }} px-2 py-1">{{ meta[0] }}</span>
        <span class="small text-muted"><i class="far fa-clock me-1"></i>{{ p.created_at }}</span>
    </div>
    <h5 class="fw-bold mb-2">
        <a href="/post/{{ p.id }}" class="text-dark text-decoration-none stretched-link">{{ p.title }}</a>
    </h5>
    <p class="text-muted small mb-3 text-truncate">{{ p.content }}</p>
    <div class="d-flex justify-content-between align-items-center small text-muted">
        <span><i class="fas fa-user-circle me-1"></i>{{ p.author }}{% if p.dept %} ({{ p.dept }}){% endif %}</span>
        <div>
            <span class="me-3"><i class="far fa-eye me-1"></i>{{ p.views }}</span>
            <span class="me-3 text-primary"><i class="far fa-comment-dots me-1"></i>{{ p.comment_count }}</span>
            <span class="text-danger"><i class="fas fa-heart me-1"></i>{{ p.like_count }}</span>
        </div>
    </div>
</div>
{% else %}
<p class="text-center text-muted py-5">게시글이 없습니다.</p>
{% endfor %}
```

검색 폼: `<form method="get" action="/community">` + `name="q"`. 페이지네이션 링크에 category/q 유지. 프로필 카드 이름/부서/통계 실데이터. 인기 태그는 `href="/community?q=태그명"`으로 연결

- [ ] **Step 3:** `create_post` 수정 — author/dept를 세션 유저에서 채움 (`SELECT name, dept FROM users WHERE id=?`)
- [ ] **Step 4:** 스모크: `?category=design` → 디자인 글만, `?q=엑셀` → 매치 1건 이상
- [ ] **Step 5:** 커밋 ("커뮤니티 목록 DB 연동: 필터/검색/페이지네이션")

### Task 5: 게시글 상세 — 조회수/댓글/좋아요/북마크

**Files:**
- Create: `templates/top/post_detail.html` (detail.html 기반 확장이 아니라 커뮤니티 전용 신규)
- Modify: `main.py` (`post_detail` 라우트 재작성, 신규 API 3개, `my_posts`/`my_bookmarks` 라우트 수정)
- Modify: `templates/top/my_posts.html`, `templates/top/my_bookmarks.html` (먼저 Read — posts 컨텍스트 형태 확인 후 comment_count 등 표시 보강)

**Interfaces:**
- Produces: `POST /api/posts/{id}/comments` (Form `content`) → 303 back, `POST /api/posts/{id}/like` → `{"liked": bool, "count": int}`, `POST /api/posts/{id}/bookmark` → `{"bookmarked": bool}`

**Steps:**

- [ ] **Step 1:** `post_detail` 재작성 — 조회수 `UPDATE posts SET views=views+1 WHERE id=?` 후 조회. 댓글 목록, 좋아요 수, 내 좋아요/북마크 여부 조회해서 `post_detail.html` 렌더
- [ ] **Step 2:** `post_detail.html` 작성 — header/topbar include + content-card 구조. 구성: 카테고리 뱃지 + 제목 + 작성자/일시/조회수 → 본문 → 좋아요·스크랩 버튼 (fetch 토글, 숫자 갱신) → 댓글 섹션:

```html
<div class="content-card mt-4">
    <div class="card-title mb-3"><span><i class="far fa-comment-dots me-2 text-primary"></i>댓글 {{ comments|length }}</span></div>
    {% for c in comments %}
    <div class="border-bottom py-3">
        <div class="d-flex justify-content-between small mb-1">
            <span class="fw-bold"><i class="fas fa-user-circle me-1 text-secondary"></i>{{ c.author }}</span>
            <span class="text-muted">{{ c.created_at }}</span>
        </div>
        <p class="mb-0 small">{{ c.content }}</p>
    </div>
    {% else %}
    <p class="text-muted small py-3 mb-0">첫 댓글을 남겨보세요.</p>
    {% endfor %}
    <form action="/api/posts/{{ post.id }}/comments" method="POST" class="mt-3 d-flex gap-2">
        <input type="text" class="form-control" name="content" placeholder="댓글을 입력하세요" required>
        <button type="submit" class="btn btn-primary px-4">등록</button>
    </form>
</div>
```

좋아요/스크랩 버튼:

```html
<div class="d-flex gap-2 justify-content-center my-4">
    <button id="likeBtn" class="btn {{ 'btn-danger' if liked else 'btn-outline-danger' }} rounded-pill px-4" onclick="toggleLike()">
        <i class="fas fa-heart me-1"></i>좋아요 <span id="likeCount">{{ like_count }}</span>
    </button>
    <button id="bmBtn" class="btn {{ 'btn-primary' if bookmarked else 'btn-outline-primary' }} rounded-pill px-4" onclick="toggleBookmark()">
        <i class="far fa-bookmark me-1"></i>스크랩
    </button>
</div>
<script>
function toggleLike() {
    fetch('/api/posts/{{ post.id }}/like', {method: 'POST'}).then(r => r.json()).then(d => {
        document.getElementById('likeCount').textContent = d.count;
        document.getElementById('likeBtn').className = 'btn rounded-pill px-4 ' + (d.liked ? 'btn-danger' : 'btn-outline-danger');
    });
}
function toggleBookmark() {
    fetch('/api/posts/{{ post.id }}/bookmark', {method: 'POST'}).then(r => r.json()).then(d => {
        document.getElementById('bmBtn').className = 'btn rounded-pill px-4 ' + (d.bookmarked ? 'btn-primary' : 'btn-outline-primary');
    });
}
</script>
```

- [ ] **Step 3:** API 3개 구현. 좋아요/북마크는 존재하면 DELETE, 없으면 INSERT (토글). 댓글 POST는 author를 세션 이름으로, 등록 후 `RedirectResponse(f"/post/{post_id}", status_code=303)`
- [ ] **Step 4:** `my_bookmarks` 라우트 — 기존 `posts.bookmarked` 컬럼 참조 제거, `JOIN bookmarks b ON b.post_id=p.id AND b.user_id=?`로 변경. `my_posts`는 `WHERE user_id=?`(세션)로
- [ ] **Step 5:** 스모크: 상세 2회 조회 → views 2 증가. 댓글 POST → 목록 반영. like 토글 2회 → 원상복구
- [ ] **Step 6:** 커밋 ("게시글 상세: 조회수/댓글/좋아요/스크랩")

### Task 6: ERP 7개 모듈 문서 리스트 DB 연동 + erp_dash 통계

**Files:**
- Create: `templates/erp/_doc_list.html` (공용 partial)
- Modify: `templates/erp/erp_hr.html`, `erp_fa.html`, `erp_inventory.html`, `erp_product.html`, `erp_purch.html`, `erp_scrm.html`, `erp_groupware.html`, `erp_dash.html` (각 파일 먼저 Read — 구조는 erp_hr과 동일 패턴)
- Modify: `main.py` (erp 페이지 라우트 8개에 조회 추가, `ERP_DOC_TYPES`에 `new_expense` 추가, `ERP_REDIRECTS`에 `"expense": "/erp_fa"` 추가)

**Interfaces:**
- Consumes: `with_status_meta()` (Global), erp_docs (Task 1)
- Produces: partial `_doc_list.html`은 컨텍스트 변수 `docs` (status_meta 부여된 dict 리스트)를 사용

**Steps:**

- [ ] **Step 1:** `_doc_list.html` 작성:

```html
<div class="task-list">
    {% for d in docs %}
    <div class="task-item {% if d.status_label == '완료' %}opacity-50{% endif %}">
        <input class="form-check-input task-checkbox" type="checkbox" id="doc{{ d.id }}"
               {% if d.status_label == '완료' %}checked disabled{% endif %}>
        <div class="task-content">
            <label class="task-title {% if d.status_label == '완료' %}text-decoration-line-through{% endif %}" for="doc{{ d.id }}">{{ d.title }}</label>
            <div class="task-meta d-flex align-items-center gap-3">
                <span class="badge-status {{ d.status_class }}" {% if d.status_style %}style="{{ d.status_style }}"{% endif %}>{{ d.status_label }}</span>
                {% if d.due_label %}<span><i class="far fa-clock"></i> {{ d.due_label }}</span>{% endif %}
                {% if d.dept %}<span><i class="far fa-folder-open"></i> {{ d.dept }}</span>{% endif %}
            </div>
        </div>
        <a href="/erp_doc/{{ d.id }}" class="btn btn-light btn-sm"><i class="fas fa-ellipsis-v"></i></a>
    </div>
    {% else %}
    <p class="text-muted text-center py-4">등록된 문서가 없습니다.</p>
    {% endfor %}
</div>
```

- [ ] **Step 2:** main.py — 모듈별 doc_type 매핑 상수 `ERP_PAGE_DOCTYPE = {"erp_hr": "hr_task", "erp_fa": "expense", "erp_inventory": "stock_move", "erp_product": "work_order", "erp_purch": "po", "erp_scrm": "activity", "erp_groupware": "draft"}`. 각 erp 라우트에서 `docs = with_status_meta(conn.execute("SELECT * FROM erp_docs WHERE doc_type=? ORDER BY CASE status WHEN 'urgent' THEN 0 WHEN 'progress' THEN 1 WHEN 'wait' THEN 2 ELSE 3 END, id DESC", (dtype,)).fetchall())` 조회 후 컨텍스트 전달. 통계 카드용 카운트도 함께 (`urgent+wait 건수`, `progress 건수`, `done 건수` 등 페이지 문구에 맞게)
- [ ] **Step 3:** 각 erp_*.html의 하드코딩 task-list 블록을 `{% include 'erp/_doc_list.html' %}`로 교체, 통계 숫자와 "김민수" 치환. 우측 알림/도구 카드는 그대로 유지
- [ ] **Step 4:** `erp_dash.html` — doc_type별 건수/최근 문서 5건을 실데이터로 (라우트에서 `SELECT doc_type, COUNT(*) ... GROUP BY doc_type`과 최근 5건 조회)
- [ ] **Step 5:** `create_erp_doc`의 기본 status를 `"wait"`로 변경 (Global 매핑과 일치)
- [ ] **Step 6:** 스모크: 7개 모듈 페이지 각각 200 + DB 제목 노출, `/new_expense` 폼 → POST → `/erp_fa` 목록 반영
- [ ] **Step 7:** 커밋 ("ERP 7개 모듈 문서 리스트 DB 연동")

### Task 7: ERP 문서 상세 승인/반려

**Files:**
- Modify: `main.py` (`erp_doc_detail` 재작성, 신규 `POST /api/erp_docs/{id}/status`)
- Create: `templates/erp/erp_doc_detail.html`

**Interfaces:**
- Produces: `POST /api/erp_docs/{doc_id}/status` (Form `status`: approved|rejected|done) → 303 back to 해당 모듈 페이지

**Steps:**

- [ ] **Step 1:** `erp_doc_detail.html` — 문서 정보(제목/유형라벨/상태뱃지/작성일/내용) + 하단 결재 버튼:

```html
{% if doc.status not in ['approved', 'done', 'rejected'] %}
<form action="/api/erp_docs/{{ doc.id }}/status" method="POST" class="d-flex gap-2 justify-content-end">
    <input type="hidden" name="status" value="" id="statusInput">
    <button type="submit" class="btn btn-success px-4" onclick="document.getElementById('statusInput').value='approved'">
        <i class="fas fa-check me-1"></i>승인
    </button>
    <button type="submit" class="btn btn-outline-danger px-4" onclick="document.getElementById('statusInput').value='rejected'">
        <i class="fas fa-times me-1"></i>반려
    </button>
</form>
{% else %}
<div class="alert alert-secondary text-center mb-0">이미 처리된 문서입니다 ({{ doc.status_label }})</div>
{% endif %}
```

- [ ] **Step 2:** 상태 변경 라우트:

```python
@app.post("/api/erp_docs/{doc_id}/status")
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
    back = ERP_REDIRECTS.get(row["doc_type"], "/") if row else "/"
    return RedirectResponse(url=back, status_code=303)
```

- [ ] **Step 3:** `erp_doc_detail` 라우트가 새 템플릿 사용하도록 재작성 (doc_type 한글 라벨은 `ERP_DOC_TYPES` 값 역매핑 상수로)
- [ ] **Step 4:** 스모크: wait 문서 승인 → 모듈 페이지에서 완료 표시, 재접근 시 "이미 처리된 문서"
- [ ] **Step 5:** 커밋 ("ERP 문서 상세 및 승인/반려 결재")

### Task 8: 채용(resume) 목록/상세 DB 연동

**Files:**
- Modify: `templates/top/resume.html` (먼저 Read — 486줄. 공고 카드 리스트 부분만 루프로 교체, 나머지 배너/필터 UI 유지)
- Create: `templates/top/resume_detail.html`
- Modify: `main.py` (`resume`, `resume_detail` 라우트)

**Interfaces:**
- Consumes: job_postings (Task 1)
- Produces: `GET /resume?q=&region=all`, `GET /resume/{id}` 실데이터 상세

**Steps:**

- [ ] **Step 1:** resume.html Read 후 공고 카드 반복 구간 식별 → 카드 1개 마크업만 남기고 `{% for jp in postings %}` 루프로 교체. 카드 링크는 `/resume/{{ jp.id }}`. 검색 폼 `q`(제목/회사 LIKE), 지역 select `region` 필터 동작
- [ ] **Step 2:** `resume` 라우트에서 필터 쿼리 후 `postings` 전달
- [ ] **Step 3:** `resume_detail.html` — 회사/제목/지역/고용형태/급여/마감일/장애인 지원사항(`disability_friendly`)/상세설명 + "지원하기" 버튼(클릭 시 `alert('샘플 데모: 지원이 접수되었습니다')`) + 목록으로 버튼. `resume_detail` 라우트를 stub에서 DB 조회로 교체 (404 처리 포함)
- [ ] **Step 4:** 스모크: `/resume` 공고 8건 노출, `?q=` 필터 동작, `/resume/1` 상세 200
- [ ] **Step 5:** 커밋 ("채용 공고 목록/상세 DB 연동")

### Task 9: contact — 내 AS 접수 내역 연동

**Files:**
- Modify: `templates/top/contact.html`, `main.py` (`contact` 라우트)

**Steps:**

- [ ] **Step 1:** `contact` 라우트에서 세션 유저 정보(`SELECT name, dept, phone FROM users WHERE id=?`)와 내 접수 내역(`SELECT * FROM as_requests WHERE user_id=? ORDER BY id DESC LIMIT 5`, with_status_meta) 전달
- [ ] **Step 2:** contact.html — 신청자/부서/연락처 실데이터 치환. 우측 "나의 AS 접수/처리 내역" tool-btn 아래에 최근 접수 5건 리스트 추가 (제목 + 상태 뱃지, `/as_request/{{ r.id }}` 링크):

```html
<div class="content-card mt-4">
    <div class="card-title"><span><i class="fas fa-history me-2 text-primary"></i>나의 최근 접수 내역</span></div>
    {% for r in my_requests %}
    <a href="/as_request/{{ r.id }}" class="d-flex justify-content-between align-items-center py-2 border-bottom text-decoration-none">
        <span class="small text-dark text-truncate me-2">{{ r.title }}</span>
        <span class="badge-status {{ r.status_class }}" {% if r.status_style %}style="{{ r.status_style }}"{% endif %}>{{ r.status_label }}</span>
    </a>
    {% else %}
    <p class="small text-muted mb-0">접수 내역이 없습니다.</p>
    {% endfor %}
</div>
```

- [ ] **Step 3:** `submit_as_request`의 user_id를 세션 값으로 변경 (하드코딩 1 제거). `create_job`, `create_post`, `create_erp_doc`의 user_id=1도 동일하게 세션 값으로 일괄 수정
- [ ] **Step 4:** 스모크: AS 접수 POST → contact 우측 내역에 pending으로 표시
- [ ] **Step 5:** 커밋 ("AS 접수 내역 연동 및 user_id 세션화")

---

## Phase 3 — 스텁 17개 샘플 페이지화 + 마무리

### Task 10: 계정/알림 스텁 → 샘플 페이지 (profile, notifications, accessibility)

**Files:**
- Create: `templates/top/profile.html`, `templates/top/notifications.html`, `templates/top/accessibility.html`
- Modify: `main.py` (STUB_PAGES에서 3개 제거, 전용 라우트 추가)

**Steps:**

- [ ] **Step 1:** `/profile` — users 테이블 실데이터(이름/부서/직급/연락처/아이디/권한) + 활동 요약(내 글/댓글/완료 업무 COUNT) 카드. 수정 폼(이름/부서/연락처) → `POST /api/profile` → users UPDATE 후 세션 `user_name` 갱신 → 303 `/profile`
- [ ] **Step 2:** `/notifications` — notifications 테이블 루프 (미읽음 강조는 new_arrived_job.html 패턴 재사용), "모두 읽음" 버튼 → `POST /api/notifications/read_all` (messages read_all과 동일 패턴)
- [ ] **Step 3:** `/accessibility` — 실제 동작하는 접근성 샘플: 글자 크기(보통/크게/아주 크게)와 고대비 모드 토글 스위치. localStorage 저장 + `document.documentElement`에 클래스/폰트사이즈 적용하는 인라인 JS. header.html에 `.a11y-large { font-size: 1.15rem; }`, `.a11y-xlarge { font-size: 1.3rem; }`, `.a11y-contrast { filter: contrast(1.2); }` 3개 클래스 추가하고 각 페이지 로드 시 적용되도록 header.html 하단에 적용 스크립트 추가
- [ ] **Step 4:** 스모크 후 커밋 ("프로필/알림/접근성 설정 샘플 기능")

### Task 11: 정보성 스텁 → 샘플 콘텐츠 페이지 (faq, guide, inquiry, terms, privacy, updates)

**Files:**
- Create: `templates/info/faq.html`, `templates/info/guide.html`, `templates/info/inquiry.html`, `templates/info/policy.html` (terms/privacy 공용 — 컨텍스트로 제목/본문 전달), `templates/info/updates.html`
- Modify: `main.py` (STUB_PAGES에서 6개 제거, 라우트 추가)

**Steps:**

- [ ] **Step 1:** `/faq` — Bootstrap accordion으로 FAQ 8문항 샘플 (로그인, 업무 등록, AS 접수, 접근성 도구, 수어통역 신청, 급여명세서, 연차 신청, 비밀번호 변경 관련 현실적 Q&A 창작). 데이터는 main.py 상수 리스트 `FAQ_ITEMS = [{"q": ..., "a": ...}, ...]`로
- [ ] **Step 2:** `/guide` — 사내 시스템 사용 매뉴얼 목차 카드 6개 (업무일지 작성법, ERP 결재 흐름, 커뮤니티 이용 수칙, 접근성 도구 안내, AS 접수 절차, 계정 관리) — 각 카드는 앵커로 같은 페이지 내 섹션 이동, 섹션마다 3~5문장 샘플 본문
- [ ] **Step 3:** `/inquiry` — 1:1 문의 폼 (분류 select/제목/내용) → `POST /submit_as_request` 재사용 (asCategory="inquiry"로 hidden 전달) → 접수 후 `/contact`
- [ ] **Step 4:** `/terms`, `/privacy` — policy.html 공용 렌더. 각 5~6개 조항 샘플 텍스트 (main.py 상수). `/updates` — CHANGELOG.md 내용을 손으로 요약한 타임라인 카드 3건
- [ ] **Step 5:** 스모크 후 커밋 ("정보성 페이지 6종 샘플 콘텐츠")

### Task 12: 업무성 스텁 → 데이터 페이지 (calendar, leave_approvals, recruitment_status, outflow_list, pending_payments, approval_pending)

**Files:**
- Create: `templates/apps/calendar.html`, `templates/erp/leave_approvals.html`, `templates/erp/recruitment_status.html`, `templates/erp/fa_list.html` (outflow/pending_payments 공용), `templates/erp/approval_pending.html`
- Modify: `main.py` (STUB_PAGES에서 6개 제거 — 이 시점에 STUB_PAGES와 stub.html은 완전히 삭제, 라우트 추가)

**Steps:**

- [ ] **Step 1:** `/calendar` — 이번 달(2026-08) 정적 달력 그리드 (Jinja로 주차 행 생성 or 템플릿에 직접 마크업) + jobs의 work_date 있는 항목을 날짜 셀에 뱃지로 표시. 라우트에서 `SELECT work_date, title, status FROM jobs WHERE work_date LIKE '2026-08%'` 전달
- [ ] **Step 2:** `/leave_approvals` — erp_docs 중 `doc_type='hr_task'` AND title LIKE '%휴가%' 목록 + 각 행에 승인/반려 버튼 (`POST /api/erp_docs/{id}/status` 재사용, Task 7). 목록은 `_doc_list.html` 재사용하되 버튼 컬럼 추가한 전용 마크업
- [ ] **Step 3:** `/recruitment_status` — job_postings를 "진행 중인 채용" 테이블로 (회사/포지션/마감일/상태 뱃지)
- [ ] **Step 4:** `/outflow_list`, `/pending_payments` — fa_list.html 공용: erp_docs `doc_type='expense'`에서 status done → 출금 완료 내역, wait/pending → 미결제 내역 필터. 금액 컬럼은 content에 "1,200,000원" 형식으로 시드돼 있어야 함 (Task 1 expense 시드에 금액 포함 확인, 없으면 시드 보강)
- [ ] **Step 5:** `/approval_pending` — erp_docs 전체 중 wait/pending/urgent 문서 목록 + 승인/반려 버튼 (leave_approvals와 동일 패턴)
- [ ] **Step 6:** main.py에서 `STUB_PAGES` 딕셔너리/루프와 `templates/common/stub.html` 삭제 (남은 스텁이 없어야 함)
- [ ] **Step 7:** 스모크 후 커밋 ("업무성 스텁 6종 실데이터 페이지 전환, 스텁 시스템 제거")

### Task 13: 전체 스모크 + 문서 갱신

**Files:**
- Modify: `README.md` (라우트/스키마 표 갱신), `CHANGELOG.md` (오늘자 항목 추가)

**Steps:**

- [ ] **Step 1:** 전체 라우트 스모크 스크립트 실행:

```bash
cd /Users/chessy/Documents/wone && python init_db.py && (uvicorn main:app --port 8001 &) && sleep 2
curl -s -c /tmp/wone_cookie -X POST http://127.0.0.1:8001/login_check -d "username=admin&password=1234" -o /dev/null
for p in / /resume /resume/1 /emp_dash /manage_dash /community "/community?category=it" /post/1 /contact /completed_jobs /newarrived_jobs /erp_dash /erp_hr /erp_fa /erp_inventory /erp_product /erp_purch /erp_scrm /erp_groupware /erp_doc/1 /profile /notifications /accessibility /faq /guide /inquiry /terms /privacy /updates /calendar /leave_approvals /recruitment_status /outflow_list /pending_payments /approval_pending /signup /write_post /my_posts /my_bookmarks /job/1 /as_request/1; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -b /tmp/wone_cookie "http://127.0.0.1:8001$p")
  echo "$code $p"
done | sort | uniq -c | head; echo "---"; # 전부 200이어야 함
```

200 아닌 경로는 전부 수정 후 재실행. 마지막에 `pkill -f "uvicorn main:app"` 으로 서버 종료

- [ ] **Step 2:** README.md의 API 목록/스키마 표를 실제 구현과 일치하게 갱신, CHANGELOG.md에 "2026-08-13 전체 샘플 기능 구현" 섹션 추가 (변경 요약)
- [ ] **Step 3:** 커밋 ("문서 갱신 및 전체 스모크 통과")

---

## Self-Review 체크 결과

- 스펙 커버리지: 커뮤니티(목록/상세/댓글/좋아요/스크랩) T4-5, 업무(토글/읽음) T3, ERP(목록/결재) T6-7, 채용 T8, AS T9, 로그인/가입/프로필 T2/T10, 스텁 17개 전부 T2(signup, forgot→Note), T10, T11, T12에서 해소
- **주의: `/forgot_password`** — T2에서 STUB_PAGES에서 제거하므로 signup.html에 "비밀번호 찾기는 관리자에게 문의(내선 119)" 안내 링크로 대체하고 라우트는 `/signup`으로 리다이렉트 처리할 것
- 타입 일관성: 세션 키(`user_id`/`user_name`), `with_status_meta()`, `ERP_REDIRECTS`+`expense`, `_doc_list.html`의 `docs` 변수명 — 전 태스크 공통 사용 확인
