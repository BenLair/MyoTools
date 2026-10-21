"""Desktop resolution embedded in the notebook interfaces."""


def default_image_directory():
    """Use the user's real Desktop, or their home if no Desktop is available.

    This standard-library-only function is embedded in the notebooks so they
    also work when launched directly, without importing or starting the hub.
    """
    import os
    import subprocess
    from pathlib import Path

    if os.name == "nt":
        command = ["powershell.exe", "-NoProfile", "-Command",
                   "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; [Environment]::GetFolderPath('DesktopDirectory')"]
    else:
        command = ["xdg-user-dir", "DESKTOP"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0 and result.stdout.strip():
            desktop = Path(result.stdout.strip().lstrip("\ufeff")).expanduser()
            if desktop.is_absolute() and desktop.is_dir():
                return desktop
    except (OSError, subprocess.SubprocessError):
        pass
    home = Path.home()
    return next((path for path in (home / "Desktop", home / "Bureau") if path.is_dir()), home)
