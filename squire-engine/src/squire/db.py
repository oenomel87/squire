from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any

from .config import Settings


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(settings: Settings) -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_synced_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pull_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            number INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            author TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('open', 'closed', 'merged')),
            head_branch TEXT NOT NULL,
            base_branch TEXT NOT NULL,
            changed_files INTEGER NOT NULL DEFAULT 0,
            reviewers TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            UNIQUE (repo_id, number)
        );

        CREATE INDEX IF NOT EXISTS idx_pull_requests_repo_updated
            ON pull_requests(repo_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS ai_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pull_request_id INTEGER NOT NULL REFERENCES pull_requests(id) ON DELETE CASCADE,
            file_path TEXT,
            line_number INTEGER,
            severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
            body TEXT NOT NULL,
            agent TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_ai_reviews_pr
            ON ai_reviews(pull_request_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS pr_review_status (
            pull_request_id INTEGER PRIMARY KEY REFERENCES pull_requests(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('pending', 'in-progress', 'done')),
            updated_at TEXT NOT NULL
        );
        """
    )


def get_repository(
    conn: sqlite3.Connection, repo_full_name: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM repositories WHERE full_name = ?",
        (repo_full_name,),
    ).fetchone()


def upsert_repository(conn: sqlite3.Connection, repo_full_name: str) -> tuple[int, bool]:
    now = utcnow_iso()
    existing = get_repository(conn, repo_full_name)

    if existing:
        conn.execute(
            """
            UPDATE repositories
            SET is_active = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (now, existing["id"]),
        )
        return int(existing["id"]), False

    cursor = conn.execute(
        """
        INSERT INTO repositories (full_name, is_active, created_at, updated_at)
        VALUES (?, 1, ?, ?)
        """,
        (repo_full_name, now, now),
    )
    return int(cursor.lastrowid), True


def list_repositories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM repositories
            ORDER BY full_name ASC
            """
        ).fetchall()
    )


def list_active_repositories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM repositories
            WHERE is_active = 1
            ORDER BY full_name ASC
            """
        ).fetchall()
    )


def remove_repository(conn: sqlite3.Connection, repo_full_name: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM repositories WHERE full_name = ?",
        (repo_full_name,),
    )
    return cursor.rowcount > 0


def touch_repository_synced_at(
    conn: sqlite3.Connection, repo_id: int, *, synced_at: str | None = None
) -> None:
    timestamp = synced_at or utcnow_iso()
    conn.execute(
        """
        UPDATE repositories
        SET last_synced_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, repo_id),
    )


def upsert_pull_request(
    conn: sqlite3.Connection,
    *,
    repo_id: int,
    number: int,
    title: str,
    body: str | None,
    author: str,
    state: str,
    head_branch: str,
    base_branch: str,
    changed_files: int,
    reviewers_json: str,
    created_at: str,
    updated_at: str,
    synced_at: str,
) -> int:
    conn.execute(
        """
        INSERT INTO pull_requests (
            repo_id,
            number,
            title,
            body,
            author,
            state,
            head_branch,
            base_branch,
            changed_files,
            reviewers,
            created_at,
            updated_at,
            synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (repo_id, number)
        DO UPDATE SET
            title = excluded.title,
            body = excluded.body,
            author = excluded.author,
            state = excluded.state,
            head_branch = excluded.head_branch,
            base_branch = excluded.base_branch,
            changed_files = excluded.changed_files,
            reviewers = excluded.reviewers,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at,
            synced_at = excluded.synced_at
        """,
        (
            repo_id,
            number,
            title,
            body,
            author,
            state,
            head_branch,
            base_branch,
            changed_files,
            reviewers_json,
            created_at,
            updated_at,
            synced_at,
        ),
    )

    row = conn.execute(
        """
        SELECT id
        FROM pull_requests
        WHERE repo_id = ? AND number = ?
        """,
        (repo_id, number),
    ).fetchone()
    return int(row["id"])


def get_pull_request_by_repo_and_number(
    conn: sqlite3.Connection, repo_full_name: str, number: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            p.*,
            r.full_name AS repo_full_name,
            COALESCE(s.status, 'pending') AS review_status
        FROM pull_requests p
        JOIN repositories r ON r.id = p.repo_id
        LEFT JOIN pr_review_status s ON s.pull_request_id = p.id
        WHERE r.full_name = ? AND p.number = ?
        """,
        (repo_full_name, number),
    ).fetchone()


def list_pull_requests(
    conn: sqlite3.Connection,
    *,
    repo_full_name: str | None,
    state: str,
) -> list[sqlite3.Row]:
    clauses = ["r.is_active = 1"]
    params: list[Any] = []

    if repo_full_name:
        clauses.append("r.full_name = ?")
        params.append(repo_full_name)

    if state != "all":
        clauses.append("p.state = ?")
        params.append(state)

    where_clause = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT
            p.id,
            p.number,
            p.title,
            p.author,
            p.state,
            p.changed_files,
            p.updated_at,
            r.full_name AS repo_full_name,
            COALESCE(s.status, 'pending') AS review_status
        FROM pull_requests p
        JOIN repositories r ON r.id = p.repo_id
        LEFT JOIN pr_review_status s ON s.pull_request_id = p.id
        WHERE {where_clause}
        ORDER BY p.updated_at DESC
        """,
        tuple(params),
    ).fetchall()

    return list(rows)


def insert_ai_review(
    conn: sqlite3.Connection,
    *,
    pull_request_id: int,
    file_path: str | None,
    line_number: int | None,
    severity: str,
    body: str,
    agent: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO ai_reviews (
            pull_request_id,
            file_path,
            line_number,
            severity,
            body,
            agent,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pull_request_id,
            file_path,
            line_number,
            severity,
            body,
            agent,
            utcnow_iso(),
        ),
    )
    return int(cursor.lastrowid)


def list_ai_reviews(
    conn: sqlite3.Connection, *, pull_request_id: int
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT *
            FROM ai_reviews
            WHERE pull_request_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (pull_request_id,),
        ).fetchall()
    )


def set_review_status(
    conn: sqlite3.Connection, *, pull_request_id: int, status: str
) -> None:
    now = utcnow_iso()
    conn.execute(
        """
        INSERT INTO pr_review_status (pull_request_id, status, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT (pull_request_id)
        DO UPDATE SET
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (pull_request_id, status, now),
    )


def get_review_status(
    conn: sqlite3.Connection, *, pull_request_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM pr_review_status
        WHERE pull_request_id = ?
        """,
        (pull_request_id,),
    ).fetchone()
