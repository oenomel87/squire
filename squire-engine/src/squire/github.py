from __future__ import annotations

from typing import Any

import httpx


class GitHubError(RuntimeError):
    """Raised when GitHub API communication fails."""


class GitHubClient:
    def __init__(self, *, token: str | None, base_url: str | None) -> None:
        if not token:
            raise GitHubError("GITHUB_TOKEN is required.")
        if not base_url:
            raise GitHubError("GITHUB_BASE_URL is required.")

        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "squire-engine/0.1.0",
            },
            timeout=30.0,
        )

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept

        response = self._client.request(
            method,
            path,
            params=params,
            headers=headers,
            json=json_body,
        )
        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GitHubError(
                f"GitHub API error ({response.status_code}) on `{path}`: {message}"
            )

        return response

    def _paginate(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        page = 1
        per_page = 100
        merged: list[dict[str, Any]] = []
        base_params = dict(params or {})

        while True:
            query = {**base_params, "per_page": per_page, "page": page}
            response = self._request("GET", path, params=query)
            chunk = response.json()
            if not chunk:
                break
            merged.extend(chunk)
            if len(chunk) < per_page:
                break
            page += 1

        return merged

    def list_pull_requests(
        self, repo_full_name: str, *, state: str = "all"
    ) -> list[dict[str, Any]]:
        return self._paginate(f"repos/{repo_full_name}/pulls", params={"state": state})

    def list_pull_requests_page(
        self,
        repo_full_name: str,
        *,
        state: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"repos/{repo_full_name}/pulls",
            params={
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": per_page,
                "page": page,
            },
        ).json()

    def get_pull_request(self, repo_full_name: str, number: int) -> dict[str, Any]:
        return self._request("GET", f"repos/{repo_full_name}/pulls/{number}").json()

    def list_pull_files(self, repo_full_name: str, number: int) -> list[dict[str, Any]]:
        return self._paginate(f"repos/{repo_full_name}/pulls/{number}/files")

    def get_pull_diff(self, repo_full_name: str, number: int) -> str:
        return self._request(
            "GET",
            f"repos/{repo_full_name}/pulls/{number}",
            accept="application/vnd.github.v3.diff",
        ).text

    def list_issue_comments(
        self, repo_full_name: str, issue_number: int
    ) -> list[dict[str, Any]]:
        return self._paginate(f"repos/{repo_full_name}/issues/{issue_number}/comments")

    def list_pull_reviews(
        self, repo_full_name: str, number: int
    ) -> list[dict[str, Any]]:
        return self._paginate(f"repos/{repo_full_name}/pulls/{number}/reviews")

    def create_issue_comment(
        self, repo_full_name: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"repos/{repo_full_name}/issues/{issue_number}/comments",
            json_body={"body": body},
        ).json()
