from __future__ import annotations

from contextlib import contextmanager
from enum import StrEnum
import json

import typer

from . import db
from .config import get_settings
from .github import GitHubClient, GitHubError
from .keychain import (
    KeychainCommandError,
    KeychainUnavailableError,
    delete_github_token,
    get_github_token,
    has_github_token,
    set_github_token,
)
from .sync import sync_repository, validate_repo_full_name

app = typer.Typer(no_args_is_help=True, help="Squire CLI")
repo_app = typer.Typer(no_args_is_help=True, help="Manage target repositories")
review_app = typer.Typer(
    no_args_is_help=True,
    help="Manage local AI reviews and publish opinion comments",
)

app.add_typer(repo_app, name="repo")
app.add_typer(review_app, name="review")


class PRState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    DONE = "done"


@contextmanager
def _open_connection():
    settings = get_settings()
    conn = db.connect(settings)
    try:
        yield conn
    finally:
        conn.close()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_repo_github_config(conn, repo_full_name: str) -> tuple[str | None, str]:
    repository = _require_registered_repo(conn, repo_full_name)
    settings = get_settings()
    repo_token = get_github_token(repo_full_name)
    if repo_token is None:
        repo_token = db.get_repository_legacy_github_token(conn, repo_full_name)
    repo_base_url = _normalize_optional_text(repository["github_base_url"])
    token = repo_token or settings.github_token
    base_url = (repo_base_url or settings.github_base_url).rstrip("/")
    return token, base_url


def _open_github_client_for_repo(conn, repo_full_name: str) -> GitHubClient:
    token, base_url = _resolve_repo_github_config(conn, repo_full_name)
    try:
        return GitHubClient(
            token=token,
            base_url=base_url,
        )
    except GitHubError as exc:
        _exit_with_error(str(exc))


def _exit_with_error(message: str, code: int = 1) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


def _require_registered_repo(conn, repo_full_name: str):
    row = db.get_repository(conn, repo_full_name)
    if row is None:
        _exit_with_error(
            f"Repository `{repo_full_name}` is not registered. "
            f"Run `squire repo add {repo_full_name}` first."
        )
    return row


def _require_pull_request(conn, repo_full_name: str, number: int):
    pull_request = db.get_pull_request_by_repo_and_number(conn, repo_full_name, number)
    if pull_request is None:
        _exit_with_error(
            f"PR #{number} for `{repo_full_name}` not found in local DB. "
            f"Run `squire sync --repo {repo_full_name}` first."
        )
    return pull_request


@repo_app.command("add")
def repo_add(
    repo_full_name: str,
    github_token: str | None = typer.Option(
        None,
        "--github-token",
        help=(
            "Repository-specific token (stored in macOS Keychain). "
            "If omitted, keep existing/global. Pass empty string to clear."
        ),
    ),
    github_base_url: str | None = typer.Option(
        None,
        "--github-base-url",
        help=(
            "Repository-specific GitHub API base URL. "
            "If omitted, keep existing/global. Pass empty string to clear."
        ),
    ),
) -> None:
    """Register repository and immediately sync once."""

    if not validate_repo_full_name(repo_full_name):
        _exit_with_error("Repository must be in `owner/repo` format.")

    with _open_connection() as conn:
        _, created_new = db.upsert_repository(conn, repo_full_name)
        if github_token is not None:
            token = _normalize_optional_text(github_token)
            try:
                if token:
                    set_github_token(repo_full_name, token)
                else:
                    delete_github_token(repo_full_name)
            except (KeychainCommandError, KeychainUnavailableError) as exc:
                _exit_with_error(
                    f"Failed to update macOS Keychain token for `{repo_full_name}`: {exc}"
                )
            db.clear_repository_legacy_github_token(conn, repo_full_name)

        db.update_repository_github_config(
            conn,
            repo_full_name,
            github_base_url=github_base_url,
            update_base_url=github_base_url is not None,
        )
        conn.commit()

        try:
            with _open_github_client_for_repo(conn, repo_full_name) as github:
                synced_count = sync_repository(conn, github, repo_full_name)
            conn.commit()
            typer.echo(
                f"Registered `{repo_full_name}` and synced {synced_count} pull request(s)."
            )
        except (GitHubError, Exception) as exc:
            conn.rollback()
            if created_new:
                db.remove_repository(conn, repo_full_name)
                conn.commit()
                if _normalize_optional_text(github_token):
                    try:
                        delete_github_token(repo_full_name)
                    except KeychainCommandError:
                        pass
            _exit_with_error(f"Failed to sync `{repo_full_name}`: {exc}")


