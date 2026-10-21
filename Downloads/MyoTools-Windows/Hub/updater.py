#!/usr/bin/env python3
"""MyoTools branch-based updater (stdlib only; never modifies Conda or user data).

Usage from an extracted distribution, after closing MyoTools:
  python Hub/updater.py --check
  python Hub/updater.py --download
  python Hub/updater.py --apply /path/to/MyoTools-Linux.zip --sha256 HEX
  python Hub/updater.py --rollback
  python Hub/updater.py --recover

Reads complete distribution ZIPs from Downloads/ on the installed update channel.\nGitHub Releases are reserved for model weights and are NEVER update sources.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile
import update_policy

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "Hub" / "runtime" / "updates"
REPO = update_policy.REPOSITORY
BRANCHES = update_policy.ALLOWED_CHANNELS
API_ROOT = "https://api.github.com/repos/" + REPO + "/"
RAW_ROOT = "https://raw.githubusercontent.com/" + REPO + "/"
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
PLATFORM = "windows" if os.name == "nt" else "linux"
ASSET = "MyoTools-Windows.zip" if PLATFORM == "windows" else "MyoTools-Linux.zip"
PREFIX = "MyoTools-Windows/" if PLATFORM == "windows" else "MyoTools-Linux/"
MAX_ZIP_BYTES = 250 * 1024 * 1024
MAX_UNPACKED_BYTES = 250 * 1024 * 1024
MAX_MEMBERS = 300
MANIFEST = "DISTRIBUTION.json"
CONFIRMATION = "UPDATE MYOTOOLS"
ENVIRONMENT_FILES = (
    "Hub/platforms/" + PLATFORM + "/environments/myotools.yml",
    "Hub/platforms/" + PLATFORM + "/environments/myofuse.yml",
)


class UpdateError(RuntimeError):
    pass


def version(value: str) -> tuple[int, int, int]:
    match = TAG.fullmatch("v" + value)
    if not match:
        raise UpdateError("Invalid suite version: " + str(value))
    return tuple(int(x) for x in match.groups())


def _channel(data: dict) -> str:
    """Older unmarked distributions are stable by default."""
    channel = data.get("update_channel", "main") if isinstance(data, dict) else None
    if channel not in BRANCHES:
        raise UpdateError("Invalid MyoTools update channel: " + str(channel))
    return channel


def _trusted_source(data: dict) -> None:
    """Reject any installed or remote source that differs from the signed-off package.

    Older 0.2-0.4 test manifests omit these keys and retain legacy behavior.
    Newly built official packages always carry both keys.
    """
    if "update_repository" in data or "update_branch" in data:
        if (data.get("update_repository") != update_policy.REPOSITORY or
                data.get("update_branch") != update_policy.BRANCH or
                data.get("update_channel") != update_policy.CHANNEL):
            raise UpdateError("Distribution update source differs from the packaged update policy")


def _installed_metadata(root: Path) -> dict:
    distribution = root / MANIFEST
    source = distribution if distribution.is_file() else root / "Hub" / "apps.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise UpdateError("Invalid installed metadata")
    version(data.get("suite_version"))
    _channel(data)
    _trusted_source(data)
    return data


def current_version(root: Path = ROOT) -> str:
    return _installed_metadata(root)["suite_version"]


def current_channel(root: Path = ROOT) -> str:
    return _channel(_installed_metadata(root))


def _github_json(endpoint: str) -> dict:
    """Read GitHub's repository API; gh provides auth for private repositories."""
    request = Request(API_ROOT + endpoint, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "MyoTools-Updater/0.3"})
    try:
        with urlopen(request, timeout=12) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise UpdateError("GitHub response exceeds metadata limit")
        data = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        if not shutil.which("gh"):
            raise UpdateError(
                "Cannot access MyoTools on GitHub. For a private repository, "
                "install GitHub CLI and run 'gh auth login'.") from exc
        command = ["gh", "api", "--method", "GET",
                   "repos/" + REPO + "/" + endpoint]
        try:
            response = subprocess.run(
                command, capture_output=True, text=True, timeout=45, check=False)
        except (OSError, subprocess.SubprocessError) as cli_error:
            raise UpdateError("GitHub CLI could not access the MyoTools repository") from cli_error
        if response.returncode or len(response.stdout) > 2 * 1024 * 1024:
            raise UpdateError("GitHub CLI cannot read repository metadata. Check 'gh auth status'.")
        try:
            data = json.loads(response.stdout)
        except (ValueError, TypeError) as invalid:
            raise UpdateError("GitHub CLI returned invalid JSON") from invalid
    if not isinstance(data, dict):
        raise UpdateError("Invalid GitHub repository response")
    return data


