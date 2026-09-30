#!/usr/bin/env bash
# Fetch source only. The next ./bac start stages it into the app container.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
die() { echo "BaC update: $*" >&2; exit 1; }
command -v git >/dev/null || die 'Install Git first.'
[[ $(git rev-parse --show-toplevel 2>/dev/null) == "$PWD" ]] || die 'Update requires a Git clone of bacdemokr/ai-studio.'
[[ $(git symbolic-ref --quiet --short HEAD) == main ]] || die 'Switch to main before updating. Development branches are left unchanged.'
[[ -z $(git status --porcelain) ]] || die 'Local changes found. Commit or stash them before updating; nothing was overwritten.'
[[ ! -e $(git rev-parse --git-path MERGE_HEAD) && ! -d $(git rev-parse --git-path rebase-merge) && ! -d $(git rev-parse --git-path rebase-apply) ]] || die 'Finish the current merge or rebase first.'
echo 'Fetching the latest private GitHub main…'
git fetch --no-tags https://github.com/bacdemokr/ai-studio.git +refs/heads/main:refs/remotes/bac-update/main || die 'GitHub fetch failed. Check your connection and GitHub access to this private repository.'
git merge-base --is-ancestor HEAD refs/remotes/bac-update/main || die 'Local main has separate commits. Update stopped without overwriting them.'
git merge --ff-only refs/remotes/bac-update/main
echo 'Source updated. Run ./bac start to apply this version. Saved data is kept.'
