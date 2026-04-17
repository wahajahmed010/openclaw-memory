# How We Adapted Hermes — A Playbook

> *A three-LLM council debated, negotiated, and built a skill extraction system in two days. Here's what we learned.*

---

## The Challenge

Buck is a personal AI assistant running 24/7. It manages sub-agents — spawned workers that handle specific tasks. The problem: sub-agents are *ephemeral*. They do good work, then vanish. Their knowledge dies with the session.

Buck needed something like Hermes Agent's self-improving skill system. Hermes is a Nous Research project that automatically extracts reusable workflows from agent executions and promotes them to installable skills. The concept is powerful.

The challenge: **How do you adapt something without breaking what already works?**

Hermes runs in a different environment. Its skill format, its extraction logic, its promotion thresholds — none of it was designed for Buck's setup. We couldn't just copy-paste code. We had to *think* about what we were taking, what we were leaving, and what we were adapting.

---

## The Council Approach

Instead of one model making all the decisions, we ran a **three-council system** with distinct perspectives:

| Council Member | Model | Philosophy | Contribution |
|---|---|---|---|
| **Mnemosyne** | kimi-k2.5:cloud | Architect — "Structure and safety first" | Data model, lifecycle, promotion thresholds |
| **Sibyl** | minimax-m2.7:cloud | UX Designer — "Friction and feel matter" | Human-facing behavior, naming, review windows |
| **Fabricator** | gemma4:31b-cloud | Builder — "Make it work, make it real" | Implementation feasibility, code structure |

Three rounds:
1. **Round 1:** Independent proposals — each council member drafts their vision
2. **Round 2:** Critique and defense — they attack each other, defend their positions
3. **Round 3:** Synthesis — concessions are made, consensus emerges

---

## Round 1 — Independent Analysis

### Mnemosyne's Position

```
"We need a proper lifecycle. DRAFT → ACTIVE → ARCHIVED.
Every subagent transcript that qualifies gets a review window.
Auto-promotion after N successful re-invocations. Safety gates everywhere."
```

Mnemosyne's instinct was correct but heavy. They wanted:
- Formal state machine for skill states
- Mandatory 24-hour review window before anything goes live
- Sign-off from the main agent before promotion
- Version tracking on every skill
- Full audit trail

### Sibyl's Position

```
"Don't make users feel like they're reviewing code merges.
The system should be invisible until it matters.
Skills appear in the list only when they're actually useful.
The user should be able to dismiss, edit, or delete without consequences."
```

Sibyl pushed for:
- Lightweight naming (timestamps + hashes, not version numbers)
- Auto-promotion without mandatory approval
- Draft folder stays hidden until user asks
- Natural language for skill descriptions (not technical metadata)
- One-click dismiss

### Fabricator's Position

```
"Both of you are overthinking it. What's the minimum viable pipeline?
Subagent completes → trigger fires → extract skill → write SKILL.md → done.
The rest is nice-to-have. Let's ship Phase 1 and see what breaks."
```

Fabricator argued for:
- Simple trigger conditions (success + tool count + complexity)
- Direct file system output (no database, no state machine)
- Stateless extraction (just read transcript, write skill)
- Minimal metadata (just created date, source session, invocation count)

---

## Round 2 — Negotiation

### The Tension Points

**Tension 1: Safety vs. Speed**

Mnemosyne wanted mandatory human review before any skill could activate. Sibyl said that would create "notification fatigue" — Buck's human would be spammed with approval requests for skills they don't care about.

**Mnemosyne:** "If we auto-promote without review, a bad skill could cause harm."
**Sibyl:** "If we require review for everything, the user ignores all of them."

**Resolution:** Draft mode. Skills go to a hidden `skills/auto-draft/` folder first. They're invisible until they've been invoked 3 times successfully. Only then do they appear in the main auto list. The user can browse drafts anytime, but they're not notified of every creation.

---

**Tension 2: Complexity vs. Simplicity**

Fabricator said the entire skill lifecycle could be two scripts. Mnemosyne said two scripts can't handle state transitions, promotion logic, and archival properly.

**Fabricator:** "I'm not building an enterprise app. This is a personal assistant."
**Mnemosyne:** "And a personal assistant that creates broken skills is worse than no skills at all."

**Resolution:** Split the difference. Phase 1 ships with simple state tracking (DRAFT → ACTIVE) in flat JSON files. If the system proves valuable, Phase 2 adds proper state machines. Start simple, prove value, then complicate.

---

**Tension 3: Naming — Human Meaningful vs. Machine Unique**

Sibyl wanted human-readable skill names like "git-commit-and-push" — things that tell you what the skill does. Mnemosyne said human names collide and conflict. Fabricator said just hash everything and be done.

**Sibyl:** "If I look at skills/auto/ and see `a3f2b1`, I have no idea what it does."
**Mnemosyne:** "If I look at skills/auto/ and see `git-commit-and-push`, and there are three of those from different sessions, which one do I use?"
**Fabricator:** "Timestamp-hash is guaranteed unique. Just include the transcript summary in the SKILL.md header."

**Resolution:** Name template = `{first-key-action}-{last-key-action}-{6-char-hash}`. Not perfectly human, but informative enough. The SKILL.md inside carries the full description and usage notes.

---

## Synthesis — The Plan

After three rounds, the council agreed on:

### Phase 1: Auto-Skill Pipeline (What We Built)

