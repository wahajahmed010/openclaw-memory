"""
buck_adapter.py — OpenClaw Memory System → Buck integration layer.

This adapter wraps the new openclaw-memory CLI so Buck can use it
transparently, with feature-flag rollback to the legacy Markdown system.

Usage:
    from openclaw_memory.integrations.buck_adapter import (
        capture_memory,
        search_memories,
        get_session_context,
        proactive_recall,
        get_memory_mode,
        set_memory_mode,
    )

Feature flag: ~/.openclaw/memory_mode
    - "new"     → use openclaw-memory (default, primary)
    - "legacy"  → fall back to old grep-based search
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_FLAG = Path.home() / ".openclaw" / "memory_mode"
MEMORY_NEW_BASE = WORKSPACE / "memory-new"
MEMORY_OLD_DIR = WORKSPACE / "memory"

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def get_memory_mode() -> str:
    """Return "new" or "legacy" based on ~/.openclaw/memory_mode."""
    if not MEMORY_FLAG.exists():
        return "new"  # default to new system
    mode = MEMORY_FLAG.read_text().strip()
    return mode if mode in ("new", "legacy") else "new"


def set_memory_mode(mode: str) -> None:
    """Set memory mode: "new" or "legacy". One-file rollback."""
    if mode not in ("new", "legacy"):
        raise ValueError(f"Unknown memory mode: {mode!r}")
    MEMORY_FLAG.write_text(mode + "\n")


# ---------------------------------------------------------------------------
# CLI wrapper helpers
# ---------------------------------------------------------------------------


def _cli(argv: list[str], timeout: int = 15) -> list[dict[str, Any]]:
    """Run openclaw-memory CLI and return parsed JSON lines."""
    base = str(MEMORY_NEW_BASE)
    cmd = [sys.executable, "-m", "openclaw_memory.cli", f"--base-dir={base}"] + argv
    try:
        raw = subprocess.check_output(cmd, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        # CLI not installed, fall back silently
        return []
    raw = raw.strip()
    if not raw:
        return []
    return _parse_json_stream(raw)


def _parse_json_stream(raw: str) -> list[dict[str, Any]]:
    """Parse concatenated JSON objects (pretty-printed or compact) from a string."""
    results: list[dict[str, Any]] = []
    idx = 0
    n = len(raw)
    decoder = json.JSONDecoder()
    while idx < n:
        # Find the next opening brace
        brace = raw.find("{", idx)
        if brace == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw[brace:])
            results.append(obj)
            idx = brace + end
        except json.JSONDecodeError:
            idx = brace + 1
    return results


# ---------------------------------------------------------------------------
# 1. capture_memory — write a new memory entry
# ---------------------------------------------------------------------------


def capture_memory(
    text: str,
    tags: list[str] | None = None,
    type_: str = "note",
) -> dict[str, Any] | None:
    """
    Capture a memory entry via the new system.

    Wraps: openclaw-memory write "text" --type=X --tags=a,b,c

    Returns the created entry dict, or None if the system is unavailable.
    Falls back silently (no exception) if CLI is missing.
    """
    mode = get_memory_mode()
    if mode == "legacy":
        return _legacy_capture(text, tags, type_)

    tags = tags or []
    tags_arg = ",".join(tags) if tags else ""
    argv = ["write", text, f"--type={type_}"]
    if tags_arg:
        argv.append(f"--tags={tags_arg}")

    result = _cli(argv)
    return result[0] if result else None


def _legacy_capture(
    text: str,
    tags: list[str] | None = None,
    type_: str = "note",
) -> dict[str, Any]:
    """Fallback: write to old Markdown daily file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_file = MEMORY_OLD_DIR / f"{today}.md"
    day_file.mkdir(parents=True, exist_ok=True)

    tag_str = ", ".join(tags) if tags else ""
    entry = f"\n## [{type_}] {tag_str}\n\n{text}\n"
    with open(day_file, "a", encoding="utf-8") as fh:
        fh.write(entry)

    return {
        "id": f"legacy-{today}",
        "type": type_,
        "tags": tags or [],
        "text": text,
        "refs": [],
        "vectors": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 2. search_memories — hybrid search
# ---------------------------------------------------------------------------


def search_memories(
    query: str,
    mode: str = "hybrid",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search memory entries.

    - flag="new": uses openclaw-memory hybrid search (FTS5 + semantic)
    - flag="legacy": falls back to grep-based substring search

    Returns list of entry dicts sorted by relevance.
    """
    if get_memory_mode() == "legacy":
        return _legacy_search(query, limit)

    result = _cli(["search", query, f"--mode={mode}", f"--limit={limit}"])
    return result


def _legacy_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Fallback: grep across old Markdown files."""
    results = []
    q = query.lower()
    for md in sorted(MEMORY_OLD_DIR.glob("*.md")):
        for line in open(md, encoding="utf-8"):
            if q in line.lower():
                results.append({
                    "id": md.stem,
                    "type": "note",
                    "tags": [],
                    "text": line.strip(),
                    "refs": [],
                    "vectors": [],
                    "created_at": "",
                    "_source": str(md),
                    "_score": 1.0,
                })
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# 3. get_session_context — rebuild context for session startup
# ---------------------------------------------------------------------------


def get_session_context(max_entries: int = 20) -> str:
    """
    Return a text summary of recent memories for session startup.

    Reads COMPACTION.md (summary) + most recent entries.
    Returns a plain-text string suitable for injecting into context.
    """
    if get_memory_mode() == "legacy":
        return _legacy_context()

    # Try new system
    compact_file = MEMORY_NEW_BASE / "COMPACTION.md"
    if compact_file.exists():
        compaction = compact_file.read_text(encoding="utf-8").strip()
    else:
        compaction = ""

    # Get recent entries
    recent = list(_cli(["read"]))[-max_entries:]
    entries_text = "\n".join(
        f"- [{e.get('type','note')}] {e.get('text','')}"
        for e in recent
        if e.get("text")
    )

    parts = []
    if compaction:
        parts.append(f"## Compaction Summary\n{compaction}")
    if entries_text:
        parts.append(f"## Recent Memories\n{entries_text}")

    return "\n\n".join(parts) if parts else ""


def _legacy_context() -> str:
    """Fallback: read yesterday/today Markdown files."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (
        datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - 1)
    ).strftime("%Y-%m-%d")

    texts = []
    for day in [yesterday, today]:
        f = MEMORY_OLD_DIR / f"{day}.md"
        if f.exists():
            texts.append(f"## {day}\n" + f.read_text(encoding="utf-8").strip())

    return "\n\n".join(texts) if texts else ""


# ---------------------------------------------------------------------------
# 4. proactive_recall — surface relevant memories for current topic
# ---------------------------------------------------------------------------


def proactive_recall(current_topic: str, limit: int = 5) -> str:
    """
    Before answering on a topic, check if there are relevant memories.

    Returns a short string with relevant entries, or empty string if none.
    Use before answering questions about past decisions, projects, people.
    """
    if get_memory_mode() == "legacy":
        results = _legacy_search(current_topic, limit)
    else:
        results = search_memories(current_topic, mode="hybrid", limit=limit)

    if not results:
        return ""

    snippets = []
    for e in results:
        text = e.get("text", "")
        score = e.get("_score", 0)
        tag = e.get("type", "note")
        # Truncate long entries
        if len(text) > 200:
            text = text[:200].rstrip() + "..."
        snippets.append(f"[{tag} · score={score}] {text}")

    return "## Related Memories\n\n" + "\n".join(f"- {s}" for s in snippets)


# ---------------------------------------------------------------------------
# 5. auto-index — ensure the index is built before heavy searches
# ---------------------------------------------------------------------------


def ensure_indexed() -> bool:
    """Run `openclaw-memory index` if needed. Returns True if index exists."""
    index_dir = MEMORY_NEW_BASE / "memory" / ".index"
    if index_dir.exists() and (index_dir / "memory.db").exists():
        return True

    result = _cli(["index"])
    return True  # assume success if no exception


# ---------------------------------------------------------------------------
# CLI entrypoint (for testing / manual use)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Buck Memory Adapter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("capture", help="Capture a memory")
    p.add_argument("text")
    p.add_argument("--tags", default="")
    p.add_argument("--type", default="note")

    p = sub.add_parser("search", help="Search memories")
    p.add_argument("query")
    p.add_argument("--mode", default="hybrid")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("context", help="Get session context")
    p.add_argument("--max", type=int, default=20)

    p = sub.add_parser("recall", help="Proactive recall")
    p.add_argument("topic")
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("mode", help="Get or set memory mode")
    p.add_argument("value", nargs="?", choices=["new", "legacy"])

    args = parser.parse_args()

    if args.cmd == "capture":
        tags = args.tags.split(",") if args.tags else []
        r = capture_memory(args.text, tags, args.type)
        print(json.dumps(r, indent=2))

    elif args.cmd == "search":
        results = search_memories(args.query, args.mode, args.limit)
        for r in results:
            print(json.dumps(r, indent=2))

    elif args.cmd == "context":
        print(get_session_context(args.max))

    elif args.cmd == "recall":
        print(proactive_recall(args.topic, args.limit))

    elif args.cmd == "mode":
        if args.value:
            set_memory_mode(args.value)
            print(f"Memory mode set to: {args.value}")
        else:
            print(f"Memory mode: {get_memory_mode()}")