def _branch_head(channel: str) -> str:
    if channel not in BRANCHES:
        raise UpdateError("Unknown update channel")
    branch = update_policy.BRANCH if channel == update_policy.CHANNEL else channel
    data = _github_json("git/ref/heads/" + branch)
    sha = (data.get("object") or {}).get("sha")
    if data.get("ref") != "refs/heads/" + branch or not isinstance(sha, str) or not COMMIT_SHA.fullmatch(sha):
        raise UpdateError("Cannot verify the MyoTools " + channel + " branch HEAD")
    return sha


def _repo_bytes(path: str, commit: str, maximum: int) -> bytes:
    """Fetch from ONE immutable Git commit (not mutable branch URLs).

    GitHub raw URLs work publicly; authenticated GitHub CLI handles a private
    repository. Only fixed package/metadata paths are permitted.
    """
    approved = {"Downloads/SHA256SUMS.txt",
                "Downloads/MyoTools-Linux/DISTRIBUTION.json",
                "Downloads/MyoTools-Windows/DISTRIBUTION.json",
                "Downloads/MyoTools-Linux.zip",
                "Downloads/MyoTools-Windows.zip"}
    if path not in approved or not COMMIT_SHA.fullmatch(commit):
        raise UpdateError("Invalid source path or Git commit")
    url = RAW_ROOT + commit + "/" + path
    try:
        with urlopen(Request(url, headers={"User-Agent": "MyoTools-Updater/0.3"}),
                     timeout=45) as response:
            result = response.read(maximum + 1)
        if len(result) > maximum:
            raise UpdateError("Repository file exceeds the permitted download size")
        return result
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        entry = _github_json("contents/" + path + "?ref=" + commit)
        declared_size = entry.get("size")
        if (entry.get("type") != "file" or entry.get("path") != path or
                not isinstance(declared_size, int) or declared_size < 0 or
                declared_size > maximum):
            raise UpdateError("GitHub file metadata is inconsistent or oversized") from exc
        if entry.get("encoding") == "base64" and isinstance(entry.get("content"), str):
            try:
                result = base64.b64decode(
                    "".join(entry["content"].split()), validate=True)
            except (ValueError, TypeError) as invalid:
                raise UpdateError("Invalid GitHub file encoding") from invalid
        else:
            # GitHub's Contents API omits base64 content for some large files.
            # Request the raw media type via authenticated gh in that case.
            if not shutil.which("gh"):
                raise UpdateError("Use authenticated GitHub CLI to download this private archive") from exc
            result_cmd = subprocess.run(
                ["gh", "api", "--method", "GET", "-H",
                 "Accept: application/vnd.github.raw+json",
                 "repos/" + REPO + "/contents/" + path + "?ref=" + commit],
                capture_output=True, timeout=240, check=False)
            if result_cmd.returncode:
                raise UpdateError("GitHub CLI could not download the archive")
            result = result_cmd.stdout
        if len(result) != declared_size or len(result) > maximum:
            raise UpdateError("Downloaded repository content has an unexpected size")
        return result


