# Monitoring — Week-Long Trial

Dual-mode trial: **2026-04-15 → 2026-04-22**

- OLD: `/home/wahaj/.openclaw/workspace/memory/` (Markdown files)
- NEW: `/home/wahaj/.openclaw/workspace/openclaw-memory/` (JSONL + SQLite FTS5)

---

## Scripts

| Script | What it does | When to run |
|---|---|---|
| `scripts/daily-check.sh` | Health check — writes, JSONL integrity, index, search | Daily (cron 9am) |
| `scripts/compare-memory.sh` | Full comparison — counts, search diff, timing | Weekly (cron Sundays 6pm) |
| `scripts/trial-decision.py` | End-of-trial analysis + recommendation | Day 7+ (manual) |

---

## Cron Setup

Add to your crontab (`crontab -e`):

```crontab
# Daily health check — 9:00 AM every day
0 9 * * * /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/daily-check.sh >> /home/wahaj/.openclaw/workspace/openclaw-memory/memory/daily-check.out 2>&1

# Weekly comparison — Sundays at 6:00 PM
0 18 * * 0 /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/compare-memory.sh >> /home/wahaj/.openclaw/workspace/openclaw-memory/reports/compare.out 2>&1
```

**Quick install:**
```bash
# Add cron entries in one shot:
(crontab -l 2>/dev/null | grep -v "openclaw-memory"; cat <<'CRON'
0 9 * * * /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/daily-check.sh >> /home/wahaj/.openclaw/workspace/openclaw-memory/memory/daily-check.out 2>&1
0 18 * * 0 /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/compare-memory.sh >> /home/wahaj/.openclaw/workspace/openclaw-memory/reports/compare.out 2>&1
CRON
) | crontab -
```

**Remove cron entries:**
```bash
crontab -l | grep -v "openclaw-memory" | crontab -
```

---

## Log Locations

- **Daily check log:** `memory/monitor.log`
- **Daily check stdout:** `memory/daily-check.out`
- **Weekly reports:** `reports/compare-*.out` (stdout redirect)
- **Decision record:** `memory/trial-decision.json` (written by trial-decision.py)

---

## daily-check.sh — What It Checks

1. Memory directory exists
2. Write path functional (writes + deletes a test entry)
3. JSONL integrity — every line in every bucket parses cleanly
4. Index DB exists + `entries == FTS5` row count match
5. Search functional (FTS5 query)
6. Disk usage (< 500MB warning threshold)
7. Today's write count

**Exit codes:** 0 = PASS/WARN, non-zero = FAIL

---

## compare-memory.sh — What It Compares

1. Entry counts (old: file/line count, new: JSONL id count)
2. Disk usage for both systems
3. New system index size + row counts
4. Write performance benchmark
5. Side-by-side search for sample queries (memory, task, project, Buck, workspace)
6. Trial-period write count
7. JSONL integrity check

---

## trial-decision.py — How It Decides

**Score-based decision (thresholds):**

| Score range | Recommendation |
|---|---|
| ≥ 15 | **MIGRATE** — new system is clearly better |
| 0 – 14 | **KEEP_DUAL** — continue gathering data |
| < 0 | **ROLLBACK** — issues detected, do not migrate |

**Scoring factors:**
- JSONL errors → −30 (hard blocker)
- Index DB errors → −20
- Monitor log warnings > 10 → −15
- Index mismatch → −10
- Low/no writes → −5
- Search faster than old → +10–15
- Write latency OK (< 500ms) → neutral; high → −5
- Data integrity + index coverage → +15–25

**Outputs:**
- Prints full report + recommendation to stdout
- Writes `memory/trial-decision.json` with structured decision record

**Usage:**
```bash
# After 7 days
python3 /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/trial-decision.py

# After more days
python3 /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/trial-decision.py --days 10

# Verbose with per-query timings
python3 /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/trial-decision.py --verbose
```

---

## Manual Smoke Test

```bash
# Quick sanity check
bash /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/daily-check.sh

# Manual comparison
bash /home/wahaj/.openclaw/workspace/openclaw-memory/scripts/compare-memory.sh

# See monitor log
tail -50 /home/wahaj/.openclaw/workspace/openclaw-memory/memory/monitor.log
```

---

## Decision Criteria Summary

### MIGRATE when:
- Zero JSONL parse errors
- Index DB functional with entries == FTS5 rows
- Monitor log shows PASS/WARN with few or no warnings
- Search performance at least as good as old system
- ≥ 7 days of data collected

### KEEP_DUAL when:
- Minor warnings in monitor log (< 10)
- Write volume low but system is healthy
- Search performance equivalent or slightly worse

### ROLLBACK when:
- Any JSONL corruption detected
- Index DB unreachable or corrupted
- Daily checks consistently FAIL
- Monitor log has > 10 warnings
- Write/search fundamentally broken

---

## Post-Decision Actions

**If MIGRATE:**
1. Back up old system: `scripts/rollback.py --backup-only`
2. Update AGENTS.md / MEMORY.md to point to new system
3. Keep `rollback.py` for 30 days before archiving old system

**If KEEP_DUAL:**
1. Continue collecting data
2. Re-run trial-decision.py after more days
3. Review which queries/features are weakest

**If ROLLBACK:**
1. Run `scripts/rollback.py`
2. Investigate root cause of failure
3. Fix and restart trial with corrected setup