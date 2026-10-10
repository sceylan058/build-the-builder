#!/usr/bin/env bash
# Fails if a secret appears in any tracked (or staged) file. Run before every commit.
cd "$(git rev-parse --show-toplevel)" || exit 2
files=$(git ls-files -c -o --exclude-standard)
bad=0
if grep -nIE 'fak_[A-Za-z0-9]{8,}|sk-ant-[A-Za-z0-9_-]{8,}' $files 2>/dev/null; then bad=1; fi
for v in "$FREYA_BANK_TEAM_KEY" "$FREYA_API_KEY" "$ANTHROPIC_API_KEY"; do
  if [ -n "$v" ] && grep -nIF -- "$v" $files 2>/dev/null; then bad=1; fi
done
if [ "$bad" = 1 ]; then echo "SECRET SCAN: FAILED"; exit 1; fi
echo "SECRET SCAN: clean ($(echo "$files" | wc -l | tr -d ' ') files)"
