# 03. CLI 커맨드 목록

## 1) 기본 형식

- 로컬 실행(권장): `./scripts/squire.sh --help`
- 하위 그룹 도움말: `./scripts/squire.sh repo --help`, `./scripts/squire.sh review --help`
- 전역 설치 후: `squire --help`

저장소 루트에서 `./scripts/squire.sh ...`를 사용하면 `squire-engine` 디렉터리로 직접 이동할 필요가 없습니다.
전역 설치 후에는 어느 디렉터리에서든 `squire ...` 실행이 가능합니다.
아래 예시는 `squire ...` 기준으로 적지만, 전역 설치 전에는 같은 위치에 `./scripts/squire.sh`를 사용하면 됩니다.

## 2) 최상위 커맨드

| 커맨드 | 설명 |
|---|---|
| `squire sync` | GitHub PR 메타데이터를 로컬 DB로 동기화 |
| `squire serve` | FastAPI 서버 실행 |
| `squire list` | 로컬 캐시 PR 목록 조회 |
| `squire create` | GitHub PR 생성 + 로컬 DB 캐시 반영 |
| `squire show` | 특정 PR 상세 조회 |
| `squire files` | PR 변경 파일 목록 조회 |
| `squire diff` | PR diff 조회 |
| `squire comments` | GitHub PR 이슈 코멘트 조회 |
| `squire reviews` | GitHub PR 리뷰 이벤트 조회 |
| `squire review-threads` | GitHub PR 인라인 리뷰 스레드 조회 |
| `squire review-thread ...` | 단일 GitHub 리뷰 스레드 상세 조회 |
| `squire repo ...` | 대상 저장소 관리 |
| `squire review ...` | 로컬 리뷰/코멘트 게시 관리 |

## 3) `repo` 그룹

### `squire repo add REPO_FULL_NAME`

- 설명: 저장소 등록 + 즉시 1회 동기화
- 옵션:
  - `--github-token`: 해당 저장소 전용 GitHub 토큰 개별 설정 (macOS Keychain에 저장)
  - `--github-base-url`: 해당 저장소 전용 GitHub API Base URL 개별 설정
- 예시:

```bash
squire repo add owner/repo
squire repo add owner/repo --github-token <repo_token>
squire repo add owner/repo --github-base-url https://github.mycompany.com/api/v3
```

참고:

- 저장소별 토큰은 SQLite가 아닌 macOS Keychain(service=`squire.github.token`)에 저장됩니다.
- `squire repo remove owner/repo` 시 해당 저장소 Keychain 토큰도 함께 삭제됩니다.

### `squire repo list`

- 설명: 등록된 저장소 목록 조회
- 예시:

```bash
squire repo list
```

### `squire repo migrate-legacy-tokens`

- 설명: 과거 SQLite에 저장된 레거시 토큰을 macOS Keychain으로 이전하고 DB 값 제거
- 예시:

```bash
squire repo migrate-legacy-tokens
```

### `squire repo remove REPO_FULL_NAME`

- 설명: 저장소 등록 해제
- 예시:

```bash
squire repo remove owner/repo
```

## 4) PR 동기화/조회 커맨드

### `squire sync [--repo owner/repo] [--full]`

- `--repo`: 특정 저장소만 동기화
- `--full`: 증분 워터마크를 무시하고 전체 동기화

예시:

```bash
# 모든 등록 저장소 증분 동기화
squire sync

# 특정 저장소 증분 동기화
squire sync --repo owner/repo

# 특정 저장소 전체 동기화
squire sync --repo owner/repo --full
```

### `squire list [--repo owner/repo] [--state open|closed|all]`

예시:

```bash
squire list --repo owner/repo --state open
```

### `squire create --repo owner/repo --title "..." --head branch --base main [--body "..."] [--draft]`

- 설명: GitHub에 새 PR 생성 후 결과를 로컬 DB에도 즉시 캐시
- 주요 옵션:
  - `--head`: 소스 브랜치명 또는 cross-repo PR용 `user:branch`
  - `--base`: 대상 브랜치명
  - `--head-repo`: same-network fork에서 필요한 경우 head 저장소 지정
  - `--maintainer-can-modify/--no-maintainer-can-modify`: maintainer push 허용 여부

예시:

```bash
squire create --repo owner/repo --title "새 기능 추가" --head feature/new-flow --base main
squire create --repo owner/repo --title "Draft PR" --head feature/wip --base develop --draft
```

