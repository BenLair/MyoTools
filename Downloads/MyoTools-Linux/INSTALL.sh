#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/Hub/platforms/linux/install.sh" "$@"
