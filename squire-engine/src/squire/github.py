from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from .review_threads import normalize_review_thread


_THREAD_COMMENT_FIELDS = """
id
databaseId
url
body
createdAt
updatedAt
author {
  login
}
replyTo {
  id
}
path
line
originalLine
commit {
  oid
}
originalCommit {
  oid
}
""".strip()

_PULL_REVIEW_THREADS_QUERY = f"""
query PullReviewThreads($owner: String!, $name: String!, $number: Int!, $after: String) {{
  viewer {{
    login
  }}
  repository(owner: $owner, name: $name) {{
    pullRequest(number: $number) {{
      headRefOid
      reviewThreads(first: 100, after: $after) {{
        nodes {{
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 100) {{
            totalCount
            pageInfo {{
              hasNextPage
              endCursor
            }}
            nodes {{
              {_THREAD_COMMENT_FIELDS}
            }}
          }}
        }}
        pageInfo {{
          hasNextPage
          endCursor
        }}
      }}
    }}
  }}
}}
""".strip()

_REVIEW_THREAD_QUERY = f"""
query ReviewThread($threadId: ID!, $after: String) {{
  viewer {{
    login
  }}
  node(id: $threadId) {{
    ... on PullRequestReviewThread {{
      id
      isResolved
      isOutdated
      path
      line
      originalLine
      comments(first: 100, after: $after) {{
        totalCount
        pageInfo {{
          hasNextPage
          endCursor
        }}
        nodes {{
          {_THREAD_COMMENT_FIELDS}
        }}
      }}
    }}
  }}
}}
""".strip()

ReactionContent = Literal[
    "+1",
    "-1",
    "laugh",
    "confused",
    "heart",
    "hooray",
    "rocket",
    "eyes",
]


def build_graphql_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")

    if path.endswith("/api/v3"):
        graphql_path = path[: -len("/v3")] + "/graphql"
    elif path in {"", "/"}:
        graphql_path = "/graphql"
    elif path.endswith("/graphql"):
        graphql_path = path
    else:
        graphql_path = path + "/graphql"

    return urlunsplit((parsed.scheme, parsed.netloc, graphql_path, "", ""))


