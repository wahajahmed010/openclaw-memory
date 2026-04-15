# OpenClaw Memory System

Persistent, searchable memory layer for OpenClaw.

## Architecture

- **Storage**: Date-bucketed JSONL files (`memory/YYYY-MM-DD.jsonl`)
- **Index**: SQLite with FTS5 full-text search (`.index/graph.db`)
- **Search**: Hybrid keyword + semantic similarity with lazy embeddings
- **Continuity**: Compaction-safe writes, snapshot + replay recovery

## Install

```bash
pip install -e .
```

## CLI

```bash
openclaw-memory --base-dir ~/.openclaw/workspace write "Remember to call mom" --tags personal
openclaw-memory --base-dir ~/.openclaw/workspace search "mom" --mode hybrid
openclaw-memory --base-dir ~/.openclaw/workspace index
```

## Modules

- `core.py` — JSONL storage, append-only writes
- `index.py` — SQLite index with FTS5
- `search.py` — Hybrid search + lazy embeddings
- `continuity.py` — Compaction survival, atomic writes, export/import
- `cli.py` — Command-line interface