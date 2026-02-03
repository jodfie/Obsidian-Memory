#!/usr/bin/env bash
#
# Delete remote branches except main and dev.
# Use: main + dev only (main is preferred over master per modern convention).
#
# Prerequisites:
# 1. On GitHub: Settings → Default branch → set to "main" (if you keep main).
# 2. Merge master into main if needed: git checkout main && git merge master
# 3. Run this script (dry-run first, then for-real).
#
# Usage:
#   ./scripts/cleanup-branches.sh           # dry run: print branches to delete
#   ./scripts/cleanup-branches.sh --delete  # actually delete remote branches
#
set -euo pipefail

KEEP_BRANCHES="main dev"
DELETE_FLAG=false

for arg in "$@"; do
  case "$arg" in
    --delete) DELETE_FLAG=true ;;
  esac
done

git fetch origin 2>/dev/null || true

to_delete=()
while read -r b; do
  [ -z "$b" ] && continue
  keep=
  for k in $KEEP_BRANCHES; do
    if [ "$b" = "$k" ]; then keep=1; break; fi
  done
  [ -n "$keep" ] && continue
  to_delete+=( "$b" )
done < <(git branch -r | grep -v HEAD | sed 's|.*origin/||' | sort -u)

if [ ${#to_delete[@]} -eq 0 ]; then
  echo "No branches to delete (only main and dev exist)."
  exit 0
fi

echo "Branches to delete (keeping: $KEEP_BRANCHES):"
printf '  %s\n' "${to_delete[@]}"
echo ""

if [ "$DELETE_FLAG" = true ]; then
  echo "Deleting ${#to_delete[@]} remote branches..."
  for b in "${to_delete[@]}"; do
    git push origin --delete "$b" 2>/dev/null || echo "  (skip or failed: $b)"
  done
  echo "Done."
else
  echo "Dry run. To delete these branches, run:"
  echo "  $0 --delete"
fi
