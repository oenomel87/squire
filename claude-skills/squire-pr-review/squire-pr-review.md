# Squire PR Review

`squire` CLI를 사용해 GitHub PR 워크플로우를 수행합니다. 저장소 등록, PR 동기화, 코드 리뷰 코멘트 게시까지의 전체 흐름을 실행합니다.

## 사용법

```
/squire-pr-review owner/repo
```

`$ARGUMENTS`가 주어지면 대상 저장소(`owner/repo`)로 사용합니다.

## 사전 확인

1. `uv`가 설치되어 있는지 확인합니다. 없으면 https://docs.astral.sh/uv/ 안내를 제공합니다.
2. `squire` 커맨드가 전역 사용 가능한지 확인합니다 (`which squire`).
   없으면 사용자에게 squire 프로젝트의 `squire-engine` 디렉터리 경로를 물어본 뒤 아래로 설치합니다:
   ```bash
   uv tool install --editable <사용자가 알려준 경로> --force && uv tool update-shell
   ```
3. `squire-engine/.env`에 `GITHUB_TOKEN`과 `GITHUB_BASE_URL`이 설정되어 있어야 합니다.

## 워크플로우

### 1단계: 저장소 등록 및 동기화

```bash
squire repo add $ARGUMENTS
squire sync --repo $ARGUMENTS
```

이미 등록된 저장소라면 `sync`만 실행합니다.

### 2단계: PR 조회 및 문맥 파악

```bash
squire list --repo $ARGUMENTS --state open
squire show <PR번호> --repo $ARGUMENTS
squire files <PR번호> --repo $ARGUMENTS
squire diff <PR번호> --repo $ARGUMENTS
squire comments <PR번호> --repo $ARGUMENTS
squire reviews <PR번호> --repo $ARGUMENTS
```

### 3단계: 리뷰 코멘트 작성 및 게시

직접 GitHub PR에 코멘트 게시:

```bash
squire review publish <PR번호> --repo $ARGUMENTS --body "리뷰 의견"
```

또는 로컬에 먼저 저장 후 일괄 게시:

```bash
squire review add <PR번호> --repo $ARGUMENTS --severity warning --body "리뷰 의견"
squire review publish-local <PR번호> --repo $ARGUMENTS --all
```

## 가드레일

- PR 상태 변경 액션(approve, merge, close, reopen)은 절대 수행하지 않습니다.
- `review publish` 또는 `review publish-local` 기반의 코멘트 게시만 수행합니다.
- `.env`의 `GITHUB_BASE_URL`을 그대로 사용하며, 별도의 base URL 로직을 추가하지 않습니다.
- 엔진 관련 실행은 반드시 `uv`를 사용합니다 (`python`/`pip` 직접 사용 금지).

## 커맨드 레퍼런스

### 저장소 관리

```bash
squire repo add owner/repo      # 저장소 등록 + 즉시 1회 동기화
squire repo list                 # 등록된 저장소 목록 조회
squire repo remove owner/repo   # 저장소 등록 해제
```

### 동기화

```bash
squire sync                            # 모든 등록 저장소 증분 동기화
squire sync --repo owner/repo         # 특정 저장소 증분 동기화
squire sync --repo owner/repo --full  # 전체 동기화 (워터마크 무시)
```

### PR 조회

```bash
squire list --repo owner/repo --state open|closed|all
squire show 123 --repo owner/repo
squire files 123 --repo owner/repo
squire diff 123 --repo owner/repo [--file path/to/file]
squire comments 123 --repo owner/repo
squire reviews 123 --repo owner/repo
```

### 리뷰 코멘트 관리

```bash
# 직접 게시
squire review publish 123 --repo owner/repo --body "의견" [--prefix "[AI Review]"]

# 로컬 저장
squire review add 123 --repo owner/repo --body "의견" [--severity info|warning|error] [--file path] [--line N]

# 로컬 리뷰 조회
squire review list 123 --repo owner/repo

# 로컬 리뷰 게시
squire review publish-local 123 --repo owner/repo --all
squire review publish-local 123 --repo owner/repo --id 10 --id 11

# 리뷰 상태 변경
squire review status 123 --repo owner/repo --set pending|in-progress|done
```

## 일반적인 오류 대응

- `Repository ... is not registered`: `squire repo add owner/repo`를 먼저 실행합니다.
- `PR #... not found in local DB`: `squire sync --repo owner/repo`를 실행합니다.
- `403/401 from GitHub`: 토큰 권한과 `GITHUB_BASE_URL` 설정을 확인합니다.
