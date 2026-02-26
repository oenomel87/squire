# squire-client

Squire 대시보드 UI입니다. squire-engine API와 연동해 AI가 생성한 PR 리뷰 코멘트를 조회하고 GitHub 게시 여부를 결정할 수 있습니다.

## 실행

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VITE_SQUIRE_API_BASE_URL` | `http://127.0.0.1:8484` | squire-engine API 주소 |

엔진을 다른 포트에서 실행한 경우:

```bash
VITE_SQUIRE_API_BASE_URL=http://127.0.0.1:9000 npm run dev -- --host 127.0.0.1 --port 5173
```

## 빌드

```bash
npm run build   # TypeScript 체크 + 프로덕션 빌드
npm run preview # 빌드 결과물 로컬 확인
npm run lint    # ESLint 검사
```
