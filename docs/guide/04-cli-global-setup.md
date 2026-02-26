# 04. CLI 글로벌 설정 방법

이 문서는 `squire` 커맨드를 다른 프로젝트 디렉터리에서도 바로 사용하도록 전역 등록하는 방법을 설명합니다.

`<project-root>`는 `squire` 저장소 루트 경로를 의미합니다.

## 1) 권장 방법: 프로젝트 스크립트 사용

```bash
cd <project-root>
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
uv tool install --editable <project-root>/squire-engine --force
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
cd <project-root>
./scripts/install-squire-tool.sh
```

## 6) 트러블슈팅

### `squire: command not found`

1. `uv tool update-shell` 재실행
2. 새 터미널 재시작
3. `echo $PATH`에 `uv` tool bin 경로 포함 여부 확인

### 실행은 되지만 GitHub 호출 실패

- `squire-engine/.env`의 `GITHUB_TOKEN`, `GITHUB_BASE_URL` 확인
- 토큰 권한(코멘트 작성 가능 여부) 확인

### 로컬 DB를 별도 위치로 사용하고 싶은 경우

- `SQUIRE_DB_PATH` 환경변수를 설정해 DB 파일 경로를 분리할 수 있습니다.
