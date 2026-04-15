"""Storage layer — date-bucketed JSONL persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MemoryStore:
    """Append-only JSONL store with date bucketing."""

    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir)
        self.memory_dir = self.base_dir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _bucket_path(self, date: str | None = None) -> Path:
        if date is None:
            date = self._today()
        return self.memory_dir / f"{date}.jsonl"

    def write(
        self,
        text: str,
        type_: str = "note",
        tags: list[str] | None = None,
        refs: list[str] | None = None,
        vectors: list[float] | None = None,
        date: str | None = None,
    ) -> dict[str, Any]:
        """Append a new entry to the current day's bucket."""
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "type": type_,
            "tags": tags or [],
            "text": text,
            "refs": refs or [],
            "vectors": vectors or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        path = self._bucket_path(date)
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)

        return entry

    def read_bucket(self, date: str) -> list[dict[str, Any]]:
        """Read all entries from a specific date bucket."""
        path = self._bucket_path(date)
        if not path.exists():
            return []
        entries = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def iter_all_entries(self):
        """Yield all entries across all date buckets, oldest first."""
        for path in sorted(self.memory_dir.glob("*.jsonl")):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)

    def search_raw(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Simple substring search across all buckets (used by indexer)."""
        results = []
        q = query.lower()
        for entry in self.iter_all_entries():
            if q in entry.get("text", "").lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results