from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_review_thread_comment(node: dict[str, Any]) -> dict[str, Any]:
    author = node.get("author") or {}
    reply_to = node.get("replyTo") or {}
    commit = node.get("commit") or {}
    original_commit = node.get("originalCommit") or {}

    return {
        "id": str(node.get("id") or ""),
        "database_id": _as_int(node.get("databaseId")),
        "url": node.get("url"),
        "body": str(node.get("body") or ""),
        "created_at": str(node.get("createdAt") or ""),
        "updated_at": str(node.get("updatedAt") or node.get("createdAt") or ""),
        "author": str(author.get("login") or "") or None,
        "reply_to_id": str(reply_to.get("id") or "") or None,
        "path": str(node.get("path") or "") or None,
        "line": _as_int(node.get("line")),
        "original_line": _as_int(node.get("originalLine")),
        "commit_oid": str(commit.get("oid") or "") or None,
        "original_commit_oid": str(original_commit.get("oid") or "") or None,
    }


def normalize_review_thread(
    node: dict[str, Any],
    *,
    head_ref_oid: str | None,
) -> dict[str, Any]:
    comments_connection = node.get("comments") or {}
    comment_nodes = comments_connection.get("nodes") or []
    comments = [
        normalize_review_thread_comment(item)
        for item in comment_nodes
        if isinstance(item, dict)
    ]
    comments.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        )
    )

    latest_timestamp: str | None = None
    if comments:
        latest_timestamp = comments[-1]["updated_at"] or comments[-1]["created_at"]

    root_comment = comments[0] if comments else None
    total_count = _as_int(comments_connection.get("totalCount")) or len(comments)

    path = str(node.get("path") or "") or None
    if path is None and root_comment is not None:
        path = root_comment["path"]

    line = _as_int(node.get("line"))
    if line is None and root_comment is not None:
        line = root_comment["line"]

    original_line = _as_int(node.get("originalLine"))
    if original_line is None and root_comment is not None:
        original_line = root_comment["original_line"]

    return {
        "id": str(node.get("id") or ""),
        "is_resolved": bool(node.get("isResolved")),
        "is_outdated": bool(node.get("isOutdated")),
        "path": path,
        "line": line,
        "original_line": original_line,
        "head_ref_oid": head_ref_oid,
        "comment_count": total_count,
        "reply_count": max(total_count - 1, 0),
        "updated_at": latest_timestamp,
        "root_comment_id": root_comment["id"] if root_comment else None,
        "root_author": root_comment["author"] if root_comment else None,
        "comments": comments,
    }


def filter_review_threads(
    threads: list[dict[str, Any]],
    *,
    author: str | None = None,
    unresolved_only: bool = False,
    file_path: str | None = None,
    since_timestamp: datetime | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    normalized_author = author.casefold() if author else None

    for thread in threads:
        if unresolved_only and thread["is_resolved"]:
            continue

        if file_path and thread["path"] != file_path:
            continue

        if normalized_author:
            root_author = thread.get("root_author")
            if not isinstance(root_author, str) or root_author.casefold() != normalized_author:
                continue

        if since_timestamp is not None:
            updated_at = parse_iso_datetime(thread.get("updated_at"))
            if updated_at is None or updated_at < since_timestamp:
                continue

        filtered.append(thread)

    return filtered


def format_thread_location(thread: dict[str, Any]) -> str:
    path = thread.get("path") or "-"
    line = thread.get("line")
    if line is None:
        line = thread.get("original_line")
    if line is None:
        return str(path)
    return f"{path}:{line}"


def _indent_block(body: str) -> list[str]:
    text = body.strip() or "(empty)"
    return [f"    {line}" for line in text.splitlines()]


def format_review_thread(thread: dict[str, Any]) -> str:
    status = "resolved" if thread["is_resolved"] else "unresolved"
    outdated = "yes" if thread["is_outdated"] else "no"
    lines = [
        f"thread_id={thread['id']}",
        (
            f"location={format_thread_location(thread)} "
            f"status={status} outdated={outdated} replies={thread['reply_count']} "
            f"updated_at={thread.get('updated_at') or '-'}"
        ),
    ]

    reply_targets = {
        comment["id"]: comment.get("author") or "unknown"
        for comment in thread.get("comments", [])
    }
    for comment in thread.get("comments", []):
        author = comment.get("author") or "unknown"
        header = f"  {author} · {comment.get('created_at') or '-'}"
        reply_to_id = comment.get("reply_to_id")
        if reply_to_id:
            header += f" reply_to={reply_targets.get(reply_to_id, reply_to_id)}"
        lines.append(header)
        lines.extend(_indent_block(str(comment.get("body") or "")))

    return "\n".join(lines)