def _checksum(raw: bytes, filename: str) -> str:
    if len(raw) > 4096:
        raise UpdateError("SHA256SUMS.txt exceeds the metadata limit")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise UpdateError("Invalid checksum text") from exc
    expected = {}
    for line in lines:
        found = re.fullmatch(
            r"([0-9a-f]{64})  (MyoTools-(?:Linux|Windows)\.zip)", line)
        if not found or found.group(2) in expected:
            raise UpdateError("Invalid or duplicate SHA256SUMS.txt entry")
        expected[found.group(2)] = found.group(1)
    if not set(expected) == {"MyoTools-Linux.zip", "MyoTools-Windows.zip"}:
        raise UpdateError("Both platform checksums are required")
    return expected[filename]


def check(root: Path = ROOT) -> dict:
    installed = _installed_metadata(root)
    channel = _channel(installed)
    commit = _branch_head(channel)
    manifest_path = "Downloads/" + ("MyoTools-Windows" if PLATFORM == "windows" else "MyoTools-Linux") + "/DISTRIBUTION.json"
    raw_manifest = _repo_bytes(manifest_path, commit, 1024 * 1024)
    remote = _manifest(raw_manifest, PLATFORM)
    branch = update_policy.BRANCH if channel == update_policy.CHANNEL else channel
    result = {"channel": channel, "branch": branch, "repository": REPO, "commit": commit,
              "installed": installed["suite_version"], "latest": remote["suite_version"]}
    if (_channel(remote) != channel or
            remote.get("update_repository") != installed.get("update_repository") or
            remote.get("update_branch") != installed.get("update_branch")):
        return {**result, "status": "not-ready",
                "message": "The remote distribution declares a different update channel or repository"}
    if version(remote["suite_version"]) <= version(installed["suite_version"]):
        return {**result, "status": "up-to-date"}
    sums = _repo_bytes("Downloads/SHA256SUMS.txt", commit, 4096)
    expected = _checksum(sums, ASSET)
    return {**result, "status": "available", "sha256": expected,
            "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
            "asset": ASSET,
            "url": RAW_ROOT + commit + "/Downloads/" + ASSET}


