from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse

from app.config import Settings


class GitHubRepoImportError(RuntimeError):
    pass


def clone_github_repo(github_url: str, settings: Settings) -> Path:
    normalized_url = _normalize_github_url(github_url)
    clone_root = Path(settings.cloned_repos_dir).expanduser().resolve()
    clone_root.mkdir(parents=True, exist_ok=True)

    destination = clone_root / _repo_folder_name(normalized_url)
    if destination.exists():
        _ensure_managed_destination(clone_root, destination)
        shutil.rmtree(destination)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", normalized_url, str(destination)],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise GitHubRepoImportError("git is not installed or is not available on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubRepoImportError("GitHub clone timed out.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Unknown git clone error.").strip()
        raise GitHubRepoImportError(f"GitHub clone failed: {detail}") from exc

    return destination


def _normalize_github_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise GitHubRepoImportError("Only public HTTPS GitHub repo URLs are supported, for example https://github.com/owner/repo.")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise GitHubRepoImportError("GitHub URL must include an owner and repository name.")

    owner = _safe_slug(parts[0])
    repo = _safe_slug(parts[1].removesuffix(".git"))
    return f"https://github.com/{owner}/{repo}.git"


def _repo_folder_name(github_url: str) -> str:
    parsed = urlparse(github_url)
    owner, repo = parsed.path.strip("/").removesuffix(".git").split("/")[:2]
    return f"{_safe_slug(owner)}__{_safe_slug(repo)}"


def _safe_slug(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise GitHubRepoImportError("GitHub owner and repository names may only contain letters, numbers, dots, dashes, and underscores.")
    return value


def _ensure_managed_destination(clone_root: Path, destination: Path) -> None:
    destination.relative_to(clone_root)
