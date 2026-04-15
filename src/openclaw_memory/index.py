"""Index layer — SQLite FTS5 index, rebuildable from source JSON files."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .core import MemoryStore


class MemoryIndex:
    """SQLite-backed index with FTS5 full-text search."""

    def __init__(self, base_dir: Path | str, store: MemoryStore | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.index_dir = self.base_dir / "memory" / ".index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_dir / "graph.db"
        self.store = store or MemoryStore(base_dir)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    text TEXT NOT NULL,
                    refs TEXT NOT NULL,
                    vectors TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    src TEXT NOT NULL,
                    dst TEXT NOT NULL,
                    UNIQUE(src, dst)
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                    id UNINDEXED,
                    type UNINDEXED,
                    text,
                    tags
                );
            """)

    def index_entry(self, entry: dict[str, Any]) -> None:
        """Insert or replace an entry in the index."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO entries (id, type, tags, text, refs, vectors, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["id"],
                    entry["type"],
                    json.dumps(entry.get("tags", [])),
                    entry["text"],
                    json.dumps(entry.get("refs", [])),
                    json.dumps(entry.get("vectors", [])),
                    entry["created_at"],
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO entries_fts (id, type, text, tags) VALUES (?, ?, ?, ?)",
                (entry["id"], entry["type"], entry["text"], json.dumps(entry.get("tags", []))),
            )
            for tag in entry.get("tags", []):
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            conn.commit()

    def add_link(self, src_id: str, dst_id: str) -> None:
        """Create a link between two entries."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO links (src, dst) VALUES (?, ?)", (src_id, dst_id)
            )
            conn.commit()

    def fts_search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Full-text search via FTS5."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT e.* FROM entries_fts AS f
                JOIN entries AS e ON e.id = f.id
                WHERE entries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            return [self._row_to_entry(dict(row)) for row in rows]

    def get_links(self, entry_id: str) -> list[str]:
        """Return all entry IDs linked from or to this entry."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT dst FROM links WHERE src = ?
                UNION
                SELECT src FROM links WHERE dst = ?
                """,
                (entry_id, entry_id),
            )
            return [r["dst"] for r in rows]

    def get_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Fetch all entries with a given tag."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE tags LIKE ? ORDER BY created_at DESC",
                (f'%"{tag}"%',),
            )
            return [self._row_to_entry(dict(r)) for r in rows]

    def get_by_type(self, type_: str) -> list[dict[str, Any]]:
        """Fetch all entries of a given type."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM entries WHERE type = ? ORDER BY created_at DESC",
                (type_,),
            )
            return [self._row_to_entry(dict(r)) for r in rows]

    def _row_to_entry(self, row: dict) -> dict[str, Any]:
        return {
            "id": row["id"],
            "type": row["type"],
            "tags": json.loads(row["tags"]),
            "text": row["text"],
            "refs": json.loads(row["refs"]),
            "vectors": json.loads(row["vectors"]),
            "created_at": row["created_at"],
        }

    def rebuild(self) -> int:
        """Drop and rebuild the entire index from source JSONL files. Returns count."""
        with self._conn() as conn:
            conn.executescript(
                "DELETE FROM links; DELETE FROM tags; DELETE FROM entries; DELETE FROM entries_fts;"
            )
        count = 0
        for entry in self.store.iter_all_entries():
            self.index_entry(entry)
            count += 1
        return count