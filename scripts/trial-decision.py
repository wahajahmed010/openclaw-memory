#!/usr/bin/env python3
"""
trial-decision.py — End-of-trial analysis & recommendation

Run after 7+ days of dual-mode operation.
Analyzes: write volume, error rate, performance, index integrity.
Outputs: MIGRATE | KEEP_DUAL | ROLLBACK

Usage:
    python3 scripts/trial-decision.py
    python3 scripts/trial-decision.py --days 7
    python3 scripts/trial-decision.py --verbose
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

NEW_DIR = Path("/home/wahaj/.openclaw/workspace/openclaw-memory")
OLD_DIR = Path("/home/wahaj/.openclaw/workspace/memory")
TRIAL_START = datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc)


def load_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trial decision helper")
    parser.add_argument("--days", type=int, default=7, help="Trial length in days")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def count_new_writes() -> int:
    """Entries written to new system since trial start."""
    store_dir = NEW_DIR / "memory"
    count = 0
    for f in sorted(store_dir.glob("*.jsonl")):
        if not f.name.startswith("2026"):
            continue
        date_str = f.stem  # "2026-04-15"
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if file_date >= TRIAL_START:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            json.loads(line)
                            count += 1
                        except json.JSONDecodeError:
                            pass
    return count


def count_old_entries() -> int:
    """Markdown files in old system (rough proxy for writes)."""
    return len(list(OLD_DIR.glob("*.md")))


def check_jsonl_integrity() -> tuple[int, int]:
    """Returns (error_count, total_entries)."""
    store_dir = NEW_DIR / "memory"
    errors = 0
    total = 0
    for f in sorted(store_dir.glob("*.jsonl")):
        if not f.name.startswith("2026"):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    total += 1
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        errors += 1
        except Exception:
            errors += 1
    return errors, total


def check_index_integrity() -> dict:
    """Returns dict with indexed_count, fts_count, rebuild_needed."""
    index_db = NEW_DIR / "memory" / ".index" / "graph.db"
    if not index_db.exists():
        return {"indexed_count": 0, "fts_count": 0, "rebuild_needed": True, "error": "no DB"}

    try:
        conn = sqlite3.connect(str(index_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        indexed = cur.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        fts = cur.execute("SELECT COUNT(*) FROM entries_fts").fetchone()[0]
        conn.close()
        return {
            "indexed_count": indexed,
            "fts_count": fts,
            "rebuild_needed": indexed != fts,
        }
    except Exception as e:
        return {"indexed_count": 0, "fts_count": 0, "rebuild_needed": False, "error": str(e)}


def benchmark_search(query: str, mode: str = "keyword", limit: int = 20) -> float:
    """Returns search time in milliseconds."""
    sys.path.insert(0, str(NEW_DIR / "src"))
    from openclaw_memory.search import MemorySearch

    sr = MemorySearch(str(NEW_DIR))
    start = time.perf_counter()
    sr.search(query=query, mode=mode, limit=limit)
    elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 2)


def benchmark_write(text: str = "TRIAL_BENCHMARK_ENTRY") -> float:
    """Returns write time in milliseconds."""
    sys.path.insert(0, str(NEW_DIR / "src"))
    from openclaw_memory.core import MemoryStore

    store = MemoryStore(str(NEW_DIR))
    start = time.perf_counter()
    store.write(text=text + " " + str(time.time()), type_="note", tags=["trial"])
    elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 2)


def benchmark_old_search(query: str) -> float:
    """Returns grep-based search time in milliseconds for old system."""
    start = time.perf_counter()
    list(OLD_DIR.glob("*.md"))  # no-op glob to establish baseline
    import subprocess

    try:
        subprocess.run(
            ["grep", "-ril", query, str(OLD_DIR)],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        pass
    elapsed = (time.perf_counter() - start) * 1000
    return round(elapsed, 2)


def monitor_log_warnings() -> int:
    """Count WARN/FAIL lines in monitor log."""
    log_path = NEW_DIR / "memory" / "monitor.log"
    if not log_path.exists():
        return 0
    warnings = 0
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if "RESULT: FAIL" in line or "⚠" in line or "✗" in line:
                warnings += 1
    return warnings


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

def decide(
    new_writes: int,
    old_entries: int,
    jsonl_errors: int,
    total_new_entries: int,
    index_info: dict,
    new_search_ms: float,
    old_search_ms: float,
    write_ms: float,
    monitor_warnings: int,
    days: int,
    verbose: bool,
) -> tuple[str, list[str]]:
    """
    Returns (recommendation: str, reasons: list[str]).
    """
    reasons = []
    score = 0

    # --- Error checks (hard blockers) ---
    if jsonl_errors > 0:
        reasons.append(f"✗ {jsonl_errors} JSONL parse error(s) — data corruption")
        score -= 30

    if index_info.get("rebuild_needed"):
        reasons.append("⚠  Index mismatch (entries ≠ FTS5 rows) — rebuild needed")
        score -= 10

    if index_info.get("error"):
        reasons.append(f"✗ Index DB error: {index_info['error']}")
        score -= 20

    if monitor_warnings > 10:
        reasons.append(f"⚠  {monitor_warnings} warnings in monitor.log")
        score -= 15

    # --- Write volume ---
    if new_writes == 0:
        reasons.append("⚠  Zero writes to new system — trial may not have run")
        score -= 5
    elif new_writes < 10:
        reasons.append(f"⚠  Low write volume ({new_writes} entries) — inconclusive trial")
        score -= 5
    else:
        reasons.append(f"✓ Write volume OK: {new_writes} entries")
        score += 10

    # --- Performance ---
    if new_search_ms < old_search_ms * 0.5:
        reasons.append(f"✓ Search speed: new {new_search_ms}ms vs old {old_search_ms}ms (2x+ faster)")
        score += 15
    elif new_search_ms < old_search_ms:
        reasons.append(f"✓ Search speed: new {new_search_ms}ms vs old {old_search_ms}ms (faster)")
        score += 10
    else:
        reasons.append(f"⚠  Search slower: new {new_search_ms}ms vs old {old_search_ms}ms")
        score -= 5

    if write_ms > 500:
        reasons.append(f"⚠  Write latency high: {write_ms}ms")
        score -= 5
    else:
        reasons.append(f"✓ Write latency OK: {write_ms}ms")

    # --- Data completeness ---
    if total_new_entries > 0 and jsonl_errors == 0:
        reasons.append(f"✓ Data integrity: {total_new_entries} entries, 0 parse errors")
        score += 10

    # --- Index coverage ---
    if total_new_entries > 0 and index_info.get("indexed_count", 0) == total_new_entries:
        reasons.append(f"✓ Index coverage complete: {index_info['indexed_count']}/{total_new_entries}")
        score += 5
    elif total_new_entries > 0:
        cov = index_info.get("indexed_count", 0)
        reasons.append(f"⚠  Index coverage incomplete: {cov}/{total_new_entries}")
        score -= 5

    # --- Trial length adjustment ---
    if days < 7:
        reasons.append(f"ℹ  Trial only {days} days — recommend waiting for 7+")
        score = min(score, -1) if score > 0 else score  # force inconclusive

    # --- Decision ---
    if score >= 15:
        recommendation = "MIGRATE"
    elif score >= 0:
        recommendation = "KEEP_DUAL"
    else:
        recommendation = "ROLLBACK"

    return recommendation, reasons


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = load_args()
    days = args.days

    print("=" * 60)
    print("  TRIAL DECISION — Memory System Evaluation")
    print(f"  Trial: {TRIAL_START.date()} → {datetime.now(timezone.utc).date()} ({days} days)")
    print("=" * 60)

    print("\n[1/6] Collecting data...")

    new_writes = count_new_writes()
    old_entries = count_old_entries()

    print("[2/6] Checking JSONL integrity...")
    jsonl_errors, total_new_entries = check_jsonl_integrity()

    print("[3/6] Checking index integrity...")
    index_info = check_index_integrity()

    print("[4/6] Benchmarking search performance...")
    queries = ["memory", "task", "workspace", "Buck", "project"]
    new_times = [benchmark_search(q) for q in queries]
    old_times = [benchmark_old_search(q) for q in queries]
    new_search_ms = sum(new_times) / len(new_times)
    old_search_ms = sum(old_times) / len(old_times)

    print("[5/6] Benchmarking write latency...")
    write_ms = benchmark_write()

    print("[6/6] Checking monitor log...")
    monitor_warnings = monitor_log_warnings()

    # --- Decision ---
    recommendation, reasons = decide(
        new_writes=new_writes,
        old_entries=old_entries,
        jsonl_errors=jsonl_errors,
        total_new_entries=total_new_entries,
        index_info=index_info,
        new_search_ms=new_search_ms,
        old_search_ms=old_search_ms,
        write_ms=write_ms,
        monitor_warnings=monitor_warnings,
        days=days,
        verbose=args.verbose,
    )

    # --- Report ---
    print("\n" + "=" * 60)
    print("  FINDINGS")
    print("=" * 60)
    print(f"  New system writes      : {new_writes}")
    print(f"  Old system entries     : {old_entries}")
    print(f"  JSONL errors           : {jsonl_errors} / {total_new_entries} total")
    print(f"  Index DB entries       : {index_info.get('indexed_count', 'N/A')}")
    print(f"  FTS5 rows              : {index_info.get('fts_count', 'N/A')}")
    print(f"  Monitor warnings       : {monitor_warnings}")
    print(f"  Avg search (new)       : {new_search_ms}ms")
    print(f"  Avg search (old)       : {old_search_ms}ms")
    print(f"  Write latency          : {write_ms}ms")

    print("\n" + "=" * 60)
    print("  REASONS")
    print("=" * 60)
    for r in reasons:
        print(f"  {r}")

    print("\n" + "=" * 60)
    print(f"  ★ RECOMMENDATION: {recommendation}")
    print("=" * 60)

    if recommendation == "MIGRATE":
        print("\n  → Safe to migrate. Old system can be archived after backup.")
        print("  → Run: openclaw-memory/scripts/rollback.py to retain rollback capability")
    elif recommendation == "KEEP_DUAL":
        print("\n  → Continue dual-mode operation. Gather more data.")
        print("  → Re-run this script after additional days")
    else:
        print("\n  → Issues detected. Do NOT migrate yet.")
        print("  → Review reasons above and fix before continuing trial")
        print("  → Run: openclaw-memory/scripts/rollback.py if rolling back to old system")

    if args.verbose:
        print("\n--- VERBOSE: Per-query timings ---")
        for q, nt, ot in zip(queries, new_times, old_times):
            print(f"  '{q}': new={nt}ms  old={ot}ms")

    # Write decision record
    decision_record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "trial_days": days,
        "recommendation": recommendation,
        "score_reasons": reasons,
        "new_writes": new_writes,
        "jsonl_errors": jsonl_errors,
        "indexed": index_info.get("indexed_count"),
        "fts": index_info.get("fts_count"),
        "new_search_ms": new_search_ms,
        "old_search_ms": old_search_ms,
        "write_ms": write_ms,
        "monitor_warnings": monitor_warnings,
    }
    record_path = NEW_DIR / "memory" / "trial-decision.json"
    with open(record_path, "w", encoding="utf-8") as fh:
        json.dump(decision_record, fh, indent=2)
    print(f"\n  Decision record written to: {record_path}")


if __name__ == "__main__":
    main()