@repo_app.command("list")
def repo_list() -> None:
    """List registered repositories."""

    with _open_connection() as conn:
        repos = db.list_repositories(conn)
        if not repos:
            typer.echo("No repositories registered.")
            return

        for repo in repos:
            status = "active" if int(repo["is_active"]) == 1 else "inactive"
            last_synced_at = repo["last_synced_at"] or "-"
            repo_name = str(repo["full_name"])
            try:
                has_keychain_token = has_github_token(repo_name)
            except KeychainCommandError:
                has_keychain_token = False
            token_scope = (
                "repo"
                if has_keychain_token
                or bool(db.get_repository_legacy_github_token(conn, repo_name))
                else "global"
            )
            base_url = _normalize_optional_text(repo["github_base_url"]) or "<global>"
            typer.echo(
                f"{repo_name} [{status}] "
                f"last_synced_at={last_synced_at} "
                f"github_token={token_scope} "
                f"github_base_url={base_url}"
            )


@repo_app.command("remove")
def repo_remove(repo_full_name: str) -> None:
    """Remove repository registration."""

    with _open_connection() as conn:
        removed = db.remove_repository(conn, repo_full_name)
        conn.commit()

        if not removed:
            _exit_with_error(f"Repository `{repo_full_name}` is not registered.")

        try:
            delete_github_token(repo_full_name)
        except KeychainCommandError as exc:
            _exit_with_error(
                f"Removed repository row but failed to delete Keychain token: {exc}"
            )
        typer.echo(f"Removed repository `{repo_full_name}`.")


@repo_app.command("migrate-legacy-tokens")
def repo_migrate_legacy_tokens() -> None:
    """Move legacy DB tokens into macOS Keychain and clear DB copies."""

    with _open_connection() as conn:
        if not db.repository_has_column(conn, "github_token"):
            typer.echo("No legacy DB token column detected. Nothing to migrate.")
            return

        repos = db.list_repositories(conn)
        migrated = 0
        failed = 0

        for repo in repos:
            repo_name = str(repo["full_name"])
            legacy_token = db.get_repository_legacy_github_token(conn, repo_name)
            if not legacy_token:
                continue

            try:
                set_github_token(repo_name, legacy_token)
                db.clear_repository_legacy_github_token(conn, repo_name)
                migrated += 1
            except (KeychainCommandError, KeychainUnavailableError) as exc:
                failed += 1
                typer.secho(
                    f"{repo_name}: token migration failed - {exc}",
                    fg=typer.colors.RED,
                    err=True,
                )

        conn.commit()

    typer.echo(f"Migrated {migrated} legacy token(s) to macOS Keychain.")
    if failed:
        raise typer.Exit(code=1)


