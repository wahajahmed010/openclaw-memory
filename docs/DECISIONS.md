# Decisions Log — Hermes Adaptation

What we took, what we left, and why.

---

## Adopted from Hermes

| Decision | Source | Rationale |
|---|---|---|
| Skill extraction from subagent completion | Hermes | Core value proposition — knowledge reuse |
| SKILL.md file format | Hermes | Human-readable, editor-friendly |
| Promotion based on re-invocation | Hermes | Natural proxy for usefulness |
| Trigger conditions (success + tool count) | Hermes | Simple, deterministic, effective |
| DRAFT lifecycle phase | Hermes | Provides safety without friction |

---

## Rejected from Hermes

| Rejection | Why Rejected |
|---|---|
| Central skill manifest file (`skills.json`) | Overhead for Phase 1; filesystem conventions are sufficient |
| Mandatory human approval before activation | Notification fatigue; draft mode provides equivalent safety |
| Rich version numbering (v1.0, v1.1) | Overhead; re-invocation count is enough for Phase 1 |
| Skill dependency tracking | Not needed yet; adds complexity |
| "Not useful" auto-demotion | Defer to Phase 2; manual deletion is sufficient for now |
| Usage analytics per skill | Defer to Phase 2; invocation count is enough signal |
| Separate skill installation step | Users can move files; auto-promotion removes friction |

---

## Adapted from Hermes

| Original | Our Adaptation |
|---|---|
| Central `extract_skill()` function | Split into trigger script + skill-extractor skill |
| Hardcoded extraction logic | Extraction logic lives in `skill-extractor/SKILL.md` (upgradeable) |
| Single skill namespace | Separate `auto-draft/` and `auto/` namespaces with different visibility |
| Manifest file tracks all skills | Directory listing + meta.json per skill |
| Promotion threshold: 5 uses | Promotion threshold: 3 uses (lower — faster feedback) |
| Named skills (e.g., "code-reviewer") | Auto-generated names (timestamp-hash) with descriptive SKILL.md |

---

## Internal Decisions (Council-Generated)

These weren't in Hermes — they emerged from the council debate.

### Trigger Logic

**Decision:** Use three conditions — `completion_status == "success"`, `tool_calls >= 3`, `complexity_score >= 5`

**Rationale:** Mnemosyne pushed for complexity scoring to filter trivial tasks. Sibyl initially wanted lower threshold (tool_calls >= 2) for more extraction. Fabricator mediated — keep tool_calls at 3, add complexity score as the filter. Compromise that gives safety (complexity) without over-restriction (tool_calls at 3).

---

### Lifecycle States

**Decision:** Two states for Phase 1 — DRAFT and ACTIVE. ARCHIVED deferred.

**Rationale:** Mnemosyne designed three states. Fabricator said Phase 1 doesn't need ARCHIVED — just delete unwanted skills. Sibyl said invisible drafts solve the safety concern. Three-state lifecycle is correct architecture, but Phase 1 can ship with two-state and add ARCHIVED when there's actual need.

---

### Metadata Fields

**Decision:** Track only five fields — `created`, `source_transcript`, `tool_count`, `complexity_score`, `invocation_count`

**Rationale:** Mnemosyne wanted full audit trail. Fabricator said overhead. Sibyl pointed out that `created` + `source_transcript` are enough for debugging. Final: five fields is the minimum viable audit (Fabricator's concession to Mnemosyne's safety concerns).

---

### Naming Convention

**Decision:** `{first-action}-{last-action}-{6-char-hash}`

**Rationale:** Sibyl wanted human-readable names. Mnemosyne said collision-prone. Fabricator said hash everything. Compromise: descriptive prefix (actions) + hash suffix (uniqueness) = `git-commit-push-a3f2b1`. Readable enough, collision-safe.

---

### Folder Structure

**Decision:**
```
skills/
├── auto-draft/{timestamp}-{hash}/   # Testing phase
│   ├── SKILL.md
│   └── meta.json
├── auto/{skill-name}/               # Promoted
│   ├── SKILL.md
│   └── meta.json
└── skill-extractor/
    └── SKILL.md                     # The extraction skill
```

**Rationale:** Fabricator's filesystem conventions. Mnemosyne's lifecycle separation. Sibyl's visibility control (draft stays hidden until promoted).

---

## What We'd Do Differently

### In the Council Process

**Would change:** Run a shorter Round 2.

The second round of critiques ran long. Mnemosyne and Fabricator debated state machine implementation details that could have been settled in 10 minutes. The moderator (main agent acting as Buck) should have cut off the technical debate earlier and pushed toward synthesis.

**Would keep:** The three-perspective format.

Every tension we hit was predictable. Architect thinks safety. UX thinks friction. Builder thinks shipping. The three-perspective format surfaces these tensions early, before implementation, when they're cheap to resolve.

---

### In the Design

**Would change:** Add invocation tracking earlier.

The promotion from DRAFT → ACTIVE is currently based on a counter in `meta.json`. But that counter isn't incremented automatically — `skill-lifecycle.py` needs to be called after every subagent completion. We discovered this gap late. Better to design the tracking mechanism upfront.

**Would keep:** Splitting trigger from extraction.

Trigger logic as a script (fast, deterministic) + extraction logic as a skill (creative, upgradeable) is the right separation. Don't merge them.

---

### In the Implementation

**Would change:** Write the SKILL.md generator first.

We built `auto-skill-trigger.py` and `skill-lifecycle.py` first. The skill extraction subagent (driven by `skill-extractor` skill) came last. But the extraction is the core value — if extraction is broken, nothing else matters. Ship the core first.

**Would keep:** The draft-hidden-by-default approach.

Users don't need to see every extraction. Skills that are invoked 3 times are the ones worth reviewing. The invisibility until proven is the right UX.

---

## Timeline

| Date | Event |
|---|---|
| 2026-04-15 | Council formed. Round 1 proposals submitted. |
| 2026-04-15 | Round 2: Critiques and defenses. |
| 2026-04-15 | Round 3: Synthesis. Design agreed. |
| 2026-04-17 | Phase 1 implemented. v0.2.0 released. |
| 2026-04-17 | This document written (Observer subagent). |

---

*Decisions are forever. Rationale is the only thing that survives context change.*