### `squire show NUMBER --repo owner/repo`

예시:

```bash
squire show 123 --repo owner/repo
```

### `squire files NUMBER --repo owner/repo`

예시:

```bash
squire files 123 --repo owner/repo
```

### `squire diff NUMBER --repo owner/repo [--file path/to/file]`

예시:

```bash
# 전체 diff
squire diff 123 --repo owner/repo

# 특정 파일 diff
squire diff 123 --repo owner/repo --file src/main.py
```

### `squire comments NUMBER --repo owner/repo`

예시:

```bash
squire comments 123 --repo owner/repo
```

### `squire reviews NUMBER --repo owner/repo`

예시:

```bash
squire reviews 123 --repo owner/repo
```

### `squire review-threads NUMBER --repo owner/repo [--author LOGIN|--mine] [--unresolved] [--file path] [--since <commit>] [--json]`

- 설명: PR의 GitHub 인라인 리뷰 스레드와 답글을 조회
- `--author`: 루트 리뷰 코멘트 작성자 기준 필터
- `--mine`: 현재 인증된 viewer login 기준 필터
- `--unresolved`: unresolved 스레드만 조회
- `--file`: 파일 경로 기준 필터
- `--since`: 지정 commit의 committer timestamp 이후로 갱신된 스레드만 근사 필터
- `--json`: 구조화된 JSON 출력

예시:

```bash
squire review-threads 123 --repo owner/repo
squire review-threads 123 --repo owner/repo --mine --unresolved
squire review-threads 123 --repo owner/repo --file src/main.py --json
```

### `squire review-thread show THREAD_ID --repo owner/repo [--json]`

- 설명: 단일 리뷰 스레드 상세 조회

예시:

```bash
squire review-thread show PRRT_kwDOExample --repo owner/repo
```

## 5) `review` 그룹

### `squire review publish NUMBER --repo owner/repo --body "..." [--prefix "..."]`

- 설명: PR 상태 변경 없이 GitHub PR에 코멘트 1건 게시
- 기본 prefix: `[AI Review]`

예시:

```bash
squire review publish 123 --repo owner/repo --body "의견 내용"
```

### `squire review publish-local NUMBER --repo owner/repo (--all | --id N...) [--prefix "..."]`

- 설명: 로컬 리뷰 코멘트를 GitHub PR에 게시
- `--all`: 해당 PR의 로컬 리뷰 전체 게시
- `--id`: 특정 로컬 리뷰 ID만 게시(반복 가능)
- `review add`에서 `--file`/`--line`이 저장된 항목은 GitHub 파일 인라인 코멘트를 우선 시도
- 인라인 diff 라인 매핑이 실패하면 일반 PR 코멘트로 자동 fallback

예시:

```bash
squire review publish-local 123 --repo owner/repo --all
squire review publish-local 123 --repo owner/repo --id 10 --id 11
```

### `squire review add NUMBER --repo owner/repo --body "..." [--file ...] [--line ...] [--severity info|warning|error] [--agent ...]`

- 설명: 로컬 리뷰 코멘트 추가
- 기본값: `--severity info`, `--agent codex`
- `--file`/`--line`을 함께 주면 이후 `publish-local`에서 인라인 게시 대상으로 사용

예시:

```bash
squire review add 123 --repo owner/repo --severity warning --file src/main.py --line 42 --body "경계값 확인 필요"
```

### `squire review list NUMBER --repo owner/repo`

- 설명: PR의 로컬 리뷰 코멘트 목록 조회

### `squire review status NUMBER --repo owner/repo --set pending|in-progress|done`

- 설명: 로컬 리뷰 진행 상태 변경

예시:

```bash
squire review status 123 --repo owner/repo --set in-progress
```

## 6) 권장 운영 흐름

```bash
# 1) 저장소 등록(초기 동기화 포함)
squire repo add owner/repo

# 2) 증분 동기화
squire sync --repo owner/repo

# 3) PR 파악
squire list --repo owner/repo --state open
squire create --repo owner/repo --title "새 기능 추가" --head feature/new-flow --base main
squire show 123 --repo owner/repo
squire files 123 --repo owner/repo

# 4) 로컬 리뷰 작성
squire review add 123 --repo owner/repo --severity warning --body "리뷰 의견"

# 5) 코멘트 게시 (PR 상태 변경 없음)
squire review publish-local 123 --repo owner/repo --all
```
