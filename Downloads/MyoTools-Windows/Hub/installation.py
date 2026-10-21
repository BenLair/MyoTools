"""Standard-library ownership records shared by setup and uninstallation.

Names alone never prove ownership. Both the installation record and the marker
inside a newly created environment must agree before that prefix is removable.
"""
from __future__ import annotations

from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "Hub" / "runtime"
STATE = RUNTIME / "installation.json"
ALLOWED_ENVIRONMENTS = ("myotools", "myofuse_env")
# Conda interprets conda-meta/*.json as package records. Keep our JSON payload
# under a different extension so real Conda never tries to load it as a package.
MARKER = "myotools-installation.record"
INVENTORY = "myotools-installed-files.json.gz"
CONFIRMATION = "UNINSTALL MYOTOOLS"


def unlinked(path: Path) -> None:
    """Reject symlinks and Windows junctions, including in parent directories."""
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise RuntimeError("Linked path is protected: " + str(part))
        # Python 3.9 has no Path.is_junction (Conda base may use that version).
        if os.name == "nt" and part.exists():
            import stat
            if part.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError("Reparse point is protected: " + str(part))


def write_json(path: Path, value: dict) -> None:
    unlinked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".myotools-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def maintenance():
    unlinked(RUNTIME)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    lock = RUNTIME / "maintenance.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError("Another installation/uninstallation is in progress. "
                           "If it was interrupted, close it before removing " + str(lock))
    try:
        yield
    finally:
        lock.rmdir()


def conda_info(conda: Path) -> dict:
    result = subprocess.run([str(conda), "info", "--json"], check=True,
                            capture_output=True, text=True)
    info = json.loads(result.stdout)
    if not Path(info["root_prefix"]).is_absolute():
        raise RuntimeError("Conda returned an invalid base prefix.")
    return info


def environment_prefixes(conda: Path) -> list[Path]:
    result = subprocess.run([str(conda), "env", "list", "--json"], check=True,
                            capture_output=True, text=True)
    return [Path(value) for value in json.loads(result.stdout)["envs"]]


def load_state() -> dict:
    unlinked(STATE)
    if not STATE.is_file():
        raise RuntimeError("No ownership record for this installation; legacy or pre-existing environments are retained.")
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schema") != 1 or state.get("installation_root") != str(ROOT):
        raise RuntimeError("Installation record belongs to another folder or version.")
    for key in ("installation_id", "conda_executable", "conda_base", "base_python"):
        if not isinstance(state.get(key), str):
            raise RuntimeError("Invalid installation record field: " + key)
    uuid.UUID(state["installation_id"])
    if not isinstance(state["environments"], dict):
        raise RuntimeError("Invalid environment ownership record.")
    if set(state["environments"]) - set(ALLOWED_ENVIRONMENTS):
        raise RuntimeError("Installation record contains a protected environment name.")
    for entry in state["environments"].values():
        if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str)
                                              for k in ("prefix", "token", "inventory_sha256")):
            raise RuntimeError("Invalid environment ownership record.")
    return state


def setup_state(conda: Path, base: Path, python: Path) -> dict:
    if STATE.exists() or STATE.is_symlink():
        state = load_state()
        if state["conda_executable"] != str(conda) or state["conda_base"] != str(base):
            raise RuntimeError("This installation is already associated with another Conda.")
        return state
    state = {"schema": 1, "installation_id": str(uuid.uuid4()),
             "installation_root": str(ROOT), "conda_executable": str(conda),
             "conda_base": str(base), "base_python": str(python), "environments": {}}
    write_json(STATE, state)
    return state


def checked_prefix(state: dict, name: str, prefix: Path) -> Path:
    if name not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError("Protected environment name: " + name)
    base = Path(state["conda_base"])
    expected = base / "envs" / name
    if not base.is_absolute() or not prefix.is_absolute() or prefix != expected:
        raise RuntimeError("Environment is outside this installation's exact Conda prefix.")
    unlinked(prefix)
    if prefix.resolve() != expected or base.resolve() != base:
        raise RuntimeError("Environment or Conda base has moved.")
    # Never remove the source/data folder, a parent of it, or the running Python.
    for protected in (ROOT, Path.home().resolve(), Path(sys.prefix).resolve()):
        if prefix == protected or prefix in protected.parents:
            raise RuntimeError("Environment contains a protected folder or running Python.")
    if ROOT in prefix.parents:
        raise RuntimeError("Environment is inside the source/data folder.")
    return prefix


