# 04. CLI 글로벌 설정 방법

이 문서는 `squire` 커맨드를 다른 프로젝트 디렉터리에서도 바로 사용하도록 전역 등록하는 방법을 설명합니다.

> 이 문서의 예시에서 `~/squire`는 이 저장소를 clone한 디렉터리를 의미합니다. 실제 경로가 다르다면 자신의 경로로 바꿔 읽으세요.

전역 설치를 원하지 않는다면 저장소 루트에서 `./scripts/squire.sh ...`를 사용해도 됩니다.

## 1) 권장 방법: 프로젝트 스크립트 사용

```bash
cd ~/squire
./scripts/install-squire-tool.sh
```

스크립트가 수행하는 작업:

1. `uv` 존재 여부 확인
2. `squire-engine` 경로 확인
3. `uv tool install --editable ... --force`로 전역 설치
4. `uv tool update-shell`로 PATH 설정 보정

설치 확인:

```bash
squire --help
```

## 2) 수동 방법: `uv` 직접 실행

```bash
uv tool install --editable ~/squire/squire-engine --force
uv tool update-shell
squire --help
```

## 3) 스킬 내 설치 스크립트 사용(선택)

`squire-pr-review` 스킬을 설치한 환경에서는 아래 스크립트로도 동일한 전역 설치를 수행할 수 있습니다.

```bash
bash /path/to/squire-pr-review/scripts/install_squire_cli.sh /path/to/squire-repo
```

## 4) 전역 설치 후 사용 예시

```bash
# 어떤 디렉터리에서도 실행 가능
squire repo list
squire sync
```

## 5) 업데이트/재설치

코드 변경 후 최신 상태를 반영하려면 다시 설치합니다.

```bash
cd ~/squire
./scripts/install-squire-tool.sh
```

## 6) 트러블슈팅

### `squire: command not found`

1. `uv tool update-shell` 재실행
2. 새 터미널 재시작
3. `echo $PATH`에 `uv` tool bin 경로 포함 여부 확인

### 실행은 되지만 GitHub 호출 실패

- `squire-engine/.env`의 `GITHUB_TOKEN`, `GITHUB_BASE_URL` 확인
- review thread 조회 기능은 GraphQL endpoint도 사용하지만, 별도 `GITHUB_GRAPHQL_URL` 설정은 필요 없습니다.
  - `GITHUB_BASE_URL=https://api.github.com` -> `https://api.github.com/graphql`
  - `GITHUB_BASE_URL=https://github.example.com/api/v3` -> `https://github.example.com/api/graphql`
- 토큰 권한 확인
  - 읽기 전용: `Pull Requests: Read`, `Contents: Read`
  - 코멘트 게시 시: `Pull Requests: Write` 추가
  - `PAT classic`의 `repo` 전체 권한은 필수 아님

### 로컬 DB를 별도 위치로 사용하고 싶은 경우

- 단일 엔진 운영이라면 DB도 단일 경로로 고정하는 것을 권장합니다.
- macOS 권장 경로: `$HOME/Library/Application Support/squire/squire.db`

```bash
mkdir -p "$HOME/Library/Application Support/squire"
export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"
```

영구 적용:

```bash
echo 'export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"' >> ~/.zshrc
source ~/.zshrc
```

### `attempt to write a readonly database` 오류

- 보통 DB 경로가 현재 실행 환경에서 쓰기 불가능한 위치를 가리킬 때 발생합니다.
- `SQUIRE_DB_PATH`를 쓰기 가능한 단일 경로로 고정하고 재시도하세요.

```bash
mkdir -p "$HOME/Library/Application Support/squire"
export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"
```
