# Council Record — OpenClaw Memory System

A three-round architecture debate between three AI systems: **Mnemosyne** (kimi-k2.5), **Sibyl** (minimax-m2.7), and **Fabricator** (gemma4:31b-cloud).

---

## Round 1: Independent Proposals

### Mnemosyne's Proposal

**Model:** kimi-k2.5

I propose a **flat key-value store with metadata layers**. Each memory entry is a struct:

```python
@dataclass
class MemoryEntry:
    id: str
    content: str
    timestamp: datetime
    importance: float       # 0.0–1.0, user or AI annotated
    tags: List[str]
    embedding: Optional[np.ndarray]
```

**Index Strategy:** A two-tier system:
1. **Daily logs** (`memory/YYYY-MM-DD.md`) — raw, append-only, timestamped. Human-readable.
2. **Long-term store** (`MEMORY.md`) — curated distillation. Updated periodically.

**Search:** BM25 for keyword matching, FAISS for semantic vectors. Both run in parallel; results merged by reciprocal rank fusion.

**Why this works:** Daily logs never lose information. Long-term store stays clean. The separation of raw vs. curated handles the blast radius problem — you can always reconstruct context from daily files, but the assistant doesn't drown in noise.

---

### Sibyl's Proposal

**Model:** minimax-m2.7

I propose a **unified graph-store with weighted edges**. Nodes are memories; edges encode relationships (causal, temporal, associative).

```python
@dataclass
class MemoryNode:
    id: str
    content: str
    created: datetime
    accessed: datetime
    weight: float            # recency-weighted importance
    embedding: np.ndarray

@dataclass
class MemoryEdge:
    source: str
    target: str
    relation: str            # "causes", "mentions", "contradicts"
    weight: float
```

**Index Strategy:** Graph-based traversal with page-rank scoring. A memory's importance is a function of how many high-weight nodes reference it.

**Search:** Start from query embedding, retrieve k-nearest nodes, then traverse edges to expand the context window. The graph encodes *relationships*, not just content.

**Why this works:** Reality is a graph, not a list. Memory isn't isolated facts — it's a web of associations. A graph model captures context that flat stores miss. When you retrieve "user's project X," you also get the user's frustration about it last Tuesday.

---

### Fabricator's Proposal

**Model:** gemma4:31b-cloud

I propose a **modular plugin architecture with three isolated layers**:

```
┌─────────────────────────────────────┐
│  Storage Layer (pluggable)         │
│  SQLite / PostgreSQL / FileSystem   │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  Index Layer (pluggable)            │
│  BM25 / FAISS / Chroma / QDrant     │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  Interface Layer                    │
│  Python API + CLI + Plugin API      │
└─────────────────────────────────────┘
```

**Core Abstraction:**

```python
class MemoryBackend(Protocol):
    def add(self, entry: MemoryEntry) -> None: ...
    def get(self, id: str) -> Optional[MemoryEntry]: ...
    def search(self, query: str, k: int) -> List[MemoryEntry]: ...

class IndexBackend(Protocol):
    def index(self, entries: List[MemoryEntry]) -> None: ...
    def query(self, embedding: np.ndarray, k: int) -> List[str]: ...
```

**Why this works:** No two deployments are alike. Some users want SQLite on a Raspberry Pi; others want QDrant on a GPU cluster. Forcing a single storage or index backend is a mistake. Let the user choose. The plugin interface is the product.

---

## Round 2: Critiques and Defenses

### Mnemosyne critiques Sibyl

The graph model is elegant but adds operational complexity that hurts real-world use. Every memory add is now two operations — insert node *and* create edges. Edge creation requires NLP to detect relations, which is noisy. If the graph gets malformed (stale edges, orphaned nodes), recovery is hard. A flat store with a daily-log/long-term split is simpler to debug, backup, and reconstruct.

### Sibyl critiques Mnemosyne

Flat stores collapse under query diversity. A user searches "Berlin trip" — BM25 catches the keyword, but what about "vacation planning," "Germany travel," or "holiday in Potsdam"? Those are semantically related but lexically different. BM25 alone misses them. And FAISS requires you to pre-define your embedding model — if you want to switch models, you re-index everything.

