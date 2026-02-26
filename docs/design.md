# PR Proxy — 기본 설계 문서

## 개요

GitHub PR 정보를 로컬 환경에서 조회·관리하며, AI 코드 에이전트(Claude Code 등)에게 CLI 인터페이스를 제공하는 시스템.

AI 에이전트의 리뷰 결과는 GitHub이 아닌 **로컬 시스템에 저장**하고, 인간 리뷰어가 Web UI를 통해 검토 내용을 확인한 뒤 선택적으로 GitHub에 반영한다.

## 핵심 원칙

- **Approve는 인간이 한다.** AI 에이전트는 코멘트(리뷰 의견)만 남긴다.
- **AI 리뷰는 로컬에 먼저 저장한다.** GitHub에 직접 쓰지 않으므로, 잘못된 리뷰가 외부에 노출되지 않는다.
- **GitHub API 프록시 역할.** AI 에이전트가 diff, 파일 목록 등을 조회할 때 GitHub API를 대신 호출한다.
- **로컬 환경 전용.** 서버 배포 없이 개발자 머신에서 실행한다.
- **단순하고 빠르게.** 먼저 동작하는 최소 구현을 만들고, 사용하면서 검증한다.

## 시스템 구조

```
GitHub ──→ PR Proxy (동기화/캐시) ──→ CLI ──→ AI 에이전트
                │                                  │
                │          리뷰 결과 저장            │
                ↓                                  ↓
             SQLite ←─────────────────────────────┘
                │
                ↓
          로컬 Web UI ──→ 인간 리뷰어
                │
                ↓ (선택적, 추후 구현)
            GitHub에 코멘트 게시
```

## 기술 스택

| 구성 요소 | 기술 | 비고 |
|-----------|------|------|
| 백엔드/API | FastAPI (Python) | CLI와 Web UI 모두에 API 제공 |
| 데이터 저장 | SQLite | PR 메타데이터 + AI 리뷰 결과 |
| CLI | Typer 또는 Click | AI 에이전트가 호출하는 인터페이스 |
| Web UI | 간단한 SPA (React 또는 정적 HTML) | 리뷰 결과 확인용 |
| GitHub 연동 | GitHub REST API / `gh` CLI | PR 데이터 동기화 |

## PR 데이터 동기화

### 수집 방식

초기 구현은 **GitHub API polling** 방식을 사용한다.

- `gh` CLI 또는 GitHub REST API를 통해 주기적으로 PR 목록을 가져온다.
- 수동 동기화 커맨드(`squire sync`)도 제공한다.
- Webhook은 로컬 환경에서 터널링(ngrok 등)이 필요하므로 추후 필요 시 추가한다.

### 대상 저장소 등록 방식

- 대상 저장소는 설정 파일이 아니라 **CLI로 등록**한다.
- `squire repo add <owner/repo>` 실행 시 저장소를 DB에 저장하고, **해당 저장소 동기화를 즉시 1회 수행**한다.
- 등록된 저장소 목록은 `squire repo list`로 조회한다.

### 저장하는 PR 메타데이터

- PR 번호, 제목, 본문
- 등록 일시, 업데이트 일시
- 작성자
- 리뷰 요청자, 리뷰어 목록
- 변경 파일 수
- 상태 (open / closed / merged)
- 브랜치 정보 (head → base)

### 캐시 정책

- PR 메타데이터: 동기화 시점에 갱신, 로컬 DB에 저장
- diff, 파일 내용: 요청 시 GitHub API를 호출하여 반환 (커밋 추가로 변경될 수 있으므로 캐싱하지 않음)

## CLI 인터페이스

AI 에이전트(Claude Code 등)가 호출하는 명령어 체계.

### 저장소 관리

```bash
squire repo add <owner/repo>               # 저장소 등록 + 즉시 동기화 1회 수행
squire repo list                            # 등록된 저장소 목록 조회
squire repo remove <owner/repo>             # 저장소 등록 해제 (선택 구현)
```

### 읽기 — GitHub 프록시

```bash
squire sync [--repo <owner/repo>]          # PR 목록 동기화 (전체 또는 특정 저장소)
squire list [--repo <owner/repo>] [--state open|closed|all]
squire show <number> --repo <owner/repo>   # PR 요약 정보 (로컬 DB)
squire diff <number> --repo <owner/repo> [--file <path>]
squire files <number> --repo <owner/repo>
squire comments <number> --repo <owner/repo>
squire reviews <number> --repo <owner/repo>
```

### 쓰기 — AI 리뷰 저장 (로컬 전용)

```bash
# PR 전체에 대한 리뷰 의견
squire review add <number> --repo <owner/repo> --body "..."

# 특정 파일/라인에 대한 리뷰 의견
squire review add <number> --repo <owner/repo> --file <path> --line <n> --body "..."

# 심각도 지정
squire review add <number> --repo <owner/repo> --severity <info|warning|error> --body "..."

# 리뷰 검토 상태 표시
squire review status <number> --repo <owner/repo> --set <pending|in-progress|done>

# 해당 PR의 AI 리뷰 목록 조회
squire review list <number> --repo <owner/repo>
```