def marker_for(state: dict, name: str) -> dict:
    return {key: state[key] for key in ("schema", "installation_id", "installation_root",
                                       "conda_executable", "conda_base")} | {
        "name": name, **state["environments"][name]}


def prefix_files(prefix: Path) -> set[str]:
    """List files and links without traversing directory symlinks or junctions."""
    result = set()
    pending = [prefix]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                path = Path(entry.path)
                linked = entry.is_symlink()
                if os.name == "nt":
                    import stat
                    linked = linked or bool(entry.stat(follow_symlinks=False).st_file_attributes &
                                            stat.FILE_ATTRIBUTE_REPARSE_POINT)
                if not linked and entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                else:
                    result.add(path.relative_to(prefix).as_posix())
    return result


def protect_added_files(state: dict, name: str, prefix: Path) -> None:
    """Conda removes the whole prefix, so retain it if user files were added."""
    inventory = prefix / "conda-meta" / INVENTORY
    unlinked(inventory)
    raw = inventory.read_bytes()
    if hashlib.sha256(raw).hexdigest() != state["environments"][name]["inventory_sha256"]:
        raise RuntimeError("Installed-file inventory is missing or does not match.")
    try:
        values = json.loads(gzip.decompress(raw))
        if not isinstance(values, list) or any(not isinstance(p, str) for p in values):
            raise ValueError("Invalid file inventory")
        installed = set(values)
    except Exception as exc:
        raise RuntimeError("Unreadable installed-file inventory.") from exc
    added = prefix_files(prefix) - installed - {"conda-meta/" + MARKER, "conda-meta/" + INVENTORY}
    # Python creates bytecode caches during normal use; no user data extension
    # or scientific output directory is exempted from the protection.
    added = {p for p in added if not ("__pycache__" in Path(p).parts and p.endswith(".pyc"))}
    if added:
        raise RuntimeError("Files added after installation are protected; environment retained: " +
                           ", ".join(sorted(added)[:3]))


def register_created(state: dict, name: str, prefix: Path) -> None:
    checked_prefix(state, name, prefix)
    history = prefix / "conda-meta" / "history"
    unlinked(history)
    if not history.is_file():
        raise RuntimeError("Conda did not create a valid environment: " + str(prefix))
    marker = prefix / "conda-meta" / MARKER
    if marker.exists():
        raise RuntimeError("Refusing to replace an existing environment ownership marker.")
    inventory = prefix / "conda-meta" / INVENTORY
    unlinked(inventory)
    raw = gzip.compress(json.dumps(sorted(prefix_files(prefix))).encode("utf-8"), mtime=0)
    with inventory.open("xb") as stream:
        stream.write(raw)
    state["environments"][name] = {"prefix": str(prefix), "token": str(uuid.uuid4()),
                                   "inventory_sha256": hashlib.sha256(raw).hexdigest()}
    # An interrupted write cannot grant ownership: both copies must be present.
    write_json(marker, marker_for(state, name))
    write_json(STATE, state)


def removable_prefix(state: dict, name: str, listed: list[Path]) -> Path:
    entry = state["environments"].get(name)
    if not entry:
        raise RuntimeError("No ownership proof; a pre-existing or legacy environment is retained.")
    prefix = checked_prefix(state, name, Path(entry["prefix"]))
    uuid.UUID(entry["token"])
    marker = prefix / "conda-meta" / MARKER
    history = prefix / "conda-meta" / "history"
    unlinked(marker)
    unlinked(history)
    if not history.is_file() or json.loads(marker.read_text(encoding="utf-8")) != marker_for(state, name):
        raise RuntimeError("Environment ownership marker is missing or does not match.")
    if prefix not in listed:
        raise RuntimeError("Environment is not registered with this installation's Conda.")
    protect_added_files(state, name, prefix)
    return prefix
