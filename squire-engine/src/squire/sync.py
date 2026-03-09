from __future__ import annotations

from datetime import datetime
import json
import re
import sqlite3
from typing import Any

from . import db
from .github import GitHubClient

REPO_FULL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def validate_repo_full_name(repo_full_name: str) -> bool:
    return bool(REPO_FULL_NAME_PATTERN.match(repo_full_name))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_pr_state(pr: dict[str, object]) -> str:
    raw_state = str(pr.get("state", "open"))
    if raw_state == "closed" and pr.get("merged_at"):
        return "merged"
    if raw_state not in {"open", "closed"}:
        return "open"
    return raw_state


def _extract_reviewers(pr: dict[str, object]) -> list[str]:
    reviewers: set[str] = set()
    for user in pr.get("requested_reviewers", []) or []:
        login = user.get("login")
        if isinstance(login, str) and login:
            reviewers.add(login)

    for team in pr.get("requested_teams", []) or []:
        slug = team.get("slug")
        if isinstance(slug, str) and slug:
            reviewers.add(f"team:{slug}")

    return sorted(reviewers)


def upsert_pull_request_from_github(
    conn: sqlite3.Connection,
    *,
    repo_full_name: str,
    detail: dict[str, Any],
    synced_at: str | None = None,
    repo_id: int | None = None,
) -> int:
    sync_timestamp = synced_at or db.utcnow_iso()
    if repo_id is None:
        repo_id, _ = db.upsert_repository(conn, repo_full_name)
    state = _normalize_pr_state(detail)
    reviewers = _extract_reviewers(detail)

    return db.upsert_pull_request(
        conn,
        repo_id=repo_id,
        number=int(detail["number"]),
        title=str(detail.get("title") or ""),
        body=detail.get("body"),
        author=str((detail.get("user") or {}).get("login") or "unknown"),
        state=state,
        head_branch=str((detail.get("head") or {}).get("ref") or ""),
        base_branch=str((detail.get("base") or {}).get("ref") or ""),
        changed_files=int(detail.get("changed_files") or 0),
        reviewers_json=json.dumps(reviewers),
        created_at=str(detail.get("created_at") or sync_timestamp),
        updated_at=str(detail.get("updated_at") or sync_timestamp),
        synced_at=sync_timestamp,
    )


def sync_repository(
    conn: sqlite3.Connection,
    github: GitHubClient,
    repo_full_name: str,
    *,
    full_sync: bool = False,
) -> int:
    sync_started_at = db.utcnow_iso()
    existing_repo = db.get_repository(conn, repo_full_name)
    last_synced_at = existing_repo["last_synced_at"] if existing_repo else None
    cutoff = _parse_iso_datetime(last_synced_at)

    repo_id, _ = db.upsert_repository(conn, repo_full_name)
    pulls: list[dict[str, object]] = []

    if full_sync or cutoff is None:
        pulls = github.list_pull_requests(repo_full_name, state="all")
    else:
        page = 1
        per_page = 100

        while True:
            page_items = github.list_pull_requests_page(
                repo_full_name,
                state="all",
                sort="updated",
                direction="desc",
                per_page=per_page,
                page=page,
            )
            if not page_items:
                break

            should_stop = False
            for pull in page_items:
                pull_updated_at = _parse_iso_datetime(str(pull.get("updated_at") or ""))
                if pull_updated_at is not None and pull_updated_at < cutoff:
                    should_stop = True
                    break
                pulls.append(pull)

            if should_stop or len(page_items) < per_page:
                break

            page += 1

    for pull in pulls:
        number = int(pull["number"])
        detail = github.get_pull_request(repo_full_name, number)
        upsert_pull_request_from_github(
            conn,
            repo_full_name=repo_full_name,
            detail=detail,
            synced_at=sync_started_at,
            repo_id=repo_id,
        )

    # Use sync start timestamp as the next incremental watermark.
    db.touch_repository_synced_at(conn, repo_id, synced_at=sync_started_at)
    return len(pulls)
