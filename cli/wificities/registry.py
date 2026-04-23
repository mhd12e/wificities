"""Registry — resolve plugins and themes by name or git URL."""
import json
import subprocess
import shutil
from pathlib import Path


def get_registry() -> dict:
    """Load the registry.json from the repo root."""
    registry_path = _repo_root() / "registry.json"
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return {"plugins": {}, "themes": {}}


def resolve_repo_url(name: str, kind: str) -> str | None:
    """Resolve a name to a git URL.

    If name is already a URL (starts with http or git@), return it.
    Otherwise look it up in the registry.
    kind is 'plugins' or 'themes'.
    """
    if name.startswith("http") or name.startswith("git@"):
        return name

    registry = get_registry()
    entry = registry.get(kind, {}).get(name)
    if entry:
        return entry["repo"]

    return None


def clone_or_update(url: str, dest: Path) -> bool:
    """Clone a git repo to dest, or pull if it already exists."""
    if (dest / ".git").exists():
        # Update
        result = subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only", "-q"],
            capture_output=True, text=True
        )
        return result.returncode == 0

    # Clone
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "-q", url, str(dest)],
        capture_output=True, text=True
    )
    return result.returncode == 0


def remove_package(dest: Path) -> bool:
    """Remove a cloned package directory."""
    if dest.exists():
        shutil.rmtree(dest)
        return True
    return False


def get_installed_dir(project_dir: Path, kind: str, name: str) -> Path:
    """Get the install path for a plugin or theme in a project."""
    return project_dir / ".wificities" / kind / name


def list_registry(kind: str) -> list[tuple[str, str, bool]]:
    """List registered packages. Returns (name, description, verified)."""
    registry = get_registry()
    entries = registry.get(kind, {})
    result = []
    for name, data in entries.items():
        desc = data.get("description", "")
        verified = data.get("verified", False)
        result.append((name, desc, verified))
    return result


def _repo_root() -> Path:
    """Get the repo root (where registry.json lives)."""
    # Walk up from this file to find registry.json
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "registry.json").exists():
            return current
        current = current.parent
    # Fallback
    return Path(__file__).resolve().parent.parent.parent
