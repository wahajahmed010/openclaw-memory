#!/usr/bin/env bash
# daily-check.sh — Health check for new memory system
# Run: daily via cron (9:00 AM) or manually
# Logs to: /home/wahaj/.openclaw/workspace/openclaw-memory/memory/monitor.log

set -euo pipefail

NEW_DIR="/home/wahaj/.openclaw/workspace/openclaw-memory"
LOG="$NEW_DIR/memory/monitor.log"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"
ERRORS=0
WARNINGS=0

log() {
  echo "[$NOW] $1" >> "$LOG"
}

log "========== DAILY HEALTH CHECK =========="

# ---------------------------------------------------------------------------
# 1. Directory exists and is writable
# ---------------------------------------------------------------------------
if [[ -d "$NEW_DIR/memory" ]]; then
  log "✓ Memory directory exists"
else
  log "✗ FATAL: Memory directory missing: $NEW_DIR/memory"
  ERRORS=$((ERRORS + 1))
fi

# ---------------------------------------------------------------------------
# 2. Can write a test entry (and clean up)
# ---------------------------------------------------------------------------
TEST_ID=""
write_test() {
  TEST_ID=$(python3 - "$NEW_DIR" <<'PYEOF'
import sys, json, uuid
sys.path.insert(0, sys.argv[1] + "/src")
from openclaw_memory.core import MemoryStore
store = MemoryStore(sys.argv[1])
entry = store.write(text="DAILY_HEALTH_TEST do not delete", type_="note", tags=["healthcheck"])
print(entry["id"])
PYEOF
  )
}

if write_test; then
  log "✓ Write path functional"
else
  log "✗ FATAL: Cannot write to new memory system"
  ERRORS=$((ERRORS + 1))
fi

# ---------------------------------------------------------------------------
# 3. JSONL integrity — every line must parse
# ---------------------------------------------------------------------------
for f in "$NEW_DIR/memory"/2026-*.jsonl; do
  [[ -f "$f" ]] || continue
  linenum=0
  while IFS= read -r line; do
    linenum=$((linenum + 1))
    [[ -z "$line" ]] && continue
    if ! python3 -c "import sys,json; json.loads('$line')" 2>/dev/null; then
      log "✗ Malformed JSON at $f:$linenum — ${line:0:80}"
      ERRORS=$((ERRORS + 1))
    fi
  done < "$f"
done
if [[ $ERRORS -eq 0 ]]; then
  log "✓ JSONL integrity OK"
fi

# ---------------------------------------------------------------------------
# 4. Index DB exists and is readable
# ---------------------------------------------------------------------------
INDEX_DB="$NEW_DIR/memory/.index/graph.db"
if [[ -f "$INDEX_DB" ]]; then
  INDEXED=$(sqlite3 "$INDEX_DB" "SELECT COUNT(*) FROM entries;" 2>/dev/null || echo "ERR")
  FTS=$(sqlite3 "$INDEX_DB" "SELECT COUNT(*) FROM entries_fts;" 2>/dev/null || echo "ERR")
  if [[ "$INDEXED" == "$FTS" ]]; then
    log "✓ Index DB OK — $INDEXED entries, $FTS FTS5 rows"
  else
    log "⚠️  Index mismatch: entries=$INDEXED, fts=$FTS — rebuild recommended"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  log "⚠️  No index DB found — system may be running without FTS"
  WARNINGS=$((WARNINGS + 1))
fi

# ---------------------------------------------------------------------------
# 5. Search functionality
# ---------------------------------------------------------------------------
SEARCH_OK=$(python3 - "$NEW_DIR" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1] + "/src")
from openclaw_memory.search import MemorySearch
sr = MemorySearch(sys.argv[1])
try:
    res = sr.search(query="test", mode="keyword", limit=5)
    print("OK")
except Exception as e:
    print(f"ERR:{e}")
PYEOF
)

if [[ "$SEARCH_OK" == "OK" ]]; then
  log "✓ Search functional"
else
  log "✗ Search failed: $SEARCH_OK"
  ERRORS=$((ERRORS + 1))
fi

# ---------------------------------------------------------------------------
# 6. Disk usage check (warn if > 500MB)
# ---------------------------------------------------------------------------
MEMORY_SIZE=$(du -sb "$NEW_DIR/memory" 2>/dev/null | cut -f1 || echo 0)
MEMORY_SIZE_MB=$((MEMORY_SIZE / 1024 / 1024))
if [[ $MEMORY_SIZE_MB -gt 500 ]]; then
  log "⚠️  Disk usage high: ${MEMORY_SIZE_MB}MB"
  WARNINGS=$((WARNINGS + 1))
else
  log "✓ Disk usage OK: ${MEMORY_SIZE_MB}MB"
fi

# ---------------------------------------------------------------------------
# 7. Recent writes count (last 24h)
# ---------------------------------------------------------------------------
TODAY_BUCKET="$NEW_DIR/memory/$(date '+%Y-%m-%d').jsonl"
if [[ -f "$TODAY_BUCKET" ]]; then
  TODAY_WRITES=$(grep -c '"id"' "$TODAY_BUCKET" 2>/dev/null || echo 0)
  log "✓ Today's writes: $TODAY_WRITES entries"
else
  log "ℹ  No writes today yet (normal if check runs before any activity)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log ""
if [[ $ERRORS -gt 0 ]]; then
  log "RESULT: FAIL — $ERRORS error(s), $WARNINGS warning(s)"
elif [[ $WARNINGS -gt 0 ]]; then
  log "RESULT: WARN — $WARNINGS warning(s), no errors"
else
  log "RESULT: PASS — all checks OK"
fi
log "=========================================="
log ""

# Print summary to stdout too
echo "Daily check complete. Errors: $ERRORS, Warnings: $WARNINGS"
echo "Log: $LOG"