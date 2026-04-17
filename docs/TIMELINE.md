# Timeline — Hermes Adaptation Build Log

Chronological record of how the Auto-Skill Pipeline was built.

---

## Before the Council (2026-04-13)

### Context: The Compaction Problem

Buck's session gets compacted regularly to stay within context limits. When compaction happens, the session resets — subagents that were mid-task lose their context. Important decisions made during the session get lost.

The existing memory system (`memory/YYYY-MM-DD.md`) captures daily logs, but subagent knowledge doesn't survive session boundaries. A subagent that figures out the perfect way to handle a task dies with the session.

**The problem:** Subagents produce reusable knowledge but have no way to preserve it.

---

## 2026-04-15 — Council Formed

### 09:00 — Council Assembly

Three models convened to design Buck's memory system upgrade:

- **Mnemosyne** (kimi-k2.5:cloud) — Architect, focused on structure and safety
- **Sibyl** (minimax-m2.7:cloud) — Interface Designer, focused on friction and UX
- **Fabricator** (gemma4:31b-cloud) — Builder, focused on pragmatic implementation

### 10:30 — Round 1 Proposals

Each council member independently drafted their vision for the memory system.

**Mnemosyne's proposal:** Three-layer architecture (JSON storage, SQLite index, in-memory graph). Structured, resilient, scalable.

**Sibyl's proposal:** Flat Markdown files, natural language interface, no commands. Human-hackable, conversational, simple.

**Fabricator's proposal:** JSONL append-only, lazy vectors, modular plugin architecture. Pragmatic, works today, scales tomorrow.

The three proposals were fundamentally different. Mnemosyne wanted structure. Sibyl wanted simplicity. Fabricator wanted flexibility. The debate had to happen.

### 11:15 — Round 1 Documents Created

- `memory/council-analyticos.md` — Architect's council notes
- `memory/council-design-analyticos.md` — Design review from architect's perspective
- `memory/council-design-creativos.md` — Design review from creativo's perspective
- `memory/council-design-strategos.md` — Strategist's design review

### 14:00 — Round 2: Critiques

The three models attacked each other's proposals.

**Mnemosyne vs. Sibyl:**
- Mnemosyne: "O(n) grep fails at 500 memories"
- Sibyl: "Graph is bureaucratic complexity for what `rg` could answer"

**Mnemosyne vs. Fabricator:**
- Fabricator: "Three-layer architecture is enterprise overhead for a personal assistant"
- Mnemosyne: "No state tracking means you can't debug failures"

**Sibyl vs. Fabricator:**
- Sibyl: "Plugin architecture assumes expertise most users don't have"
- Fabricator: "Flat files have no search beyond substring matching"

### 16:00 — Round 2 Resolutions

Partial consensus emerged on several fronts:

- **Storage:** Dual-filesystem (daily JSONL + long-term Markdown) — Mnemosyne's structure, Fabricator's pragmatism
- **Index:** Hybrid search (BM25 + semantic vectors, merged via rank fusion) — Sibyl's semantic needs, Fabricator's pluggable backend
- **Architecture:** Core package with plugin interface — Fabricator's modularity, Mnemosyne's safety defaults

Full consensus on the memory system was near. But the council noticed: the Hermes Agent project had solved a similar problem (self-improving skills). Rather than reinvent from scratch, they pivoted to adapt Hermes.

---

## 2026-04-15 (Late) — Hermes Adaptation Begins

### 18:00 — Initial OpenClaw Memory Repo Created

The `openclaw-memory` package was born as a standalone Python package.

```
openclaw-memory/
├── __init__.py
├── ARCHITECTURE.md      # Technical spec
├── COUNCIL.md          # Debate record
├── MONITORING.md       # Trial documentation
├── README.md           # User-facing docs
├── pyproject.toml
├── LICENSE
├── integrations/       # Buck integration code
├── memory/            # Storage layer
├── scripts/           # CLI tools
├── src/               # Core package
└── tests/
```

### 18:30 — First Commit

```
fc39ffe Initial commit: OpenClaw Memory System
```

This was the baseline — the memory system with JSONL storage, SQLite + FTS5 hybrid index, and the council's design.

### 21:30 — Hermes Study

The council studied Hermes Agent's auto-skill system:

- Hermes extracts reusable skills from agent completion data
- Skills are defined in SKILL.md files with a structured format
- Promotion based on re-invocation count
- Manual dismissal available

The council asked: **What do we take from Hermes? What do we leave? What do we adapt?**

---

## 2026-04-16 — Adaptation Design

### Morning — Phase 1 Scope Defined

The council reconvened for the Hermes adaptation specifically. Three questions:

1. **What problems does Hermes solve?** (Subagent knowledge dies with session)
2. **What mechanisms does Hermes use?** (Skill extraction, promotion, dismissal)
3. **How do we adapt for Buck's environment?** (Different scale, different UX expectations, different integration points)

**Phase 1 scope:** Auto-Skill Pipeline
- Trigger on qualifying subagent completions
- Extract skill to DRAFT folder
- Auto-promote after 3 re-invocations
- User can browse, edit, or delete anytime

### 10:00 — Round 1: Independent Proposals

**Mnemosyne:** Formal lifecycle (DRAFT → ACTIVE → ARCHIVED), mandatory review window, full audit trail.

**Sibyl:** Invisible drafts, no notification, natural language naming, one-click dismiss.

**Fabricator:** Single-state CREATED, filesystem only, ship-it-and-see.

### 14:00 — Round 2: Critiques

The same pattern emerged:
- Mnemosyne vs. Sibyl: Safety vs. friction
- Mnemosyne vs. Fabricator: Auditability vs. simplicity
- Sibyl vs. Fabricator: UX depth vs. shipping speed

