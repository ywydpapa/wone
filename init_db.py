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
          "job_applications", "approval_lines", "doc_history", "slip_lines"]


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
             "2026년 하반기 개인정보보호법 개정사항을 반영한 내부 규정 개정안 공람 요청",
             "법무팀", "오늘 18:00 마감", "urgent"),
            (1, "draft", "전사 복리후생 개편안 검토 요청",
             "직원 만족도 조사 결과를 바탕으로 한 복리후생 제도 개편안 검토 및 의견 수렴",
             "경영지원팀", "8/15 까지", "progress"),
            (1, "draft", "2026년 하반기 사업계획서 결재 기안",
             "2026년 하반기 신규 프로젝트 예산 및 인력 계획 수립안",
             "경영지원팀", "8/20 까지", "wait"),
            (1, "hr_task", "[휴가승인] 개발팀 이대리 연차 휴가 신청 (8/10 ~ 8/12)",
             "개발팀 이대리 연차 3일 휴가 신청. 대리업무: 박철수 과장",
             "개발1팀", "오늘 18:00 마감", "urgent"),
            (1, "hr_task", "[채용] 프론트엔드 개발자 서류 심사 결과 승인",
             "8월 2차 채용 프론트엔드 개발자 지원자 15명 중 서류 합격자 5명 선정 승인 요청",
             "채용팀", "8/14 12:00", "wait"),
            (2, "hr_task", "[교육] 하반기 직무교육 이수 현황 확인",
             "하반기 필수 직무교육 대상자 이수 현황 확인 및 미이수자 안내",
             "인사팀", "8/20 까지", "progress"),
            (1, "hr_task", "[징계위원회] 취업규칙 위반 사유서 검토 완료",
             "해당 직원의 사유서 검토 및 징계위원회 의견 첨부 완료",
             "인사팀", "8/5 완료", "done"),
            (3, "stock_move", "[긴급] 서버 부품 반출 승인 요청",
             "노후 서버 교체를 위한 기존 부품 반출 승인 요청. 처분 예정 장비 목록 첨부",
             "IT 지원팀", "오늘 15:00", "urgent"),
            (1, "stock_move", "3분기 사무용품 재고 조사 결과 상신",
             "3분기 사무용품 재고 현황 조사 완료. A4용지 잔량 부족으로 추가 발주 요청 포함",
             "총무팀", "8/18 까지", "wait"),
            (2, "stock_move", "A4용지 500박스 입고 처리",
             "8월분 A4용지 500박스 창고 입고 완료. 재고 시스템 업데이트 완료",
             "물류창고", "8/1 완료", "done"),
            (1, "work_order", "웹 접근성 개선 작업 지시서 - 스크린리더 대응",
             "사내 포털 주요 페이지 스크린리더 호환성 개선 작업 지시. WCAG 2.1 AA 기준 적용",
             "IT 지원팀", "8/20 까지", "progress"),
            (3, "work_order", "사옥 3층 인테리어 보수 작업 지시",
             "3층 회의실 및 복도 도배/바닥재 교체 작업 지시. 업무 외 시간(야간) 시공",
             "총무팀", "8/25 까지", "wait"),
            (2, "work_order", "생산라인 B 정기 점검 작업지시서",
             "생산라인 B 구역 월간 정기 점검 완료. 이상 없음 확인",
             "생산팀", "8/12 완료", "done"),
            (1, "po", "스크린리더 소프트웨어 라이선스 발주",
             "NVDA Enterprise 라이선스 5카피 발주 요청. 연간 유지보수 포함",
             "IT 지원팀", "8/15 승인 필요", "progress"),
            (1, "po", "Dell PowerEdge R750 서버 2대 발주",
             "노후 서버 교체용 Dell PowerEdge R750 서버 2대 발주 요청. 견적서 첨부",
             "IT 지원팀", "결제 대기", "wait"),
            (3, "po", "사무용 노트북 10대 구매 발주서",
             "신규 입사자 및 노후 장비 교체용 노트북 10대 발주 완료 및 수령 확인",
             "총무팀", "8/10 완료", "done"),
            (2, "activity", "B2B 고객사 니즈 현장 조사 계획서",
             "잠재 고객사 3곳 현장 방문 일정 및 인터뷰 항목 계획서 작성",
             "영업팀", "8/16 까지", "progress"),
            (1, "activity", "상반기 고객 만족도 설문 결과 분석",
             "상반기 고객 만족도 설문(응답자 142명) 결과 분석 및 개선 방향 도출",
             "경영전략팀", "8/20 까지", "wait"),
            (1, "activity", "거래처 A사 신규 계약 미팅 완료보고",
             "거래처 A사와의 신규 용역 계약 체결 미팅 완료. 계약서 법무팀 검토 중",
             "영업팀", "8/8 완료", "done"),
            (1, "expense", "8월 법인카드 사용내역 정산 (합계: 1,230,000원)",
             "8월 1일~10일 법인카드 사용내역 정산 요청. 합계: 1,230,000원. 영수증 스캔본 첨부",
             "경영지원팀", "8/15 마감", "wait"),
            (2, "expense", "일본 출장비 선지급 신청 (합계: 850,000원)",
             "도쿄 출장 2박3일 항공/숙박/식비 선지급 신청. 합계: 850,000원",
             "영업팀", "8/9 완료", "done"),
            (3, "expense", "사무용품 구매 비용 지출결의서 (합계: 320,000원)",
             "A4용지, 토너 카트리지 등 소모품 구매비용 정산. 합계: 320,000원",
             "총무팀", "승인 대기", "pending"),
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

    conn.commit()
    conn.close()
    print(f"DB initialized ({_DB_SCHEME})")


if __name__ == "__main__":
    init()
