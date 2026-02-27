# 05. 스킬 설명

## 1) 스킬 개요

- 스킬 이름: `squire-pr-review`
- 위치:
  - Codex: `<project-root>/skills/codex/squire-pr-review`
  - Claude Code: `<project-root>/skills/claude-code/squire-pr-review`
- 목적:
  - `squire` CLI 설치/등록
  - 저장소 등록 및 동기화
  - PR 조회/검토
  - GitHub PR에 코멘트 게시

핵심 가드레일:

- 승인/머지/상태 변경 액션은 수행하지 않습니다.
- `review publish`, `review publish-local` 기반의 코멘트 게시만 수행합니다.

## 2) 스킬 내부 구성

- Codex 버전 (`skills/codex/squire-pr-review`)
  - `SKILL.md`: 트리거 조건, 워크플로우, 가드레일
  - `agents/openai.yaml`: Codex UI 표시 정보 및 기본 프롬프트
  - `scripts/install_squire_cli.sh`: `squire` 전역 설치 스크립트
  - `references/commands.md`: 커맨드 템플릿/오류 대응 레퍼런스
- Claude Code 버전 (`skills/claude-code/squire-pr-review`)
  - `squire-pr-review.md`: Claude Code 슬래시 커맨드 정의
  - `scripts/install_squire_cli.sh`: `squire` 전역 설치 스크립트
  - `references/commands.md`: 커맨드 템플릿/오류 대응 레퍼런스

## 3) 플랫폼별 설치 및 호출

### Codex (OpenAI)

`squire-pr-review` 스킬의 역할은 `squire` CLI 기반 PR 리뷰 워크플로우(저장소 등록/동기화/조회/코멘트 게시)를 Codex에서 재사용 가능하게 만드는 것입니다.

설치 소스(이 프로젝트 기준):

- 저장소: `oenomel87/squire`
- 경로: `skills/codex/squire-pr-review`
- 포크 저장소를 사용한다면 `--repo`만 자신의 저장소로 바꿉니다.

설치 방법 (프로젝트별 설치, 글로벌 설치 안 함):

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

호출:

```text
$squire-pr-review를 사용해 owner/repo를 등록하고 최신 PR을 동기화해줘.
```

여기서 `owner/repo`는 스킬 설치 소스 저장소가 아니라, 리뷰 대상 GitHub 저장소입니다.

### Claude Code

`skills/claude-code/squire-pr-review/squire-pr-review.md` 파일을 사용하려는 프로젝트의 `.claude/commands/`에 복사합니다.

```bash
mkdir -p /path/to/project/.claude/commands
cp <project-root>/skills/claude-code/squire-pr-review/squire-pr-review.md \
   /path/to/project/.claude/commands/
```

이후 해당 프로젝트에서 Claude Code를 실행하면 슬래시 커맨드로 사용할 수 있습니다.

호출:

```text
/squire-pr-review owner/repo
```

## 4) 스킬이 수행하는 기본 흐름

1. `uv`와 환경 변수 상태를 확인합니다.
2. 필요 시 `scripts/install_squire_cli.sh`로 CLI를 전역 설치합니다.
3. `squire repo add`로 저장소 등록/초기 동기화를 수행합니다.
4. `squire sync`(증분) 또는 `--full`(전체)로 동기화합니다.
5. `squire list/show/files/diff/comments/reviews`로 PR 문맥을 수집합니다.
6. `squire review publish` 또는 `publish-local`로 코멘트를 게시합니다.

## 5) 운영 팁

- 다수 저장소 운영 시 `squire repo list`와 `squire sync` 조합으로 일괄 갱신할 수 있습니다.
- PR 코멘트 게시 전 `squire review add`로 로컬 저장 후 일괄 게시하면 추적이 쉽습니다.
- 엔터프라이즈 환경에서는 `.env`의 `GITHUB_BASE_URL`을 조직 API 엔드포인트로 고정해 관리하세요.
