#!/usr/bin/env bash
# Compatibility entry point for existing host/development previews.
set -euo pipefail
exec "$(dirname -- "${BASH_SOURCE[0]}")/bac" dev preview "$@"
