#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 is required. On Ubuntu: sudo apt-get install python3' >&2
  exit 1
fi
python3 scripts/build.py
exec python3 scripts/serve.py "$@"