## 데이터 모델

### repositories

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 내부 ID |
| full_name | TEXT UNIQUE | 저장소 이름 (`owner/repo`) |
| is_active | BOOLEAN | 활성 여부 |
| created_at | DATETIME | 등록 일시 |
| updated_at | DATETIME | 수정 일시 |
| last_synced_at | DATETIME (nullable) | 마지막 동기화 일시 |

### pull_requests

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 내부 ID |
| repo_id | INTEGER FK | `repositories.id` |
| number | INTEGER | PR 번호 |
| title | TEXT | 제목 |
| body | TEXT | 본문 |
| author | TEXT | 작성자 |
| state | TEXT | open / closed / merged |
| head_branch | TEXT | 소스 브랜치 |
| base_branch | TEXT | 대상 브랜치 |
| changed_files | INTEGER | 변경 파일 수 |
| reviewers | TEXT (JSON) | 리뷰어 목록 |
| created_at | DATETIME | 생성 일시 |
| updated_at | DATETIME | 업데이트 일시 |
| synced_at | DATETIME | 마지막 동기화 일시 |

제약 조건:
- `UNIQUE(repo_id, number)`로 저장소별 PR 번호 중복 방지

### ai_reviews

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 내부 ID |
| pull_request_id | INTEGER FK | 대상 PR (`pull_requests.id`) |
| file_path | TEXT (nullable) | 대상 파일 경로 |
| line_number | INTEGER (nullable) | 대상 라인 번호 |
| severity | TEXT | info / warning / error |
| body | TEXT | 리뷰 내용 |
| agent | TEXT | 작성 에이전트 (claude-code 등) |
| created_at | DATETIME | 작성 일시 |

### pr_review_status

| 컬럼 | 타입 | 설명 |
|------|------|------|
| pull_request_id | INTEGER PK/FK | 대상 PR (`pull_requests.id`) |
| status | TEXT | pending / in-progress / done |
| updated_at | DATETIME | 상태 변경 일시 |

## Web UI

로컬 브라우저에서 접근하는 대시보드. FastAPI에서 정적 파일로 서빙한다.

### 화면 구성

**PR 목록 (메인 대시보드)**
- PR 번호, 제목, 작성자, 변경 파일 수
- AI 리뷰 상태 표시 (pending / in-progress / done)
- severity 별 코멘트 수 요약 (error: 2, warning: 5, info: 3)

**PR 상세**
- PR 기본 정보 (메타데이터)
- AI 리뷰 코멘트 목록 (파일별, 심각도별 필터링)
- 각 코멘트에 대한 액션: 확인 완료, GitHub에 게시 (추후)

## GitHub 연결 설정

### 초기 구현: 읽기 전용

AI 리뷰를 로컬에만 저장하므로, **읽기 전용 토큰**으로 동작 가능하다.

- Fine-grained PAT 권한: `Pull Requests: Read`, `Contents: Read`
- 환경 변수 `GITHUB_TOKEN` 사용
- GitHub API URL은 **항상** 환경 변수 `GITHUB_BASE_URL`을 사용
- GitHub.com 사용 시에도 `.env`에서 `GITHUB_BASE_URL=https://api.github.com`으로 명시

### 추후 확장: GitHub 코멘트 게시

Web UI에서 "GitHub에 게시" 기능을 추가할 경우 `Pull Requests: Write` 권한이 필요하다.

## 설정 파일

```yaml
# config.yaml (선택)
github:
  sync_interval: 300              # 자동 동기화 간격 (초), 0이면 수동만

server:
  host: 127.0.0.1
  port: 8484

review:
  default_severity: info
  comment_prefix: "🤖 [AI Review]"  # 코멘트 자동 prefix
```

저장소 목록은 `config.yaml`이 아니라 `squire repo add`로 DB에 저장한다.

## 구현 우선순위

### Phase 1 — MVP

1. `squire repo add`, `squire repo list` — 저장소 등록/조회 + 등록 시 즉시 동기화
2. `squire sync` — GitHub에서 PR 목록을 가져와 SQLite에 저장
3. `squire list`, `squire show` — 로컬 DB에서 PR 조회
4. `squire diff`, `squire files` — GitHub API 프록시
5. `squire review add`, `squire review list` — AI 리뷰 저장 및 조회

### Phase 2 — Web UI

1. FastAPI 서버 + 정적 Web UI
2. PR 목록 대시보드
3. PR 상세 화면 (AI 리뷰 코멘트 확인)

### Phase 3 — 확장

1. GitHub 코멘트 게시 기능 (Web UI에서 선택적으로)
2. 자동 동기화 (백그라운드 polling)
3. 리뷰 품질 통계/분석
