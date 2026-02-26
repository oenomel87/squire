# squire-engine

`squire-engine` is the backend/CLI implementation for local PR proxy workflows.

## Environment

- Use `uv` venv only.
- Required env vars in `.env`:
  - `GITHUB_TOKEN`
  - `GITHUB_BASE_URL` (always required, e.g. `https://api.github.com`)

## Commands

```bash
uv sync
uv run squire --help
uv run squire serve --host 127.0.0.1 --port 8484
```

Repository registration and immediate sync:

```bash
uv run squire repo add owner/repo
uv run squire repo list
```

PR sync and local query:

```bash
uv run squire sync
uv run squire sync --repo owner/repo --full
uv run squire list --repo owner/repo --state open
uv run squire show 123 --repo owner/repo
```

Publish review opinion to actual GitHub PR (no approve/merge action):

```bash
uv run squire review publish 123 --repo owner/repo --body "의견 내용"

# 로컬에 저장된 리뷰 코멘트를 GitHub에 게시
uv run squire review publish-local 123 --repo owner/repo --all
```

`squire review publish`/`publish-local`은 PR 상태를 변경하지 않고 GitHub 코멘트만 추가합니다.

## API (MVP)

Run:

```bash
uv run squire serve --reload
```

Main endpoints:

- `GET /health`
- `GET /repos`
- `POST /repos` (register + immediate sync)
- `DELETE /repos/{owner/repo}`
- `POST /sync?repo=owner/repo&full=false`
- `GET /pulls?repo=owner/repo&state=open`
- `GET /pulls/{number}?repo=owner/repo`
- `GET /pulls/{number}/files?repo=owner/repo`
- `GET /pulls/{number}/diff?repo=owner/repo`
- `GET /pulls/{number}/comments?repo=owner/repo`
- `GET /pulls/{number}/github-reviews?repo=owner/repo`
- `POST /pulls/{number}/local-reviews?repo=owner/repo`
- `GET /pulls/{number}/local-reviews?repo=owner/repo`
- `PUT /pulls/{number}/review-status?repo=owner/repo`
