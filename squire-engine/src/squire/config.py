from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GITHUB_BASE_URL = "https://api.github.com"


def load_environment() -> None:
    project_env = PROJECT_ROOT / ".env"
    cwd_env = Path.cwd() / ".env"

    load_dotenv(project_env, override=False)
    if cwd_env != project_env:
        load_dotenv(cwd_env, override=False)


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    github_base_url: str
    db_path: Path


def _find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _default_db_path() -> Path:
    git_root = _find_git_root(Path.cwd())
    if git_root is not None:
        return git_root / ".squire" / "squire.db"
    return PROJECT_ROOT / "data" / "squire.db"


def get_settings() -> Settings:
    load_environment()

    raw_db_path = os.getenv("SQUIRE_DB_PATH")
    db_path = (
        Path(raw_db_path).expanduser()
        if raw_db_path
        else _default_db_path()
    )

    token = os.getenv("GITHUB_TOKEN")
    base_url = os.getenv("GITHUB_BASE_URL")
    normalized_base_url = (base_url or "").strip() or DEFAULT_GITHUB_BASE_URL

    return Settings(
        github_token=token.strip() if token else None,
        github_base_url=normalized_base_url.rstrip("/"),
        db_path=db_path,
    )
