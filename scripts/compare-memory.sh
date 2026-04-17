#!/usr/bin/env bash
# compare-memory.sh — Side-by-side comparison of old vs new memory systems
# Run: manually or via cron (Sundays 18:00)
# Outputs: entry counts, search result diffs, timing benchmarks

set -euo pipefail

OLD_DIR="/home/wahaj/.openclaw/workspace/memory"
NEW_DIR="/home/wahaj/.openclaw/workspace/openclaw-memory"
OUTDIR="$NEW_DIR/reports"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$OUTDIR"

echo "========================================"
echo "  Memory Systems Comparison"
echo "  $NOW"
echo "========================================"

# ---------------------------------------------------------------------------
# 1. Entry counts
# ---------------------------------------------------------------------------
echo ""
echo "--- ENTRY COUNTS ---"

OLD_COUNT=$(find "$OLD_DIR" -name "*.md" -not -path "*/\.*" | wc -l)
OLD_ENTRIES=0
for f in "$OLD_DIR"/*.md; do
  [[ -f "$f" ]] || continue
  # Count frontmatter-lite entries: lines that look like --- or ## entries
  lines=$(wc -l < "$f")
  OLD_ENTRIES=$((OLD_ENTRIES + lines))
done

NEW_ENTRIES=$(find "$NEW_DIR/memory" -name "*.jsonl" -exec cat {} \; 2>/dev/null | grep -c '"id"' || 0)

echo "OLD (Markdown files)  : $OLD_COUNT files, ~$OLD_ENTRIES lines"
echo "NEW (JSONL buckets)   : $NEW_ENTRIES entries"

# ---------------------------------------------------------------------------
# 2. Disk usage
# ---------------------------------------------------------------------------
echo ""
echo "--- DISK USAGE ---"
OLD_SIZE=$(du -sh "$OLD_DIR" 2>/dev/null | cut -f1 || echo "N/A")
NEW_SIZE=$(du -sh "$NEW_DIR/memory" 2>/dev/null | cut -f1 || echo "N/A")
echo "OLD system            : $OLD_SIZE"
echo "NEW system (memory/)  : $NEW_SIZE"

# ---------------------------------------------------------------------------
# 3. Index integrity (new system only)
# ---------------------------------------------------------------------------
echo ""
echo "--- NEW SYSTEM INDEX ---"
INDEX_DB="$NEW_DIR/memory/.index/graph.db"
if [[ -f "$INDEX_DB" ]]; then
  INDEX_SIZE=$(du -sh "$INDEX_DB" 2>/dev/null | cut -f1)
  INDEXED=$(sqlite3 "$INDEX_DB" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "ERR")
  FTS_COUNT=$(sqlite3 "$INDEX_DB" "SELECT COUNT(*) FROM entries_fts;" 2>/dev/null || echo "ERR")
  echo "Index DB              : $INDEX_SIZE"
  echo "Indexed entries      : $INDEXED"
  echo "FTS5 entries         : $FTS_COUNT"
  if [[ "$INDEXED" != "$FTS_COUNT" ]]; then
    echo "⚠️  FTS/index mismatch — rebuild may be needed"
  fi
else
  echo "⚠️  No index DB found at $INDEX_DB"
fi

# ---------------------------------------------------------------------------
# 4. Timing — write a test entry to new system
# ---------------------------------------------------------------------------
echo ""
echo "--- WRITE PERFORMANCE (NEW SYSTEM) ---"

TMP_OUT=$(mktemp)
WRITE_TIME_NEW=$( {
    time python3 - "$NEW_DIR" <<'PYEOF'
import sys, json, uuid, datetime, timezone
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/src")
from openclaw_memory.core import MemoryStore
store = MemoryStore(sys.argv[1])
store.write(text="COMPARE_TEST_ENTRY Do not delete — automated performance test " + str(uuid.uuid4()),
            type_="note", tags=["compare"], refs=[])
PYEOF
} 2>&1 | grep real | awk '{print $2}' )

echo "Write time (new)      : $WRITE_TIME_NEW"

# ---------------------------------------------------------------------------
# 5. Search comparison for sample queries
# ---------------------------------------------------------------------------
echo ""
echo "--- SEARCH COMPARISON ---"

QUERIES=("memory" "task" "project" "Buck" "workspace")

for q in "${QUERIES[@]}"; do
  echo ""
  echo "Query: \"$q\""

  # OLD system — simple grep across all .md files
  OLD_START=$(date +%s%N)
  OLD_RESULTS=$(grep -ril "$q" "$OLD_DIR"/*.md 2>/dev/null | head -5 || true)
  OLD_COUNT_Q=$(echo "$OLD_RESULTS" | grep -c . || echo 0)
  OLD_TIME=$(python3 -c "print(round(($(date +%s%N) - $OLD_START) / 1e6, 2))")

  # NEW system — FTS5 keyword search
  NEW_START=$(date +%s%N)
  NEW_RESULTS=$(python3 - "$NEW_DIR" "$q" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1] + "/src")
from openclaw_memory.search import MemorySearch
sr = MemorySearch(sys.argv[1])
res = sr.search(query=sys.argv[2], mode="keyword", limit=5)
for e in res:
    print(e["id"])
PYEOF
  )
  NEW_COUNT_Q=$(echo "$NEW_RESULTS" | grep -c . || echo 0)
  NEW_TIME=$(python3 -c "print(round(($(date +%s%N) - $NEW_START) / 1e6, 2))")

  echo "  OLD — $OLD_COUNT_Q hits in ${OLD_TIME}ms"
  echo "  NEW — $NEW_COUNT_Q hits in ${NEW_TIME}ms"
done

# ---------------------------------------------------------------------------
# 6. New-system write count over trial period
# ---------------------------------------------------------------------------
echo ""
echo "--- TRIAL WRITE COUNT ---"
TRIAL_START="2026-04-15"
WRITE_COUNT=$(find "$NEW_DIR/memory" -name "*.jsonl" -newermt "$TRIAL_START" -exec cat {} \; 2>/dev/null | grep -c '"id"' || echo 0)
echo "Writes since $TRIAL_START : $WRITE_COUNT"

# ---------------------------------------------------------------------------
# 7. Any JSONL parse errors?
# ---------------------------------------------------------------------------
echo ""
echo "--- INTEGRITY CHECKS ---"
ERRORS=0
for f in "$NEW_DIR/memory"/*.jsonl; do
  [[ -f "$f" ]] || continue
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    python3 -c "import sys,json; json.loads('$line')" 2>/dev/null || {
      echo "⚠️  Malformed line in $f: ${line:0:60}"
      ERRORS=$((ERRORS + 1))
    }
  done < "$f"
done
if [[ $ERRORS -eq 0 ]]; then
  echo "JSONL integrity         : ✓ All entries parse cleanly"
else
  echo "JSONL integrity         : ⚠️  $ERRORS errors found"
fi

echo ""
echo "========================================"
echo "  Comparison complete — $NOW"
echo "========================================"
echo ""
echo "Next step: review output, then after 7 days run:"
echo "  python3 $NEW_DIR/scripts/trial-decision.py"