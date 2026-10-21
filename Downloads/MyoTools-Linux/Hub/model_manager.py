#!/usr/bin/env python3
"""Pinned release models for the local MyoTools installation (stdlib only).

Model files are intentionally outside the generated distributions. Downloading a
model never executes it; the corresponding notebook loads it only when selected.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prepare_models import TARGET as SVETLANA_TARGET, install_model as install_svetlana
from prepare_models import valid_model as valid_svetlana
import update_policy

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "Hub" / "runtime" / "models"

# Exact assets and SHA-256 values returned by the public MyoTools Releases API.
# A replaced release asset cannot silently change the model used for analysis.
MODELS = {
    "myoseg": {
        "name": "MyoSeg · fluorescence", "asset": "MyoSeg", "tag": "MyoSeg",
        "size": 26561372,
        "sha256": "8ef4c909ef0d3b3573e88a632526daa036d9b1a297193a53fc00ee69e1067df6",
        "applications": "MyoSeg (fluorescence)",
    },
    "myoseg_he": {
        "name": "MyoSeg · H&E", "asset": "MyoSeg_HE", "tag": "MyoSeg_HE",
        "size": 26559787,
        "sha256": "9488606007e52f804e1aaa9731b229a54d2ac2285d18a4f29379824053728151",
        "applications": "MyoSeg (H&E RGB)",
    },
    "myoclass": {
        "name": "MyoClass · marqueurs", "asset": "MyoClass", "tag": "MyoClass",
        "size": 26559879,
        "sha256": "cda4a76563fb87a33ec641b7b7fad936877c942188456a68723521db8b7a4924",
        "applications": "MyoClass (mode Automatic)",
    },
    "myonuclei": {
        "name": "MyoNuclei · noyaux", "asset": "MyoNuclei", "tag": "MyoNuclei",
        "size": 26556687,
        "sha256": "4166d70eaccdf50321aad93dfc4cda1791708aa9c702075d08de240e698890c1",
        "applications": "MyoFuse (segmentation des noyaux)",
    },
}


def path_for(key: str) -> Path:
    if key == "svetlana":
        return SVETLANA_TARGET
    return MODEL_DIR / MODELS[key]["asset"]


def _unlinked(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise RuntimeError("Refusing a linked model path: " + str(part))
        if part == ROOT:
            break


def valid_model(key: str) -> bool:
    target = path_for(key)
    if key == "svetlana":
        return valid_svetlana(target)
    try:
        _unlinked(target)
        if not target.is_file() or target.stat().st_size != MODELS[key]["size"]:
            return False
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest() == MODELS[key]["sha256"]
    except OSError:
        return False


def catalog() -> list[dict]:
    items = []
    for key, info in MODELS.items():
        items.append({"id": key, "name": info["name"], "applications": info["applications"],
                      "size": info["size"], "path": str(path_for(key)),
                      "release": f"https://github.com/{update_policy.MODEL_REPOSITORY}/releases/tag/{info['tag']}",
                      "installed": valid_model(key)})
    items.append({"id": "svetlana", "name": "Svetlana · classification", "applications": "MyoFuse (classification)",
                  "size": 286804, "path": str(SVETLANA_TARGET),
                  "release": "https://github.com/BenLair/MyoFuse", "installed": valid_svetlana()})
    return items



def _release_bytes(info: dict):
    """Yield model weight bytes from public HTTPS or private authenticated GitHub CLI.

    All downloaded data are checked against pinned SHA-256 and size by install().
    The public channel never switches model repositories on authentication fallback.
    """
    url = (f"https://github.com/{update_policy.MODEL_REPOSITORY}/releases/"
           f"download/{info['tag']}/{info['asset']}")
    try:
        with urlopen(Request(url, headers={"User-Agent": "MyoTools-Hub/0.4"}),
                     timeout=90) as response:
            yield from iter(lambda: response.read(1024 * 1024), b"")
            return
    except (HTTPError, URLError) as exc:
        if update_policy.EDITION != "internal" or not shutil.which("gh"):
            raise RuntimeError(
                "Cannot download model from GitHub Releases. For a private "
                "repository, install GitHub CLI and run 'gh auth login'.") from exc
    with tempfile.TemporaryDirectory(prefix=".model-gh-", dir=MODEL_DIR) as folder:
        result = subprocess.run(
            ["gh", "release", "download", info["tag"],
             "--repo", update_policy.MODEL_REPOSITORY,
             "--pattern", info["asset"], "--dir", folder],
            capture_output=True, text=True, timeout=240, check=False)
        if result.returncode:
            raise RuntimeError("GitHub CLI cannot download this private release asset. "
                               "Check 'gh auth status'.")
        verified = Path(folder) / info["asset"]
        if not verified.is_file() or verified.stat().st_size > info["size"]:
            raise RuntimeError("Private release model file missing or oversized")
        with verified.open("rb") as stream:
            yield from iter(lambda: stream.read(1024 * 1024), b"")


def install(key: str) -> Path:
    if key == "svetlana":
        _unlinked(SVETLANA_TARGET)
        if SVETLANA_TARGET.exists() and not valid_svetlana():
            raise RuntimeError("Existing Svetlana file differs; retained: " + str(SVETLANA_TARGET))
        install_svetlana()
        return SVETLANA_TARGET
    info = MODELS[key]
    target = path_for(key)
    _unlinked(target)
    if target.exists():
        if valid_model(key):
            return target
        raise RuntimeError("Existing model file differs; retained: " + str(target))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    _unlinked(target)
    fd, temporary = tempfile.mkstemp(prefix=".model-", dir=MODEL_DIR)
    pending = Path(temporary)
    try:
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(fd, "wb") as output:
            for block in _release_bytes(info):
                size += len(block)
                if size > info["size"]:
                    raise RuntimeError("Downloaded model exceeds its published size")
                digest.update(block)
                output.write(block)
        if size != info["size"] or digest.hexdigest() != info["sha256"]:
            raise RuntimeError("Downloaded model differs from the pinned GitHub release")
        _unlinked(target)
        if target.exists():
            raise RuntimeError("Model destination was created during download; retained: " + str(target))
        os.replace(pending, target)
        return target
    finally:
        pending.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify released MyoTools models")
    parser.add_argument("models", nargs="*", choices=[*MODELS, "svetlana"], metavar="MODEL",
                        help="myoseg, myoseg_he, myoclass, myonuclei, svetlana")
    args = parser.parse_args()
    if not args.models:
        for model in catalog():
            print(("Installed" if model["installed"] else "Missing") + ": " + model["name"] + " — " + model["path"])
        return 0
    for key in args.models:
        try:
            print("Verified: " + str(install(key)), flush=True)
        except (OSError, RuntimeError) as exc:
            parser.exit(1, "Model download failed: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
