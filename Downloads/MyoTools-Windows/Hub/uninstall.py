#!/usr/bin/env python3
"""Remove only proven-owned Conda environments and the matching desktop link."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from installation import (ALLOWED_ENVIRONMENTS, CONFIRMATION, ROOT,
                          conda_info, environment_prefixes, load_state,
                          maintenance, removable_prefix, unlinked)


def desktop_linux() -> Path:
    if shutil.which("xdg-user-dir"):
        result = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).expanduser()
    return next((p for p in (Path.home() / "Bureau", Path.home() / "Desktop") if p.is_dir()),
                Path.home() / "Desktop")


def shortcut(remove: bool = False) -> dict:
    try:
        if os.name == "nt":
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(ROOT / "Hub" / "platforms" / "windows" / "remove_shortcut.ps1"),
                       "-LauncherPath", str(ROOT / "Hub" / "platforms" / "windows" / "launch.bat"),
                       "-LegacyLauncherPath", str(ROOT / "Hub" / "launch_windows.bat"),
                       "-PreviousLauncherPath", str(ROOT / "Windows" / "launch.bat")]
            if remove:
                command.append("-Remove")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return {"state": "checked", "message": result.stdout.strip()}
        path = desktop_linux() / "MyoTools.desktop"
        # The desktop directory itself can be redirected; the link cannot.
        if path.is_symlink():
            raise RuntimeError("Linked desktop shortcut is protected.")
        if not path.exists():
            return {"state": "absent", "message": "MyoTools desktop shortcut is absent."}
        values = {}
        section = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("["):
                section = line
            elif section == "[Desktop Entry]" and "=" in line:
                key, value = line.split("=", 1)
                if key in values:
                    raise RuntimeError("Ambiguous desktop shortcut is protected.")
                values[key] = value
        # Accept the previous layout only for this exact installation root.
        # This also permits uninstalling an old shortcut after a repository update.
        allowed_exec = []
        for launcher in (ROOT / "Hub" / "platforms" / "linux" / "launch.sh",
                         ROOT / "Linux" / "launch.sh", ROOT / "Hub" / "launch_linux.sh"):
            escaped = '"' + str(launcher).replace("\\", "\\\\").replace('"', '\\"').replace(
                "$", "\\$").replace(chr(96), "\\" + chr(96)).replace("%", "%%") + '"'
            allowed_exec.append("/bin/bash " + escaped)
        if (values.get("Exec") not in allowed_exec or
                values.get("Path") != str(ROOT / "Hub") or values.get("Type") != "Application"):
            raise RuntimeError("Desktop shortcut targets another installation; retained.")
        if remove:
            path.unlink()
        return {"state": "removed" if remove else "owned", "message": str(path)}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return {"state": "retained", "message": str(exc)}


def installation_context() -> tuple[dict, Path, list[Path]]:
    state = load_state()
    conda = Path(state["conda_executable"])
    if not conda.is_absolute():
        raise RuntimeError("Invalid saved Conda executable.")
    unlinked(conda)
    if not conda.is_file():
        raise RuntimeError("The saved Conda executable is missing; no fallback Conda is used.")
    info = conda_info(conda)
    if str(Path(info["root_prefix"]).resolve()) != state["conda_base"]:
        raise RuntimeError("Conda base differs from this installation's record.")
    return state, conda, environment_prefixes(conda)


def plan() -> dict:
    result = {"environments": [], "shortcut": shortcut(), "confirmation": CONFIRMATION}
    try:
        state, _, listed = installation_context()
        for name in ALLOWED_ENVIRONMENTS:
            try:
                prefix = removable_prefix(state, name, listed)
                result["environments"].append({"name": name, "state": "owned", "prefix": str(prefix)})
            except (OSError, KeyError, ValueError, RuntimeError) as exc:
                result["environments"].append({"name": name, "state": "retained", "message": str(exc)})
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        for name in ALLOWED_ENVIRONMENTS:
            result["environments"].append({"name": name, "state": "retained", "message": str(exc)})
    return result


def uninstall(confirmation: str) -> dict:
    if confirmation != CONFIRMATION:
        raise ValueError("Explicit confirmation required: type " + CONFIRMATION)
    result = {"environments": [], "errors": []}
    with maintenance():
        try:
            state, conda, _ = installation_context()
        except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            state = None
            result["errors"].append(str(exc))
        for name in ALLOWED_ENVIRONMENTS:
            if state is None:
                result["environments"].append({"name": name, "state": "retained",
                                                "message": "No valid installation ownership record."})
                continue
            try:
                # Revalidate immediately before each removal, including marker,
                # exact prefix, live Conda registration and base association.
                current, current_conda, listed = installation_context()
                if current != state or current_conda != conda:
                    raise RuntimeError("Installation record changed during uninstallation.")
                prefix = removable_prefix(current, name, listed)
                command = [str(conda), "env", "remove", "--prefix", str(prefix), "--yes"]
                print("\n> " + " ".join(command), flush=True)
                # No shell and no recursive filesystem deletion/fallback.
                subprocess.run(command, check=True)
                if prefix.exists():
                    raise RuntimeError("Conda left the prefix in place; retained without forced deletion.")
                result["environments"].append({"name": name, "state": "removed", "prefix": str(prefix)})
            except subprocess.SubprocessError as exc:
                result["errors"].append(str(exc))
                result["environments"].append({"name": name, "state": "failed", "message": str(exc)})
            except (OSError, KeyError, ValueError, RuntimeError) as exc:
                result["environments"].append({"name": name, "state": "retained", "message": str(exc)})
        result["shortcut"] = shortcut(remove=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without removing anything.")
    args = parser.parse_args()
    print("MyoTools uninstaller\nAnaconda/Miniforge, source files, models and scientific data are kept.")
    print(json.dumps(plan(), indent=2))
    if args.dry_run:
        return 0
    try:
        answer = input("\nType " + CONFIRMATION + " to remove the owned environments and shortcut: ")
    except EOFError:
        answer = ""
    if answer != CONFIRMATION:
        print("Cancelled. Nothing was removed.")
        return 0
    result = uninstall(answer)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("UNINSTALLATION FAILED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
