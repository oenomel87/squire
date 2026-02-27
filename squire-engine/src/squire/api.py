from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

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

app = FastAPI(title="Squire API", version="0.1.0")


def _load_allowed_origins() -> list[str]:
    raw = os.getenv("SQUIRE_ALLOWED_ORIGINS")
    if raw:
        parsed = [item.strip() for item in raw.split(",") if item.strip()]
        if parsed:
            return parsed

    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PRState = Literal["open", "closed", "all"]
Severity = Literal["info", "warning", "error"]
ReviewStatus = Literal["pending", "in-progress", "done"]


class RepoAddRequest(BaseModel):
    full_name: str = Field(..., description="Repository in owner/repo format")
    full_sync: bool = Field(
        False,
        description="Force full sync instead of incremental sync after registration",
    )
    github_token: str | None = Field(
        default=None,
        description=(
            "Optional repository-specific GitHub token. "
            "If omitted, the global `GITHUB_TOKEN` is used. "
            "When provided, token is stored in macOS Keychain."
        ),
    )
    github_base_url: str | None = Field(
        default=None,
        description=(
            "Optional repository-specific GitHub API base URL. "
            "If omitted, the global `GITHUB_BASE_URL` (or default) is used."
        ),
    )


class RepoResponse(BaseModel):
    id: int
    full_name: str
    is_active: bool
    created_at: str
    updated_at: str
    last_synced_at: str | None
    has_custom_github_token: bool
    github_base_url: str | None


class RepoAddResponse(BaseModel):
    full_name: str
    created: bool
    synced_pull_requests: int


class SyncResult(BaseModel):
    repo: str
    synced_pull_requests: int


class PullRequestSummary(BaseModel):
    id: int
    repo: str
    number: int
    title: str
    author: str
    state: str
    changed_files: int
    updated_at: str
    review_status: str


class PullRequestDetail(BaseModel):
    id: int
    repo: str
    number: int
    title: str
    body: str | None
    author: str
    state: str
    head_branch: str
    base_branch: str
    changed_files: int
    reviewers: list[str]
    created_at: str
    updated_at: str
    synced_at: str
    review_status: str


class LocalReviewCreateRequest(BaseModel):
    body: str
    severity: Severity = "info"
    file_path: str | None = None
    line_number: int | None = None
    agent: str = "codex"


class LocalReviewResponse(BaseModel):
    id: int
    file_path: str | None
    line_number: int | None
    severity: Severity
    body: str
    agent: str
    created_at: str


class LocalReviewListResponse(BaseModel):
    review_status: ReviewStatus
    items: list[LocalReviewResponse]


class ReviewStatusUpdateRequest(BaseModel):
    status: ReviewStatus


@contextmanager
def open_connection():
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


def _resolve_repo_github_config(
    conn: sqlite3.Connection, repo: str
) -> tuple[str | None, str]:
    repository = _require_repository(conn, repo)
    settings = get_settings()

    repo_token = get_github_token(repo)
    if repo_token is None:
        repo_token = db.get_repository_legacy_github_token(conn, repo)

    repo_base_url = _normalize_optional_text(repository["github_base_url"])

    token = repo_token or settings.github_token
    base_url = (repo_base_url or settings.github_base_url).rstrip("/")
    return token, base_url


@contextmanager
def open_github_client_for_repo(conn: sqlite3.Connection, repo: str):
    token, base_url = _resolve_repo_github_config(conn, repo)
    try:
        client = GitHubClient(
            token=token,
            base_url=base_url,
        )
    except GitHubError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        yield client
    finally:
        client.close()


def _to_repo_response(conn: sqlite3.Connection, row: sqlite3.Row) -> RepoResponse:
    full_name = str(row["full_name"])
    try:
        has_keychain_token = has_github_token(full_name)
    except KeychainCommandError:
        has_keychain_token = False
    has_custom_token = has_keychain_token or bool(
        db.get_repository_legacy_github_token(conn, full_name)
    )
    return RepoResponse(
        id=int(row["id"]),
        full_name=full_name,
        is_active=int(row["is_active"]) == 1,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        last_synced_at=row["last_synced_at"],
        has_custom_github_token=has_custom_token,
        github_base_url=_normalize_optional_text(row["github_base_url"]),
    )


def _to_pull_summary(row: sqlite3.Row) -> PullRequestSummary:
    return PullRequestSummary(
        id=int(row["id"]),
        repo=str(row["repo_full_name"]),
        number=int(row["number"]),
        title=str(row["title"]),
        author=str(row["author"]),
        state=str(row["state"]),
        changed_files=int(row["changed_files"]),
        updated_at=str(row["updated_at"]),
        review_status=str(row["review_status"]),
    )


