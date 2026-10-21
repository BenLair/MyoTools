#!/usr/bin/env python3
"""Install the original MyoFuse/Svetlana classifier (Python standard library only).

The notebook is bundled with MyoTools Hub, while the original .pth classifier
is fetched separately from the public BenLair/MyoFuse repository.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "MyoFuse" / "Models" / "Svetlana" / "MyoFuse.pth"
URL = "https://raw.githubusercontent.com/BenLair/MyoFuse/main/Models/Svetlana/MyoFuse.pth"
EXPECTED_BYTES = 286804
# SHA-1 of the Git blob from BenLair/MyoFuse; includes "blob <length>\\0" prefix.
EXPECTED_GIT_BLOB = "f21eeee19a417d3db0eed871bded76d6b10b7c5f"


def valid_model(path: Path = TARGET) -> bool:
    """Check size and Git blob hash, not just filename or extension."""
    try:
        size = path.stat().st_size
        if size != EXPECTED_BYTES:
            return False
        digest = hashlib.sha1()
        digest.update(f"blob {size}\0".encode("ascii"))
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest() == EXPECTED_GIT_BLOB
    except OSError:
        return False


def install_model() -> str:
    """Download and validate the model, with an atomic destination replacement."""
    if valid_model():
        return "Svetlana classifier is already installed."
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".svetlana-", suffix=".pth.tmp", dir=TARGET.parent)
    tmp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as output:
            request = Request(URL, headers={"User-Agent": "MyoTools-Hub/0.2"})
            with urlopen(request, timeout=45) as response:
                size = 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > EXPECTED_BYTES:
                        raise RuntimeError("Model download is larger than expected.")
                    output.write(chunk)
        if not valid_model(tmp_path):
            raise RuntimeError(
                "Downloaded Svetlana model does not match the official GitHub release "
                "(size or Git blob SHA-1 mismatch)."
            )
        os.replace(tmp_path, TARGET)
    finally:
        tmp_path.unlink(missing_ok=True)
    return "Svetlana classifier downloaded and verified at " + str(TARGET)


def main() -> int:
    print("Downloading the original Svetlana classifier if needed...", flush=True)
    try:
        print(install_model())
    except Exception as exc:
        print("ERROR: Svetlana download failed: " + str(exc), flush=True)
        return 1
    print("Cellpose custom segmentation models remain separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