class GitHubError(RuntimeError):
    """Raised when GitHub API communication fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class GitHubClient:
    def __init__(self, *, token: str | None, base_url: str | None) -> None:
        if not token:
            raise GitHubError("GITHUB_TOKEN is required.")
        if not base_url:
            raise GitHubError("GITHUB_BASE_URL is required.")

        normalized_base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=normalized_base_url + "/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "squire-engine/0.1.0",
            },
            timeout=30.0,
        )
        self._graphql_url = build_graphql_url(normalized_base_url)

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
                f"GitHub API error ({response.status_code}) on `{path}`: {message}",
                status_code=response.status_code,
                path=path,
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

    def _graphql(
        self,
        query: str,
        *,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._client.post(
            self._graphql_url,
            json={
                "query": query,
                "variables": variables or {},
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        if response.status_code >= 400:
            try:
                message = response.json().get("message", response.text)
            except ValueError:
                message = response.text
            raise GitHubError(
                f"GitHub API error ({response.status_code}) on `{self._graphql_url}`: {message}",
                status_code=response.status_code,
                path=self._graphql_url,
            )

        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            messages = ", ".join(
                str(item.get("message") or "Unknown GraphQL error")
                for item in errors
                if isinstance(item, dict)
            ) or "Unknown GraphQL error"
            raise GitHubError(
                f"GitHub GraphQL error on `{self._graphql_url}`: {messages}",
                path=self._graphql_url,
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise GitHubError(
                f"GitHub GraphQL error on `{self._graphql_url}`: missing `data` payload",
                path=self._graphql_url,
            )
        return data

    def _split_repo_full_name(self, repo_full_name: str) -> tuple[str, str]:
        owner, separator, name = repo_full_name.partition("/")
        if not separator or not owner or not name:
            raise GitHubError(f"Invalid repository name: `{repo_full_name}`")
        return owner, name

    def _load_review_thread_comments(
        self,
        thread_id: str,
        *,
        initial_nodes: list[dict[str, Any]],
        after: str | None,
    ) -> list[dict[str, Any]]:
        comments = list(initial_nodes)
        cursor = after

        while cursor:
            data = self._graphql(
                _REVIEW_THREAD_QUERY,
                variables={
                    "threadId": thread_id,
                    "after": cursor,
                },
            )
            node = data.get("node")
            if not isinstance(node, dict):
                break

            connection = node.get("comments") or {}
            nodes = connection.get("nodes") or []
            comments.extend(item for item in nodes if isinstance(item, dict))

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return comments

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

    def get_commit(self, repo_full_name: str, ref: str) -> dict[str, Any]:
        return self._request("GET", f"repos/{repo_full_name}/commits/{ref}").json()

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

    def list_pull_review_threads(
        self,
        repo_full_name: str,
        number: int,
    ) -> dict[str, Any]:
        owner, name = self._split_repo_full_name(repo_full_name)
        cursor: str | None = None
        threads: list[dict[str, Any]] = []
        viewer_login: str | None = None
        head_ref_oid: str | None = None

        while True:
            data = self._graphql(
                _PULL_REVIEW_THREADS_QUERY,
                variables={
                    "owner": owner,
                    "name": name,
                    "number": number,
                    "after": cursor,
                },
            )

            viewer = data.get("viewer") or {}
            viewer_login = str(viewer.get("login") or "") or viewer_login

            repository = data.get("repository")
            if repository is None:
                raise GitHubError(
                    f"Repository `{repo_full_name}` not found in GraphQL response."
                )

            pull_request = (repository or {}).get("pullRequest")
            if pull_request is None:
                raise GitHubError(
                    f"Pull request #{number} not found in `{repo_full_name}`."
                )

            head_ref_oid = str(pull_request.get("headRefOid") or "") or head_ref_oid
            connection = pull_request.get("reviewThreads") or {}
            nodes = connection.get("nodes") or []

            for node in nodes:
                if not isinstance(node, dict):
                    continue

                comments_connection = node.get("comments") or {}
                comment_nodes = comments_connection.get("nodes") or []
                page_info = comments_connection.get("pageInfo") or {}
                if page_info.get("hasNextPage"):
                    node = dict(node)
                    node["comments"] = dict(comments_connection)
                    node["comments"]["nodes"] = self._load_review_thread_comments(
                        str(node.get("id") or ""),
                        initial_nodes=[
                            item for item in comment_nodes if isinstance(item, dict)
                        ],
                        after=page_info.get("endCursor"),
                    )

                threads.append(
                    normalize_review_thread(node, head_ref_oid=head_ref_oid)
                )

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return {
            "viewer_login": viewer_login,
            "head_ref_oid": head_ref_oid,
            "threads": threads,
        }

    def get_pull_review_thread(self, thread_id: str) -> dict[str, Any]:
        cursor: str | None = None
        viewer_login: str | None = None
        thread_node: dict[str, Any] | None = None
        all_comments: list[dict[str, Any]] = []

        while True:
            data = self._graphql(
                _REVIEW_THREAD_QUERY,
                variables={
                    "threadId": thread_id,
                    "after": cursor,
                },
            )

            viewer = data.get("viewer") or {}
            viewer_login = str(viewer.get("login") or "") or viewer_login

            node = data.get("node")
            if not isinstance(node, dict):
                raise GitHubError(f"Review thread `{thread_id}` not found.")

            thread_node = node
            comments_connection = node.get("comments") or {}
            nodes = comments_connection.get("nodes") or []
            all_comments.extend(item for item in nodes if isinstance(item, dict))

            page_info = comments_connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        if thread_node is None:
            raise GitHubError(f"Review thread `{thread_id}` not found.")

        thread_payload = dict(thread_node)
        thread_payload["comments"] = {
            "totalCount": len(all_comments),
            "nodes": all_comments,
        }
        return {
            "viewer_login": viewer_login,
            "thread": normalize_review_thread(thread_payload, head_ref_oid=None),
        }

    def create_issue_comment(
        self, repo_full_name: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"repos/{repo_full_name}/issues/{issue_number}/comments",
            json_body={"body": body},
        ).json()

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
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"repos/{repo_full_name}/pulls/{number}/comments",
            json_body={
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": side,
            },
        ).json()

    def create_issue_comment_reaction(
        self,
        repo_full_name: str,
        comment_id: int,
        *,
        content: ReactionContent,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"repos/{repo_full_name}/issues/comments/{comment_id}/reactions",
            json_body={"content": content},
        ).json()

    def create_pull_review_comment_reaction(
        self,
        repo_full_name: str,
        comment_id: int,
        *,
        content: ReactionContent,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"repos/{repo_full_name}/pulls/comments/{comment_id}/reactions",
            json_body={"content": content},
        ).json()

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
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": title,
            "head": head,
            "base": base,
            "draft": draft,
            "maintainer_can_modify": maintainer_can_modify,
        }
        if body is not None:
            payload["body"] = body
        if head_repo is not None:
            payload["head_repo"] = head_repo

        return self._request(
            "POST",
            f"repos/{repo_full_name}/pulls",
            json_body=payload,
        ).json()
