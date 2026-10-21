#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ -f runtime/python_path.txt ]; then
 candidate="$(head -n 1 runtime/python_path.txt)"
 if [ -x "$candidate" ]; then exec "$candidate" launcher.py "$@"; fi
fi
for candidate in "$HOME/miniforge3/bin/python" "$HOME/miniconda3/bin/python" "$HOME/anaconda3/bin/python"; do
 if [ -x "$candidate" ]; then exec "$candidate" launcher.py "$@"; fi
done
echo "Conda Python not found. Run: bash Hub/platforms/linux/install.sh" >&2
exit 1