@app.command("sync")
def sync(
    repo_full_name: str | None = typer.Option(
        None,
        "--repo",
        help="Target repository in owner/repo format",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Force full sync and ignore incremental watermark.",
    ),
) -> None:
    """Synchronize PR metadata from GitHub into local DB."""

    with _open_connection() as conn:
        if repo_full_name:
            _require_registered_repo(conn, repo_full_name)
            targets = [repo_full_name]
        else:
            targets = [r["full_name"] for r in db.list_active_repositories(conn)]

        if not targets:
            typer.echo("No active repositories. Run `squire repo add <owner/repo>` first.")
            return

        errors = 0
        for target in targets:
            try:
                with _open_github_client_for_repo(conn, target) as github:
                    synced = sync_repository(conn, github, target, full_sync=full)
                conn.commit()
                typer.echo(f"{target}: synced {synced} pull request(s).")
            except (GitHubError, Exception) as exc:
                conn.rollback()
                errors += 1
                typer.secho(
                    f"{target}: sync failed - {exc}",
                    fg=typer.colors.RED,
                    err=True,
                )

        if errors:
            raise typer.Exit(code=1)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8484, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Run FastAPI server."""

    import uvicorn

    uvicorn.run(
        "squire.api:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command("list")
def list_pull_requests(
    repo_full_name: str | None = typer.Option(
        None,
        "--repo",
        help="Filter by repository (owner/repo)",
    ),
    state: PRState = typer.Option(PRState.OPEN, "--state"),
) -> None:
    """List locally cached pull requests."""

    with _open_connection() as conn:
        if repo_full_name:
            _require_registered_repo(conn, repo_full_name)

        rows = db.list_pull_requests(
            conn,
            repo_full_name=repo_full_name,
            state=state.value,
        )

        if not rows:
            typer.echo("No pull requests found.")
            return

        for row in rows:
            typer.echo(
                f"{row['repo_full_name']}#{row['number']} "
                f"[{row['state']}] [review:{row['review_status']}] "
                f"files={row['changed_files']} "
                f"by={row['author']} "
                f"title={row['title']}"
            )


@app.command("show")
def show_pull_request(
    number: int,
    repo_full_name: str = typer.Option(
        ...,
        "--repo",
        help="Repository in owner/repo format",
    ),
) -> None:
    """Show local PR details."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        row = _require_pull_request(conn, repo_full_name, number)

        data = {
            "id": row["id"],
            "repo": row["repo_full_name"],
            "number": row["number"],
            "title": row["title"],
            "body": row["body"],
            "author": row["author"],
            "state": row["state"],
            "head_branch": row["head_branch"],
            "base_branch": row["base_branch"],
            "changed_files": row["changed_files"],
            "reviewers": json.loads(row["reviewers"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "synced_at": row["synced_at"],
            "review_status": row["review_status"],
        }
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command("files")
def files(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
) -> None:
    """Show changed file list from GitHub API."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        with _open_github_client_for_repo(conn, repo_full_name) as github:
            files_data = github.list_pull_files(repo_full_name, number)

    if not files_data:
        typer.echo("No changed files found.")
        return

    for file_data in files_data:
        typer.echo(
            f"{str(file_data.get('status', '-')).ljust(8)} "
            f"+{int(file_data.get('additions') or 0):<4} "
            f"-{int(file_data.get('deletions') or 0):<4} "
            f"{file_data.get('filename')}"
        )


@app.command("diff")
def diff(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
    file_path: str | None = typer.Option(None, "--file"),
) -> None:
    """Show PR diff from GitHub API."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        with _open_github_client_for_repo(conn, repo_full_name) as github:
            if file_path:
                files_data = github.list_pull_files(repo_full_name, number)
                for file_data in files_data:
                    if file_data.get("filename") == file_path:
                        patch = file_data.get("patch")
                        if patch:
                            typer.echo(patch)
                        else:
                            typer.echo(f"No text diff available for `{file_path}`.")
                        return
                _exit_with_error(f"`{file_path}` is not part of PR #{number}.")
            else:
                typer.echo(github.get_pull_diff(repo_full_name, number))


@app.command("comments")
def comments(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
) -> None:
    """Show GitHub issue comments for a PR."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        with _open_github_client_for_repo(conn, repo_full_name) as github:
            comments_data = github.list_issue_comments(repo_full_name, number)
    typer.echo(json.dumps(comments_data, indent=2, ensure_ascii=False))


@app.command("reviews")
def reviews(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
) -> None:
    """Show GitHub review events for a PR."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        with _open_github_client_for_repo(conn, repo_full_name) as github:
            reviews_data = github.list_pull_reviews(repo_full_name, number)
    typer.echo(json.dumps(reviews_data, indent=2, ensure_ascii=False))


def _publish_github_comment(
    *,
    repo_full_name: str,
    number: int,
    body: str,
    prefix: str,
) -> None:
    text = body.strip()
    if not text:
        _exit_with_error("Comment body must not be empty.")

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        _require_pull_request(conn, repo_full_name, number)
        comment_body = f"{prefix}\n\n{text}" if prefix else text

        with _open_github_client_for_repo(conn, repo_full_name) as github:
            created = github.create_issue_comment(repo_full_name, number, comment_body)

    comment_id = created.get("id", "-")
    comment_url = created.get("html_url", "-")
    typer.echo(f"Posted GitHub comment id={comment_id} url={comment_url}")


@review_app.command("publish")
def review_publish(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
    body: str = typer.Option(..., "--body"),
    prefix: str = typer.Option(
        "[AI Review]",
        "--prefix",
        help="Prefix added before comment body",
    ),
) -> None:
    """Publish one opinion comment to GitHub PR without changing PR state."""

    _publish_github_comment(
        repo_full_name=repo_full_name,
        number=number,
        body=body,
        prefix=prefix,
    )


@review_app.command("publish-local")
def review_publish_local(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
    all_items: bool = typer.Option(
        False,
        "--all",
        help="Publish all locally saved review comments for the PR",
    ),
    review_id: list[int] = typer.Option(
        [],
        "--id",
        help="Specific local review id to publish (repeatable)",
    ),
    prefix: str = typer.Option(
        "[AI Review]",
        "--prefix",
        help="Prefix added before comment body",
    ),
) -> None:
    """Publish local AI review comments to GitHub PR without changing PR state."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        pr = _require_pull_request(conn, repo_full_name, number)
        local_reviews = db.list_ai_reviews(conn, pull_request_id=pr["id"])

    if not local_reviews:
        _exit_with_error("No local AI review comments to publish.")

    selected: list = []
    if all_items:
        selected = local_reviews
    elif review_id:
        wanted = set(review_id)
        selected = [item for item in local_reviews if int(item["id"]) in wanted]
        missing = sorted(wanted - {int(item["id"]) for item in selected})
        if missing:
            _exit_with_error(
                "Some review id(s) were not found for this PR: "
                + ", ".join(str(item) for item in missing)
            )
    else:
        _exit_with_error("Specify either `--all` or one/more `--id`.")

    for item in selected:
        target = "PR"
        if item["file_path"]:
            target = f"{item['file_path']}:{item['line_number'] or '-'}"
        body = (
            f"[{item['severity']}] {target}\n\n"
            f"{item['body']}\n\n"
            f"(agent={item['agent']}, local_review_id={item['id']})"
        )
        _publish_github_comment(
            repo_full_name=repo_full_name,
            number=number,
            body=body,
            prefix=prefix,
        )

    typer.echo(f"Published {len(selected)} local review comment(s) to GitHub PR #{number}.")


@review_app.command("add")
def review_add(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
    body: str = typer.Option(..., "--body"),
    file_path: str | None = typer.Option(None, "--file"),
    line: int | None = typer.Option(None, "--line"),
    severity: Severity = typer.Option(Severity.INFO, "--severity"),
    agent: str = typer.Option("codex", "--agent"),
) -> None:
    """Add local AI review comment."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        pr = _require_pull_request(conn, repo_full_name, number)
        review_id = db.insert_ai_review(
            conn,
            pull_request_id=pr["id"],
            file_path=file_path,
            line_number=line,
            severity=severity.value,
            body=body,
            agent=agent,
        )
        conn.commit()

    typer.echo(f"Added AI review comment id={review_id}.")


@review_app.command("list")
def review_list(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
) -> None:
    """List local AI review comments for a PR."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        pr = _require_pull_request(conn, repo_full_name, number)
        reviews_data = db.list_ai_reviews(conn, pull_request_id=pr["id"])
        status = db.get_review_status(conn, pull_request_id=pr["id"])

    review_status = status["status"] if status else "pending"
    typer.echo(f"review_status={review_status}")

    if not reviews_data:
        typer.echo("No AI review comments.")
        return

    for item in reviews_data:
        target = "PR"
        if item["file_path"]:
            target = f"{item['file_path']}:{item['line_number'] or '-'}"
        typer.echo(
            f"[{item['severity']}] {target} {item['body']} "
            f"(agent={item['agent']}, created_at={item['created_at']})"
        )


@review_app.command("status")
def review_status(
    number: int,
    repo_full_name: str = typer.Option(..., "--repo"),
    set_status: ReviewStatus = typer.Option(..., "--set"),
) -> None:
    """Set local review workflow status for a PR."""

    with _open_connection() as conn:
        _require_registered_repo(conn, repo_full_name)
        pr = _require_pull_request(conn, repo_full_name, number)
        db.set_review_status(
            conn,
            pull_request_id=pr["id"],
            status=set_status.value,
        )
        conn.commit()

    typer.echo(f"Set review status to `{set_status.value}` for PR #{number}.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
