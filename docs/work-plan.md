# Squire 작업 계획

## 1) 현재 프로젝트 구조 확인 결과

- 루트: `squire-engine`(백엔드), `squire-client`(프론트엔드), `design.md`
- 백엔드: `squire-engine/main.py` 단일 파일(현재 Hello World 수준), `pyproject.toml` 존재
- 프론트엔드: Vite + React + TypeScript 기본 템플릿 상태
- Git 상태: 초기 커밋 전(전체 파일 untracked)

## 2) 개발 환경 확인 결과

- 시스템 Python: `3.9.6` (참고용, `squire-engine` 실행에 사용하지 않음)
- Engine Python: `uv`가 관리하는 프로젝트 venv 사용
- Node.js: `v22.14.0`
- npm: `10.9.2`
- `uv`: 설치됨 (`0.6.9`)
- `pyenv`: 미설치

### 실행 원칙 (중요)

- `squire-engine`은 시스템 기본 `python`/`pip`를 사용하지 않고, `uv` venv에서만 실행한다.
- 백엔드 관련 의존성 설치/실행 명령은 `uv sync`, `uv run`을 기준으로 통일한다.

## 3) 작업 목표 (design.md 기준)

- 로컬에서 GitHub PR 정보를 조회/프록시
- AI 리뷰 코멘트를 GitHub가 아닌 로컬 SQLite에 저장
- CLI(`squire`)로 조회/저장 흐름 제공
- 이후 FastAPI + Web UI로 인간 리뷰 검토 흐름 제공

## 4) 실행 계획

## Phase 0. 기반 정리

1. `uv` venv 전용 실행 규칙 고정
2. 디렉터리 구조 표준화 (`app/`, `api/`, `db/`, `services/`, `cli/`)
3. 공통 설정 로더(`.env` + `config.yaml`) 구현 (`GITHUB_BASE_URL` 필수 사용)

### 산출물

- 백엔드 초기 앱 실행 가능 상태
- 개발용 실행 명령 문서화

## Phase 1. MVP (우선 구현)

1. DB 스키마 구현 (`repositories`, `pull_requests`, `ai_reviews`, `pr_review_status`)
2. PR 식별키 보강 (`UNIQUE(repo_id, number)`, 리뷰/상태는 `pull_request_id` FK 기반)
3. `squire repo add/list/remove` 구현 (add 시 대상 저장소 즉시 동기화)
4. `squire sync` 구현 (GitHub -> SQLite)
5. `squire list`, `squire show` 구현 (SQLite 조회)
6. `squire diff`, `squire files` 구현 (GitHub API 프록시)
7. `squire review add`, `squire review list`, `squire review status` 구현 (로컬 리뷰 저장/조회)

### 산출물

- design.md에 정의된 핵심 CLI 동작 가능
- PR 메타데이터/AI 리뷰 데이터 로컬 저장 확인

## Phase 2. Web UI 연동

1. FastAPI API 엔드포인트 정리
2. PR 목록 대시보드 구현
3. PR 상세 + AI 리뷰 필터링 화면 구현

### 산출물

- 로컬 브라우저에서 PR/AI 리뷰 조회 가능

## Phase 3. 확장

1. 자동 동기화(polling) 추가
2. GitHub 코멘트 게시 기능(옵션) 추가
3. 리뷰 통계/품질 지표 추가

## 5) 권장 시작 순서

1. `uv sync`/`uv run` 기준으로 백엔드 실행 명령을 먼저 확정
2. `repositories` + `pull_requests` 중심 스키마(복합 유니크 키) 먼저 고정
3. `repo add`(즉시 sync) -> `sync/list/show` -> `diff/files` 순으로 GitHub 연동 통합

## 6) 완료 기준(Definition of Done)

- `squire repo add/list/remove`, `squire sync`, `squire list/show`, `squire diff/files`, `squire review add/list/status`가 로컬 환경에서 동작
- SQLite에 `repositories`, `pull_requests`, `ai_reviews`, `pr_review_status`가 FK/유니크 제약 포함으로 저장
- 최소 실행/검증 절차가 문서화되어 신규 개발자가 재현 가능
