# Wone - 장애우 취업 지원 포털

## 프로젝트 개요

장애인 근로자를 위한 **채용/업무/ERP 통합 포털 시스템**.
채용 공고 검색, 사내 업무 관리, ERP 모듈, 접근성 도구를 하나의 플랫폼에서 제공합니다.

## 기술 스택

| 구분 | 기술 |
|---|---|
| Backend | FastAPI (Python 3.9+) |
| Frontend | Jinja2 Template + Bootstrap 5 + FontAwesome 6 |
| DB (테스트) | SQLite (`test.db`) |
| DB (실서비스) | MySQL (asyncmy 드라이버) |
| 인증 | 세션 기반 (Starlette SessionMiddleware) |

## 폴더 구조

```
wone/
├── main.py                  # FastAPI 앱 + 전체 라우트 정의
├── init_db.py               # SQLite 테이블 생성 + mock 데이터 삽입
├── funchub.py               # 유틸리티 함수 모듈 (확장용)
├── requirements.txt         # Python 의존성
├── .env                     # 환경변수 (DB URL, 세션 키)
├── test.db                  # SQLite 테스트 DB (자동 생성)
├── static/                  # 정적 파일 (이미지, CSS 등)
│   └── photo/event_photos/
├── templates/
│   ├── common/              # 공통 컴포넌트
│   │   ├── header.html      #   CSS 스타일 + head 태그 + 접근성 스크립트
│   │   ├── topbar.html      #   상단 네비게이션 바
│   │   └── detail.html      #   상세보기 공통 템플릿
│   ├── login/
│   │   ├── login.html       # 로그인 페이지
│   │   └── signup.html      # 회원가입 페이지
│   ├── info/                # 정보성 페이지
│   │   ├── faq.html         #   자주 묻는 질문 (accordion)
│   │   ├── guide.html       #   사용 가이드 (목차 + 섹션)
│   │   ├── inquiry.html     #   1:1 문의 폼
│   │   ├── policy.html      #   이용약관/개인정보처리방침 공용
│   │   └── updates.html     #   업데이트 내역 타임라인
│   ├── top/                 # 메인 페이지들
│   │   ├── index.html       #   홈 (메인 대시보드)
│   │   ├── emp_dash.html    #   직원 업무 대시보드
│   │   ├── manage_dash.html #   관리자 대시보드
│   │   ├── resume.html      #   채용 공고 목록
│   │   ├── resume_detail.html #  채용 공고 상세
│   │   ├── community.html   #   커뮤니티 게시판
│   │   ├── post_detail.html #   게시글 상세 (댓글/좋아요/스크랩)
│   │   ├── contact.html     #   AS/지원 요청
│   │   ├── new_job.html     #   새 업무 등록 폼
│   │   ├── write_post.html  #   게시글 작성 폼
│   │   ├── my_posts.html    #   내가 쓴 글
│   │   ├── my_bookmarks.html#   북마크
│   │   ├── profile.html     #   내 프로필 (수정 포함)
│   │   ├── notifications.html #  알림 목록
│   │   └── accessibility.html # 접근성 설정
│   ├── apps/                # 업무 도구
│   │   ├── job_diary.html   #   업무일지 작성 폼
│   │   ├── complete_job.html#   완료 업무 목록
│   │   ├── new_arrived_job.html # 신규 업무/메시지
│   │   ├── calendar.html    #   일정 관리 (달력 그리드)
│   │   ├── eyemouse.html    #   시선 추적 (아이마우스)
│   │   └── realtime_trans.html  # 실시간 통역/자막
│   └── erp/                 # ERP 모듈
│       ├── erp_dash.html    #   ERP 대시보드
│       ├── erp_form.html    #   ERP 문서 등록 공통 폼
│       ├── erp_doc_detail.html # ERP 문서 상세 (승인/반려)
│       ├── _doc_list.html   #   문서 목록 공통 partial
│       ├── erp_groupware.html #  그룹웨어 (결재)
│       ├── erp_hr.html      #   인사 관리
│       ├── erp_fa.html      #   자금 관리
│       ├── erp_inventory.html #  재고 관리
│       ├── erp_product.html #   생산 관리
│       ├── erp_purch.html   #   구매 관리
│       ├── erp_scrm.html    #   영업/CRM
│       ├── leave_approvals.html # 휴가 승인 목록
│       ├── recruitment_status.html # 채용 현황 테이블
│       ├── fa_list.html     #   출금/미결제 내역 공용
│       └── approval_pending.html # 결재 대기 전체 목록
```

