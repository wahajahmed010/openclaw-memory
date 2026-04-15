# Architecture — OpenClaw Memory System

Technical specification derived from the council's three-round consensus.

---

## Design Principles

1. **Simple by default, powerful on demand** — Works out of the box; advanced users can swap components
2. **Raw and curated are separate** — Daily logs capture everything; long-term memory is explicitly curated
3. **Human-readable storage** — Files are ground truth; open a `.md` file and read it
4. **API-first, CLI-second** — Python API is primary; CLI is convenience
5. **No embedding vendor lock-in** — Embedding model is injectable

---

## Storage Layer

### File-Based Storage (Default)

Two files form the persistence layer:

```
memory/
  YYYY-MM-DD.md    # Daily raw logs (append-only, auto-loaded for today + yesterday)
  YYYY-MM-DD.md
  ...

MEMORY.md          # Long-term curated memory (explicitly written/updated)
```

**Daily Log Format:**
```markdown
# 2026-04-15

## 21:30
- User asked about Frankfurt weather
- Reminded them about tomorrow's meeting at 10am

## 21:45
- Looked up flights to Berlin
- Found cheaper option on Lufthansa
```

**Long-Term Memory Format:**
```markdown
# Long-Term Memory

## Preferences
- User prefers dark mode in all UIs
- Timezone: Europe/Berlin (GMT+2)

## Context
- Works at [Company], leads a team of sub-agents
- Main project: OpenClaw configuration
- Based in Frankfurt am Main, Germany

## Key Decisions
- 2026-04-10: Chose Ollama over remote API for local model inference
- 2026-04-12: Memory system architecture settled via council debate
```

### Database Storage (Optional Plugin)

A pluggable `StorageBackend` allows SQLite or PostgreSQL backing:

```python
class StorageBackend(Protocol):
    def add(self, entry: MemoryEntry) -> None: ...
    def get(self, id: str) -> Optional[MemoryEntry]: ...
    def list(self, limit: int = 100) -> List[MemoryEntry]: ...
    def delete(self, id: str) -> None: ...
    def update(self, entry: MemoryEntry) -> None: ...
```

---

## Memory Data Model

```python
@dataclass
class MemoryEntry:
    id: str                    # UUID
    content: str               # The memory text
    timestamp: datetime        # When it was recorded
    importance: float          # 0.0–1.0 user/AI annotated
    tags: List[str]            # Manual categorizations
    entry_type: str            # "daily" | "longterm" | "transient"
```

---

## Index Layer

### Hybrid Search Architecture

The index layer uses two complementary approaches, merged via **reciprocal rank fusion**:

```
Query String
    │
    ├──► BM25 Index ──────► BM25 Scores
    │
    └──► Embedding Model ──► Vector Index (FAISS/etc.) ──► Vector Scores
                                    │
                         Reciprocal Rank Fusion
                                    │
                              Final Results
```

### BM25 Index

- Fast keyword/exact-match search
- No embedding cost
- Built on memory content + tags

### Vector Index

- Semantic similarity search
- Default: FAISS `IndexFlatIP` (inner product, cosine-like after normalization)
- Embedding model: injectable (default: `sentence-transformers/all-MiniLM-L6-v2`)
- Supports: Chroma, QDrant as swap-in alternatives via plugin interface

### Reciprocal Rank Fusion

```python
def reciprocal_rank_fusion(results_list: List[List[ScoredResult]], k: int = 60) -> List[ScoredResult]:
    """
    Merge ranked results from multiple retrieval methods.
    k=60 balances recall vs precision per academic literature.
    """
    scores = defaultdict(float)
    for results in results_list:
        for rank, result in enumerate(results):
            scores[result.id] += 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

## Module Structure

```
openclaw_memory/
├── __init__.py      # Public API exports
├── core.py          # MemoryStore, MemoryEntry, file-backed storage
├── index.py         # HybridSearchIndex, BM25, vector index wrapper
├── search.py        # Query processing, rank fusion, result formatting
└── cli.py           # Command-line interface
```

### `core.py`

```python
class MemoryStore:
    def __init__(self, storage: Optional[StorageBackend] = None): ...
    def add(self, content: str, tags: List[str] = [], importance: float = 0.5) -> MemoryEntry: ...
    def get(self, id: str) -> Optional[MemoryEntry]: ...
    def list(self, limit: int = 100, entry_type: Optional[str] = None) -> List[MemoryEntry]: ...
    def delete(self, id: str) -> None: ...
    def update(self, entry: MemoryEntry) -> None: ...
    def search(self, query: str, k: int = 10) -> List[SearchResult]: ...
```

### `index.py`

```python
class HybridSearchIndex:
    def __init__(
        self,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        vector_backend: str = "faiss",  # or "chroma", "qdrant"
    ): ...
    def add_entries(self, entries: List[MemoryEntry]) -> None: ...
    def search(self, query: str, k: int = 10) -> List[str]: ...  # returns entry IDs
    def rebuild(self) -> None: ...
```

### `search.py`

```python
class SearchResult:
    id: str
    content: str
    score: float
    rank: int
    entry_type: str

def search(query: str, k: int = 10) -> List[SearchResult]: ...
def format_results(results: List[SearchResult], style: str = "plain") -> str: ...
```

### `cli.py`

```bash
openclaw-memory add "Remember this"
openclaw-memory search "query"
openclaw-memory list --limit 20 --type daily
openclaw-memory delete <id>
openclaw-memory stats
```

---

## CLI

```
Usage: openclaw-memory [command] [options]

Commands:
  add <text>          Add a new memory
  search <query>      Search memories (hybrid BM25 + semantic)
  list                List recent memories
  delete <id>         Delete a memory by ID
  stats               Show memory statistics
  rebuild             Rebuild search index

Options:
  --type daily|longterm   Filter by entry type
  --limit N               Limit results (default: 10)
  --format plain|json     Output format (default: plain)
```

---

## Configuration

Default paths (can be overridden via environment or init params):

| Variable | Default | Description |
|---|---|---|
| `OPENCLAW_MEMORY_DIR` | `~/.openclaw/memory` | Base memory directory |
| `OPENCLAW_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `OPENCLAW_VECTOR_BACKEND` | `faiss` | Vector index backend |
| `OPENCLAW_STORAGE` | `filesystem` | `filesystem` or `sqlite` |

---

## Extension Points

### Custom Embedding Model

```python
from openclaw_memory import MemoryStore

store = MemoryStore()
store.configure_index(embedding_model="custom/my-model")
```

### Custom Vector Backend

```python
store.configure_index(vector_backend="qdrant", qdrant_url="http://localhost:6333")
```

### Custom Storage Backend

```python
from openclaw_memory.storage import SQLiteBackend

store = MemoryStore(storage=SQLiteBackend("~/memory.db"))
```

---

## Security Considerations

- Memory files are stored locally by default — no data leaves the machine unless explicitly configured
- No credentials in code or config — use environment variables for secrets
- Optional HTTP Basic Auth for dashboard endpoints
- Plugin isolation: each plugin runs in-process with no explicit sandboxing (user-installed plugins have full Python access)

---

## Performance Notes

- Daily logs are append-only — writes are O(1)
- Vector index rebuilds on demand, not on every write
- BM25 is lightweight and rebuilt in-memory on startup
- For >100K entries, consider QDrant or a dedicated vector database over FAISS

---

*Derived from the council consensus documented in COUNCIL.md.*