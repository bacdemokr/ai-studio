#!/usr/bin/env bash
# Keep api.cfg populated locally while Git records only an empty placeholder.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if command -v git >/dev/null && [[ $(git rev-parse --show-toplevel 2>/dev/null || true) == "$PWD" ]]; then
  git config --local filter.bac-api-key.clean 'cat >/dev/null'
  git config --local filter.bac-api-key.smudge cat
  git config --local filter.bac-api-key.required true
fi
