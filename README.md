# Squire

로컬 환경에서 GitHub PR을 조회/동기화하고, AI 리뷰 코멘트를 GitHub에 바로 쓰지 않고 로컬 DB에 저장해 검토할 수 있는 프로젝트입니다.

## 구성

- `squire-engine`: FastAPI + CLI(`squire`) + SQLite
- `squire-client`: React(Vite) 기반 대시보드 UI

## 상세 가이드

- [사용 가이드 인덱스](./docs/guide/README.md)

## 사전 준비

### 1) Engine 환경 변수

`<project-root>/squire-engine/.env`에 아래 값을 설정합니다.

- `GITHUB_TOKEN`
- `GITHUB_BASE_URL`
  - `.env.sample` 형식 그대로 설정: `https://github.hostname.url/api/v3`

### 1-1) `GITHUB_TOKEN` 권한 가이드

- 권장: **Fine-grained PAT** 사용
- 읽기 전용 기능(저장소 등록/동기화/조회) 기준 최소 권한:
  - `Pull Requests: Read`
  - `Contents: Read`
- 코멘트 게시 기능(`squire review publish`, `squire review publish-local`) 사용 시:
  - `Pull Requests: Write` 추가 필요
- `PAT classic`의 `repo` 전체 권한은 **필수 아님**
- 토큰은 `.env`에만 저장하고 저장소에 커밋하지 않습니다.

### 2) 런타임

- Engine: `uv` 사용 (`python/pip` 직접 사용하지 않음)
- Client: Node.js + npm

## 실행 방법

### 1) Engine 실행

```bash
cd <project-root>/squire-engine
uv sync
uv run squire serve --host 127.0.0.1 --port 8484
```

API 문서: [http://127.0.0.1:8484/docs](http://127.0.0.1:8484/docs)

### 2) Client 실행

```bash
cd <project-root>/squire-client
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## 전역 커맨드 등록 (다른 프로젝트에서도 사용)

아래 스크립트를 한 번 실행하면 `squire` 커맨드를 전역으로 등록할 수 있습니다.

```bash
cd <project-root>
./scripts/install-squire-tool.sh
```

설치 후 새 터미널에서 확인:

```bash
squire --help
```

이후 어떤 프로젝트 디렉터리에서도 `squire`를 바로 실행할 수 있습니다.

## AI 에이전트 스킬

### Codex

이 저장소에는 Codex용 스킬 [claude-skills/squire-pr-review](./claude-skills/squire-pr-review)가 포함되어 있습니다.

`$skill-installer`로 아래처럼 설치할 수 있습니다.

```bash
scripts/install-skill-from-github.py --repo <owner>/<repo> --path claude-skills/squire-pr-review
```

설치 후 Codex를 재시작하면 스킬을 사용할 수 있습니다.

### Claude Code

`claude-skills/squire-pr-review/` 안의 커맨드 파일을 사용하려는 프로젝트의 `.claude/commands/`에 복사합니다.

```bash
mkdir -p /path/to/project/.claude/commands
cp claude-skills/squire-pr-review/squire-pr-review.md \
   /path/to/project/.claude/commands/
```

이후 해당 프로젝트에서 Claude Code를 실행하면 슬래시 커맨드로 사용할 수 있습니다.

```text
/squire-pr-review owner/repo
```

다른 프로젝트에서도 사용하려면 `.claude/commands/squire-pr-review.md`를 해당 프로젝트의 `.claude/commands/`에 복사합니다.

## 기본 사용 흐름

```bash
cd <project-root>/squire-engine

# 저장소 등록 + 즉시 동기화
uv run squire repo add owner/repo

# 증분 동기화
uv run squire sync --repo owner/repo

# 전체 동기화 강제
uv run squire sync --repo owner/repo --full

# PR 조회
uv run squire list --repo owner/repo --state open
uv run squire show 123 --repo owner/repo

# 실제 GitHub PR에 의견 코멘트 추가 (상태 변경 없음)
uv run squire review publish 123 --repo owner/repo --body "의견 내용"

# 로컬 리뷰 코멘트를 GitHub에 게시
uv run squire review publish-local 123 --repo owner/repo --all
```

참고: 실제 PR 코멘트 추가에는 `GITHUB_TOKEN`에 `Pull Requests: Write` 권한이 필요합니다.
