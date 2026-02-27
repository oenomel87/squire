# 01. 동작 환경 구성

## 1) 프로젝트 구조

- 루트: `<project-root>` (예: `/path/to/squire`)
- 엔진(백엔드+CLI): `squire-engine`
- 웹 클라이언트: `squire-client`
- 문서: `docs`
- AI 에이전트 스킬:
  - Codex: `skills/codex/squire-pr-review`
  - Claude Code: `skills/claude-code/squire-pr-review`

## 2) 필수 도구

- `uv` (엔진 의존성 설치/실행)
- Node.js + npm (웹 클라이언트 실행)

엔진은 `uv` 기반으로만 운영합니다. `python`/`pip` 직접 실행을 기본 경로로 사용하지 않습니다.

## 3) 엔진 환경 변수

`<project-root>/squire-engine/.env.sample` 기준으로 `.env` 파일을 준비합니다.

```bash
cd <project-root>/squire-engine
cp .env.sample .env
```

필수 값:

- `GITHUB_TOKEN` (모든 저장소를 Keychain 토큰으로만 운영하지 않는 경우)

선택 값:

- `GITHUB_BASE_URL`
  - 미설정 시 기본값 `https://api.github.com` 사용
  - GitHub Enterprise Server 사용 시 `.env.sample` 형식대로 설정: `https://github.hostname.url/api/v3`

`GITHUB_TOKEN` 권한 가이드:

- 권장: **Fine-grained PAT**
- 읽기 전용 기능(등록/동기화/조회) 기준 최소 권한:
  - `Pull Requests: Read`
  - `Contents: Read`
- 코멘트 게시(`squire review publish`, `squire review publish-local`)를 사용할 경우:
  - `Pull Requests: Write` 추가 필요
- `PAT classic`의 `repo` 전체 권한은 필수 아님

참고:

- 구현은 `GITHUB_BASE_URL`만 사용합니다.
- `GITHUB_TOKEN`/`GITHUB_BASE_URL`는 전역 기본값이며, 저장소 등록 시 프로젝트별 개별 설정을 줄 수 있습니다.
- 저장소별 `GITHUB_TOKEN` 개별 설정 값은 macOS Keychain(service=`squire.github.token`)에 저장됩니다.
- 저장소별 토큰은 SQLite DB에 평문으로 저장하지 않습니다.
- 단일 엔진 운영 시 DB도 단일 경로로 고정하는 것을 권장합니다.
  - macOS 권장 경로: `$HOME/Library/Application Support/squire/squire.db`
- `SQUIRE_DB_PATH`로 DB 경로를 명시적으로 고정하세요.

```bash
mkdir -p "$HOME/Library/Application Support/squire"
export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"
```

셸 시작 시 자동 적용하려면:

```bash
echo 'export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"' >> ~/.zshrc
source ~/.zshrc
```

### Keychain 수동 명령 (macOS)

```bash
# 저장/갱신 (토큰은 프롬프트로 입력)
security add-generic-password -a owner/repo -s squire.github.token -U -w

# 조회
security find-generic-password -a owner/repo -s squire.github.token -w

# 삭제
security delete-generic-password -a owner/repo -s squire.github.token
```

## 4) 버전/설치 확인

```bash
uv --version
node -v
npm -v
```

`squire-engine/pyproject.toml` 기준 Python 런타임 요구사항은 `>=3.13`입니다. 실제 실행은 `uv`가 관리합니다.

## 5) 빠른 준비 체크리스트

- `.env` 파일 생성 및 전역 기본 토큰(`GITHUB_TOKEN`) 필요 여부 확인 완료
- `uv sync`로 엔진 의존성 설치 가능
- `npm install`로 클라이언트 의존성 설치 가능
