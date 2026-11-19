#!/usr/bin/env python3
"""Stage an official verified updater to repair an older MyoTools installation.

Close the Hub and analysis applications, then run this file with --root pointing
to the extracted installation. The normal updater still asks for confirmation,
protects locally modified files, and makes its usual rollback backup.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

ALLOWED_REPOSITORY = "BenLair/MyoTools"


def installed_updater(root: Path):
    manifest = json.loads((root / "DISTRIBUTION.json").read_text(encoding="utf-8"))
    if (manifest.get("update_repository") != ALLOWED_REPOSITORY or
            manifest.get("update_branch") != "main"):
        raise RuntimeError("This repair script is for a different MyoTools edition. Download the script from your installation's official repository.")
    # Check executable dependencies before importing any installed code.
    for relative in ("Hub/updater.py", "Hub/update_policy.py"):
        path = root / relative
        for parent in (path, *path.parents):
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise RuntimeError("Linked installation paths are protected.")
            if parent == root:
                break
        expected = manifest.get("sha256", {}).get(relative)
        if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Locally modified updater code is protected: " + relative)
    sys.path.insert(0, str(root / "Hub"))
    spec = importlib.util.spec_from_file_location("myotools_repair_installed_updater", root / "Hub/updater.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._read_installed(root)
    if module.REPO != ALLOWED_REPOSITORY:
        raise RuntimeError("Installed update policy does not match this repair script.")
    return module


def prepare_repair(root: Path, workspace: Path, updater=None):
    updater = updater or installed_updater(root)
    channel = updater.current_channel(root)
    commit = updater._branch_head(channel)
    platform = "MyoTools-Windows" if updater.PLATFORM == "windows" else "MyoTools-Linux"
    raw_manifest = updater._repo_bytes("Downloads/" + platform + "/DISTRIBUTION.json", commit, 1024 * 1024)
    remote = updater._manifest(raw_manifest, updater.PLATFORM)
    if (remote.get("update_repository") != ALLOWED_REPOSITORY or remote.get("update_branch") != "main"
            or remote.get("update_channel") != channel):
        raise RuntimeError("Remote package origin differs from the installed edition.")
    sums = updater._repo_bytes("Downloads/SHA256SUMS.txt", commit, 4096)
    digest = updater._checksum(sums, updater.ASSET)
    raw = updater._repo_bytes("Downloads/" + updater.ASSET, commit, updater.MAX_ZIP_BYTES)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("Downloaded archive failed SHA-256 verification.")
    workspace.mkdir(parents=True, exist_ok=True)
    archive = workspace / updater.ASSET
    archive.write_bytes(raw)
    manifest, files, _ = updater._read_zip(archive, digest, root)
    if hashlib.sha256(files[updater.MANIFEST]).digest() != hashlib.sha256(raw_manifest).digest():
        raise RuntimeError("Archive and pinned remote manifest differ.")
    stage = workspace / "verified-updater" / "Hub"
    stage.mkdir(parents=True)
    for name in ("updater.py", "update_policy.py"):
        (stage / name).write_bytes(files["Hub/" + name])
    print("Verified official package:", remote["suite_version"], "from", ALLOWED_REPOSITORY, "commit", commit, flush=True)
    return [sys.executable, str(stage / "updater.py"), "--root", str(root),
            "--apply", str(archive), "--sha256", digest]


def record_completed_repair(root: Path, command: list[str], updater, started: float) -> bool:
    """Replace obsolete failure feedback only after verifying the installed build."""
    archive = Path(command[command.index("--apply") + 1])
    digest = command[command.index("--sha256") + 1]
    manifest, files, _ = updater._read_zip(archive, digest, root)
    if (root / updater.MANIFEST).read_bytes() != files[updater.MANIFEST]:
        return False  # A cancelled confirmation returns zero without installing.
    state = {"id": secrets.token_hex(12), "action": "install", "status": "complete",
             "to": manifest["suite_version"], "started": started,
             "details": "Verified maintenance repair completed. Reopen MyoTools using its usual shortcut."}
    path = root / "Hub/runtime/updates/operation.json"
    updater._assert_unlinked(path, root)
    updater._atomic_write(path, (json.dumps(state, indent=2) + "\n").encode("utf-8"), 0o600)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Existing extracted MyoTools installation")
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    try:
        with tempfile.TemporaryDirectory(prefix="myotools-verified-repair-") as directory:
            started = time.time()
            updater = installed_updater(root)
            command = prepare_repair(root, Path(directory), updater=updater)
            # No --force and no automatic confirmation: preserve the normal
            # updater's live-process, source, transaction and file protections.
            code = subprocess.call(command)
            if code == 0:
                if record_completed_repair(root, command, updater, started):
                    print("Repair completed. You can now reopen MyoTools using its usual shortcut or LAUNCH script.")
                else:
                    print("Repair cancelled; installation was not confirmed.")
        return code
    except Exception as exc:
        print("Repair: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
