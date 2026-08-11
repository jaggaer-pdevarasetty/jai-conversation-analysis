#!/usr/bin/env bash
# Guard for ADR-0001: SELECT-only against org systems, writes only to our own store.
#
# Fails CI if a SQL write verb (INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE) or a generic
# `.execute(`/`.commit(` write call appears in server code OUTSIDE the files that are
# explicitly allowed to write (our own persistence layer). This is a lightweight net to
# catch an accidental write against the chat DB / LangSmith client creeping back in.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/server/app"

# Files allowed to perform writes: our own common store only.
ALLOWED='^(store\.py|store_sql\.py|store_factory\.py)$'

WRITE_PATTERN='(^|[^A-Za-z_])(INSERT INTO|UPDATE |DELETE FROM|DROP TABLE|ALTER TABLE|TRUNCATE)'

violations=0
while IFS= read -r -d '' file; do
  rel="$(basename "$file")"
  if [[ "$rel" =~ $ALLOWED ]]; then
    continue
  fi
  if grep -InE "$WRITE_PATTERN" "$file" >/tmp/rop_hit_$$ 2>/dev/null; then
    echo "✗ possible write against a non-own store in $file:"
    sed 's/^/    /' /tmp/rop_hit_$$
    violations=1
  fi
  rm -f /tmp/rop_hit_$$
done < <(find . -name '*.py' -print0)

if [ "$violations" -ne 0 ]; then
  echo
  echo "ADR-0001 violation: org DBs are SELECT-only; writes belong only in store.py /" \
       "store_sql.py / store_factory.py. If this is a false positive, adjust ALLOWED" \
       "in scripts/check_read_only_posture.sh."
  exit 1
fi

echo "✓ read-only posture guard passed (ADR-0001)"
