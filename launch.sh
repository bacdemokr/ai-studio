#!/usr/bin/env bash
# Development preview shortcut. For Docker installation, use ./bac start.
set -euo pipefail
exec "$(dirname -- "${BASH_SOURCE[0]}")/bac" dev preview "$@"
