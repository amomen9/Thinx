#!/usr/bin/env bash
# Checks the safeguards for the real interview data (D-S9).
# Usage: ./scripts/check_real_data.sh
#   REAL_DATA_DIR      folder that holds the one allowed copy (default ~/Documents/DSIP-real-data)
#   REAL_DATA_PATTERN  part of the real data file name (default "Tesfa", matches the data file with spaces or underscores)
# Exit code 0 = all checks passed.

set -u
cd "$(dirname "$0")/.." || exit 2
REAL_DATA_DIR="${REAL_DATA_DIR:-$HOME/Documents/DSIP-real-data}"
PATTERN="${REAL_DATA_PATTERN:-Tesfa}"
fails=0
ok()   { echo "  OK    $1"; }
fail() { echo "  FAIL  $1"; fails=$((fails + 1)); }

echo "Thinx real-data safeguards check (D-S9)"

# 1. The device is encrypted (D-S7)
if ./scripts/check_encryption_at_rest.sh >/dev/null 2>&1; then
  ok "disk is encrypted (check_encryption_at_rest.sh)"
else
  fail "disk encryption not confirmed - run ./scripts/check_encryption_at_rest.sh"
fi

# 2. No data files in the repository or its history, apart from the mock data
in_history=$(git log --all --name-only --format= 2>/dev/null \
             | grep -iE '\.(xlsx|xls|csv|json)$' | grep -v '^Mock data/' \
             | grep -viE '(package(-lock)?|tsconfig|jsconfig)\.json$|^frontend/|^backend/data/connections\.json$' \
             | sort -u)
if [ -z "$in_history" ]; then
  ok "no data files in the git history (only Mock data/)"
else
  fail "data files found in the git history:"; echo "$in_history" | sed 's/^/          /'
fi
if git log --all --name-only --format= 2>/dev/null | grep -qi "$PATTERN"; then
  fail "a file named like the real data ($PATTERN) was committed at some point"
else
  ok "real data file was never committed"
fi

# 3. A real_data/ folder in the project is ignored by git
if git check-ignore -q real_data/test.xlsx; then
  ok "real_data/ is ignored by git"
else
  fail "real_data/ is not in .gitignore"
fi

# 4. Only one copy on this computer, inside REAL_DATA_DIR
if [ "$(uname -s)" = "Darwin" ]; then
  copies=$(mdfind -name "$PATTERN" 2>/dev/null)
else
  copies=$(find "$HOME" -iname "*$PATTERN*" -not -path '*/.Trash/*' 2>/dev/null)
fi
outside=$(echo "$copies" | grep -v '^$' | grep -v "^$REAL_DATA_DIR/" || true)
inside=$(echo "$copies" | grep -c "^$REAL_DATA_DIR/" || true)
if [ -n "$outside" ]; then
  fail "copies outside $REAL_DATA_DIR (delete them or move the one you keep there):"
  echo "$outside" | sed 's/^/          /'
else
  ok "no copies outside $REAL_DATA_DIR"
fi
echo "        copies inside $REAL_DATA_DIR: $inside"

echo
if [ "$fails" -eq 0 ]; then echo "RESULT: all checks passed"; exit 0; fi
echo "RESULT: $fails check(s) failed"; exit 1