def _to_pull_detail(row: sqlite3.Row) -> PullRequestDetail:
    reviewers: list[str] = []
    raw_reviewers = row["reviewers"]
    if isinstance(raw_reviewers, str):
        try:
            parsed = json.loads(raw_reviewers)
            if isinstance(parsed, list):
                reviewers = [str(item) for item in parsed]
        except json.JSONDecodeError:
            reviewers = []

    return PullRequestDetail(
        id=int(row["id"]),
        repo=str(row["repo_full_name"]),
        number=int(row["number"]),
        title=str(row["title"]),
        body=row["body"],
        author=str(row["author"]),
        state=str(row["state"]),
        head_branch=str(row["head_branch"]),
        base_branch=str(row["base_branch"]),
        changed_files=int(row["changed_files"]),
        reviewers=reviewers,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        synced_at=str(row["synced_at"]),
        review_status=str(row["review_status"]),
    )


def _to_local_review(row: sqlite3.Row) -> LocalReviewResponse:
    return LocalReviewResponse(
        id=int(row["id"]),
        file_path=row["file_path"],
        line_number=row["line_number"],
        severity=row["severity"],
        body=str(row["body"]),
        agent=str(row["agent"]),
        created_at=str(row["created_at"]),
    )


def _require_repository(conn: sqlite3.Connection, repo: str) -> sqlite3.Row:
    row = db.get_repository(conn, repo)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Repository `{repo}` is not registered. "
                "Register it first via `POST /repos`."
            ),
        )
    return row


def _require_pull_request(
    conn: sqlite3.Connection, repo: str, number: int
) -> sqlite3.Row:
    row = db.get_pull_request_by_repo_and_number(conn, repo, number)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR #{number} for `{repo}` not found in local DB.",
        )
    return row


def _sync_single_repository(
    conn: sqlite3.Connection, repo: str, *, full_sync: bool
) -> SyncResult:
    try:
        with open_github_client_for_repo(conn, repo) as github:
            synced = sync_repository(conn, github, repo, full_sync=full_sync)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except GitHubError as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{repo}: sync failed - {exc}",
        ) from exc
    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{repo}: sync failed - {exc}",
        ) from exc

    return SyncResult(repo=repo, synced_pull_requests=synced)


def _apply_repo_github_overrides(
    conn: sqlite3.Connection,
    repo: str,
    request: RepoAddRequest,
) -> None:
    update_token = "github_token" in request.model_fields_set
    update_base_url = "github_base_url" in request.model_fields_set
    if update_token:
        token = _normalize_optional_text(request.github_token)
        try:
            if token:
                set_github_token(repo, token)
            else:
                delete_github_token(repo)
        except KeychainUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Repository token override requires macOS Keychain: {exc}",
            ) from exc
        except KeychainCommandError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update macOS Keychain token for `{repo}`: {exc}",
            ) from exc

        db.clear_repository_legacy_github_token(conn, repo)

    if update_base_url:
        db.update_repository_github_config(
            conn,
            repo,
            github_base_url=request.github_base_url,
            update_base_url=True,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/repos", response_model=list[RepoResponse])
def list_repos() -> list[RepoResponse]:
    with open_connection() as conn:
        rows = db.list_repositories(conn)
        return [_to_repo_response(conn, row) for row in rows]


@app.post("/repos", response_model=RepoAddResponse)
def add_repo(request: RepoAddRequest) -> RepoAddResponse:
    repo = request.full_name.strip()
    if not validate_repo_full_name(repo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository must be in `owner/repo` format.",
        )
    created_with_new_token = "github_token" in request.model_fields_set and bool(
        _normalize_optional_text(request.github_token)
    )

    with open_connection() as conn:
        _, created = db.upsert_repository(conn, repo)
        _apply_repo_github_overrides(conn, repo, request)
        conn.commit()

        try:
            result = _sync_single_repository(conn, repo, full_sync=request.full_sync)
        except HTTPException:
            if created:
                db.remove_repository(conn, repo)
                conn.commit()
                if created_with_new_token:
                    try:
                        delete_github_token(repo)
                    except KeychainCommandError:
                        pass
            raise

    return RepoAddResponse(
        full_name=repo,
        created=created,
        synced_pull_requests=result.synced_pull_requests,
    )


@app.delete("/repos/{repo_full_name:path}")
def remove_repo(repo_full_name: str) -> dict[str, Any]:
    repo = repo_full_name.strip()
    with open_connection() as conn:
        removed = db.remove_repository(conn, repo)
        conn.commit()

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository `{repo}` is not registered.",
        )
    try:
        delete_github_token(repo)
    except KeychainCommandError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository row removed, but failed to delete Keychain token: {exc}",
        ) from exc
    return {"removed": True, "repo": repo}


@app.post("/sync", response_model=list[SyncResult])
def sync(
    repo: str | None = Query(None, description="Repository in owner/repo format"),
    full: bool = Query(False, description="Force full sync"),
) -> list[SyncResult]:
    with open_connection() as conn:
        targets: list[str]
        if repo:
            _require_repository(conn, repo)
            targets = [repo]
        else:
            targets = [str(row["full_name"]) for row in db.list_active_repositories(conn)]

        if not targets:
            return []

        results: list[SyncResult] = []
        for target in targets:
            results.append(_sync_single_repository(conn, target, full_sync=full))
        return results


