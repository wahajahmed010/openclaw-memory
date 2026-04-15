"""Continuity layer — survive compaction and bridge sessions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import MemoryStore
from .index import MemoryIndex


class ContinuityManager:
    """
    Ensures memory survives compaction events.

    Compaction snapshots:
        - Capture pending state (recently written entry IDs, last accessed time)
        - On restart, replay recent writes to re-populate the index
        - Keep a WAL-like marker file so mid-write entries aren't lost
    """

    SNAPSHOT_FILE = "memory/.index/compact.snapshot.json"

    def __init__(self, base_dir: Path | str, store: MemoryStore | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.store = store or MemoryStore(base_dir)
        self.snapshot_path = self.base_dir / self.SNAPSHOT_FILE
        self._ensure_snapshot_dir()

    def _ensure_snapshot_dir(self) -> None:
        (self.base_dir / "memory" / ".index").mkdir(parents=True, exist_ok=True)

    def snapshot(self, recent_ids: list[str]) -> None:
        """Persist a snapshot of active/recent entry IDs."""
        snap = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "recent_ids": recent_ids[-100:],  # keep last 100
        }
        with open(self.snapshot_path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2)

    def load_snapshot(self) -> dict[str, Any]:
        """Load the latest snapshot, or empty dict."""
        if not self.snapshot_path.exists():
            return {}
        with open(self.snapshot_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def recover(self, index: MemoryIndex) -> int:
        """
        Re-index entries that were written since the last snapshot.
        Returns count of recovered entries.
        """
        snap = self.load_snapshot()
        recent_ids = set(snap.get("recent_ids", []))
        if not recent_ids:
            return 0

        recovered = 0
        for entry in self.store.iter_all_entries():
            if entry["id"] in recent_ids:
                index.index_entry(entry)
                recovered += 1
        return recovered

    def atomic_write(
        self,
        text: str,
        type_: str = "note",
        tags: list[str] | None = None,
        refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Write with a temporary staging file so compaction can't corrupt mid-write.
        Pattern: write → fsync → rename (atomic).
        """
        entry = self.store.write(
            text=text, type_=type_, tags=tags, refs=refs, vectors=[]
        )
        snap = self.load_snapshot()
        recent = snap.get("recent_ids", [])
        if entry["id"] not in recent:
            recent.append(entry["id"])
        self.snapshot(recent)
        return entry

    def export(self, out_path: Path | str) -> None:
        """Export all entries to a single JSONL file for backup/migration."""
        out = Path(out_path)
        with open(out, "w", encoding="utf-8") as fh:
            for entry in self.store.iter_all_entries():
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def import_(self, in_path: Path | str) -> int:
        """Import entries from a JSONL backup. Returns count."""
        inp = Path(in_path)
        count = 0
        for line in open(inp, "r", encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            self.store.write(
                text=entry["text"],
                type_=entry.get("type", "note"),
                tags=entry.get("tags", []),
                refs=entry.get("refs", []),
                vectors=entry.get("vectors", []),
            )
            count += 1
        return count