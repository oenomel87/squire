# Squire Command Reference

## Prerequisites

- `uv` installed
- `GITHUB_TOKEN` and `GITHUB_BASE_URL` set in `squire-engine/.env`
- single shared DB path configured (recommended):

```bash
mkdir -p "$HOME/Library/Application Support/squire"
export SQUIRE_DB_PATH="$HOME/Library/Application Support/squire/squire.db"
```

## Install Once

```bash
bash scripts/install_squire_cli.sh /path/to/squire-repo
squire --help
```

## Register Repositories

```bash
squire repo add owner/repo
squire repo list
squire repo remove owner/repo
```

## Synchronization

```bash
# Incremental (default)
squire sync --repo owner/repo

# All registered repos
squire sync

# Full resync
squire sync --repo owner/repo --full
```

## PR Inspection

```bash
squire list --repo owner/repo --state open
squire show 123 --repo owner/repo
squire files 123 --repo owner/repo
squire diff 123 --repo owner/repo
squire comments 123 --repo owner/repo
squire reviews 123 --repo owner/repo
```

## Comment-Only Review Publishing

```bash
# Direct comment
squire review publish 123 --repo owner/repo --body "review comment"

# Local staging + publish
squire review add 123 --repo owner/repo --severity warning --body "local finding"
squire review list 123 --repo owner/repo
squire review publish-local 123 --repo owner/repo --all
```

## Common Errors

- `Repository ... is not registered`: run `squire repo add owner/repo` first.
- `PR #... not found in local DB`: run `squire sync --repo owner/repo`.
- `403/401 from GitHub`: verify token permission and `GITHUB_BASE_URL`.
- `attempt to write a readonly database`: set `SQUIRE_DB_PATH` to a writable
  shared path and retry (recommended:
  `$HOME/Library/Application Support/squire/squire.db`).