## 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 테스트 DB 초기화
```bash
python init_db.py
```

### 3. 서버 실행
```bash
uvicorn main:app --reload
```

### 4. 접속
http://127.0.0.1:8000 → 아이디/비밀번호 입력 후 로그인

## 환경변수 (.env)

| 변수 | 설명 | 예시 |
|---|---|---|
| `DATABASE_URL` | DB 접속 URL | `sqlite:///test.db` (기본) |
| | | `mysql://user:pass@host:3306/dbname` (MySQL) |
| `SESSION_SECRET_KEY` | 세션 암호화 키 | `supersecretkey` |

## DB 설정

기본값은 SQLite(`test.db`)다. `.env` 파일의 `DATABASE_URL` 한 줄만 바꾸면 MySQL로 전환된다.

### SQLite (기본)

별도 설정 없이 바로 실행 가능하다. `DATABASE_URL`을 생략하거나 아래처럼 지정한다.

```
DATABASE_URL=sqlite:///test.db
```

### MySQL 전환

1. `.env`에 MySQL URL을 설정한다.
   ```
   DATABASE_URL=mysql://user:password@localhost:3306/wone_db
   ```
2. DB와 유저를 MySQL에서 미리 생성해 둔다.
3. 목업 데이터를 포함한 테이블 초기화를 실행한다.
   ```bash
   python3 init_db.py
   ```
4. 서버를 기동한다.
   ```bash
   uvicorn main:app --reload
   ```

PyMySQL이 설치되어 있어야 MySQL 모드가 동작한다(`pip install PyMySQL`).
SQLite 모드에서는 PyMySQL을 설치하지 않아도 무방하다.

## DB 스키마

### users
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| username | TEXT | 로그인 ID |
| password | TEXT | 비밀번호 (목업 평문, 실서비스 전 해시 필요) |
| name | TEXT | 이름 |
| dept | TEXT | 부서 |
| position | TEXT | 직급 |
| phone | TEXT | 연락처 |
| role | TEXT | 권한 (admin/employee) |

### jobs
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 작성자 |
| work_date | TEXT | 작업일 (YYYY-MM-DD) |
| category | TEXT | 업무 분류 |
| title | TEXT | 제목 |
| details | TEXT | 상세 내용 |
| issues | TEXT | 이슈/특이사항 |
| dept | TEXT | 소속 부서 |
| due_label | TEXT | 마감 표시 |
| status | TEXT | 상태 (urgent/progress/wait/done) |

### as_requests
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 신청자 |
| category | TEXT | 요청 분류 |
| urgency | TEXT | 긴급도 |
| title | TEXT | 제목 |
| details | TEXT | 상세 내용 |
| attachment | TEXT | 첨부파일명 |
| status | TEXT | 처리 상태 (pending/progress/resolved) |

### posts (커뮤니티 게시글)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 작성자 |
| category | TEXT | 카테고리 (it/biz/design/sales/notice/general/qna) |
| title | TEXT | 제목 |
| content | TEXT | 내용 |
| author | TEXT | 작성자명 |
| dept | TEXT | 소속 부서 |
| views | INTEGER | 조회수 |

### comments / post_likes / bookmarks
별도 테이블로 post_id + user_id 기반 관리 (좋아요·스크랩 토글 지원)

### erp_docs
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 작성자 |
| doc_type | TEXT | 유형 (draft/hr_task/stock_move/work_order/po/activity/expense) |
| title | TEXT | 제목 |
| content | TEXT | 내용 |
| dept | TEXT | 부서 |
| due_label | TEXT | 마감 표시 |
| status | TEXT | 상태 (urgent/progress/wait/done/approved/rejected) |

### job_postings (채용 공고)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| company | TEXT | 회사/기관 |
| title | TEXT | 포지션명 |
| region | TEXT | 지역 |
| employment_type | TEXT | 고용형태 |
| disability_friendly | TEXT | 장애인 지원사항 |
| salary | TEXT | 급여 |
| deadline | TEXT | 마감일 |
| description | TEXT | 상세 설명 |