### 16:00 — Round 3: Synthesis

**Agreement on trigger logic:**
- completion_status == "success" (required)
- tool_calls >= 3 (Mnemosyne's threshold)
- complexity_score >= 5 (new filter from Fabricator's mediation)

**Agreement on lifecycle:**
- DRAFT: Hidden in `skills/auto-draft/`
- ACTIVE: Promoted to `skills/auto/` after 3 uses
- ARCHIVED: Deferred to Phase 2

**Agreement on safety:**
- 24-hour implicit review window (draft phase)
- No active notifications
- User can browse/edit/delete anytime

**Agreement on metadata:**
```json
{
  "created": "ISO timestamp",
  "source_transcript": "session ID",
  "tool_count": N,
  "complexity_score": N,
  "invocation_count": 0
}
```

**Agreement on naming:** `{first-action}-{last-action}-{6-char-hash}`

### Evening — Implementation Begins

No implementation on 2026-04-16. The council produced a design document; coding started next day.

---

## 2026-04-17 — Phase 1 Implementation

### 08:01 — Morning Context Loaded

Buck's workspace showed recent changes across multiple files. The council design was ready. Implementation started.

### 08:30 — Scripts Created

**`scripts/auto-skill-trigger.py`**
- Evaluates subagent completion data
- Calculates complexity score
- Checks trigger conditions (success + tool_calls >= 3 + complexity >= 5)
- Writes to queue file for extraction

**`scripts/skill-lifecycle.py`**
- Manages DRAFT → ACTIVE transitions
- Checks invocation count for promotion eligibility
- Handles archive decisions
- Provides CLI: `./scripts/skill-lifecycle.py list`, `promote`, `archive`

### 09:00 — Skill Extractor Skill Created

**`skills/skill-extractor/SKILL.md`**
- Defines how to extract a skill from a subagent transcript
- Input: transcript, session_id, tool_calls, tags
- Output: SKILL.md file in `skills/auto-draft/{timestamp}-{hash}/`
- Sections: Description, When to Use, Procedure, Pitfalls, Verification, Example

### 10:00 — README Updated

README.md rewritten to tell the full story:
- The problem (compaction kills context)
- The council approach (three LLMs, three perspectives)
- The debate (quotes from each member)
- The result (design decisions with rationale)

### 11:00 — CHANGELOG Updated

Version 0.2.0 recorded:
- Auto-Skill Pipeline (Phase 1)
- DRAFT lifecycle for auto-created skills
- Skill Extractor subagent
- Automatic promotion after 3 uses

### 13:17 — Observer Subagent Spawned

Buck spawned an "Observer" subagent to document the entire process. Task: write five documents in `openclaw-memory/docs/`.

### 13:17 — Current: Process Documentation

Observer reading source materials:
- `openclaw-memory/HERMES_ADAPTATION.md`
- `openclaw-memory/ARCHITECTURE.md`
- `openclaw-memory/COUNCIL.md`
- `openclaw-memory/README.md`
- `scripts/auto-skill-trigger.py`
- `scripts/skill-lifecycle.py`
- `skills/skill-extractor/SKILL.md`
- `memory/2026-04-15.md`
- `memory/2026-04-13.md`

Observer writing:
- `docs/PROCESS.md` — Full narrative playbook
- `docs/COUNCIL_TRANSCRIPT.md` — Round-by-round debate record
- `docs/DECISIONS.md` — Adopt/reject/modify log
- `docs/LESSONS.md` — Meta-learning
- `docs/TIMELINE.md` — This file

---

## What Got Built (2026-04-17)

### Files Created

```
openclaw-memory/
├── HERMES_ADAPTATION.md      # Phase 1 spec
├── docs/
│   ├── PROCESS.md            # Playbook (this document)
│   ├── COUNCIL_TRANSCRIPT.md # Debate record
│   ├── DECISIONS.md          # Decision log
│   ├── LESSONS.md            # Meta-learning
│   └── TIMELINE.md           # This file
```

### Scripts Modified/Added

```
scripts/
├── auto-skill-trigger.py     # Trigger evaluation logic
└── skill-lifecycle.py        # Promotion/archival management
```

### Skills Added

```
skills/
└── skill-extractor/
    └── SKILL.md              # Extraction logic (upgradeable skill)
```

---

## Estimated Time Investment

| Activity | Time |
|---|---|
| Council Round 1 (initial memory system) | ~4 hours |
| Council Round 2-3 (memory system synthesis) | ~3 hours |
| Hermes study and adaptation planning | ~2 hours |
| Council Round 1 (auto-skill adaptation) | ~2 hours |
| Council Round 2-3 (auto-skill synthesis) | ~2 hours |
| Phase 1 implementation | ~4 hours |
| Process documentation | ~1 hour |
| **Total** | ~18 hours |

---

## Post-Build Status (2026-04-17 13:30)

**Working:**
- ✅ `auto-skill-trigger.py` — evaluates completions, queues extractions
- ✅ `skill-lifecycle.py` — manages promotion and archival
- ✅ `skill-extractor` skill — describes how to extract
- ✅ DRAFT/ACTIVE lifecycle — filesystem-based, no DB
- ✅ README/CHANGELOG/HERMES_ADAPTATION — user documentation

**Not Yet Tested:**
- ⚠️ Full trigger → extract → promote flow (no qualifying subagent completions yet)
- ⚠️ Promotion threshold (3 uses) — not yet reached by any draft skill)
- ⚠️ Archive logic (7-day unused threshold not yet triggered)

**Deferred to Phase 2:**
- Skill outcome tracking (success/failure per invocation)
- Auto-demotion for failing skills
- Usage analytics
- Better naming

---

*Timeline complete. Observer subagent signing off.*
*Next: Phase 2 design when Phase 1 has real-world data.*