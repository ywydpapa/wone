"""DB 초기화 — 테이블 생성 + mock 데이터 삽입.

실행 시 기존 테이블 DROP 후 재생성 (test.db는 목업 전용).
DATABASE_URL 환경변수로 SQLite/MySQL 전환 가능.
"""
import os
import hashlib

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from core.db import get_sqlite, _DB_SCHEME

TABLES = ["users", "jobs", "as_requests", "as_comments", "posts", "comments", "post_likes",
          "bookmarks", "messages", "erp_docs", "job_postings", "notifications",
          "job_applications", "approval_lines", "doc_history", "slip_lines",
          "accounts", "partners"]


# ---------------------------------------------------------------------------
# DDL dialect conversion
# ---------------------------------------------------------------------------

def _dialect(ddl: str) -> str:
    """Convert SQLite DDL to the dialect required by the current DB backend.

    Rules applied for MySQL:
      INTEGER PRIMARY KEY AUTOINCREMENT  -> INT PRIMARY KEY AUTO_INCREMENT
      TEXT DEFAULT (datetime(...))       -> DATETIME DEFAULT CURRENT_TIMESTAMP
                                           (column stores Python-formatted strings
                                            anyway, so VARCHAR(255) is fine too;
                                            we use DATETIME for schema clarity)
      standalone TEXT columns that appear
        in index/unique contexts need
        VARCHAR(255) — handled per-table
        via targeted replace below.
    """
    if _DB_SCHEME != "mysql":
        return ddl

    import re

    # AUTOINCREMENT -> AUTO_INCREMENT
    ddl = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
                 "INT PRIMARY KEY AUTO_INCREMENT", ddl, flags=re.IGNORECASE)

    # DEFAULT (datetime('now','localtime')) -> DEFAULT CURRENT_TIMESTAMP
    # MySQL은 TEXT 컬럼에 CURRENT_TIMESTAMP 기본값 불가 -> DATETIME으로 전환
    ddl = re.sub(r"\bTEXT\s+DEFAULT\s+\(datetime\([^)]*\)\)",
                 "DATETIME DEFAULT CURRENT_TIMESTAMP", ddl, flags=re.IGNORECASE)
    ddl = re.sub(r"DEFAULT\s+\(datetime\([^)]*\)\)",
                 "DEFAULT CURRENT_TIMESTAMP", ddl, flags=re.IGNORECASE)

    # TEXT UNIQUE -> VARCHAR(255) UNIQUE  (MySQL cannot index unbounded TEXT)
    ddl = re.sub(r"\bTEXT\b(\s+UNIQUE\b)", r"VARCHAR(255)\1", ddl, flags=re.IGNORECASE)

    return ddl


