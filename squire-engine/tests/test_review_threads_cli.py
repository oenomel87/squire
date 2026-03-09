from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from squire import db
import squire.cli as cli_module
from squire.config import Settings
from squire.github import build_graphql_url


class FakeReviewThreadsGitHubClient:
    def __init__(self) -> None:
        self.threads = [
            {
                "id": "thread-1",
                "is_resolved": False,
                "is_outdated": True,
                "path": "src/main.py",
                "line": 42,
                "original_line": 40,
                "head_ref_oid": "head-sha",
                "comment_count": 2,
                "reply_count": 1,
                "updated_at": "2026-03-09T12:00:00Z",
                "root_comment_id": "comment-1",
                "root_author": "dane-park",
                "comments": [
                    {
                        "id": "comment-1",
                        "database_id": 101,
                        "url": "https://github.example.com/thread-1#comment-1",
                        "body": "변수 이름을 명확하게 바꿔주세요.",
                        "created_at": "2026-03-09T11:00:00Z",
                        "updated_at": "2026-03-09T11:00:00Z",
                        "author": "dane-park",
                        "reply_to_id": None,
                        "path": "src/main.py",
                        "line": 42,
                        "original_line": 40,
                        "commit_oid": "comment-sha-1",
                        "original_commit_oid": "comment-sha-1",
                    },
                    {
                        "id": "comment-2",
                        "database_id": 102,
                        "url": "https://github.example.com/thread-1#comment-2",
                        "body": "최신 커밋에서 반영했습니다.",
                        "created_at": "2026-03-09T12:00:00Z",
                        "updated_at": "2026-03-09T12:00:00Z",
                        "author": "repo-author",
                        "reply_to_id": "comment-1",
                        "path": "src/main.py",
                        "line": 42,
                        "original_line": 40,
                        "commit_oid": "comment-sha-2",
                        "original_commit_oid": "comment-sha-1",
                    },
                ],
            },
            {
                "id": "thread-2",
                "is_resolved": True,
                "is_outdated": False,
                "path": "src/other.py",
                "line": 10,
                "original_line": 10,
                "head_ref_oid": "head-sha",
                "comment_count": 1,
                "reply_count": 0,
                "updated_at": "2026-03-08T08:00:00Z",
                "root_comment_id": "comment-3",
                "root_author": "someone-else",
                "comments": [
                    {
                        "id": "comment-3",
                        "database_id": 103,
                        "url": "https://github.example.com/thread-2#comment-3",
                        "body": "이건 이미 확인했습니다.",
                        "created_at": "2026-03-08T08:00:00Z",
                        "updated_at": "2026-03-08T08:00:00Z",
                        "author": "someone-else",
                        "reply_to_id": None,
                        "path": "src/other.py",
                        "line": 10,
                        "original_line": 10,
                        "commit_oid": "comment-sha-3",
                        "original_commit_oid": "comment-sha-3",
                    }
                ],
            },
        ]

    def __enter__(self) -> "FakeReviewThreadsGitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def list_pull_review_threads(
        self,
        repo_full_name: str,
        number: int,
    ) -> dict[str, object]:
        return {
            "viewer_login": "dane-park",
            "head_ref_oid": "head-sha",
            "threads": list(self.threads),
        }

    def get_pull_review_thread(self, thread_id: str) -> dict[str, object]:
        for thread in self.threads:
            if thread["id"] == thread_id:
                return {
                    "viewer_login": "dane-park",
                    "thread": thread,
                }
        raise AssertionError(f"unknown thread id: {thread_id}")

    def get_commit(self, repo_full_name: str, ref: str) -> dict[str, object]:
        assert ref == "base-sha"
        return {
            "sha": ref,
            "commit": {
                "committer": {
                    "date": "2026-03-09T09:00:00Z",
                }
            },
        }


def _settings_for(db_path: Path) -> Settings:
    return Settings(
        github_token=None,
        github_base_url="https://api.github.com",
        db_path=db_path,
    )


def _seed_repo(db_path: Path, repo_full_name: str) -> None:
    conn = db.connect(_settings_for(db_path))
    try:
        db.upsert_repository(conn, repo_full_name)
        conn.commit()
    finally:
        conn.close()


def test_build_graphql_url_derives_public_and_enterprise_endpoints() -> None:
    assert build_graphql_url("https://api.github.com") == "https://api.github.com/graphql"
    assert (
        build_graphql_url("https://github.example.com/api/v3")
        == "https://github.example.com/api/graphql"
    )


def test_review_threads_lists_unresolved_threads_in_text_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_repo(db_path, repo_full_name)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReviewThreadsGitHubClient()
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["review-threads", "39", "--repo", repo_full_name, "--unresolved"],
    )

    assert result.exit_code == 0, result.output
    assert "thread_id=thread-1" in result.output
    assert "reply_to=dane-park" in result.output
    assert "thread_id=thread-2" not in result.output


def test_review_threads_support_mine_since_and_json_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_repo(db_path, repo_full_name)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReviewThreadsGitHubClient()
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "review-threads",
            "39",
            "--repo",
            repo_full_name,
            "--mine",
            "--since",
            "base-sha",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["viewer_login"] == "dane-park"
    assert [item["id"] for item in payload["items"]] == ["thread-1"]


def test_review_thread_show_outputs_json_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_repo(db_path, repo_full_name)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReviewThreadsGitHubClient()
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["review-thread", "show", "thread-1", "--repo", repo_full_name, "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["thread"]["id"] == "thread-1"
    assert payload["thread"]["reply_count"] == 1
