"""Resolve versioned MyoTools notebooks from portable, relative paths.

No third-party dependencies. 'release' uses explicit package pins; 'development'
selects the greatest major.minor.patch[-rc.N] version found.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import NamedTuple


class Tool(NamedTuple):
    id: str
    name: str
    description: str
    environment: str
    notebook: str
    version: str | None
    error: str | None


_VERSION = r"(?P<version>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-(?:dev|alpha|a|beta|b|rc)[.-]?\d+)?)"
_FILE_RE = re.compile(r"_v" + _VERSION + r"\.ipynb$", re.IGNORECASE)
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<stage>dev|alpha|a|beta|b|rc)[.-]?(?P<number>\d+))?$", re.IGNORECASE
)
_STAGE = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3}


def version_key(version: str) -> tuple[int, int, int, int, int]:
    """Sort numeric versions; 1.10.0 > 1.9.0 and stable > prerelease."""
    m = _SEMVER_RE.fullmatch(version)
    if not m:
        raise ValueError(f"Unsupported notebook version: {version!r}")
    return (
        int(m["major"]), int(m["minor"]), int(m["patch"]),
        _STAGE[m["stage"].lower()] if m["stage"] else 4,
        int(m["number"]) if m["number"] else 0,
    )


def notebook_version(filename: str) -> str | None:
    match = _FILE_RE.search(filename)
    return match["version"] if match else None


def _relative_directory(root: Path, directory: str) -> Path:
    relative = Path(directory)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe notebook directory: {directory!r}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Notebook directory escapes installation: {directory!r}")
    return target


def resolve_tool(root: Path, entry: dict, mode: str, platform: str) -> Tool:
    name = entry["name"]
    directory = entry["directory_by_platform"][platform] if "directory_by_platform" in entry else entry["directory"]
    pattern = entry.get("pattern_by_platform", {}).get(platform) if "pattern_by_platform" in entry else entry.get("pattern")
    if not pattern or Path(pattern).name != pattern or "/" in pattern or "\\" in pattern:
        raise ValueError(f"Invalid notebook pattern for {name}: {pattern!r}")
    folder = _relative_directory(root, directory)
    matches = []
    for file in folder.glob(pattern):
        if not file.is_file():
            continue
        version = notebook_version(file.name)
        if version:
            matches.append((version_key(version), version, file))

    error = None
    if not matches:
        error = f"No versioned notebook found for {name} ({directory}/{pattern})"
        chosen = None
    elif mode == "release":
        pin = entry.get("release_version")
        if not pin:
            error = f"No release_version pin configured for {name}"
            chosen = None
        else:
            pinned = version_key(pin)
            found = [match for match in matches if match[0] == pinned]
            if len(found) != 1:
                error = (f"Pinned {name} v{pin} is "
                         + ("missing" if not found else "ambiguous")
                         + f" in {directory} (release mode never picks an unapproved version)")
                chosen = None
            else:
                chosen = found[0]
    elif mode == "development":
        best_key = max(match[0] for match in matches)
        best = [match for match in matches if match[0] == best_key]
        if len(best) != 1:
            error = f"Multiple {name} notebooks have the same latest version in {directory}"
            chosen = None
        else:
            chosen = best[0]
    else:
        raise ValueError(f"Unknown Hub mode: {mode}")

    if chosen:
        version = chosen[1]
        relative_path = chosen[2].relative_to(root.resolve()).as_posix()
    else:
        version = None
        relative_path = (Path(directory) / pattern).as_posix()
    return Tool(entry["id"], name, entry["description"], entry["environment"],
                relative_path, version, error)


def load_tools(root: Path, mode: str | None = None, platform: str | None = None) -> tuple[list[Tool], str]:
    root = Path(root).resolve()
    config = json.loads((root / "Hub" / "apps.json").read_text(encoding="utf-8"))
    mode = mode or os.environ.get("MYOTOOLS_HUB_MODE") or config.get("default_mode", "release")
    if mode not in ("release", "development"):
        raise ValueError(f"Invalid Hub mode {mode!r}; use release or development")
    platform = platform or ("windows" if os.name == "nt" else "linux")
    if platform not in ("windows", "linux"):
        raise ValueError(f"Invalid platform: {platform!r}")
    tools = [resolve_tool(root, entry, mode, platform) for entry in config["apps"]]
    ids = [tool.id for tool in tools]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate application IDs in Hub/apps.json")
    return tools, mode