def _assert_unlinked(path: Path, root: Path) -> None:
    root = root.absolute()
    path = path.absolute()
    if path != root and root not in path.parents:
        raise UpdateError("Path escapes the MyoTools installation: " + str(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise UpdateError("Linked path is protected: " + str(part))
        if part == root:
            break


def _managed_path(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise UpdateError("Invalid archive path")
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in (".", "..", "") for x in name.split("/")) or p.as_posix() != name:
        raise UpdateError("Unsafe archive path: " + name)
    parts = p.parts
    if name == MANIFEST:
        return name
    if parts[0] in ("Hub", "MyoSeg", "MyoClass", "MyoFuse", "MyoSurface"):
        if name.startswith("Hub/runtime/"):
            raise UpdateError("Archive attempts to modify Hub/runtime")
        return name
    if name in {"README.md", "INSTALL.sh", "LAUNCH.sh", "UNINSTALL.sh", "UPDATE.sh",
                "INSTALL.bat", "LAUNCH.bat", "UNINSTALL.bat", "UPDATE.bat"}:
        return name
    raise UpdateError("Non-application file is protected: " + name)


def _manifest(raw: bytes, platform: str) -> dict:
    if len(raw) > 1024 * 1024:
        raise UpdateError("Distribution manifest is too large")
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get("schema_version") != 1 or
            data.get("platform") != platform or not isinstance(data.get("sha256"), dict)):
        raise UpdateError("Invalid distribution manifest or platform")
    version(data.get("suite_version"))
    _channel(data)
    _trusted_source(data)
    hashes = data["sha256"]
    if not hashes or len(hashes) > MAX_MEMBERS:
        raise UpdateError("Invalid distribution file inventory")
    for name, digest in hashes.items():
        _managed_path(name)
        if name == MANIFEST or not isinstance(digest, str) or not SHA.fullmatch(digest):
            raise UpdateError("Invalid distribution inventory: " + name)
    return data


def _read_zip(archive: Path, digest: str, root: Path) -> tuple[dict, dict[str, bytes], dict[str, int]]:
    if not SHA.fullmatch(digest):
        raise UpdateError("Expected SHA-256 must be 64 hexadecimal characters")
    _assert_unlinked(archive, archive.parent)
    if not archive.is_file() or archive.stat().st_size > MAX_ZIP_BYTES:
        raise UpdateError("Update ZIP is missing or oversized")
    h = hashlib.sha256()
    with archive.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            h.update(part)
    if h.hexdigest() != digest:
        raise UpdateError("ZIP does not match the trusted release SHA-256")
    try:
        with ZipFile(archive) as zipped:
            infos = zipped.infolist()
            if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
                raise UpdateError("Update archive exceeds extraction limits")
            files = {}
            modes = {}
            for info in infos:
                if info.is_dir() or not info.filename.startswith(PREFIX):
                    raise UpdateError("Unexpected ZIP member: " + info.filename)
                name = _managed_path(info.filename[len(PREFIX):])
                if name in files or info.file_size > MAX_UNPACKED_BYTES:
                    raise UpdateError("Duplicate or oversized ZIP member: " + name)
                fmode = info.external_attr >> 16
                if info.create_system == 3 and stat.S_IFMT(fmode) not in (0, stat.S_IFREG):
                    raise UpdateError("Non-regular file in ZIP: " + name)
                files[name] = zipped.read(info)
                modes[name] = stat.S_IMODE(fmode) & 0o755 or 0o644
    except (BadZipFile, EOFError, OSError) as exc:
        raise UpdateError("Invalid ZIP archive: " + str(exc)) from exc
    if MANIFEST not in files:
        raise UpdateError("ZIP lacks DISTRIBUTION.json")
    manifest = _manifest(files[MANIFEST], PLATFORM)
    if set(files) != set(manifest["sha256"]) | {MANIFEST}:
        raise UpdateError("ZIP contents do not match its distribution manifest")
    for name, expected in manifest["sha256"].items():
        if hashlib.sha256(files[name]).hexdigest() != expected:
            raise UpdateError("Incorrect packaged file checksum: " + name)
    return manifest, files, modes


def _read_installed(root: Path) -> dict:
    path = root / MANIFEST
    _assert_unlinked(path, root)
    if not path.is_file():
        raise UpdateError("Only extracted official MyoTools distributions can be upgraded in place")
    return _manifest(path.read_bytes(), PLATFORM)


def plan(archive: Path, digest: str, root: Path = ROOT) -> dict:
    root = root.absolute()
    old = _read_installed(root)
    new, files, modes = _read_zip(archive, digest, root)
    if version(new["suite_version"]) <= version(old["suite_version"]):
        raise UpdateError("An update must be newer than the installed suite")
    if (_channel(new) != _channel(old) or
            new.get("update_repository") != old.get("update_repository") or
            new.get("update_branch") != old.get("update_branch")):
        raise UpdateError("Changing update channels or repositories requires a separate installation")
    for path in ENVIRONMENT_FILES:
        if old["sha256"].get(path) != new["sha256"].get(path):
            raise UpdateError("Conda specifications have changed; environment migration must be validated separately: " + path)
    old_names = set(old["sha256"]) | {MANIFEST}
    new_names = set(files)
    for name in old_names | new_names:
        _managed_path(name)
        dest = root / name
        _assert_unlinked(dest, root)
        if name in old_names:
            if not dest.is_file():
                raise UpdateError("Managed file was removed: " + name)
            if name != MANIFEST and hashlib.sha256(dest.read_bytes()).hexdigest() != old["sha256"][name]:
                raise UpdateError("Locally modified file is protected: " + name)
        elif dest.exists():
            raise UpdateError("Unmanaged existing file is protected: " + name)
    return {"old_version": old["suite_version"], "new_version": new["suite_version"],
            "replace": sorted(new_names), "remove": sorted(old_names - new_names),
            "old": old, "new": new, "files": files, "modes": modes}


@contextmanager
def _lock(root: Path):
    """Share the maintenance lock with installation/uninstallation.

    The updater owns a PID file inside the lock directory. After a hard crash
    its own stale lock can be reclaimed, but a lock of unknown provenance
    (e.g. an interrupted installer) must be checked manually.
    """
    runtime = root / "Hub" / "runtime"
    updates = runtime / "updates"
    _assert_unlinked(updates, root)
    updates.mkdir(parents=True, exist_ok=True)
    lock = runtime / "maintenance.lock"
    _assert_unlinked(lock, root)
    try:
        lock.mkdir()
    except FileExistsError:
        owner = lock / "updater.pid"
        _assert_unlinked(owner, root)
        if not lock.is_dir() or not owner.is_file():
            raise UpdateError("MyoTools maintenance is locked by another operation: " + str(lock))
        try:
            pid = int(owner.read_text(encoding="ascii").strip())
        except (OSError, ValueError) as exc:
            raise UpdateError("Cannot safely identify the maintenance lock owner") from exc
        if pid == os.getpid() or _pid_alive(pid):
            raise UpdateError("Another updater is still running (PID %d)" % pid)
        # A dead updater left a lock directory after a hard interruption.
        # Never clear locks lacking our exact PID marker.
        owner.unlink()
        try:
            lock.rmdir()
            lock.mkdir()
        except OSError as exc:
            raise UpdateError("Could not safely reclaim a stale updater lock") from exc
    marker = lock / "updater.pid"
    _assert_unlinked(marker, root)
    marker.write_text(str(os.getpid()), encoding="ascii")
    try:
        yield updates
    finally:
        marker.unlink(missing_ok=True)
        lock.rmdir()

def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".myotools-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _pid_alive(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if os.name == "nt":
        result = subprocess.run(["tasklist", "/FI", "PID eq " + str(pid), "/FO", "CSV", "/NH"],
                                capture_output=True, text=True, timeout=5, check=False)
        if result.returncode:
            raise UpdateError("Cannot confirm that the MyoTools Hub is closed")
        return '"' + str(pid) + '"' in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _hub_running(root: Path) -> bool:
    runtime = root / "Hub" / "runtime"
    _assert_unlinked(runtime, root)
    if not runtime.is_dir():
        return False
    markers = [runtime / "hub.pid", *runtime.glob("hub-*.pid")]
    for marker in markers:
        _assert_unlinked(marker, root)
        if not marker.is_file():
            continue
        try:
            if _pid_alive(int(marker.read_text(encoding="utf-8").strip())):
                return True
        except (OSError, ValueError):
            raise UpdateError("Cannot validate the MyoTools Hub session marker")
    return False


_TX_NAME = re.compile(r"^backup-\d{8}-\d{6}-[0-9a-f]{12}$")
_ACTIVE = "active-transaction.json"
_LAST = "last-update.json"


def _read_pointer(path: Path, root: Path) -> str:
    _assert_unlinked(path, root)
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data.get("transaction") if isinstance(data, dict) else None
    if not isinstance(name, str) or not _TX_NAME.fullmatch(name):
        raise UpdateError("Invalid maintenance transaction pointer: " + str(path))
    return name


def _write_pointer(path: Path, name: str, root: Path) -> None:
    _assert_unlinked(path, root)
    if not _TX_NAME.fullmatch(name):
        raise UpdateError("Invalid transaction identifier")
    _atomic_write(path, (json.dumps({"transaction": name}) + "\n").encode("utf-8"), 0o600)


def _load_transaction(updates: Path, name: str, root: Path) -> tuple[Path, Path, dict]:
    if not _TX_NAME.fullmatch(name):
        raise UpdateError("Invalid transaction reference")
    folder = updates / name
    journal = folder / "transaction.json"
    _assert_unlinked(journal, root)
    record = json.loads(journal.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("status") not in (
            "prepared", "applying", "applied", "rolling-back", "recovering", "rolled-back"):
        raise UpdateError("Invalid update transaction journal")
    old_names, new_names = record.get("old_names"), record.get("new_names")
    if (not isinstance(old_names, list) or not isinstance(new_names, list) or
            len(old_names) != len(set(old_names)) or len(new_names) != len(set(new_names)) or
            MANIFEST not in old_names or MANIFEST not in new_names or
            not isinstance(record.get("old_hashes"), dict) or
            not isinstance(record.get("new_hashes"), dict)):
        raise UpdateError("Invalid saved transaction inventory")
    for item in old_names + new_names:
        _managed_path(item)
    for side, names in (("old", old_names), ("new", new_names)):
        hashes = record[side + "_hashes"]
        if set(hashes) != set(names) - {MANIFEST}:
            raise UpdateError("Transaction hashes do not match the saved inventory")
        for digest in hashes.values():
            if not isinstance(digest, str) or not SHA.fullmatch(digest):
                raise UpdateError("Invalid saved transaction checksum")
        if not SHA.fullmatch(str(record.get(side + "_manifest_sha", ""))):
            raise UpdateError("Missing distribution-manifest checksum")
    prior = record.get("previous_transaction")
    if prior is not None and (not isinstance(prior, str) or not _TX_NAME.fullmatch(prior) or prior == name):
        raise UpdateError("Invalid previous update pointer")
    version(record.get("old_version"))
    version(record.get("new_version"))
    return folder, journal, record


def _expected_sha(record: dict, side: str, name: str) -> str:
    if name == MANIFEST:
        return record[side + "_manifest_sha"]
    return record[side + "_hashes"][name]


def _validate_recovery(root: Path, updates: Path, name: str) -> tuple[Path, dict]:
    """Accept only original/released managed bytes; reject unrelated local edits."""
    tx, journal, record = _load_transaction(updates, name, root)
    old_names, new_names = set(record["old_names"]), set(record["new_names"])
    for item in old_names:
        backup = tx / "previous" / item
        _assert_unlinked(backup, root)
        if not backup.is_file() or hashlib.sha256(backup.read_bytes()).hexdigest() != _expected_sha(record, "old", item):
            raise UpdateError("Original backup is missing or changed; recovery refused: " + item)
    for item in old_names | new_names:
        dest = root / item
        _assert_unlinked(dest, root)
        if not dest.exists():
            if item in old_names and item in new_names:
                raise UpdateError("Shared managed file is missing; automatic recovery refused: " + item)
            continue
        if not dest.is_file():
            raise UpdateError("Non-file managed path blocks recovery: " + item)
        actual = hashlib.sha256(dest.read_bytes()).hexdigest()
        allowed = set()
        if item in old_names:
            allowed.add(_expected_sha(record, "old", item))
        if item in new_names:
            allowed.add(_expected_sha(record, "new", item))
        if actual not in allowed:
            raise UpdateError("Managed file changed unexpectedly; automatic recovery refused: " + item)
    last = updates / _LAST
    _assert_unlinked(last, root)
    if last.exists() and _read_pointer(last, root) not in (name, record.get("previous_transaction")):
        raise UpdateError("A different successful update is recorded; recovery refused")
    return journal, record


def _restore_previous(root: Path, updates: Path, name: str) -> dict:
    """Idempotent restoration used by failed apply, rollback, and --recover."""
    journal, record = _validate_recovery(root, updates, name)
    record["status"] = "recovering"
    _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
    tx = updates / name
    old_names, new_names = set(record["old_names"]), set(record["new_names"])
    for item in sorted(old_names):
        backup = tx / "previous" / item
        dest = root / item
        _assert_unlinked(dest, root)
        _atomic_write(dest, backup.read_bytes(), stat.S_IMODE(backup.stat().st_mode))
    for item in sorted(new_names - old_names):
        target = root / item
        _assert_unlinked(target, root)
        target.unlink(missing_ok=True)
    record["status"] = "rolled-back"
    _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
    last = updates / _LAST
    prior = record.get("previous_transaction")
    if prior:
        _write_pointer(last, prior, root)
    else:
        _assert_unlinked(last, root)
        last.unlink(missing_ok=True)
    active = updates / _ACTIVE
    _assert_unlinked(active, root)
    active.unlink(missing_ok=True)
    return {"status": "rolled-back", "restored": record["old_version"],
            "transaction": name}


def _no_pending(updates: Path, root: Path) -> None:
    active = updates / _ACTIVE
    _assert_unlinked(active, root)
    if active.exists():
        raise UpdateError("An update was interrupted. Run updater.py --recover before continuing.")


def apply(archive: Path, digest: str, root: Path = ROOT) -> dict:
    root = root.absolute()
    if _hub_running(root):
        raise UpdateError("Close the MyoTools Hub and all notebook sessions before updating")
    # Bind the archive to the installed channel, immutable Git commit and remote manifest.
    release = check(root)
    if (release.get("status") != "available" or
            release.get("sha256") != digest or
            release.get("channel") != current_channel(root)):
        raise UpdateError("ZIP SHA-256 or channel is not verified against GitHub Downloads")
    with _lock(root) as update_dir:
        _no_pending(update_dir, root)
        p = plan(archive, digest, root)
        if p["new_version"] != release.get("latest"):
            raise UpdateError("Archive version differs from the verified GitHub distribution")
        if hashlib.sha256(p["files"][MANIFEST]).hexdigest() != release.get("manifest_sha256"):
            raise UpdateError("ZIP manifest differs from the verified GitHub Downloads manifest")
        tx_dir = update_dir / ("backup-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:12])
        _assert_unlinked(tx_dir, root)
        tx_dir.mkdir(mode=0o700)
        old_names = set(p["old"]["sha256"]) | {MANIFEST}
        for name in old_names:
            previous = root / name
            backup = tx_dir / "previous" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(previous, backup, follow_symlinks=False)
        last = update_dir / _LAST
        _assert_unlinked(last, root)
        prior = _read_pointer(last, root) if last.is_file() else None
        record = {"status": "prepared", "old_version": p["old_version"],
                  "new_version": p["new_version"], "old_names": sorted(old_names),
                  "new_names": sorted(p["files"]), "old_hashes": p["old"]["sha256"],
                  "new_hashes": p["new"]["sha256"],
                  "old_manifest_sha": hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest(),
                  "new_manifest_sha": hashlib.sha256(p["files"][MANIFEST]).hexdigest(),
                  "previous_transaction": prior}
        journal = tx_dir / "transaction.json"
        _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
        _write_pointer(update_dir / _ACTIVE, tx_dir.name, root)
        record["status"] = "applying"
        _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
        try:
            for name in p["replace"]:
                _assert_unlinked(root / name, root)
                _atomic_write(root / name, p["files"][name], p["modes"][name])
            for name in p["remove"]:
                _assert_unlinked(root / name, root)
                (root / name).unlink()
            record["status"] = "applied"
            _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
            _write_pointer(last, tx_dir.name, root)
            (update_dir / _ACTIVE).unlink()
        except Exception:
            # Keep the active marker if restoration itself fails. --recover
            # may then be retried without making unverified file changes.
            _restore_previous(root, update_dir, tx_dir.name)
            raise
        return {"from": p["old_version"], "to": p["new_version"],
                "backup": str(tx_dir), "status": "applied", "conda": "unchanged", "data": "retained"}


def rollback(root: Path = ROOT) -> dict:
    root = root.absolute()
    if _hub_running(root):
        raise UpdateError("Close MyoTools before rolling back")
    with _lock(root) as updates:
        _no_pending(updates, root)
        last = updates / _LAST
        _assert_unlinked(last, root)
        if not last.is_file():
            raise UpdateError("No successful update to roll back")
        name = _read_pointer(last, root)
        _, journal, record = _load_transaction(updates, name, root)
        if record["status"] != "applied":
            raise UpdateError("Update is not in an applied state")
        current = _read_installed(root)
        if current["suite_version"] != record["new_version"]:
            raise UpdateError("A different version is installed; rollback refused")
        _validate_recovery(root, updates, name)
        _write_pointer(updates / _ACTIVE, name, root)
        record["status"] = "rolling-back"
        _atomic_write(journal, json.dumps(record, indent=2).encode(), 0o600)
        return _restore_previous(root, updates, name)


def recover(root: Path = ROOT) -> dict:
    """Resume the conservative rollback after a crash or forced termination."""
    root = root.absolute()
    if _hub_running(root):
        raise UpdateError("Close all MyoTools processes before recovery")
    with _lock(root) as updates:
        active = updates / _ACTIVE
        _assert_unlinked(active, root)
        if not active.is_file():
            raise UpdateError("No interrupted update requires recovery")
        name = _read_pointer(active, root)
        return _restore_previous(root, updates, name)

def download(root: Path = ROOT) -> dict:
    info = check(root)
    if info["status"] != "available":
        raise UpdateError(info.get("message", "No newer distribution on the " + info["channel"] + " channel"))
    folder = root / "Hub" / "runtime" / "updates" / "downloads"
    _assert_unlinked(folder, root)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (info["channel"] + "-" + info["latest"] + "-" + info["commit"][:12] + "-" + ASSET)
    _assert_unlinked(dest, root)
    if dest.exists():
        if (dest.is_file() and dest.stat().st_size <= MAX_ZIP_BYTES and
                hashlib.sha256(dest.read_bytes()).hexdigest() == info["sha256"]):
            return {**info, "path": str(dest), "status": "downloaded"}
        raise UpdateError("Existing download differs; refusing to overwrite: " + str(dest))
    with tempfile.TemporaryDirectory(prefix=".myotools-download-", dir=folder) as temporary:
        pending = Path(temporary) / ASSET
        raw = _repo_bytes("Downloads/" + ASSET, info["commit"], MAX_ZIP_BYTES)
        if not raw or hashlib.sha256(raw).hexdigest() != info["sha256"]:
            raise UpdateError("Downloaded ZIP differs from verified Downloads/SHA256SUMS.txt")
        pending.write_bytes(raw)
        manifest, files, _ = _read_zip(pending, info["sha256"], root)
        if (_channel(manifest) != info["channel"] or
                manifest["suite_version"] != info["latest"] or
                hashlib.sha256(files[MANIFEST]).hexdigest() != info["manifest_sha256"]):
            raise UpdateError("Downloaded archive differs from its verified branch manifest")
        pending.replace(dest)
    return {**info, "path": str(dest), "status": "downloaded"}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--apply", type=Path, metavar="ZIP")
    mode.add_argument("--rollback", action="store_true")
    mode.add_argument("--recover", action="store_true", help="Restore the previous version after interrupted apply or rollback")
    parser.add_argument("--sha256", help="SHA-256 reported by the installed distribution channel (mandatory for --apply)")
    args = parser.parse_args()
    try:
        if args.check:
            result = check()
        elif args.download:
            result = download()
        elif args.apply:
            if not args.sha256:
                parser.error("--apply requires --sha256 matching GitHub Downloads on the installed channel")
            preview = plan(args.apply, args.sha256)
            print(json.dumps({key: preview[key] for key in ("old_version", "new_version", "replace", "remove")}, indent=2))
            if input("Type " + CONFIRMATION + " to install this update: ") != CONFIRMATION:
                print("Cancelled. No files changed.")
                return 0
            result = apply(args.apply, args.sha256)
        elif args.rollback:
            if input("Type " + CONFIRMATION + " to restore the previous version: ") != CONFIRMATION:
                print("Cancelled. No files changed.")
                return 0
            result = rollback()
        else:
            if input("Type " + CONFIRMATION + " to recover an interrupted transaction: ") != CONFIRMATION:
                print("Cancelled. No files changed.")
                return 0
            result = recover()
        print(json.dumps(result, indent=2))
        return 0
    except (UpdateError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print("Updater: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
