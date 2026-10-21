"""Detached maintenance worker for MyoTools.

Executed from Hub/runtime/updates/ (outside managed distribution files) so that
updater.py and launcher.py can be replaced while update code is executing.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

def perform(root: Path, job_id: str) -> int:
    # Import only stable stdlib and initial code until the Hub has stopped.
    sys.path.insert(0, str(root / "Hub"))
    import update_service
    import updater

    state = update_service.operation(root)
    if not state or state.get("id") != job_id or state.get("status") != "queued":
        raise updater.UpdateError("Missing or inconsistent maintenance job")
    hub_pid = state["hub_pid"]
    tool_pids = state["tool_pids"]
    state["status"] = "waiting"
    update_service._write_operation(root, state)

    # Do not race the hub or its previously started analysis processes.
    for _ in range(150):
        if not updater._pid_alive(hub_pid) and not any(
                updater._pid_alive(pid) for pid in tool_pids):
            break
        time.sleep(0.2)
    else:
        raise updater.UpdateError("Hub or analysis process did not stop: update aborted")

    if updater._hub_running(root):
        raise updater.UpdateError("Another MyoTools Hub remains active: update aborted")

    state["status"] = "applying" if state["action"] == "install" else "recovering"
    update_service._write_operation(root, state)
    # Treat repository metadata as untrusted even if staged by the previous Hub.
    if state["action"] == "install":
        result = updater.apply(Path(state["archive"]), state["sha256"], root)
    elif state["action"] == "rollback":
        result = updater.rollback(root)
    else:
        raise updater.UpdateError("Unsupported maintenance action")

    state["status"] = "restarting"
    state["details"] = "Applied changes; relaunching MyoTools."
    state["result"] = result
    update_service._write_operation(root, state)
    # Reuse the same Python executable already used to start the Hub.
    # This avoids recreating Conda or touching the models.
    launch = [sys.executable, str(root / "Hub" / "launcher.py")]
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0) |
             getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) if os.name == "nt" else 0
    with (root / "Hub" / "runtime" / "updates" / "restart.log").open("ab") as log:
        subprocess.Popen(launch, cwd=root, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=subprocess.STDOUT, close_fds=True,
                         creationflags=flags, start_new_session=(os.name != "nt"))
    state["status"] = "complete"
    state["details"] = "Update completed; a fresh MyoTools Hub was started."
    update_service._write_operation(root, state)
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    root = args.root.absolute()
    sys.path.insert(0, str(root / "Hub"))
    import update_service
    try:
        return perform(root, args.job)
    except BaseException as exc:
        try:
            record = update_service.operation(root)
            if record and record.get("id") == args.job:
                record["status"] = "error"
                record["details"] = str(exc)
                update_service._write_operation(root, record)
        finally:
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
