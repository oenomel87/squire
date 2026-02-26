from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment() -> None:
    project_env = PROJECT_ROOT / ".env"
    cwd_env = Path.cwd() / ".env"

    load_dotenv(project_env, override=False)
    if cwd_env != project_env:
        load_dotenv(cwd_env, override=False)


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    github_base_url: str | None
    db_path: Path


def get_settings() -> Settings:
    load_environment()

    default_db_path = PROJECT_ROOT / "data" / "squire.db"
    db_path = Path(os.getenv("SQUIRE_DB_PATH", str(default_db_path))).expanduser()

    token = os.getenv("GITHUB_TOKEN")
    base_url = os.getenv("GITHUB_BASE_URL")

    return Settings(
        github_token=token.strip() if token else None,
        github_base_url=base_url.rstrip("/") if base_url else None,
        db_path=db_path,
    )

