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

- `GITHUB_TOKEN` (모든 저장소를 Keychain 토큰으로만 운영하지 않는 경우)
- `GITHUB_BASE_URL` (GitHub Enterprise Server 사용 시만 설정)
  - 예시: `https://github.mycompany.com/api/v3`
  - github.com 사용 시 비워 두거나 항목을 삭제합니다.

기본값은 전역 설정이며, 저장소 등록 시 프로젝트별 개별 설정으로 덮어쓸 수 있습니다.

저장소별 토큰 개별 설정(`--github-token`)은 macOS Keychain에 저장됩니다.
SQLite DB에는 저장소별 토큰 평문을 저장하지 않습니다.

### 1-1) `GITHUB_TOKEN` 권한 가이드

- 권장: **Fine-grained PAT** 사용
- 읽기 전용 기능(저장소 등록/동기화/조회) 기준 최소 권한:
  - `Pull Requests: Read`
  - `Contents: Read`
- 코멘트 게시 기능(`squire review publish`, `squire review publish-local`) 사용 시:
  - `Pull Requests: Write` 추가 필요
- `PAT classic`의 `repo` 전체 권한은 **필수 아님**
- 전역 토큰은 `.env`, 저장소별 개별 설정 토큰은 macOS Keychain에 저장하며 저장소에는 커밋하지 않습니다.

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

클라이언트는 기본적으로 `http://127.0.0.1:8484`의 엔진 API에 연결합니다. 엔진 포트를 변경한 경우 `VITE_SQUIRE_API_BASE_URL` 환경변수를 설정하세요.

```bash
VITE_SQUIRE_API_BASE_URL=http://127.0.0.1:9000 npm run dev -- --host 127.0.0.1 --port 5173
```

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

이 저장소에는 Codex용 스킬 [skills/codex/squire-pr-review](./skills/codex/squire-pr-review)가 포함되어 있습니다.

이 스킬의 역할은 `squire` CLI 기반 PR 리뷰 워크플로우(저장소 등록/동기화/조회/코멘트 게시)를 Codex에서 재사용 가능하게 만드는 것입니다.

다른 프로젝트의 Codex에서 설치하는 방법 (프로젝트별 설치, 글로벌 설치 안 함):

1) 대상 프로젝트 루트에서 Codex를 프로젝트 전용 홈으로 실행합니다.

```bash
TARGET_PROJECT=/path/to/target-project
cd "$TARGET_PROJECT"
CODEX_HOME="$PWD/.codex" codex -C "$PWD"
```

2) Codex 채팅에서 아래처럼 요청합니다.

```text
$skill-installer를 사용해서 oenomel87/squire의 skills/codex/squire-pr-review 스킬을 설치해줘.
```

3) 설치 후 Codex를 재시작할 때도 같은 방식으로 실행합니다.

```bash
cd "$TARGET_PROJECT"
CODEX_HOME="$PWD/.codex" codex -C "$PWD"
```

이 방식은 스킬이 전역 `~/.codex/skills`가 아니라 `대상프로젝트/.codex/skills`에 설치되도록 합니다.

### Claude Code

`skills/claude-code/squire-pr-review/` 안의 커맨드 파일을 사용하려는 프로젝트의 `.claude/commands/`에 복사합니다.

```bash
mkdir -p /path/to/project/.claude/commands
cp skills/claude-code/squire-pr-review/squire-pr-review.md \
   /path/to/project/.claude/commands/
```

이후 해당 프로젝트에서 Claude Code를 실행하면 슬래시 커맨드로 사용할 수 있습니다.

```text
/squire-pr-review owner/repo
```

위 명령의 `owner/repo`는 스킬 설치 소스가 아니라, 리뷰 대상 GitHub 저장소를 의미합니다.

다른 프로젝트에서도 사용하려면 `.claude/commands/squire-pr-review.md`를 해당 프로젝트의 `.claude/commands/`에 복사합니다.

## 기본 사용 흐름

```bash
cd <project-root>/squire-engine

# 저장소 등록 + 즉시 동기화
uv run squire repo add owner/repo

# 프로젝트별 GitHub 설정 개별 지정
uv run squire repo add owner/repo --github-token <repo_token>
uv run squire repo add owner/repo --github-base-url https://github.mycompany.com/api/v3

# (선택) 과거 DB 평문 토큰을 Keychain으로 마이그레이션
uv run squire repo migrate-legacy-tokens

# macOS Keychain 직접 관리
security add-generic-password -a owner/repo -s squire.github.token -U -w
security find-generic-password -a owner/repo -s squire.github.token -w
security delete-generic-password -a owner/repo -s squire.github.token

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