**Trigger Logic:**
```
Subagent completes
    → completion_status == "success" ?
    → tool_calls >= 3 ?
    → complexity_score >= 5 ?
    → YES: extract skill
    → NO: skip
```

**Lifecycle:**
```
skills/auto-draft/{timestamp}-{hash}/   # Testing phase
    SKILL.md
    meta.json (invocation_count: 0)
    
    [After 3 successful re-invocations]
    
skills/auto/{skill-name}/              # Promoted
    SKILL.md
    meta.json (invocation_count: N)
```

**Safety:**
- 24-hour review window built into the draft phase
- Auto-archive after 7 days of no usage
- User can browse, edit, or delete anytime

---

### What We Rejected

| Rejected Idea | Why |
|---|---|
| Mandatory human approval before any skill activates | Notification fatigue; draft mode covers safety |
| Formal version numbering (v1.0, v1.1, etc.) | Overhead for Phase 1; re-invocation count is enough |
| Central database for skill state | Filesystem + JSON is sufficient; no external deps |
| Rich audit trail with timestamps for every action | Can add later if needed |

---

### What We Adapted from Hermes

| Hermes Feature | Adaptation |
|---|---|
| `extract_skill()` function | Split into trigger script + extractor subagent |
| Skill manifest file | Replaced with filesystem conventions + SKILL.md |
| Promotion based on usage | Re-invocation count tracked in `meta.json` |
| "Skill not useful" dismissal | User can delete draft or promoted skill anytime |

---

## Implementation — Phase 1

### Files Created

```
scripts/
├── auto-skill-trigger.py     # Evaluates subagent completion, decides if extraction needed
├── skill-lifecycle.py        # Manages DRAFT → ACTIVE transitions, archive decisions

skills/
├── skill-extractor/
│   └── SKILL.md              # The skill that knows how to extract skills
├── auto-draft/               # Testing skills live here until promoted
└── auto/                     # Promoted skills — the working library
```

### Key Design Decisions

**1. Trigger is a script, not a subagent**

The `auto-skill-trigger.py` runs synchronously after subagent completion. It evaluates the completion data and writes to a queue file. A separate subagent (driven by `skill-extractor` skill) does the actual extraction.

*Why:* Subagent startup overhead for a simple evaluation is wasteful. The trigger is fast and deterministic.

**2. Extraction uses a skill, not a hardcoded function**

The `skill-extractor` skill describes *how* to extract a skill from a transcript. It's reusable, editable, and upgradeable. When we improve extraction logic, we edit the skill, not the trigger script.

**3. Metadata is minimal**

```json
{
  "created": "2026-04-17T13:30:00",
  "source_transcript": "session-id-123",
  "tool_count": 8,
  "complexity_score": 7,
  "invocation_count": 0
}
```

No version history, no approval chain, no timestamps for last access. Re-invocation count is the only state that matters for promotion.

---

## Results

### What Worked

✅ **Draft mode** — Skills appear invisibly until proven. No notification fatigue.  
✅ **Simple trigger** — Three conditions, no ML, no ambiguity.  
✅ **Skill-as-skill-extractor** — The extraction logic is upgradeable via skill editing.  
✅ **Filesystem conventions** — No database, no external dependencies.  

### What Didn't Work

❌ **Naming collision** — Two different subagents doing similar things produce similarly-named skills. We resolved with hash suffixes, but the root issue remains.  
❌ **No rollback for bad extractions** — If a skill gets promoted and is wrong, we have to manually delete it. Auto-demotion isn't implemented yet.  
❌ **Session context overflow** — The skill-extractor subagent still inherits too much context. We fixed with `lightContext: true` on spawn, but this required learning the hard way.

---

## The Playbook

### For Anyone Adapting Hermes (or any external system)

**1. Don't copy. Think.**

The first instinct is to find the equivalent file in the source and port it. Resist. Ask instead: *what problem does this solve, and what's the simplest way to solve it in my environment?*

**2. Run a council.**

Three perspectives catch what one misses. Architect thinks safety. UX thinks friction. Builder thinks feasibility. The negotiation between them produces better design than any single mind.

**3. Start simple. Prove value. Complicate later.**

We didn't build the full state machine because we didn't need it yet. We built enough to test the hypothesis: "Does auto-skill extraction actually help?" If it does, Phase 2 adds sophistication. If it doesn't, we haven't wasted weeks building features nobody uses.

**4. Separate trigger from extraction.**

Trigger logic is fast and deterministic — it should be a script. Extraction logic is creative and evolving — it should be a skill. Mixing them creates brittleness.

**5. Design for dismissal.**

Every automation system needs an escape hatch. Users must be able to see what was created, edit it, ignore it, or delete it. If the system feels like it's making decisions *for* them rather than *helping* them, trust erodes.

**6. Document the debate.**

The council produced better design than any single member would have alone. But only if the reasoning survives the session. The COUNCIL.md file captures not just what was decided, but *why* — and what was rejected and why. Future maintainers (that's future-you) need that context.

---

## Credits

- **Mnemosyne** (kimi-k2.5:cloud) — Architecture and safety
- **Sibyl** (minimax-m2.7:cloud) — UX and human factors
- **Fabricator** (gemma4:31b-cloud) — Implementation and pragmatism

Inspired by [Hermes Agent](https://github.com/NousResearch/Hermes-Agent) by Nous Research.

---

*Documenting the process of documenting. Meta all the way down.*