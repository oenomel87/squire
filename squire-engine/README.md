# squire-engine

`squire-engine`는 로컬 PR 프록시 워크플로를 위한 백엔드/CLI 구현입니다.

## 환경 변수

- 런타임/의존성 관리는 `uv`만 사용합니다.
- `.env`의 필수/선택 변수:
  - `GITHUB_TOKEN` (모든 저장소를 Keychain 토큰으로만 운영하지 않는 경우)
  - `GITHUB_BASE_URL` (선택, 기본값 `https://api.github.com`)
    - GitHub Enterprise Server 사용 시 설정합니다.
    - 예시: `https://github.mycompany.com/api/v3`
    - review thread 조회용 GraphQL URL은 이 값으로부터 자동 파생합니다.
      - `https://api.github.com` -> `https://api.github.com/graphql`
      - `https://github.mycompany.com/api/v3` -> `https://github.mycompany.com/api/graphql`
- `GITHUB_TOKEN` / `GITHUB_BASE_URL`는 전역 기본값입니다.
  - 저장소 등록 시 저장소별 값으로 덮어쓸 수 있습니다.

## 토큰 저장 방식 (macOS)

- 저장소 전용 `--github-token` 값은 macOS Keychain에 저장됩니다.
- Squire는 저장소 전용 토큰 값을 SQLite에 평문 저장하지 않습니다.
- Keychain 항목 형식:
  - service: `squire.github.token`
  - account: `<owner/repo>`
- 기존 DB의 레거시 토큰은 하위 호환용 보조 경로로만 읽습니다.

## 기본 명령

저장소 루트(`~/squire`)에서 아래처럼 실행하면 `squire-engine` 디렉터리로 직접 이동할 필요가 없습니다.

```bash
cd ~/squire
uv sync --project squire-engine
./scripts/squire.sh --help
./scripts/squire.sh serve --host 127.0.0.1 --port 8484
```

저장소 등록 및 즉시 동기화:

```bash
./scripts/squire.sh repo add owner/repo
./scripts/squire.sh repo add owner/repo --github-token <repo_token>
./scripts/squire.sh repo add owner/repo --github-base-url https://github.mycompany.com/api/v3
./scripts/squire.sh repo migrate-legacy-tokens
./scripts/squire.sh repo list
```

Keychain 수동 관리:

```bash
# 토큰 저장/갱신 (프롬프트 입력)
security add-generic-password -a owner/repo -s squire.github.token -U -w

# 토큰 조회
security find-generic-password -a owner/repo -s squire.github.token -w

# 토큰 삭제
security delete-generic-password -a owner/repo -s squire.github.token
```

PR 동기화 및 로컬 조회:

```bash
./scripts/squire.sh sync
./scripts/squire.sh sync --repo owner/repo --full
./scripts/squire.sh list --repo owner/repo --state open
./scripts/squire.sh show 123 --repo owner/repo
./scripts/squire.sh review-threads 123 --repo owner/repo
./scripts/squire.sh review-thread show <thread-id> --repo owner/repo
./scripts/squire.sh create --repo owner/repo --title "새 기능 추가" --head feature/new-flow --base main
```

실제 GitHub PR에 리뷰 의견 코멘트 게시 (approve/merge 동작 없음):

```bash
./scripts/squire.sh review publish 123 --repo owner/repo --body "의견 내용"

# 로컬에 저장된 리뷰 코멘트를 GitHub에 게시
./scripts/squire.sh review publish-local 123 --repo owner/repo --all
```

`squire create`/`review publish`/`publish-local`은 모두 `Pull Requests: Write` 권한이 필요합니다.
`squire review publish`/`publish-local`은 PR 상태를 변경하지 않고 GitHub 코멘트만 추가합니다.
`squire review add --file ... --line ...`로 저장한 로컬 리뷰는 `publish-local` 시 GitHub 인라인 코멘트를 우선 시도하고, diff 라인 매핑이 불가능하면 일반 PR 코멘트로 fallback 합니다.

## API (MVP)

실행:

```bash
./scripts/squire.sh serve --reload
```

주요 엔드포인트:

- `GET /health`
- `GET /repos`
- `POST /repos` (저장소 등록 + 즉시 동기화, `github_token` / `github_base_url` 저장소별 지정 가능)
- `DELETE /repos/{owner/repo}`
- `POST /sync?repo=owner/repo&full=false`
- `GET /pulls?repo=owner/repo&state=open`
- `POST /pulls?repo=owner/repo`
- `GET /pulls/{number}?repo=owner/repo`
- `GET /pulls/{number}/files?repo=owner/repo`
- `GET /pulls/{number}/diff?repo=owner/repo`
- `GET /pulls/{number}/comments?repo=owner/repo`
- `GET /pulls/{number}/github-reviews?repo=owner/repo`
- `POST /pulls/{number}/local-reviews?repo=owner/repo`
- `GET /pulls/{number}/local-reviews?repo=owner/repo`
- `PUT /pulls/{number}/review-status?repo=owner/repo`
