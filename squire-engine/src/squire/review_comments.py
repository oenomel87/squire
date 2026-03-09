from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

DiffSide = Literal["LEFT", "RIGHT"]

_HUNK_HEADER_PATTERN = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


@dataclass(frozen=True)
class InlineCommentTarget:
    commit_id: str
    path: str
    line: int
    side: DiffSide


def _match_line_in_patch(patch: str, target_line: int) -> tuple[int, DiffSide] | None:
    right_match: tuple[int, DiffSide] | None = None
    left_match: tuple[int, DiffSide] | None = None
    old_line: int | None = None
    new_line: int | None = None

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            match = _HUNK_HEADER_PATTERN.match(raw_line)
            if match is None:
                old_line = None
                new_line = None
                continue
            old_line = int(match.group("old_start"))
            new_line = int(match.group("new_start"))
            continue

        if old_line is None or new_line is None:
            continue
        if raw_line.startswith("\\"):
            continue

        prefix = raw_line[:1]
        if prefix == " ":
            if right_match is None and new_line == target_line:
                right_match = (new_line, "RIGHT")
            old_line += 1
            new_line += 1
            continue

        if prefix == "+":
            if right_match is None and new_line == target_line:
                right_match = (new_line, "RIGHT")
            new_line += 1
            continue

        if prefix == "-":
            if left_match is None and old_line == target_line:
                left_match = (old_line, "LEFT")
            old_line += 1
            continue

    return right_match or left_match


def resolve_inline_comment_target(
    pull_request: dict[str, Any],
    pull_files: list[dict[str, Any]],
    *,
    file_path: str,
    line_number: int,
) -> InlineCommentTarget | None:
    if line_number <= 0:
        return None

    commit_id = str((pull_request.get("head") or {}).get("sha") or "").strip()
    if not commit_id:
        return None

    target_file: dict[str, Any] | None = None
    for file_data in pull_files:
        if file_data.get("filename") == file_path:
            target_file = file_data
            break

    if target_file is None:
        return None

    patch = target_file.get("patch")
    if not isinstance(patch, str) or not patch.strip():
        return None

    matched_line = _match_line_in_patch(patch, line_number)
    if matched_line is None:
        return None

    line, side = matched_line
    return InlineCommentTarget(
        commit_id=commit_id,
        path=file_path,
        line=line,
        side=side,
    )
