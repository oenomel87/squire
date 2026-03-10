from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from squire import db
import squire.api as api_module
import squire.cli as cli_module
from squire.config import Settings


class FakeReactionGitHubClient:
    def __init__(self) -> None:
        self.issue_reactions: list[dict[str, object]] = []
        self.review_reactions: list[dict[str, object]] = []

    def __enter__(self) -> "FakeReactionGitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def create_issue_comment_reaction(
        self,
        repo_full_name: str,
        comment_id: int,
        *,
        content: str,
    ) -> dict[str, object]:
        payload = {
            "repo_full_name": repo_full_name,
            "comment_id": comment_id,
            "content": content,
        }
        self.issue_reactions.append(payload)
        return {
            "id": 5001,
            "content": content,
            "user": {"login": "octocat"},
        }

    def create_pull_review_comment_reaction(
        self,
        repo_full_name: str,
        comment_id: int,
        *,
        content: str,
    ) -> dict[str, object]:
        payload = {
            "repo_full_name": repo_full_name,
            "comment_id": comment_id,
            "content": content,
        }
        self.review_reactions.append(payload)
        return {
            "id": 6001,
            "content": content,
            "user": {"login": "octocat"},
        }


def _settings_for(db_path: Path) -> Settings:
    return Settings(
        github_token=None,
        github_base_url="https://api.github.com",
        db_path=db_path,
    )


def _seed_pull_request(
    db_path: Path,
    *,
    repo_full_name: str,
    number: int,
) -> None:
    conn = db.connect(_settings_for(db_path))
    try:
        repo_id, _ = db.upsert_repository(conn, repo_full_name)
        db.upsert_pull_request(
            conn,
            repo_id=repo_id,
            number=number,
            title="Example PR",
            body="",
            author="octocat",
            state="open",
            head_branch="feature/reactions",
            base_branch="main",
            changed_files=1,
            reviewers_json="[]",
            created_at="2026-03-09T12:00:00+00:00",
            updated_at="2026-03-09T12:00:00+00:00",
            synced_at="2026-03-09T12:00:00+00:00",
        )
        conn.commit()
    finally:
        conn.close()


def test_create_comment_reaction_api_posts_issue_comment_reaction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_pull_request(db_path, repo_full_name=repo_full_name, number=42)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReactionGitHubClient()
    monkeypatch.setattr(
        api_module,
        "open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    client = TestClient(api_module.app)
    response = client.post(
        "/pulls/42/comment-reactions",
        params={"repo": repo_full_name},
        json={
            "comment_id": 101,
            "comment_type": "issue",
            "content": "eyes",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 5001,
        "content": "eyes",
        "user_login": "octocat",
    }
    assert fake_github.issue_reactions == [
        {
            "repo_full_name": repo_full_name,
            "comment_id": 101,
            "content": "eyes",
        }
    ]
    assert fake_github.review_reactions == []


def test_react_cli_posts_review_comment_reaction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_pull_request(db_path, repo_full_name=repo_full_name, number=42)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReactionGitHubClient()
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "react",
            "42",
            "--repo",
            repo_full_name,
            "--comment-id",
            "202",
            "--type",
            "review",
            "--content",
            "rocket",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "content=rocket" in result.output
    assert fake_github.issue_reactions == []
    assert fake_github.review_reactions == [
        {
            "repo_full_name": repo_full_name,
            "comment_id": 202,
            "content": "rocket",
        }
    ]
