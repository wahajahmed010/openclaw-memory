"""Search layer — hybrid keyword + semantic search with lazy embeddings."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .core import MemoryStore
from .index import MemoryIndex


class MemorySearch:
    """Hybrid search: FTS5 keyword + cosine similarity on cached vectors."""

    def __init__(
        self,
        base_dir: Path | str,
        store: MemoryStore | None = None,
        index: MemoryIndex | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.store = store or MemoryStore(base_dir)
        self.index = index or MemoryIndex(self.base_dir, self.store)

    # ------------------------------------------------------------------
    # Vector helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _embed(text: str) -> list[float]:
        """Compute embedding vector for text.

        Stub implementation: deterministic pseudo-vector (128-dim) so
        results are stable without an external embedding service.
        Replace with your embedder of choice (OpenAI, Ollama, etc.).
        """
        h = hash(text) & 0xFFFFFFFFFFFFFFFF
        vec = []
        c1 = 0x9E3779B97F4A7C15
        c2 = 0x5
        for i in range(128):
            h = (h * c1 + c2) & 0xFFFFFFFFFFFFFFFF
            vec.append((h >> (i % 64)) / float(0xFFFFFFFFFFFFFFFF + 1))
        return vec

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def write(
        self,
        text: str,
        type_: str = "note",
        tags: list[str] | None = None,
        refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Write-through capture: persist then index."""
        entry = self.store.write(
            text=text, type_=type_, tags=tags, refs=refs, vectors=[]
        )
        self.index.index_entry(entry)
        return entry

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        mode: str = "hybrid",
        type_: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search entries.

        Args:
            query:    Search query string.
            mode:     "keyword" | "semantic" | "hybrid" (default).
            type_:    Filter by entry type.
            tag:      Filter by tag.
            limit:    Max results.
        """
        if mode == "semantic":
            raw = self._semantic_search(query, limit * 2)
        elif mode == "keyword":
            raw = self._keyword_search(query, limit * 2)
        else:
            raw = self._hybrid_search(query, limit * 2)

        return self._filter(raw, type_, tag, limit)

    def _keyword_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        return self.index.fts_search(query, limit=limit)

    def _semantic_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        q_vec = self._embed(query)
        scored = []
        for entry in self.store.iter_all_entries():
            e_vec = entry.get("vectors")
            if not e_vec:
                continue
            score = self._cosine(q_vec, e_vec)
            entry_copy = dict(entry)
            entry_copy["_score"] = round(score, 4)
            scored.append(entry_copy)
        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored[:limit]

    def _hybrid_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Keyword hits first, then semantic-only entries above threshold."""
        kw_map = {e["id"]: e for e in self._keyword_search(query, limit)}
        q_vec = self._embed(query)

        for entry in self.store.iter_all_entries():
            if entry["id"] in kw_map:
                continue
            e_vec = entry.get("vectors")
            if not e_vec:
                continue
            score = self._cosine(q_vec, e_vec)
            if score >= 0.7:
                ec = dict(entry)
                ec["_score"] = round(score, 4)
                kw_map[ec["id"]] = ec

        results = list(kw_map.values())
        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return results[:limit]

    @staticmethod
    def _filter(
        entries: list[dict[str, Any]],
        type_: str | None,
        tag: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if type_:
            entries = [e for e in entries if e.get("type") == type_]
        if tag:
            entries = [e for e in entries if tag in e.get("tags", [])]
        return entries[:limit]

    # ------------------------------------------------------------------
    # Auto-linking
    # ------------------------------------------------------------------
    def auto_link(self, entry_id: str, threshold: float = 0.8) -> list[str]:
        """Find and link semantically similar entries above threshold."""
        target = None
        for e in self.store.iter_all_entries():
            if e["id"] == entry_id:
                target = e
                break
        if not target:
            return []

        t_vec = target.get("vectors")
        if not t_vec:
            return []

        linked = []
        for other in self.store.iter_all_entries():
            if other["id"] == entry_id:
                continue
            o_vec = other.get("vectors")
            if not o_vec:
                continue
            if self._cosine(t_vec, o_vec) >= threshold:
                self.index.add_link(entry_id, other["id"])
                linked.append(other["id"])
        return linked

    # ------------------------------------------------------------------
    # Lazy vector backfill
    # ------------------------------------------------------------------
    def backfill_vectors(self, batch_size: int = 100) -> int:
        """Compute & cache embeddings for entries that lack them. Returns count."""
        count = 0
        for entry in self.store.iter_all_entries():
            if entry.get("vectors"):
                continue
            entry["vectors"] = self._embed(entry["text"])
            count += 1
            if count % batch_size == 0:
                self.index.index_entry(entry)
        if count > 0:
            last_entry = None
            for entry in self.store.iter_all_entries():
                last_entry = entry
            if last_entry:
                self.index.index_entry(last_entry)
        return count