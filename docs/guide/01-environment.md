# 01. 동작 환경 구성

## 1) 프로젝트 구조

- 루트: `<project-root>` (예: `/path/to/squire`)
- 엔진(백엔드+CLI): `squire-engine`
- 웹 클라이언트: `squire-client`
- 문서: `docs`
- Codex 스킬: `skills/squire-pr-review`

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

- `GITHUB_TOKEN`
- `GITHUB_BASE_URL`
  - `.env.sample` 형식 그대로 사용: `https://github.hostname.url/api/v3`

참고:

- 구현은 `GITHUB_BASE_URL`만 사용합니다.
- 기본 DB 파일은 `squire-engine/data/squire.db` 입니다.
- 필요 시 `SQUIRE_DB_PATH`로 DB 경로를 변경할 수 있습니다.

## 4) 버전/설치 확인

```bash
uv --version
node -v
npm -v
```

`squire-engine/pyproject.toml` 기준 Python 런타임 요구사항은 `>=3.13`입니다. 실제 실행은 `uv`가 관리합니다.

## 5) 빠른 준비 체크리스트

- `.env` 파일 생성 및 필수 변수 입력 완료
- `uv sync`로 엔진 의존성 설치 가능
- `npm install`로 클라이언트 의존성 설치 가능
