from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from squire import db
import squire.cli as cli_module
from squire.config import Settings
from squire.review_comments import resolve_inline_comment_target


class FakeReviewPublishGitHubClient:
    def __init__(self, *, patch: str | None, status_code_for_inline: int | None = None) -> None:
        self.patch = patch
        self.status_code_for_inline = status_code_for_inline
        self.inline_comments: list[dict[str, object]] = []
        self.issue_comments: list[dict[str, object]] = []

    def __enter__(self) -> "FakeReviewPublishGitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_pull_request(self, repo_full_name: str, number: int) -> dict[str, object]:
        return {
            "number": number,
            "head": {"sha": "abc123def"},
        }

    def list_pull_files(self, repo_full_name: str, number: int) -> list[dict[str, object]]:
        return [
            {
                "filename": "src/main.py",
                "patch": self.patch,
            }
        ]

    def create_pull_review_comment(
        self,
        repo_full_name: str,
        number: int,
        *,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str,
    ) -> dict[str, object]:
        if self.status_code_for_inline is not None:
            raise cli_module.GitHubError(
                "validation failed",
                status_code=self.status_code_for_inline,
                path=f"repos/{repo_full_name}/pulls/{number}/comments",
            )

        payload = {
            "repo_full_name": repo_full_name,
            "number": number,
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": side,
        }
        self.inline_comments.append(payload)
        return {
            "id": 9001,
            "html_url": "https://github.example.com/owner/repo/pull/42#discussion_r9001",
        }

    def create_issue_comment(
        self,
        repo_full_name: str,
        issue_number: int,
        body: str,
    ) -> dict[str, object]:
        payload = {
            "repo_full_name": repo_full_name,
            "issue_number": issue_number,
            "body": body,
        }
        self.issue_comments.append(payload)
        return {
            "id": 7001,
            "html_url": "https://github.example.com/owner/repo/pull/42#issuecomment-7001",
        }


def _settings_for(db_path: Path) -> Settings:
    return Settings(
        github_token=None,
        github_base_url="https://api.github.com",
        db_path=db_path,
    )


def _seed_review(
    db_path: Path,
    *,
    repo_full_name: str,
    number: int,
    file_path: str,
    line_number: int,
) -> int:
    conn = db.connect(_settings_for(db_path))
    try:
        repo_id, _ = db.upsert_repository(conn, repo_full_name)
        pull_request_id = db.upsert_pull_request(
            conn,
            repo_id=repo_id,
            number=number,
            title="Example PR",
            body="",
            author="octocat",
            state="open",
            head_branch="feature/inline",
            base_branch="main",
            changed_files=1,
            reviewers_json="[]",
            created_at="2026-03-09T12:00:00+00:00",
            updated_at="2026-03-09T12:00:00+00:00",
            synced_at="2026-03-09T12:00:00+00:00",
        )
        review_id = db.insert_ai_review(
            conn,
            pull_request_id=pull_request_id,
            file_path=file_path,
            line_number=line_number,
            severity="warning",
            body="경계값 확인 필요",
            agent="codex",
        )
        conn.commit()
        return review_id
    finally:
        conn.close()


def test_resolve_inline_comment_target_prefers_right_side() -> None:
    target = resolve_inline_comment_target(
        {"head": {"sha": "abc123def"}},
        [
            {
                "filename": "src/main.py",
                "patch": "@@ -10,2 +10,2 @@\n-old_value\n+new_value\n",
            }
        ],
        file_path="src/main.py",
        line_number=10,
    )

    assert target is not None
    assert target.commit_id == "abc123def"
    assert target.path == "src/main.py"
    assert target.line == 10
    assert target.side == "RIGHT"


def test_review_publish_local_posts_inline_comment_when_diff_line_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_review(
        db_path,
        repo_full_name=repo_full_name,
        number=42,
        file_path="src/main.py",
        line_number=11,
    )
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReviewPublishGitHubClient(
        patch="@@ -10,2 +10,3 @@\n context\n+new_value\n tail\n",
    )
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["review", "publish-local", "42", "--repo", repo_full_name, "--all"],
    )

    assert result.exit_code == 0, result.output
    assert len(fake_github.inline_comments) == 1
    assert fake_github.inline_comments[0]["path"] == "src/main.py"
    assert fake_github.inline_comments[0]["line"] == 11
    assert fake_github.inline_comments[0]["side"] == "RIGHT"
    assert len(fake_github.issue_comments) == 0


def test_review_publish_local_falls_back_to_pr_comment_when_line_unmapped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "squire.db"
    repo_full_name = "owner/repo"
    _seed_review(
        db_path,
        repo_full_name=repo_full_name,
        number=42,
        file_path="src/main.py",
        line_number=99,
    )
    monkeypatch.setenv("SQUIRE_DB_PATH", str(db_path))

    fake_github = FakeReviewPublishGitHubClient(
        patch="@@ -10,2 +10,3 @@\n context\n+new_value\n tail\n",
    )
    monkeypatch.setattr(
        cli_module,
        "_open_github_client_for_repo",
        lambda conn, repo: fake_github,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["review", "publish-local", "42", "--repo", repo_full_name, "--all"],
    )

    assert result.exit_code == 0, result.output
    assert len(fake_github.inline_comments) == 0
    assert len(fake_github.issue_comments) == 1
    assert "src/main.py:99" in str(fake_github.issue_comments[0]["body"])
