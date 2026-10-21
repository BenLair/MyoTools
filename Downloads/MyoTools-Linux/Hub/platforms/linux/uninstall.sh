#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -f runtime/python_path.txt ]; then
 candidate="$(head -n 1 runtime/python_path.txt)"
 if [ -x "$candidate" ]; then exec "$candidate" uninstall.py "$@"; fi
fi
for candidate in "$HOME/miniforge3/bin/python" "$HOME/miniconda3/bin/python" "$HOME/anaconda3/bin/python"; do
 if [ -x "$candidate" ]; then exec "$candidate" uninstall.py "$@"; fi
done
if command -v python3 >/dev/null 2>&1; then exec python3 uninstall.py "$@"; fi
echo "Python 3.9 or newer is required. Anaconda/Miniforge and all data were kept." >&2
exit 1
