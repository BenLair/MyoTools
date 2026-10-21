"""Safe handoff from the MyoTools Hub to a detached maintenance worker.

The Hub can CHECK and DOWNLOAD while running. Applying or restoring distribution
files is always delegated to a different Python process, after the Hub exits.
Only verified package files are managed; data and Conda live outside that scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import updater

VALID_ACTIONS = ("install", "rollback")
FINISHED = ("complete", "error")
WAITING = ("queued", "waiting", "applying", "recovering", "restarting")


def _operation_path(root: Path) -> Path:
    path = root / "Hub" / "runtime" / "updates" / "operation.json"
    updater._assert_unlinked(path, root)
    return path


def operation(root: Path = updater.ROOT) -> dict | None:
    path = _operation_path(root)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 128 * 1024:
        raise updater.UpdateError("Invalid update operation record")
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("status") not in (*WAITING, *FINISHED):
        raise updater.UpdateError("Invalid update operation state")
    return state


def _write_operation(root: Path, value: dict) -> None:
    path = _operation_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    updater._atomic_write(
        path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        0o600)


def inspect(root: Path = updater.ROOT) -> dict:
    """Return only local information; never contacts GitHub."""
    root = root.absolute()
    record = operation(root)
    busy = bool(record and record["status"] in WAITING)
    updates = root / "Hub" / "runtime" / "updates"
    last = updates / "last-update.json"
    active = updates / "active-transaction.json"
    updater._assert_unlinked(last, root)
    updater._assert_unlinked(active, root)
    return {
        "installed": updater.current_version(root),
        "channel": updater.current_channel(root),
        "platform": updater.PLATFORM,
        "install_enabled": not busy and not active.exists(),
        "rollback_enabled": last.is_file() and not busy and not active.exists(),
        "operation": record,
    }


def _prepare_install(root: Path) -> tuple[dict, dict]:
    # download() verifies both SHA-256 and manifest, even for cached ZIPs.
    info = updater.download(root)
    package = Path(info["path"])
    plan = updater.plan(package, info["sha256"], root)
    if plan["new_version"] != info["latest"]:
        raise updater.UpdateError("Verified download and installation plan disagree")
    return info, plan


def queue(root: Path, action: str, hub_pid: int, python_executable: str,
          tool_pids: list[int] | None = None) -> dict:
    """Stage a maintenance worker without changing any managed source files.

    The caller must hold the Hub's local session and update-request locks.
    After a successful return, the Hub must finish its HTTP reply and shut down.
    """
    root = root.absolute()
    if action not in VALID_ACTIONS:
        raise updater.UpdateError("Unknown update operation")
    if not isinstance(hub_pid, int) or hub_pid <= 0:
        raise updater.UpdateError("Cannot identify the running Hub")
    if not Path(python_executable).is_file():
        raise updater.UpdateError("Hub Python interpreter no longer exists")
    state = inspect(root)
    if state["operation"] and state["operation"]["status"] in WAITING:
        raise updater.UpdateError("A previous update is still in progress")
    if not state["install_enabled"]:
        raise updater.UpdateError("An interrupted transaction needs recovery before another update")
    maintenance = root / "Hub" / "runtime" / "maintenance.lock"
    updater._assert_unlinked(maintenance, root)
    if maintenance.exists():
        raise updater.UpdateError("An installation, uninstallation or update currently holds the maintenance lock")
    if action == "install":
        info, plan = _prepare_install(root)
        args = {"archive": info["path"], "digest": info["sha256"],
                "from": plan["old_version"], "to": plan["new_version"]}
    else:
        if not state["rollback_enabled"]:
            raise updater.UpdateError("No previous update is available to roll back")
        last = root / "Hub" / "runtime" / "updates" / "last-update.json"
        transaction = updater._read_pointer(last, root)
        updates = last.parent
        _, _, record = updater._load_transaction(updates, transaction, root)
        if record["status"] != "applied" or state["installed"] != record["new_version"]:
            raise updater.UpdateError("Rollback does not match the currently installed version")
        updater._validate_recovery(root, updates, transaction)
        args = {"from": record["new_version"], "to": record["old_version"]}

    active_tools = tool_pids or []
    if any(not isinstance(pid, int) or pid <= 0 or pid == hub_pid for pid in active_tools):
        raise updater.UpdateError("Invalid application process IDs")
    job = {
        "id": secrets.token_hex(12),
        "action": action,
        "status": "queued",
        "from": args["from"],
        "to": args["to"],
        "started": time.time(),
        "hub_pid": hub_pid,
        "tool_pids": sorted(set(active_tools)),
        "details": "Waiting for the Hub to close before modifying any files.",
    }
    if action == "install":
        job["archive"] = args["archive"]
        job["sha256"] = args["digest"]

    updates = root / "Hub" / "runtime" / "updates"
    updater._assert_unlinked(updates, root)
    updates.mkdir(parents=True, exist_ok=True)
    stage = updates / ("worker-" + job["id"] + ".py")
    updater._assert_unlinked(stage, root)
    worker_source = root / "Hub" / "update_worker.py"
    updater._assert_unlinked(worker_source, root)
    if not worker_source.is_file() or stage.exists():
        raise updater.UpdateError("Maintenance worker missing or already present")

    # Keep the executing worker outside the managed distribution tree.
    updater._atomic_write(stage, worker_source.read_bytes(), 0o600)
    _write_operation(root, job)
    logfile = updates / ("worker-" + job["id"] + ".log")
    updater._assert_unlinked(logfile, root)
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0) |
             getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
    command = [python_executable, str(stage), "--root", str(root), "--job", job["id"]]
    try:
        with logfile.open("ab") as output:
            subprocess.Popen(
                command, cwd=root, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, close_fds=True,
                creationflags=flags, start_new_session=(os.name != "nt"))
    except (OSError, subprocess.SubprocessError) as exc:
        job["status"] = "error"
        job["details"] = "Could not start the maintenance process: " + str(exc)
        _write_operation(root, job)
        raise updater.UpdateError(job["details"]) from exc
    return {"status": "queued", "action": action, "from": args["from"],
            "to": args["to"], "message": "Save work: the Hub will close and restart automatically."}
