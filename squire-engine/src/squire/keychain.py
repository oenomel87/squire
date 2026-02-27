from __future__ import annotations

import platform
import shutil
import subprocess

GITHUB_TOKEN_SERVICE = "squire.github.token"


class KeychainError(RuntimeError):
    """Base error for keychain integration."""


class KeychainUnavailableError(KeychainError):
    """Raised when macOS keychain CLI is unavailable."""


class KeychainCommandError(KeychainError):
    """Raised when `security` command fails."""


def _normalize_token(token: str | None) -> str | None:
    if token is None:
        return None
    normalized = token.strip()
    return normalized or None


def _security_exists() -> bool:
    return shutil.which("security") is not None


def is_available() -> bool:
    return platform.system() == "Darwin" and _security_exists()


def _assert_available() -> None:
    if is_available():
        return
    raise KeychainUnavailableError(
        "macOS Keychain CLI (`security`) is unavailable on this environment."
    )


def _is_not_found(return_code: int, stderr: str) -> bool:
    return return_code == 44 or "could not be found in the keychain" in stderr.lower()


def _run_security(
    args: list[str],
    *,
    input_text: str | None = None,
    allow_not_found: bool = False,
) -> tuple[int, str, str]:
    _assert_available()
    result = subprocess.run(
        ["security", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode == 0:
        return result.returncode, stdout, stderr
    if allow_not_found and _is_not_found(result.returncode, stderr):
        return result.returncode, stdout, stderr
    raise KeychainCommandError(
        f"`security {' '.join(args)}` failed "
        f"(code={result.returncode}): {stderr or stdout or 'unknown error'}"
    )


def has_github_token(account: str) -> bool:
    if not is_available():
        return False
    return_code, _, _ = _run_security(
        [
            "find-generic-password",
            "-a",
            account,
            "-s",
            GITHUB_TOKEN_SERVICE,
        ],
        allow_not_found=True,
    )
    return return_code == 0


def get_github_token(account: str) -> str | None:
    if not is_available():
        return None
    return_code, stdout, _ = _run_security(
        [
            "find-generic-password",
            "-a",
            account,
            "-s",
            GITHUB_TOKEN_SERVICE,
            "-w",
        ],
        allow_not_found=True,
    )
    if return_code != 0:
        return None
    return stdout or None


def set_github_token(account: str, token: str) -> None:
    normalized = _normalize_token(token)
    if not normalized:
        raise KeychainCommandError("GitHub token must not be empty.")

    # Avoid token exposure in process args: use interactive mode fed by stdin.
    _run_security(
        [
            "add-generic-password",
            "-a",
            account,
            "-s",
            GITHUB_TOKEN_SERVICE,
            "-l",
            f"Squire GitHub token ({account})",
            "-U",
            "-w",
        ],
        input_text=f"{normalized}\n{normalized}\n",
    )


def delete_github_token(account: str) -> None:
    if not is_available():
        return
    _run_security(
        [
            "delete-generic-password",
            "-a",
            account,
            "-s",
            GITHUB_TOKEN_SERVICE,
        ],
        allow_not_found=True,
    )
