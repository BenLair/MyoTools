#!/usr/bin/env python3
"""Set up the two validated MyoTools environments and a desktop shortcut.

Executed with the already-installed (or newly bootstrapped) Conda base Python.
Standard-library only: this script never depends on Cellpose or Voila.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from installation import (checked_prefix, environment_prefixes, maintenance,
                          register_created, setup_state, unlinked)

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "Hub"
RUNTIME = HUB / "runtime"


def run(*args: str) -> None:
    command = [str(x) for x in args]
    print("\n> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(ROOT), check=True)


def ensure_nbclient(conda: Path) -> None:
    # Existing older installations are repaired, not simply skipped.
    args = (str(conda), "run", "--no-capture-output", "-n", "myofuse_env",
            "python", "-c",
            "import nbclient, sys; sys.exit(0 if nbclient.__version__ == '0.10.2' else 1)")
    print("\nChecking MyoFuse Python 3.9 / nbclient compatibility...", flush=True)
    if subprocess.run(args, cwd=str(ROOT)).returncode:
        run(str(conda), "run", "--no-capture-output", "-n", "myofuse_env",
            "python", "-m", "pip", "install", "--no-deps", "nbclient==0.10.2")
    run(str(conda), "run", "--no-capture-output", "-n", "myofuse_env",
        "python", "-c",
        "import sys, nbclient; assert sys.version_info[:2] == (3, 9); "
        "assert nbclient.__version__ == '0.10.2'; "
        "print('MyoFuse: Python', sys.version.split()[0], 'nbclient', nbclient.__version__)")


def write_runtime(conda: Path, base_python: Path) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    # Do not export user-specific absolute paths into the git repository.
    (RUNTIME / "conda_path.txt").write_text(str(conda.resolve()) + "\n", encoding="utf-8")
    (RUNTIME / "python_path.txt").write_text(str(base_python.resolve()) + "\n", encoding="utf-8")


def desktop_linux() -> Path:
    launcher = HUB / "platforms" / "linux" / "launch.sh"
    icon = HUB / "assets" / "myotools-icon.svg"
    if not launcher.is_file() or not icon.is_file():
        raise FileNotFoundError("Linux launcher or MyoTools icon is missing.")

    desktop = None
    if shutil.which("xdg-user-dir"):
        output = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
        if output.returncode == 0 and output.stdout.strip():
            desktop = Path(output.stdout.strip()).expanduser()
    if desktop is None:
        desktop = next(
            (p for p in (Path.home() / "Bureau", Path.home() / "Desktop") if p.is_dir()),
            Path.home() / "Desktop",
        )
    desktop.mkdir(parents=True, exist_ok=True)

    def escape_command_arg(arg: Path) -> str:
        # Desktop entry Exec quoting, not shell-style quoting; double % in field codes.
        return '"' + str(arg).replace("\\", "\\\\").replace('"', '\\"').replace(
            "$", "\\$").replace(chr(96), "\\" + chr(96)).replace("%", "%%") + '"'

    contents = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=MyoTools\n"
        "Comment=Muscle image analysis suite\n"
        "Exec=/bin/bash " + escape_command_arg(launcher.resolve()) + "\n"
        "Path=" + str(HUB.resolve()) + "\n"
        "Icon=" + str(icon.resolve()) + "\n"
        "Terminal=true\n"
        "Categories=Science;Education;\n"
        "StartupNotify=true\n"
    )
    shortcut = desktop / "MyoTools.desktop"
    shortcut.write_text(contents, encoding="utf-8")
    shortcut.chmod(0o755)
    # Some GNOME installations require explicit trust for newly-created desktop launchers.
    if shutil.which("gio"):
        subprocess.run(["gio", "set", str(shortcut), "metadata::trusted", "true"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return shortcut


def desktop_windows() -> Path:
    launcher = HUB / "platforms" / "windows" / "launch.bat"
    icon = HUB / "assets" / "myotools-icon.ico"
    helper = HUB / "platforms" / "windows" / "create_shortcut.ps1"
    if not launcher.is_file() or not icon.is_file() or not helper.is_file():
        raise FileNotFoundError("Windows launcher, shortcut helper or icon is missing.")
    run("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(helper), "-LauncherPath", str(launcher.resolve()),
        "-IconPath", str(icon.resolve()))
    return launcher


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conda", type=Path, required=True)
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    args = parser.parse_args()
    windows = args.platform == "windows"
    conda = args.conda.expanduser().resolve()
    if not conda.is_file():
        raise FileNotFoundError("Conda executable not found: " + str(conda))
    if windows != (os.name == "nt"):
        raise RuntimeError("Selected platform does not match the current OS.")

    base = subprocess.check_output([str(conda), "info", "--base"], text=True).strip()
    python = Path(base) / ("python.exe" if windows else "bin/python")
    if not python.is_file():
        raise FileNotFoundError("Cannot find Conda base Python: " + str(python))

    with maintenance():
        return install(conda, Path(base).resolve(), python.resolve(), windows)


def install(conda: Path, base: Path, python: Path, windows: bool) -> int:
    state = setup_state(conda, base, python)
    # Save immediately so standalone uninstallation also works after a later
    # package/model/shortcut failure. Existing environments are never adopted.
    write_runtime(conda, python)

    platform_setup = HUB / "platforms" / ("windows" if windows else "linux") / "environments"
    manifests = [
        ("myotools", platform_setup / "myotools.yml"),
        ("myofuse_env", platform_setup / "myofuse.yml"),
    ]
    for environment, yaml in manifests:
        if not yaml.is_file():
            raise FileNotFoundError("Missing environment specification: " + str(yaml))
        available = environment_prefixes(conda)
        if any(p.name.lower() == environment for p in available):
            print(environment + ": existing environment retained.", flush=True)
        else:
            prefix = checked_prefix(state, environment, base / "envs" / environment)
            unlinked(prefix)
            if prefix.exists():
                raise RuntimeError("Unregistered existing folder is protected: " + str(prefix))
            print("Installing " + environment + " (may take a while)...", flush=True)
            run(str(conda), "env", "create", "--prefix", str(prefix), "-f", str(yaml))
            register_created(state, environment, prefix)
    ensure_nbclient(conda)

    # Uses only stdlib; downloads the original public Svetlana classifier, if missing.
    run(str(python), str(HUB / "prepare_models.py"))
    write_runtime(conda, python)
    try:
        shortcut = desktop_windows() if windows else desktop_linux()
        print("Desktop shortcut ready: " + str(shortcut), flush=True)
    except Exception as exc:
        # The scientific software is installed; a desktop integration failure
        # must not invalidate an otherwise usable installation.
        print("WARNING: desktop shortcut could not be created: " + str(exc), flush=True)

    print("\nMyoTools installation completed.", flush=True)
    print("Use Hub/platforms/windows/launch.bat or Hub/platforms/linux/launch.sh to start MyoTools.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("\nINSTALLATION FAILED: " + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)