def _create_table(conn, ddl: str):
    conn.execute(_dialect(ddl))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init():
    conn = get_sqlite()
    c = conn

    for t in reversed(TABLES):   # reverse order to respect FK deps
        c.execute(f"DROP TABLE IF EXISTS {t}")

    _create_table(c, """CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        dept TEXT DEFAULT '경영지원팀',
        position TEXT DEFAULT '사원',
        phone TEXT DEFAULT '070-1234-5678',
        role TEXT DEFAULT 'employee',
        photo TEXT DEFAULT ''
    )""")

    _create_table(c, """CREATE TABLE jobs (
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

    _create_table(c, """CREATE TABLE as_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        urgency TEXT,
        title TEXT NOT NULL,
        details TEXT,
        attachment TEXT,
        status TEXT DEFAULT 'pending',
        assigned_to INTEGER DEFAULT NULL,
        assigned_name TEXT DEFAULT '',
        resolved_at TEXT DEFAULT '',
        admin_memo TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    _create_table(c, """CREATE TABLE as_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    _create_table(c, """CREATE TABLE posts (
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

    _create_table(c, """CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER,
        author TEXT DEFAULT '',
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    _create_table(c, """CREATE TABLE post_likes (
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (post_id, user_id)
    )""")

    _create_table(c, """CREATE TABLE bookmarks (
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (post_id, user_id)
    )""")

    _create_table(c, """CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sender TEXT NOT NULL,
        recipient TEXT DEFAULT '',
        body TEXT NOT NULL,
        time_label TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0,
        direction TEXT DEFAULT 'in',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    _create_table(c, """CREATE TABLE erp_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doc_type TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        dept TEXT DEFAULT '',
        due_label TEXT DEFAULT '',
        attachment TEXT DEFAULT '',
        status TEXT DEFAULT 'wait',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        doc_number TEXT DEFAULT '',
        visibility TEXT DEFAULT '공개',
        retention_period TEXT DEFAULT '3년',
        effective_date TEXT DEFAULT '',
        approved_by INTEGER,
        approved_at TEXT,
        reject_reason TEXT DEFAULT '',
        slip_type TEXT DEFAULT '',
        slip_date TEXT DEFAULT '',
        slip_total INTEGER DEFAULT 0
    )""")

    _create_table(c, """CREATE TABLE job_postings (
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

    _create_table(c, """CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        cover_letter TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(job_id, user_id)
    )""")

    _create_table(c, """CREATE TABLE IF NOT EXISTS approval_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        step INTEGER NOT NULL,
        approver_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        comment TEXT DEFAULT '',
        acted_at TEXT
    )""")

    _create_table(c, """CREATE TABLE IF NOT EXISTS doc_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL,
        comment TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    _create_table(c, """CREATE TABLE IF NOT EXISTS slip_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL,
        line_no INTEGER NOT NULL,
        account_name TEXT NOT NULL,
        debit INTEGER DEFAULT 0,
        credit INTEGER DEFAULT 0,
        partner TEXT DEFAULT '',
        summary TEXT DEFAULT ''
    )""")

    _create_table(c, """CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        is_debit INTEGER DEFAULT 1,
        parent_code TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )""")

    _create_table(c, """CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        biz_no TEXT DEFAULT '',
        representative TEXT DEFAULT '',
        biz_type TEXT DEFAULT '',
        biz_item TEXT DEFAULT '',
        address TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )""")

    _create_table(c, """CREATE TABLE notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        icon TEXT DEFAULT 'far fa-bell',
        title TEXT NOT NULL,
        body TEXT DEFAULT '',
        time_label TEXT DEFAULT '',
        is_read INTEGER DEFAULT 0
    )""")

    # ===== 사용자 =====
    c.executemany(
        "INSERT INTO users (username, password, name, dept, position, phone, role) VALUES (?,?,?,?,?,?,?)",
        [
            ("admin", hashlib.sha256("1234".encode()).hexdigest(), "김민수", "경영지원팀", "사원", "070-1234-5678", "admin"),
            ("user1", hashlib.sha256("1234".encode()).hexdigest(), "이영희", "디자인팀", "대리", "070-1234-5679", "employee"),
            ("user2", hashlib.sha256("1234".encode()).hexdigest(), "박철수", "개발팀", "과장", "070-1234-5680", "employee"),
        ]
    )

    # ===== 업무 =====
    c.executemany(
        "INSERT INTO jobs (user_id, work_date, category, title, details, issues, dept, due_label, status) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, "2026-08-13", "IT", "웹 접근성 모니터링 결과 보고서 작성",
             "WCAG 2.1 AA 기준으로 주요 페이지 점검 결과를 정리한 보고서 작성", "스크린리더 대응 항목 추가 검토 필요",
             "IT 지원팀", "오늘 18:00 까지", "urgent"),
            (1, "2026-08-13", "사무", "고객사 영수증 데이터 엑셀 입력 (200건)",
             "8월분 법인카드 영수증 스캔본을 엑셀 양식에 입력 후 재무팀 제출", "",
             "경영지원팀", "내일 12:00 까지", "progress"),
            (1, "2026-08-13", "IT", "사내 포털 UI 개선 - 모바일 반응형 점검",
             "모바일 환경에서 메뉴 오버플로우 이슈 수정 및 터치 영역 최적화", "iOS Safari 15 이하 호환 확인 필요",
             "IT 지원팀", "이번주 금요일까지", "progress"),
            (1, "2026-08-13", "공통", "주간 팀 화상 회의 참석",
             "매주 수요일 팀 전체 화상 회의 참석 및 회의록 작성", "",
             "공통 업무", "오늘 14:00 (Zoom)", "wait"),
            (1, "2026-08-13", "사무", "전일자 업무 일지 제출",
             "전일자 업무 일지 작성 완료 후 팀장 결재 상신", "", "경영지원팀", "오늘 09:30 완료", "done"),
            (1, "2026-08-12", "사무", "주간 회의록 작성 및 팀 내 공유",
             "이번 주 화요일 전체 회의 회의록 작성 후 팀 메신저 공유", "", "경영지원팀", "어제 17:30 완료", "done"),
            (1, "2026-08-12", "재무", "1분기 부서 지출 결의서 1차 검토",
             "1분기 부서별 지출 항목 검토 및 의견 첨부 완료", "", "재무팀", "어제 15:00 완료", "done"),
            (1, "2026-08-12", "IT", "신규 입사자(디자인팀) PC 세팅 및 권한 부여",
             "노트북 초기화, 필수 소프트웨어 설치, Active Directory 계정 생성 완료", "", "IT 지원팀", "어제 11:00 완료", "done"),
            (1, "2026-08-11", "IT", "사내 인트라넷 메인 페이지 오타 및 링크 수정",
             "메인 배너 텍스트 2건 수정, 깨진 링크 3건 수정 완료", "", "IT 지원팀", "수요일 16:45 완료", "done"),
            (1, "2026-08-11", "영업", "고객사 A사 미팅 발표 자료(PPT) 초안 완성",
             "신규 계약 제안 PPT 20슬라이드 초안 작성 완료 및 팀장 검토 요청", "", "영업팀", "수요일 14:20 완료", "done"),
            (1, "2026-08-11", "사무", "5월 부서 비품 및 소모품 구매 기안 상신",
             "A4용지 볼펜 스테이플러 등 소모품 목록 취합 후 구매 기안 상신 완료", "", "경영지원팀", "수요일 10:00 완료", "done"),
            (1, "2026-08-10", "공통", "전사 필수 정보보안 교육 이수",
             "정보보안 온라인 필수 교육 2시간 수료 및 이수 완료 처리", "", "공통 업무", "화요일 17:00 완료", "done"),
            (1, "2026-08-10", "IT", "웹 접근성 진단 툴 연간 라이선스 갱신 처리",
             "WAVE/axe 라이선스 갱신 견적 검토 후 발주서 제출 완료", "", "IT 지원팀", "화요일 13:30 완료", "done"),
            (1, "2026-08-10", "디자인", "홍보 영상 자막 싱크 오류 3건 수정",
             "8월 회사 홍보 영상 자막 타이밍 오류 수정 후 재업로드 완료", "", "디자인팀", "화요일 11:15 완료", "done"),
            (1, "2026-08-09", "사무", "상반기 팀 워크샵 장소 예약 및 식당 섭외",
             "경기도 가평 펜션 2박3일 예약 완료 및 식사 케이터링 섭외 완료", "", "경영지원팀", "월요일 16:00 완료", "done"),
            (1, "2026-08-09", "기획", "하반기 신규 프로젝트 WBS(일정표) 초안 작성",
             "사내 포털 2.0 프로젝트 WBS 초안 작성 완료 및 PM 검토 요청", "", "개발팀", "월요일 14:30 완료", "done"),
        ]
    )

    # ===== AS 요청 =====
    c.executemany(
        "INSERT INTO as_requests (user_id, category, urgency, title, details, status, assigned_to, assigned_name) VALUES (?,?,?,?,?,?,?,?)",
        [
            (2, "hardware", "high", "모니터 깜빡임 현상", "업무 중 모니터가 간헐적으로 깜빡입니다. 재부팅 후에도 동일.", "pending", None, ""),
            (3, "software", "medium", "ERP 접속 오류", "오전 9시경부터 ERP 페이지 로딩이 되지 않습니다.", "in_progress", 1, "김민수"),
            (1, "network", "low", "Wi-Fi 속도 저하", "오후 시간대 2층 사무실 네트워크가 느려집니다.", "resolved", None, ""),
        ]
    )

    # ===== 게시글 =====
    c.executemany(
        "INSERT INTO posts (user_id, category, title, content, author, dept, views) VALUES (?,?,?,?,?,?,?)",
        [
            (3, "it", "웹 접근성 개선 팁 공유합니다 (스크린 리더 최적화)",
             "최근 프로젝트에서 스크린 리더 호환성을 높이기 위해 적용했던 aria 속성 활용법을 정리해 보았습니다. 특히 모달 창 띄울 때 포커스 이동 처리가 중요하더라고요. aria-live, role=dialog, focus trap 패턴을 실제 코드와 함께 소개합니다.",
             "김개발", "프론트엔드", 124),
            (1, "biz", "엑셀 매크로 활용해서 영수증 처리 시간 단축한 후기",
             "매달 500건씩 들어오는 법인카드 영수증 내역을 엑셀 VBA 매크로를 짜서 자동 분류되게 만들었더니 업무 시간이 절반으로 줄었습니다! 코드 원하시는 분 계시면 공유할게요.",
             "이사무", "재무회계", 342),
            (2, "design", "실무에서 자주 쓰는 피그마(Figma) 플러그인 추천 5가지",
             "디자인 작업 속도를 2배 올려주는 피그마 플러그인 리스트입니다. 아이콘 삽입, 이미지 배경 제거, 더미 텍스트 생성 등 유용한 것들만 모아봤어요. 각 플러그인 설치 방법과 활용 팁도 함께 정리했습니다.",
             "박디잔", "UI/UX", 210),
            (1, "sales", "B2B 콜드메일 오픈율 높이는 제목 작성 노하우 질문드립니다",
             "요즘 신규 고객사 발굴 때문에 콜드메일을 돌리고 있는데 오픈율이 10%도 안 나오네요. 선배님들만의 메일 제목 작성 꿀팁이 있다면 조언 부탁드립니다. 현재는 회사명+포지션 조합으로 쓰고 있어요.",
             "최영업", "B2B세일즈", 156),
            (1, "notice", "8월 시스템 점검 안내",
             "8월 15일(금) 오전 2시~6시 서버 정기 점검이 예정되어 있습니다. 해당 시간 동안 사내 포털 및 ERP 시스템 이용이 불가합니다. 긴급 업무는 사전에 처리 부탁드립니다.",
             "김민수", "경영지원팀", 89),
            (2, "general", "신입사원 환영합니다!",
             "이번 달 입사하신 이영희 대리님, 박철수 과장님 환영합니다. 궁금한 점은 편하게 메신저로 연락 주세요. 온보딩 자료는 팀 공유 폴더에서 확인하실 수 있습니다.",
             "이영희", "디자인팀", 67),
            (3, "qna", "연차 신청 방법 문의",
             "연차 신청은 어디서 하나요? ERP 인사 모듈에서 가능한 건가요? 입사한 지 얼마 안 되어서 아직 시스템이 익숙하지 않습니다. 담당자분께서 안내 부탁드립니다.",
             "박철수", "개발팀", 45),
            (1, "general", "사내 동호회 신규 회원 모집",
             "축구(매주 토요일), 볼링(격주 금요일), 독서(월 1회) 동호회에서 신규 회원을 모집합니다. 관심 있으신 분은 경영지원팀 김민수에게 메신저 주세요!",
             "김민수", "경영지원팀", 132),
        ]
    )

    # ===== 댓글 =====
    c.executemany(
        "INSERT INTO comments (post_id, user_id, author, content) VALUES (?,?,?,?)",
        [
            (1, 1, "이사무", "aria-live 처리 부분 정말 유용하네요! 저도 모달 포커스 이슈 때문에 고생했었는데 바로 적용해보겠습니다."),
            (1, 3, "박철수", "좋은 자료 감사합니다. role=dialog 관련해서 추가 설명도 부탁드려도 될까요?"),
            (2, 3, "박철수", "와 이거 정말 탐납니다! 저도 매달 영수증 정리 때문에 힘든데 코드 공유 부탁드려요."),
            (2, 1, "김민수", "엄청난 시간 절약이네요! 혹시 피벗테이블 연동도 가능한가요?"),
            (2, 2, "이영희", "저도 써보고 싶어요. 맥OS에서도 동작하나요?"),
            (3, 1, "김민수", "컨텐츠 리샘플러 플러그인은 저도 애용하고 있어요. 좋은 리스트 감사합니다!"),
            (3, 3, "박철수", "개발자 입장에서도 디자이너분들이 이런 툴 쓰는 걸 알면 협업이 더 쉬울 것 같아요."),
            (4, 2, "이영희", "저도 같은 고민 중이에요. 수신자 이름 개인화가 꽤 효과 있다는 글을 본 적 있어요!"),
        ]
    )

    # ===== 좋아요 =====
    c.executemany(
        "INSERT INTO post_likes (post_id, user_id) VALUES (?,?)",
        [
            (1, 2), (1, 3),
            (2, 1), (2, 2), (2, 3),
            (3, 1), (3, 2),
            (4, 3),
            (5, 2), (5, 3),
            (6, 1), (6, 3),
            (8, 1), (8, 2), (8, 3),
        ]
    )

    # ===== 북마크 =====
    c.executemany(
        "INSERT INTO bookmarks (post_id, user_id) VALUES (?,?)",
        [(2, 1), (3, 1)]
    )

    # ===== 메시지 =====
    c.executemany(
        "INSERT INTO messages (user_id, sender, recipient, body, time_label, is_read, direction) VALUES (?,?,?,?,?,?,?)",
        [
            (1, "이매니저", "김민수",
             "민수님, 오늘 오후 2시 화상회의 링크 메일로 보내드렸습니다. 수어 통역사분도 함께 참석하실 예정입니다. 회의 전 마이크/카메라 테스트 부탁드립니다.",
             "오늘 오전 10:30", 0, "in"),
            (1, "박팀장", "김민수",
             "접근성 보고서 초안 확인했습니다. 수정 요청사항 코멘트로 남겨두었으니 확인 부탁드립니다. 수고하셨습니다! 내일 오전 중으로 수정본 다시 공유해주세요.",
             "어제 오후 04:15", 0, "in"),
            (1, "최사원", "김민수",
             "선배님, 요청하신 고객사 영수증 데이터 스캔본 폴더에 업로드 완료했습니다. 확인 부탁드립니다.",
             "수요일 오전 09:00", 1, "in"),
            (1, "시스템 알림", "김민수",
             "[알림] 5월 급여 명세서가 발급되었습니다. 인트라넷 마이페이지에서 확인하실 수 있습니다.",
             "화요일 오후 01:00", 1, "in"),
            (1, "김민수", "이매니저",
             "네 알겠습니다! 2시 전에 테스트해 두겠습니다. 통역사분께 인사 전해주세요.",
             "오늘 오전 10:45", 1, "out"),
        ]
    )

    # ===== ERP 문서 =====
    c.executemany(
        "INSERT INTO erp_docs (user_id, doc_type, title, content, dept, due_label, status) VALUES (?,?,?,?,?,?,?)",
        [
            (1, "draft", "[긴급] 개인정보보호 규정 개정 내부 공람",
             "1. 목적\n  2026년 8월 시행 개인정보보호법 개정사항을 내부 규정에 반영하기 위한 공람입니다.\n\n2. 주요 내용\n  - 개인정보 보유기간 단축 (5년 → 3년) 적용 부서 안내\n  - 개인정보 처리방침 고지문 문구 수정 (제3조, 제7조 해당)\n  - 동의서 양식 개정본 배포 및 기존 양식 폐기 일정 공지\n\n3. 시행 일정\n  개정 규정 적용: 2026-09-01부터\n  의견 제출 마감: 2026-08-18 18:00\n\n4. 비고\n  의견 있으신 분은 법무팀 이슬기(내선 214)로 오늘 18시까지 회신 부탁드립니다.",
             "법무팀", "오늘 18:00 마감", "urgent"),
            (1, "draft", "전사 복리후생 개편안 검토 요청",
             "1. 목적\n  2026년 상반기 직원 만족도 조사(응답 87명, 응답률 72%) 결과를 반영한 복리후생 개편안 검토를 요청합니다.\n\n2. 주요 내용\n  - 선택적 복리후생 포인트 연 120만원 → 150만원 상향 (안)\n  - 재택근무 월 8일 → 12일 확대 (안)\n  - 경조사 지원금 현행 유지, 문화생활비 항목 신설 (연 24만원 한도)\n\n3. 시행 일정\n  의견 수렴: 8/15까지\n  최종안 확정: 8/25\n  시행 예정: 2026-10-01\n\n4. 비고\n  부서별 의견은 경영지원팀 김민수(내선 101)로 취합해주세요.",
             "경영지원팀", "8/15 까지", "progress"),
            (1, "draft", "2026년 하반기 사업계획서 결재 기안",
             "1. 목적\n  2026년 하반기(9~12월) 사업 방향 및 예산 집행 계획에 대한 결재를 요청합니다.\n\n2. 주요 내용\n  - 하반기 총 예산: 4억 2,000만원 (전년 동기 대비 8% 증가)\n  - 신규 프로젝트 3건 착수 (ERP 고도화, 모바일 앱 개편, 영업망 확대)\n  - 인력 충원 계획: 개발직 2명, 영업직 1명\n\n3. 시행 일정\n  결재 완료 목표: 8/20\n  하반기 킥오프 미팅: 9/2\n\n4. 비고\n  세부 예산 배분표 및 프로젝트별 WBS는 첨부 파일 참조 바랍니다.",
             "경영지원팀", "8/20 까지", "wait"),
            (1, "hr_task", "[휴가승인] 개발팀 이대리 연차 휴가 신청 (8/10 ~ 8/12)",
             "1. 대상자\n  성명: 이준혁 / 부서: 개발1팀 / 직위: 대리\n\n2. 신청 내용\n  휴가 유형: 연차 휴가\n  휴가 기간: 2026-08-10(월) ~ 2026-08-12(수), 3일\n  잔여 연차: 신청 후 4일 남음\n  업무 대행: 박철수 과장 (진행 중인 API 연동 건 인수인계 완료)\n\n3. 비고\n  복귀일: 2026-08-13(목)\n  긴급 연락처: 010-xxxx-1234 (휴가 중 연락 가능)",
             "개발1팀", "오늘 18:00 마감", "urgent"),
            (1, "hr_task", "[채용] 프론트엔드 개발자 서류 심사 결과 승인",
             "1. 대상자\n  채용 직무: 프론트엔드 개발자 / 부서: 개발1팀 / 채용 인원: 1명\n\n2. 신청 내용\n  지원자 현황: 총 15명 접수\n  서류 합격자: 5명 선정\n  탈락 사유: 포트폴리오 미제출 4명, 필수 스킬 미달 6명\n  면접 일정: 2026-08-19(화) 오전 10시부터, 개별 안내 예정\n\n3. 비고\n  합격자 5명 명단은 채용팀 공유 폴더에 업로드 완료.\n  최종 합격자 발표: 8/22 예정.",
             "채용팀", "8/14 12:00", "wait"),
            (2, "hr_task", "[교육] 하반기 직무교육 이수 현황 확인",
             "1. 대상자\n  성명: 전체 임직원 / 부서: 전사 / 직위: 전 직급\n\n2. 신청 내용\n  하반기 필수 직무교육 과목: 3개 (정보보안, 개인정보, 직장내 괴롭힘 예방)\n  이수 완료: 61명 / 전체 대상: 74명\n  미이수자: 13명 (명단 별첨)\n  이수 마감: 2026-08-20\n\n3. 비고\n  미이수자에게는 오늘 중 개별 안내 메일 발송 예정.\n  마감일 이후 미이수 시 부서장 보고 조치합니다.",
             "인사팀", "8/20 까지", "progress"),
            (1, "hr_task", "[징계위원회] 취업규칙 위반 사유서 검토 완료",
             "1. 대상자\n  성명: (비공개) / 부서: 생산팀 / 직위: 사원\n\n2. 신청 내용\n  위반 사항: 취업규칙 제22조 (무단결근 3회 이상)\n  사유서 제출일: 2026-08-01\n  징계위원회 심의일: 2026-08-05\n  심의 결과: 경고 처분 (서면 경고, 향후 6개월 관찰)\n\n3. 비고\n  처분 통보서는 인사팀에서 당사자에게 직접 전달 완료.\n  관련 기록은 인사 파일에 보관.",
             "인사팀", "8/5 완료", "done"),
            (3, "stock_move", "[긴급] 서버 부품 반출 승인 요청",
             "1. 이동 사유\n  노후 서버 교체에 따른 기존 장비 폐기 처리. 2021년 이전 도입 장비로 보증 기간 만료 및 유지보수 계약 종료.\n\n2. 품목 내역\n  - PowerEdge R440 (SN: PE44-0812) / 1대 / 폐기 예정\n  - 16GB DDR4 RAM 모듈 / 8개 / 재활용 검토\n  - 2.5인치 SATA SSD 960GB / 4개 / 데이터 완전 삭제 후 폐기\n\n3. 보관 장소\n  서버실 랙 A-3 → 1층 자산폐기 임시보관소",
             "IT 지원팀", "오늘 15:00", "urgent"),
            (1, "stock_move", "3분기 사무용품 재고 조사 결과 상신",
             "1. 이동 사유\n  3분기 정기 재고 조사 완료. 일부 품목 재고 부족으로 추가 발주 필요.\n\n2. 품목 내역\n  - A4용지 80g (박스) / 현재 12박스 / 적정 재고 30박스, 18박스 발주 필요\n  - 볼펜(흑색, 12자루입) / 현재 3묶음 / 발주 불필요\n  - 토너 카트리지 HP CF217A / 현재 0개 / 즉시 발주 필요\n  - 포스트잇 76x76mm / 현재 8팩 / 발주 불필요\n\n3. 보관 장소\n  2층 문서고 D-선반 (현 재고 위치)",
             "총무팀", "8/18 까지", "wait"),
            (2, "stock_move", "A4용지 500박스 입고 처리",
             "1. 이동 사유\n  3분기 재고 부족 해소를 위한 A4용지 대량 발주분 입고 처리.\n\n2. 품목 내역\n  - A4용지 80g, 500매입 (더블A) / 500박스 / 이상 없음 확인\n\n3. 보관 장소\n  물류창고 입고 게이트 → 2층 문서고 D-선반 (분산 적재 완료)\n  재고 시스템 수량 업데이트: 2026-08-01 14:30 완료",
             "물류창고", "8/1 완료", "done"),
            (1, "work_order", "웹 접근성 개선 작업 지시서 - 스크린리더 대응",
             "1. 작업 개요\n  사내 포털 주요 페이지의 스크린리더 호환성을 WCAG 2.1 AA 기준에 맞게 개선합니다.\n\n2. 작업 범위\n  - 메인 대시보드: aria-label 누락 버튼 12개 속성 추가\n  - 공지사항 목록: 키보드 포커스 순서 재정의\n  - 모달 창: focus trap 및 role=dialog 적용\n  - 이미지 전체: alt 텍스트 보완 (약 40건)\n\n3. 작업 일정\n  착수: 2026-08-13 / 완료 목표: 2026-08-20\n\n4. 안전 유의사항\n  운영 서버 직접 수정 금지. 개발 서버에서 검증 후 배포 절차 준수.",
             "IT 지원팀", "8/20 까지", "progress"),
            (3, "work_order", "사옥 3층 인테리어 보수 작업 지시",
             "1. 작업 개요\n  3층 회의실(301호, 302호) 및 복도 노후 도배, 바닥재 교체 작업을 지시합니다.\n\n2. 작업 범위\n  - 301호 회의실: 벽지 전면 교체, 바닥 장판 교체 (약 42㎡)\n  - 302호 회의실: 벽지 부분 보수, 바닥 타일 줄눈 보수\n  - 3층 복도: 천장 도장 재도색 (약 18m 구간)\n\n3. 작업 일정\n  착수: 2026-08-22(토) 오후 6시 / 완료 목표: 2026-08-24(월) 오전 7시\n\n4. 안전 유의사항\n  야간 작업이므로 비상구 통로 확보 필수. 작업 전 경비실 사전 통보.",
             "총무팀", "8/25 까지", "wait"),
            (2, "work_order", "생산라인 B 정기 점검 작업지시서",
             "1. 작업 개요\n  생산라인 B 구역 월간 정기 점검을 실시합니다.\n\n2. 작업 범위\n  - 컨베이어 벨트 마모 상태 육안 점검\n  - 유압 실린더 오일 잔량 및 누유 확인\n  - 비상정지 버튼 동작 테스트 (전 구역 12개소)\n  - 집진 필터 교체 (B-3 라인 1개)\n\n3. 작업 일정\n  실시일: 2026-08-12 / 점검 시간: 오전 7시~11시\n\n4. 안전 유의사항\n  점검 중 라인 가동 중단 필수. 잠금장치(LOTO) 적용 확인 후 작업 진입.",
             "생산팀", "8/12 완료", "done"),
            (1, "po", "스크린리더 소프트웨어 라이선스 발주",
             "1. 발주 사유\n  웹 접근성 개선 작업 및 QA 테스트용 스크린리더 소프트웨어 라이선스가 필요합니다.\n\n2. 발주 품목\n  - NVDA (NonVisual Desktop Access) 기업 기부금 라이선스 / 5카피 / 카피당 50,000원 / 합계 250,000원\n  - JAWS Professional 연간 라이선스 / 2카피 / 카피당 1,200,000원 / 합계 2,400,000원\n\n3. 납품 조건\n  납품일: 2026-08-20 / 납품처: IT 지원팀 (담당: 김민수)\n  결제조건: 계산서 발행 후 30일 이내 계좌이체",
             "IT 지원팀", "8/15 승인 필요", "progress"),
            (1, "po", "Dell PowerEdge R750 서버 2대 발주",
             "1. 발주 사유\n  2021년 도입 서버의 보증 만료 및 성능 한계로 교체가 필요합니다.\n\n2. 발주 품목\n  - Dell PowerEdge R750 (Xeon Silver 4314, 32GB RAM, 1.8TB SSD) / 2대 / 대당 8,500,000원 / 합계 17,000,000원\n  - 3년 ProSupport Plus 유지보수 / 2식 / 식당 850,000원 / 합계 1,700,000원\n\n3. 납품 조건\n  납품일: 2026-08-30 / 납품처: 사옥 1층 서버실 (반입 사전 조율 필요)\n  결제조건: 납품 확인 후 세금계산서 기준 60일 이내",
             "IT 지원팀", "결제 대기", "wait"),
            (3, "po", "사무용 노트북 10대 구매 발주서",
             "1. 발주 사유\n  신규 입사자 3명 및 노후 장비(4년 이상) 교체 대상 7명에게 지급할 노트북 발주.\n\n2. 발주 품목\n  - LG그램 16 (16ZD90S, i5-1340P, 16GB, 512GB) / 10대 / 대당 1,490,000원 / 합계 14,900,000원\n\n3. 납품 조건\n  납품일: 2026-08-08 / 납품처: 총무팀 창고 (담당: 박철수)\n  결제조건: 세금계산서 발행 후 당월 말일 지급\n  수령 확인: 2026-08-10 완료",
             "총무팀", "8/10 완료", "done"),
            (2, "activity", "B2B 고객사 니즈 현장 조사 계획서",
             "1. 목적\n  신규 B2B 계약 발굴을 위해 잠재 고객사 3곳의 현장을 직접 방문하여 니즈를 파악합니다.\n\n2. 활동 내용\n  방문 일정:\n  - (주)한라산업: 2026-08-18(월) 오전 10시, 담당 구매팀장 미팅\n  - 세종물산: 2026-08-19(화) 오후 2시, 물류 현장 투어 + 인터뷰\n  - 대명테크: 2026-08-20(수) 오전 11시, IT 인프라 담당자 면담\n  인터뷰 항목: 현 시스템 불편 사항, 도입 예산 범위, 의사결정 구조\n\n3. 결과 및 향후 계획\n  방문 완료 후 각 고객사별 니즈 분석 보고서 작성, 8/22까지 영업팀장에게 공유 예정.",
             "영업팀", "8/16 까지", "progress"),
            (1, "activity", "상반기 고객 만족도 설문 결과 분석",
             "1. 목적\n  상반기 서비스 품질 점검 및 하반기 개선 방향 도출을 위해 고객 만족도 설문 결과를 분석합니다.\n\n2. 활동 내용\n  설문 기간: 2026-07-01 ~ 07-31\n  응답 고객사: 142개사 (배포 200개사, 응답률 71%)\n  주요 결과:\n  - 전체 만족도: 4.1점 / 5점\n  - 불만 상위 항목: 납기 지연(32%), 사후 대응 속도(27%)\n  - 재계약 의향 있음: 118개사(83%)\n\n3. 결과 및 향후 계획\n  납기 관리 프로세스 개선안을 9/1까지 경영전략팀에 제출 예정. 불만 상위 고객사 15곳은 담당 영업이 직접 재방문.",
             "경영전략팀", "8/20 까지", "wait"),
            (1, "activity", "거래처 A사 신규 계약 미팅 완료보고",
             "1. 목적\n  거래처 A사((주)한라산업)와의 신규 IT 유지보수 용역 계약 체결 논의 미팅 완료 보고.\n\n2. 활동 내용\n  미팅 일시: 2026-08-07(목) 오후 3시\n  참석자: 당사 김민수 과장, 이준혁 대리 / A사 구매팀장, 실무 담당자\n  논의 내용: 계약 범위(월 유지보수 + 장애 대응 4시간 SLA), 계약 금액 연 3,600만원, 계약 기간 1년\n  결과: 양사 합의 완료, 계약서 초안 공유\n\n3. 결과 및 향후 계획\n  계약서 법무팀 검토 중(8/10 완료 예정). 검토 완료 후 양사 날인 진행.",
             "영업팀", "8/8 완료", "done"),
            (1, "expense", "8월 법인카드 사용내역 정산 (합계: 1,230,000원)",
             "1. 지출 목적\n  8월 1일~10일 업무 관련 법인카드 사용내역 정산 요청입니다.\n\n2. 지출 내역\n  - 거래처 접대비 (한라산업 미팅 식사) / 87,000원\n  - 사무용품 구매 (온라인 주문) / 143,000원\n  - 교통비 (출장 택시, KTX) / 215,000원\n  - 팀 회식 (8/5, 인원 8명) / 456,000원\n  - 소프트웨어 구독료 (어도비 CC) / 329,000원\n\n3. 합계: 1,230,000원\n  영수증 스캔본 전체 첨부. 팀 회식 건은 부서장 사전 승인 완료.",
             "경영지원팀", "8/15 마감", "wait"),
            (2, "expense", "일본 출장비 선지급 신청 (합계: 850,000원)",
             "1. 지출 목적\n  도쿄 거래처 방문 출장(2026-08-18~20, 2박3일) 관련 경비 선지급 신청입니다.\n\n2. 지출 내역\n  - 왕복 항공권 (인천~나리타, 이코노미) / 420,000원\n  - 숙박비 (2박, 신주쿠 비즈니스호텔) / 280,000원\n  - 현지 교통비 및 통신비 예상액 / 90,000원\n  - 식비 (일당 기준 1일 30,000원 x 3일) / 60,000원\n\n3. 합계: 850,000원\n  복귀 후 7일 이내 영수증 정산 및 차액 반환 처리 예정.",
             "영업팀", "8/9 완료", "done"),
            (3, "expense", "사무용품 구매 비용 지출결의서 (합계: 320,000원)",
             "1. 지출 목적\n  총무팀 비품 부족분 긴급 구매 비용 정산 요청입니다.\n\n2. 지출 내역\n  - A4용지 80g 5박스 / 55,000원\n  - HP 토너 카트리지 CF217A / 89,000원\n  - 무선 마우스 (직원 요청, 2개) / 58,000원\n  - 파일 바인더 10개입 / 23,000원\n  - 화이트보드 마커 세트 5개 / 15,000원\n  - 포스트잇, 스테이플러심 등 소모품 / 80,000원\n\n3. 합계: 320,000원\n  현금 영수증 발행 완료. 담당자 개인카드 선결제 건으로 즉시 정산 요청.",
             "총무팀", "승인 대기", "pending"),
            # 고객 VOC (activity + urgent 상태로 조회됨)
            (2, "activity", "[VOC] 배송 지연 관련 고객 불만 접수 - (주)한빛유통",
             "1. 접수 내용\n  고객사: (주)한빛유통 / 접수일: 2026-08-14 / 담당: 이준혁 대리\n\n2. 상세\n  8/11 출고 예정 물량(팔레트 3개, 약 180개)이 8/14 현재까지 미도착.\n  고객사 측 재고가 오늘 중 소진 예정으로 생산 라인 중단 우려 제기.\n  운송사(대한통운) 확인 결과 차량 배차 오류로 발송 자체가 지연된 상태.\n\n3. 요청 사항\n  오늘 오후 3시까지 긴급 배차 재조율 및 고객사 도착 예정일 확인 회신 필요.\n  유사 재발 방지를 위한 출고 확인 프로세스 개선안 검토 요청.",
             "영업팀", "긴급 처리", "urgent"),
            (1, "activity", "[VOC] 납품 제품 파손 교환 요청 - 세종상사",
             "1. 접수 내용\n  고객사: 세종상사 / 접수일: 2026-08-13 / 담당: 김민수 과장\n\n2. 상세\n  8/10 납품 제품 20개 중 3개(박스 외포 파손, 내용물 긁힘)를 수령 시 발견.\n  고객사에서 사진 자료 4장 첨부하여 교환 요청 접수.\n  해당 물량은 2층 창고에서 직접 포장하여 출고한 건으로, 포장 불량 가능성 있음.\n\n3. 요청 사항\n  교환품 금일 중 출고 처리 및 파손품 회수 일정 조율 필요.\n  포장 담당자 확인 및 포장 기준 재교육 검토 요청.",
             "영업팀", "금일 회신", "urgent"),
            (2, "activity", "[VOC] 견적서 금액 오류 정정 요청 - 대명테크",
             "1. 접수 내용\n  고객사: 대명테크 / 접수일: 2026-08-14 / 담당: 이준혁 대리\n\n2. 상세\n  2026-08-12 발행 견적서(GW-2026-0047) 내 품목 단가 오류 확인.\n  협의 단가: 개당 45,000원 / 견적서 기재 단가: 개당 54,000원 (9,000원 초과 기재)\n  수량 20개 기준으로 180,000원 차이 발생. 고객사 계약 검토 담당자가 불일치 발견 후 문의.\n\n3. 요청 사항\n  정정 견적서 오늘 중 재발행 및 이메일 발송 필요.\n  내부 견적 승인 프로세스에서 금액 검토 단계 추가 검토 요청.",
             "영업팀", "긴급 처리", "urgent"),
        ]
    )

    # ===== ERP 문서 첨부파일 =====
    attachment_samples = [
        (1, "개인정보보호_규정_개정안.pdf|1e62743edb34405f9776969615f7ed0c.pdf"),
        (3, "2026년_하반기_예산안.xlsx|3fa60ece702e4a4b914788b71278c15b.xlsx"),
        (5, "인사발령_통지서.pdf|645d7d653c214a21a1a0eefc593e817f.pdf"),
        (7, "발주요청서_IT장비.pdf|7eec9571cb564bf9b404b09e659b49cb.pdf"),
        (9, "품질검사_결과보고.xlsx|8752bce24fa04bd9a8e477d3b3c82472.xlsx"),
        (11, "출장비_정산서.pdf|b8f06fbcbdd1433ab9510834005ebfe9.pdf"),
        (13, "신규입사자_교육계획.pdf|c50ca409c41b4edd8f8821c7ffb8382b.pdf"),
    ]
    for doc_id, att in attachment_samples:
        c.execute("UPDATE erp_docs SET attachment=? WHERE id=?", (att, doc_id))

    # ===== doc_number 생성 =====
    DOC_NUMBER_PREFIXES = {
        "draft": "GW", "hr_task": "HR", "stock_move": "INV",
        "work_order": "WO", "po": "PO", "activity": "CRM", "expense": "EXP",
    }
    docs = c.execute("SELECT id, doc_type FROM erp_docs ORDER BY id").fetchall()
    counters = {}
    for doc in docs:
        dtype = doc[1]
        prefix = DOC_NUMBER_PREFIXES.get(dtype, "DOC")
        counters[dtype] = counters.get(dtype, 0) + 1
        doc_number = f"{prefix}-2026-{counters[dtype]:04d}"
        c.execute("UPDATE erp_docs SET doc_number=? WHERE id=?", (doc_number, doc[0]))

    # ===== approval_lines =====
    docs_full = c.execute("SELECT id, user_id, status, created_at FROM erp_docs").fetchall()
    for doc in docs_full:
        doc_id, uid, status, created = doc[0], doc[1], doc[2], doc[3]
        c.execute(
            "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, acted_at) VALUES (?,?,?,?,?,?)",
            (doc_id, 0, uid, "기안", "approved", created))

        if status in ("done", "approved", "resolved"):
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, acted_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 1, 2, "검토", "approved", created))
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, acted_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 2, 3, "승인", "approved", created))
        elif status == "rejected":
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, comment, acted_at) VALUES (?,?,?,?,?,?,?)",
                (doc_id, 1, 2, "검토", "rejected", "요건 재검토 필요", created))
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
                (doc_id, 2, 3, "승인", "pending"))
        elif status in ("urgent", "progress", "in_progress"):
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status, acted_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 1, 2, "검토", "approved", created))
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
                (doc_id, 2, 3, "승인", "pending"))
        else:
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
                (doc_id, 1, 2, "검토", "pending"))
            c.execute(
                "INSERT INTO approval_lines (doc_id, step, approver_id, role, status) VALUES (?,?,?,?,?)",
                (doc_id, 2, 3, "승인", "pending"))

    # ===== doc_history =====
    for doc in docs_full:
        doc_id, uid, status, created = doc[0], doc[1], doc[2], doc[3]
        drafter = c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
        drafter_name = drafter[0] if drafter else "Unknown"

        c.execute(
            "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment, created_at) VALUES (?,?,?,?,?,?)",
            (doc_id, uid, drafter_name, "기안", "문서 기안", created))

        if status in ("done", "approved", "resolved"):
            reviewer = c.execute("SELECT name FROM users WHERE id=?", (2,)).fetchone()
            approver = c.execute("SELECT name FROM users WHERE id=?", (3,)).fetchone()
            c.execute(
                "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment, created_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 2, reviewer[0], "승인", "검토 완료", created))
            c.execute(
                "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment, created_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 3, approver[0], "승인", "최종 승인", created))
        elif status == "rejected":
            reviewer = c.execute("SELECT name FROM users WHERE id=?", (2,)).fetchone()
            c.execute(
                "INSERT INTO doc_history (doc_id, user_id, user_name, action, comment, created_at) VALUES (?,?,?,?,?,?)",
                (doc_id, 2, reviewer[0], "반려", "요건 재검토 필요", created))

    # ===== 채용 공고 =====
    c.executemany(
        "INSERT INTO job_postings (company, title, region, employment_type, disability_friendly, salary, deadline, description) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("한국장애인고용공단 협력사", "웹 접근성 QA 담당자",
             "서울", "정규직", "재택근무 가능, 수어통역 지원",
             "2,800~3,500만원", "2026-09-30",
             "웹 사이트 및 앱의 접근성 진단/개선 가이드 작성 담당. WCAG 기준 이해 가능자 우대. 장애인 고용촉진법에 따른 우선 채용."),
            ("(주)디지털인클루전", "사내 시스템 운영 및 IT 지원",
             "경기", "계약직", "출퇴근 시간 탄력 운영, 보조공학기기 지원",
             "2,400~2,800만원", "2026-09-15",
             "사내 그룹웨어/ERP 운영 지원 및 1차 IT 헬프데스크 담당. 지체/시각장애인 지원 가능 환경 완비."),
            ("(재)장애인고용촉진연구원", "데이터 입력 및 통계 보조",
             "서울", "시간제", "단순 반복 업무, 주 20시간 이내",
             "시급 10,500원", "2026-09-10",
             "연구 자료 데이터 입력 및 통계 집계 보조. 엑셀 기초 사용 가능자. 장애 유형 무관 지원 가능."),
            ("소셜임팩트(주)", "SNS 콘텐츠 기획 및 채널 운영",
             "서울", "정규직", "재택근무 병행 가능, 영상통화 수어통역 지원",
             "2,600~3,200만원", "2026-09-20",
             "인스타그램/유튜브 콘텐츠 기획 및 채널 운영 담당. 청각/언어장애인 지원 가능 업무 환경."),
            ("(주)드림테크솔루션", "소프트웨어 QA 테스터",
             "부산", "정규직", "휠체어 접근 가능 사옥, 전동 승강기 완비",
             "3,000~3,800만원", "2026-10-05",
             "웹/모바일 앱 기능 테스트 및 버그 리포트 작성. 지체장애인 친화적 업무 공간 및 주차 지원."),
            ("(주)그린케어서비스", "전화 상담사 (문자/영상통화 기반)",
             "인천", "정규직", "청각장애 가능 직종, 문자/영상통화 기반 상담",
             "2,200~2,600만원", "2026-09-25",
             "문자/채팅 기반 고객 상담 업무. 청각장애인 가능 직종으로 음성 통화 불필요. 관련 장비 전액 지원."),
            ("서울시장애인복지관", "행정 지원 및 문서 관리",
             "서울", "정규직", "장애인 우대 공채, 편의시설 완비",
             "회사내규", "2026-09-30",
             "복지관 행정 문서 작성/관리 및 민원 응대 지원. 장애인 우대 채용, 무장애 시설 완비. 복리후생 우수."),
            ("(주)이지크리에이티브", "그래픽 디자이너 (UI 작업)",
             "경기", "정규직", "재택근무 상시 가능, 보조기기 지원",
             "2,800~3,400만원", "2026-09-28",
             "웹/앱 UI 디자인 및 마케팅 시각물 제작. 피그마 사용 가능자. 재택근무 풀타임 가능, 지체장애인 환영."),
        ]
    )

    # ===== 알림 =====
    c.executemany(
        "INSERT INTO notifications (user_id, icon, title, body, time_label, is_read) VALUES (?,?,?,?,?,?)",
        [
            (1, "fas fa-bell", "새 업무가 배정되었습니다",
             "이매니저님이 '웹 접근성 보고서 작성' 업무를 배정했습니다.", "10분 전", 0),
            (1, "fas fa-comment-dots", "커뮤니티 댓글 알림",
             "내가 작성한 글에 새 댓글이 등록되었습니다.", "1시간 전", 0),
            (1, "far fa-check-circle", "AS 요청이 처리되었습니다",
             "'Wi-Fi 속도 저하' 건이 완료 처리되었습니다.", "어제", 1),
            (1, "fas fa-file-signature", "결재 문서가 승인되었습니다",
             "상신하신 '하반기 사업계획서'가 최종 승인되었습니다.", "2일 전", 1),
            (1, "fas fa-user-plus", "신규 회원이 가입했습니다",
             "이영희님이 시스템에 가입했습니다.", "3일 전", 1),
        ]
    )

    # ===== 계정과목 =====
    c.executemany(
        "INSERT INTO accounts (code, name, category, is_debit) VALUES (?,?,?,?)",
        [
            ("101","현금","자산",1),("102","당좌예금","자산",1),("103","보통예금","자산",1),
            ("104","정기예금","자산",1),("108","외상매출금","자산",1),("110","받을어음","자산",1),
            ("112","미수금","자산",1),("114","선급금","자산",1),("115","선급비용","자산",1),
            ("116","부가세대급금","자산",1),("120","상품","자산",1),("121","제품","자산",1),
            ("122","원재료","자산",1),("150","건물","자산",1),("152","비품","자산",1),
            ("153","차량운반구","자산",1),("155","토지","자산",1),
            ("201","외상매입금","부채",0),("202","지급어음","부채",0),("204","미지급금","부채",0),
            ("205","미지급비용","부채",0),("206","선수금","부채",0),("207","예수금","부채",0),
            ("208","부가세예수금","부채",0),("210","단기차입금","부채",0),("215","장기차입금","부채",0),
            ("301","자본금","자본",0),("310","이익잉여금","자본",0),
            ("401","상품매출","수익",0),("402","제품매출","수익",0),("403","용역매출","수익",0),
            ("410","이자수익","수익",0),("490","잡이익","수익",0),
            ("501","급여","비용",1),("502","상여금","비용",1),("503","퇴직급여","비용",1),
            ("510","복리후생비","비용",1),("511","여비교통비","비용",1),("512","접대비","비용",1),
            ("513","통신비","비용",1),("514","수도광열비","비용",1),("515","세금과공과","비용",1),
            ("516","감가상각비","비용",1),("517","임차료","비용",1),("518","수선비","비용",1),
            ("519","보험료","비용",1),("520","차량유지비","비용",1),("521","운반비","비용",1),
            ("522","교육훈련비","비용",1),("523","도서인쇄비","비용",1),("524","소모품비","비용",1),
            ("525","지급수수료","비용",1),("526","광고선전비","비용",1),("527","대손상각비","비용",1),
            ("590","잡손실","비용",1),("591","이자비용","비용",1),
        ]
    )

    # ===== 거래처 =====
    c.executemany(
        "INSERT INTO partners (code, name, biz_no, representative, biz_type, biz_item) VALUES (?,?,?,?,?,?)",
        [
            ("V001","(주)한라산업","123-45-67890","김한라","제조업","산업용 부품"),
            ("V002","세종물산","234-56-78901","이세종","도소매","사무용품"),
            ("V003","대명테크","345-67-89012","박대명","서비스","IT 솔루션"),
            ("V004","(주)한빛유통","456-78-90123","최한빛","도소매","유통"),
            ("V005","더블에이코리아","567-89-01234","정더블","제조업","제지"),
            ("V006","Dell Technologies","678-90-12345","Michael Dell","제조업","서버/PC"),
            ("V007","LG전자","789-01-23456","조주완","제조업","전자제품"),
            ("V008","Adobe Korea","890-12-34567","—","서비스","소프트웨어"),
        ]
    )

    conn.commit()
    conn.close()
    print(f"DB initialized ({_DB_SCHEME})")


if __name__ == "__main__":
    init()
