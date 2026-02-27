---
name: squire-pr-review
description: Operate GitHub pull request workflows with the `squire` CLI. Use when a user wants to install/register `squire`, add target repositories (`squire repo add owner/repo`), run incremental or full sync, inspect PR context (`list/show/files/diff/comments/reviews`), and publish review comments (`squire review publish` or `squire review publish-local`) without changing PR state (no approve/merge/close actions).
---

# Squire PR Review

Use this skill to run the `squire` CLI end-to-end for repository registration, PR synchronization, and comment-only review publishing.

## Quick Checklist

- Confirm `uv` is installed and available.
- Ensure target `squire-engine/.env` has `GITHUB_TOKEN` and `GITHUB_BASE_URL`.
- Prefer a globally installed `squire` command for cross-project usage.
- Use a single shared DB path via `SQUIRE_DB_PATH` (recommended: `$HOME/Library/Application Support/squire/squire.db`).
- If repo/PR is missing locally, run sync first.

## Install CLI

1. Identify the local checkout path that contains `squire-engine/`.
1. Run the installer script in this skill:

```bash
bash scripts/install_squire_cli.sh /path/to/squire-repo
```

1. Open a new shell and verify:

```bash
squire --help
```

If global installation is not possible, run `uv run squire ...` from the `squire-engine` directory.

## Repository Workflow

1. Register target repository and do initial sync:

```bash
squire repo add owner/repo
```

1. Check registered repositories:

```bash
squire repo list
```

1. Run incremental sync (default):

```bash
squire sync --repo owner/repo
```

1. Force full sync only when needed:

```bash
squire sync --repo owner/repo --full
```

## Review Workflow

1. Inspect PR candidates and details:

```bash
squire list --repo owner/repo --state open
squire show 123 --repo owner/repo
```

1. Review file-level and discussion context:

```bash
squire files 123 --repo owner/repo
squire diff 123 --repo owner/repo
squire comments 123 --repo owner/repo
squire reviews 123 --repo owner/repo
```

1. Publish a direct opinion comment to GitHub PR:

```bash
squire review publish 123 --repo owner/repo --body "review comment"
```

1. Or publish previously staged local review comments:

```bash
squire review add 123 --repo owner/repo --severity warning --body "local finding"
squire review publish-local 123 --repo owner/repo --all
```

## Guardrails

- Do not run approve/merge/close/reopen or any PR state-changing actions.
- Use only comment publishing flows (`review publish`, `review publish-local`) for GitHub write operations.
- Always rely on `GITHUB_BASE_URL` from `.env`; do not introduce alternate base URL logic.
- Use `uv` for installation/execution in this project context, not plain `python`/`pip`.

## References

Read [references/commands.md](references/commands.md) for command templates and troubleshooting.