### notifications (알림)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 수신자 |
| icon | TEXT | FontAwesome 아이콘 클래스 |
| title | TEXT | 알림 제목 |
| body | TEXT | 알림 본문 |
| time_label | TEXT | 시간 표시 |
| is_read | INTEGER | 읽음 여부 (0/1) |

### messages (업무 메시지)
| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | INTEGER PK | 자동증가 |
| user_id | INTEGER | 수신자 |
| sender | TEXT | 발신자명 |
| body | TEXT | 내용 |
| time_label | TEXT | 시간 표시 |
| is_read | INTEGER | 읽음 여부 (0/1) |

## API 목록

### 페이지 라우트 (GET → HTML)

**메인/인증**
| URL | 기능 |
|---|---|
| `/` | 메인 홈 |
| `/login` | 로그인 |
| `/signup` | 회원가입 |
| `/logout` | 로그아웃 |
| `/profile` | 내 프로필 |
| `/notifications` | 알림 목록 |
| `/accessibility` | 접근성 설정 |

**업무**
| URL | 기능 |
|---|---|
| `/emp_dash` | 직원 업무 대시보드 |
| `/manage_dash` | 관리자 대시보드 |
| `/new_job` | 새 업무 등록 |
| `/completed_jobs` | 완료 업무 목록 |
| `/newarrived_jobs` | 메시지함 |
| `/calendar` | 일정 관리 (달력) |
| `/job_diary` | 업무일지 작성 |

**커뮤니티**
| URL | 기능 |
|---|---|
| `/community` | 게시판 목록 (필터/검색/페이지네이션) |
| `/write_post` | 게시글 작성 |
| `/my_posts` | 내가 쓴 글 |
| `/my_bookmarks` | 스크랩 목록 |

**채용/AS/정보**
| URL | 기능 |
|---|---|
| `/resume` | 채용 공고 목록 |
| `/contact` | AS 접수 |
| `/faq` | 자주 묻는 질문 |
| `/guide` | 사용 가이드 |
| `/inquiry` | 1:1 문의 |
| `/terms` | 이용약관 |
| `/privacy` | 개인정보처리방침 |
| `/updates` | 업데이트 내역 |

**ERP**
| URL | 기능 |
|---|---|
| `/erp_dash` | ERP 대시보드 |
| `/erp_hr` | 인사관리 |
| `/erp_fa` | 자금관리 |
| `/erp_inventory` | 재고관리 |
| `/erp_product` | 생산관리 |
| `/erp_purch` | 구매관리 |
| `/erp_scrm` | 영업/CRM |
| `/erp_groupware` | 그룹웨어 |
| `/leave_approvals` | 휴가 승인 |
| `/recruitment_status` | 채용 현황 |
| `/outflow_list` | 출금 완료 내역 |
| `/pending_payments` | 미결제 내역 |
| `/approval_pending` | 결재 대기 전체 |

### 상세보기 (GET → HTML)
| URL | 기능 |
|---|---|
| `/job/{id}` | 업무 상세 |
| `/post/{id}` | 게시글 상세 (댓글/좋아요/스크랩) |
| `/erp_doc/{id}` | ERP 문서 상세 (승인/반려) |
| `/resume/{id}` | 채용 공고 상세 |
| `/as_request/{id}` | AS 요청 상세 |

### API (POST → Action)
| URL | 기능 |
|---|---|
| `/login_check` | 로그인 처리 |
| `/submit_as_request` | AS/문의 접수 |
| `/api/jobs` | 업무 저장 |
| `/api/jobs/{id}/toggle` | 업무 완료 토글 |
| `/api/messages/{id}/read` | 메시지 읽음 처리 |
| `/api/messages/read_all` | 전체 읽음 처리 |
| `/api/posts/{id}/comments` | 댓글 등록 |
| `/api/posts/{id}/like` | 좋아요 토글 |
| `/api/posts/{id}/bookmark` | 스크랩 토글 |
| `/api/erp_docs/{id}/status` | ERP 문서 승인/반려 |
| `/api/profile` | 프로필 수정 |
| `/api/notifications/read_all` | 알림 전체 읽음 |

## 실서비스 전환 시 변경사항

1. `.env`의 `dburl`을 MySQL URL로 변경
2. `init_db.py` 대신 실제 MySQL 스키마 마이그레이션 적용
3. `login_check`에 실제 비밀번호 검증 로직 추가
4. `SESSION_SECRET_KEY`를 안전한 랜덤 값으로 변경