@app.get("/pulls", response_model=list[PullRequestSummary])
def list_pulls(
    repo: str | None = Query(None, description="Filter by owner/repo"),
    state: PRState = Query("open", description="open, closed, all"),
) -> list[PullRequestSummary]:
    with open_connection() as conn:
        if repo:
            _require_repository(conn, repo)

        rows = db.list_pull_requests(conn, repo_full_name=repo, state=state)
    return [_to_pull_summary(row) for row in rows]


@app.get("/pulls/{number}", response_model=PullRequestDetail)
def get_pull(number: int, repo: str = Query(..., description="owner/repo")) -> PullRequestDetail:
    with open_connection() as conn:
        _require_repository(conn, repo)
        row = _require_pull_request(conn, repo, number)
    return _to_pull_detail(row)


@app.get("/pulls/{number}/files")
def get_pull_files(
    number: int,
    repo: str = Query(..., description="owner/repo"),
) -> list[dict[str, Any]]:
    with open_connection() as conn:
        _require_repository(conn, repo)
        with open_github_client_for_repo(conn, repo) as github:
            try:
                files = github.list_pull_files(repo, number)
            except GitHubError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc

    normalized: list[dict[str, Any]] = []
    for item in files:
        normalized.append(
            {
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
                "changes": item.get("changes"),
            }
        )
    return normalized


@app.get("/pulls/{number}/diff", response_class=PlainTextResponse)
def get_pull_diff(
    number: int,
    repo: str = Query(..., description="owner/repo"),
    file: str | None = Query(None, description="Return patch for a specific file"),
) -> str:
    with open_connection() as conn:
        _require_repository(conn, repo)
        with open_github_client_for_repo(conn, repo) as github:
            try:
                if file:
                    files = github.list_pull_files(repo, number)
                    for item in files:
                        if item.get("filename") == file:
                            patch = item.get("patch")
                            if patch:
                                return str(patch)
                            return f"No text diff available for `{file}`."
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"`{file}` is not part of PR #{number}.",
                    )

                return github.get_pull_diff(repo, number)
            except HTTPException:
                raise
            except GitHubError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc


@app.get("/pulls/{number}/comments")
def get_pull_comments(
    number: int,
    repo: str = Query(..., description="owner/repo"),
) -> list[dict[str, Any]]:
    with open_connection() as conn:
        _require_repository(conn, repo)
        with open_github_client_for_repo(conn, repo) as github:
            try:
                return github.list_issue_comments(repo, number)
            except GitHubError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc


@app.get("/pulls/{number}/github-reviews")
def get_pull_github_reviews(
    number: int,
    repo: str = Query(..., description="owner/repo"),
) -> list[dict[str, Any]]:
    with open_connection() as conn:
        _require_repository(conn, repo)
        with open_github_client_for_repo(conn, repo) as github:
            try:
                return github.list_pull_reviews(repo, number)
            except GitHubError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc


@app.post("/pulls/{number}/local-reviews", response_model=LocalReviewResponse)
def create_local_review(
    number: int,
    request: LocalReviewCreateRequest,
    repo: str = Query(..., description="owner/repo"),
) -> LocalReviewResponse:
    with open_connection() as conn:
        _require_repository(conn, repo)
        pull_request = _require_pull_request(conn, repo, number)
        review_id = db.insert_ai_review(
            conn,
            pull_request_id=int(pull_request["id"]),
            file_path=request.file_path,
            line_number=request.line_number,
            severity=request.severity,
            body=request.body,
            agent=request.agent,
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM ai_reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load created review record.",
            )
    return _to_local_review(row)


@app.get("/pulls/{number}/local-reviews", response_model=LocalReviewListResponse)
def list_local_reviews(
    number: int,
    repo: str = Query(..., description="owner/repo"),
) -> LocalReviewListResponse:
    with open_connection() as conn:
        _require_repository(conn, repo)
        pull_request = _require_pull_request(conn, repo, number)
        pull_request_id = int(pull_request["id"])

        status_row = db.get_review_status(conn, pull_request_id=pull_request_id)
        review_status: ReviewStatus = (
            status_row["status"] if status_row else "pending"
        )
        rows = db.list_ai_reviews(conn, pull_request_id=pull_request_id)

    return LocalReviewListResponse(
        review_status=review_status,
        items=[_to_local_review(row) for row in rows],
    )


@app.put("/pulls/{number}/review-status")
def update_local_review_status(
    number: int,
    request: ReviewStatusUpdateRequest,
    repo: str = Query(..., description="owner/repo"),
) -> dict[str, Any]:
    with open_connection() as conn:
        _require_repository(conn, repo)
        pull_request = _require_pull_request(conn, repo, number)
        db.set_review_status(
            conn,
            pull_request_id=int(pull_request["id"]),
            status=request.status,
        )
        conn.commit()

    return {
        "repo": repo,
        "number": number,
        "status": request.status,
    }
