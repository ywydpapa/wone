# 변경 이력

## 2026-08-13 전체 샘플 기능 구현 완료 (Tasks 1–13)

### 기반 (Tasks 1–3)
- SQLite 스키마 전면 개편: 11개 테이블 (users/jobs/messages/posts/comments/post_likes/bookmarks/erp_docs/job_postings/notifications/messages)
- 로그인 DB 검증, 회원가입(/signup), topbar 개인화(세션 user_name)
- 업무 대시보드 체크박스 완료 토글, 메시지 읽음 처리 API

### 커뮤니티·ERP·채용·AS (Tasks 4–9)
- 커뮤니티: 카테고리 필터/검색/페이지네이션, 게시글 상세(조회수·댓글·좋아요·스크랩)
- ERP 7개 모듈 문서 리스트 DB 연동 + erp_dash 통계
- ERP 문서 상세 승인/반려 결재 (`POST /api/erp_docs/{id}/status`)
- 채용 공고 목록/상세 DB 연동 (장애인 친화 8건 시드)
- AS 접수 내역 세션 유저 기준 조회 + user_id 세션화

### 스텁 17개 샘플 페이지화 (Tasks 10–12)
- /profile: DB 실데이터 + 활동 통계, 이름/부서/연락처 수정 지원
- /notifications: notifications 테이블 루프, 전체 읽음 처리
- /accessibility: 글자 크기·고대비 모드 localStorage 저장
- /faq: Bootstrap accordion 8문항, /guide: 6섹션 앵커 매뉴얼
- /inquiry → /submit_as_request 재사용, /terms·/privacy: 공용 템플릿, /updates: 타임라인
- /calendar: 2026-08 달력 그리드 + jobs.work_date 뱃지
- /leave_approvals: 휴가 신청 승인/반려 테이블
- /recruitment_status: job_postings 채용 현황
- /outflow_list, /pending_payments: expense doc_type 상태별 필터
- /approval_pending: 전체 대기 문서 + 승인/반려
- STUB_PAGES 딕셔너리/루프 완전 제거

### 스모크 결과
- 전체 42개 라우트 HTTP 200 확인 (2026-08-13)

---

## 2026-08-12 테스트 API 연결 및 전체 기능 동작

### 환경 수정
- `req.txt` UTF-16 인코딩 깨짐 → `requirements.txt` UTF-8로 재생성
- `static/` 디렉토리 생성 (앱 마운트 경로)
- `.env` 파일 생성 (SQLite 테스트 DB URL + 세션 키)
- `aiosqlite` 의존성 추가 (SQLite async 드라이버)

### DB 구축
- SQLite 테스트 DB (`test.db`) 생성
- 5개 테이블: users, jobs, as_requests, posts, erp_docs
- mock 데이터 삽입 (사용자 3명, 업무 5건, AS요청 3건, 게시글 4건, ERP문서 6건)
- `init_db.py` 스크립트 작성 (DB 초기화 자동화)

### API 추가 (main.py)
- `POST /api/jobs` — 업무 저장
- `GET /api/jobs` — 업무 목록 JSON
- `POST /submit_as_request` — AS 요청 접수
- `GET /api/as_requests` — AS 요청 목록 JSON
- `POST /api/posts` — 게시글 등록
- `GET /api/posts` — 게시글 목록 JSON
- `POST /api/erp_docs` — ERP 문서 등록
- `GET /api/erp_docs` — ERP 문서 목록 JSON

### 페이지 라우트 추가 (기존 404 해소)
- ERP 폼 6개: `/draft_doc`, `/new_hr_task`, `/new_stock_move`, `/new_work_order`, `/new_po`, `/new_activity`
- 커뮤니티 3개: `/write_post`, `/my_posts`, `/my_bookmarks`
- 상세보기 5종: `/job/{id}`, `/post/{id}`, `/erp_doc/{id}`, `/resume/{id}`, `/as_request/{id}`
- 스텁 페이지 17개: 회원가입, 비밀번호찾기, 프로필, 알림, FAQ 등

### HTML 템플릿 수정
- `href="#"` 172개 → 28개로 감소 (실제 라우트 연결)
- 남은 28개: 소셜 아이콘, Bootstrap 토글, 페이지네이션 (원래 `#`이 맞는 것들)
- 업무일지/새업무 폼 action → `POST /api/jobs`로 변경
- 검색 폼 action → 자기 페이지 GET으로 변경

### 템플릿 신규 생성
- `common/stub.html` — 준비중 페이지 공통 템플릿
- `common/detail.html` — 상세보기 공통 템플릿 (배지, 작성자, 조회수/댓글/좋아요 표시)
- `erp/erp_form.html` — ERP 문서 등록 공통 폼
- `top/write_post.html` — 게시글 작성 폼
- `top/my_posts.html` — 내가 쓴 글 목록
- `top/my_bookmarks.html` — 북마크 목록

### main.py 수정
- `DATABASE_URL` 기본값 SQLite로 설정 (RuntimeError 제거)
- SQLite일 때 MySQL 전용 풀 옵션 비활성화
- 인라인 HTML → 템플릿 파일로 전환 (디자인 통일)

### 배포
- ngrok으로 외부 접속 URL 생성
- 테스트 URL: https://vixen-pretended-simply.ngrok-free.dev

### 총 결과
- 전체 59개 라우트 정상 동작 확인
- GET 54개 (200 OK), POST 5개 (303/200)