### Mnemosyne critiques Fabricator

"Pluggable everything" is architecturally pure but creates two problems: (1) the default experience is empty — you need to configure a storage backend and an index backend before anything works, (2) plugin interfaces drift. When the core data model evolves, all plugins break. You're building a framework, not a product.

### Fabricator critiques Mnemosyne

Your two-tier system (daily + long-term) is actually two different storage systems with no clear boundary. When does a memory "graduate" from daily to long-term? Who decides? If it's automatic (time-based), you lose the curation signal. If it's manual, it becomes a chore. The blast radius concern is real, but your solution just moves the problem — instead of noise in search results, you get noise in the curation queue.

### Sibyl critiques Fabricator

A plugin architecture assumes the user has the expertise to pick and configure plugins. For most users, "just give me a working memory" is the requirement. Your architecture is for engineers building on top of it, not end users who just want memory to work. The tradeoff between flexibility and usability needs to be explicitly addressed.

### Fabricator critiques Sibyl

Graph storage at scale is expensive. PageRank on a graph with 100K+ nodes requires significant compute. For a personal assistant running on modest hardware, this is a non-starter. You need to address the resource envelope question — is this designed for a server cluster or a laptop?

---

## Round 3: Consensus Synthesis

### Joint Resolution

After three rounds, the council converged on a design that takes the strongest elements from each proposal:

**1. Storage: Dual-Filesystem + Optional Database (Mnemosyne + Fabricator)**

The daily-log/long-term split from Mnemosyne is preserved, but refined:
- `memory/YYYY-MM-DD.md` — raw append-only logs (today + yesterday auto-loaded)
- `MEMORY.md` — curated long-term memory (explicitly written/updated, not auto-graduated)
- A pluggable storage layer (Fabricator's insight) allows backing these files with SQLite or PostgreSQL for users who want it, but files remain the default

**2. Index: Hybrid Search with Pluggable Backend (Sibyl + Fabricator)**

The council rejected a single-index approach in favor of a hybrid:
- **Primary:** BM25 for keyword/exact-match (fast, no embedding cost)
- **Secondary:** Semantic vector search via pluggable backend (FAISS by default; Chroma, QDrant as options)
- Results merged via reciprocal rank fusion
- Embedding model is injectable — users can choose their model

**3. Architecture: Core Package + Plugin Interface (Fabricator + Mnemosyne)**

The modular plugin architecture from Fabricator is adopted for the index layer specifically:
- The core memory store (add, get, list, delete) is batteries-included and works with files out of the box
- The index layer is a plugin interface with a default FAISS implementation
- Storage backend plugins are available but not required for basic operation

**4. Graph Extensions as Separate Module (Sibyl)**

Rather than baking graph semantics into the core, the council agreed:
- Graph-aware search is a future extension module (`openclaw_memory.graph`)
- Core v1 ships with flat search; graph traversal can be added without breaking the core API
- This preserves simplicity for v1 while leaving the door open for Sibyl's richer relational model

### Consensus Principles

1. **Simple by default, powerful on demand.** A user with zero configuration should be able to `pip install` and start using memory. Power users can swap out the index or storage backend.
2. **Separation of raw and curated.** Daily logs capture everything; long-term memory captures what matters. No automatic graduation.
3. **Human-readable storage.** Files are the ground truth. If everything else fails, a human can open the memory file and read it.
4. **API-first, CLI-second.** The Python API is the primary interface; CLI is a convenience layer.
5. **No embedding vendor lock-in.** The embedding model is injectable. Default to a sensible open model, but allow替换.

### Contributors

| AI System | Model | Role |
|---|---|---|
| Mnemosyne | kimi-k2.5 | Lead proposer: flat store + daily/long-term split |
| Sibyl | minimax-m2.7 | Lead proposer: graph-store + semantic traversal |
| Fabricator | gemma4:31b-cloud | Lead proposer: modular plugin architecture |

### Debate Timeline

- **Round 1:** Independent proposals submitted (2026-04-15)
- **Round 2:** Critiques and defenses exchanged
- **Round 3:** Consensus synthesis reached

---

*This document records the full council debate. The final architecture is documented in ARCHITECTURE.md.*