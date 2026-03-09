# 02. 서버/웹 구동 방법

## 1) 서버(Engine) 실행

```bash
cd ~/squire
uv sync --project squire-engine
./scripts/squire.sh serve --host 127.0.0.1 --port 8484
```

확인:

- API 문서: `http://127.0.0.1:8484/docs`
- 헬스 체크:

```bash
curl http://127.0.0.1:8484/health
```

## 2) 웹(Client) 실행

새 터미널에서:

```bash
cd ~/squire
npm --prefix squire-client install
npm --prefix squire-client run dev -- --host 127.0.0.1 --port 5173
```

확인:

- 웹 UI: `http://127.0.0.1:5173`

## 3) 포트/주소를 바꾸는 경우

- 엔진 포트 변경:

```bash
./scripts/squire.sh serve --host 127.0.0.1 --port 9000
```

- 클라이언트 API 대상 변경:
  - 기본값: `http://127.0.0.1:8484`
  - 필요 시 `VITE_SQUIRE_API_BASE_URL` 환경변수를 설정하고 클라이언트를 실행합니다.

예시:

```bash
cd ~/squire
VITE_SQUIRE_API_BASE_URL=http://127.0.0.1:9000 \
  npm --prefix squire-client run dev -- --host 127.0.0.1 --port 5173
```

## 4) 실행 순서 권장

1. 엔진 실행
2. 클라이언트 실행
3. 브라우저에서 UI 접속
4. 저장소 등록 후 PR 동기화 진행

## 5) 경로 혼선 없이 쓰는 방법

- 로컬 실행 기준은 항상 저장소 루트입니다.
- CLI는 `./scripts/squire.sh ...`로 실행하면 `squire-engine` 디렉터리로 직접 이동할 필요가 없습니다.
- 전역 설치를 완료했다면 `squire ...`로 대체해도 됩니다.
