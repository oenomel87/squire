from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from squire import db
import squire.api as api_module
import squire.cli as cli_module
from squire.config import Settings


class FakeGitHubClient:
    def __init__(self) -> None:
        self.created_requests: list[dict[str, object]] = []

    def __enter__(self) -> "FakeGitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def create_pull_request(
        self,
        repo_full_name: str,
        *,
        title: str,
        head: str,
        base: str,
        body: str | None = None,
        draft: bool = False,
        maintainer_can_modify: bool = True,
        head_repo: str | None = None,
    ) -> dict[str, object]:
        request = {
            "repo_full_name": repo_full_name,
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
            "maintainer_can_modify": maintainer_can_modify,
            "head_repo": head_repo,
        }
        self.created_requests.append(request)
        return {
            "number": 42,
            "html_url": "https://github.example.com/owner/repo/pull/42",
            "draft": draft,
        }

    def get_pull_request(self, repo_full_name: str, number: int) -> dict[str, object]:
        request = self.created_requests[-1]
        return {
            "number": number,
            "title": request["title"],
            "body": request["body"],
            "state": "open",
            "draft": request["draft"],
            "html_url": "https://github.example.com/owner/repo/pull/42",
            "user": {"login": "octocat"},
            "head": {"ref": request["head"]},
            "base": {"ref": request["base"]},
            "requested_reviewers": [{"login": "alice"}],
            "requested_teams": [{"slug": "backend"}],
            "changed_files": 0,
            "created_at": "2026-03-09T12:00:00+00:00",
            "updated_at": "2026-03-09T12:00:00+00:00",
        }


def _settings_for(db_path: Path) -> Settings:
    return Settings(
        github_token=None,
        github_base_url="https://api.github.com",
        db_path=db_path,
    )


def _seed_repository(db_path: Path, repo_full_name: str) -> None:
    conn = db.connect(_settings_for(db_path))
    try:
        db.upsert_repository(conn, repo_full_name)
        conn.commit()
    finally:
        conn.close()


def test_create_pull_api_creates_and_caches_pull_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_repository(db_path, repo_full_name)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeGitHubClient()
    monkeypatch.setattr(
        api_module,
        "open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    client = TestClient(api_module.app)
    response = client.post(
        "/pulls",
        params={"repo": repo_full_name},
        json={
            "title": "Add PR creation",
            "head": "feature/pr-create",
            "base": "main",
            "body": "Implements PR creation",
            "draft": True,
            "maintainer_can_modify": False,
            "head_repo": "owner-fork",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["repo"] == repo_full_name
    assert payload["number"] == 42
    assert payload["title"] == "Add PR creation"
    assert payload["draft"] is True
    assert payload["html_url"] == "https://github.example.com/owner/repo/pull/42"
    assert fake_github.created_requests == [
        {
            "repo_full_name": repo_full_name,
            "title": "Add PR creation",
            "head": "feature/pr-create",
            "base": "main",
            "body": "Implements PR creation",
            "draft": True,
            "maintainer_can_modify": False,
            "head_repo": "owner-fork",
        }
    ]

    conn = db.connect(_settings_for(db_path))
    try:
        row = db.get_pull_request_by_repo_and_number(conn, repo_full_name, 42)
    finally:
        conn.close()

    assert row is not None
    assert row["title"] == "Add PR creation"
    assert row["head_branch"] == "feature/pr-create"
    assert row["base_branch"] == "main"


def test_create_pull_cli_prints_json_and_caches_pull_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_repository(db_path, repo_full_name)
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeGitHubClient()
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "create",
            "--repo",
            repo_full_name,
            "--title",
            "Ship PR creation",
            "--head",
            "feature/pr-create",
            "--base",
            "main",
            "--body",
            "CLI path",
            "--draft",
            "--head-repo",
            "owner-fork",
            "--no-maintainer-can-modify",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["repo"] == repo_full_name
    assert payload["number"] == 42
    assert payload["title"] == "Ship PR creation"
    assert payload["draft"] is True
    assert payload["head_branch"] == "feature/pr-create"
    assert payload["base_branch"] == "main"

    conn = db.connect(_settings_for(db_path))
    try:
        row = db.get_pull_request_by_repo_and_number(conn, repo_full_name, 42)
    finally:
        conn.close()

    assert row is not None
    assert row["title"] == "Ship PR creation"
