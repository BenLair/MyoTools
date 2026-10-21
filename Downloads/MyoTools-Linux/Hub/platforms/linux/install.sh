#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
echo "=== MyoTools automatic installation (Linux x86_64) ==="
if [ "$(uname -s)" != "Linux" ] || [ "$(uname -m)" != "x86_64" ]; then
 echo "This installer currently supports Linux x86_64 only." >&2; exit 1
fi
CONDA_BIN=""
if [ -f "Hub/runtime/conda_path.txt" ]; then
 candidate="$(head -n 1 "Hub/runtime/conda_path.txt")"
 if [ -x "$candidate" ]; then CONDA_BIN="$candidate"; fi
fi
for candidate in "$HOME/miniforge3/bin/conda" "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda"; do
 if [ -z "$CONDA_BIN" ] && [ -x "$candidate" ]; then CONDA_BIN="$candidate"; fi
done
if [ -z "$CONDA_BIN" ] && command -v conda >/dev/null 2>&1; then CONDA_BIN="$(command -v conda)"; fi
if [ -z "$CONDA_BIN" ]; then
 version="26.7.2-0"
 url="https://github.com/conda-forge/miniforge/releases/download/$version/Miniforge3-$version-Linux-x86_64.sh"
 checksum="281b0ac7d550802efc81af633225a5e6116d29ae72f3ab4eae7168c3931a4c05"
 destination="$HOME/miniforge3"
 if [ -e "$destination" ]; then echo "Existing Miniforge folder: $destination; resolve it first." >&2; exit 1; fi
 tmp="$(mktemp)"
 trap 'rm -f "$tmp"' EXIT
 echo "Downloading official Miniforge and checking SHA-256..."
 if command -v curl >/dev/null 2>&1; then curl --fail --location --retry 2 --output "$tmp" "$url"
 elif command -v wget >/dev/null 2>&1; then wget -O "$tmp" "$url"
 else echo "Install curl or wget first." >&2; exit 1; fi
 echo "$checksum  $tmp" | sha256sum -c -
 bash "$tmp" -b -p "$destination"
 CONDA_BIN="$destination/bin/conda"
fi
if [ ! -x "$CONDA_BIN" ]; then echo "Conda executable not found: $CONDA_BIN" >&2; exit 1; fi
base="$("$CONDA_BIN" info --base)"
python_bin="$base/bin/python"
if [ ! -x "$python_bin" ]; then echo "Conda base Python not found: $python_bin" >&2; exit 1; fi
"$python_bin" Hub/setup_environment.py --conda "$CONDA_BIN" --platform linux
