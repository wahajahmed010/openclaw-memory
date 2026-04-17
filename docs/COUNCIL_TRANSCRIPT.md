# Council Transcript — Hermes Adaptation

Three LLMs debated and designed the Auto-Skill Pipeline for Buck. This is the record.

---

## Round 1 — Independent Proposals

### Mnemosyne (Architect)

**Model:** kimi-k2.5:cloud

> "Every extracted workflow needs a formal lifecycle. DRAFT means 'not yet validated.' ACTIVE means 'promoted after proving itself.' ARCHIVED means 'retired or superseded.' Without state tracking, you have no idea which skills are trustworthy."

**Proposal:**
```
Trigger conditions:
- completion_status == "success"
- tool_calls >= 3
- complexity_score >= 5

Lifecycle:
DRAFT → ACTIVE → ARCHIVED

Review window: 24 hours before first activation
Promotion: Manual sign-off from main agent
```

**Core concern:** Safety and auditability.

---

### Sibyl (UX Designer)

**Model:** minimax-m2.7:cloud

> "Formal state machines are fine for enterprise software. For a personal assistant, they create friction that outweighs safety benefits. Users don't want to review skill approvals — they want skills that work and don't bother them."

**Proposal:**
```
Trigger conditions:
- completion_status == "success"
- tool_calls >= 2 (lower threshold — more skills extracted)
- automatic naming from transcript content

Lifecycle:
DRAFT (invisible) → PROMOTED (auto, after 3 uses) → USER-DELETED

No mandatory review. No approval queue.
```

**Core concern:** User experience and friction.

---

### Fabricator (Builder)

**Model:** gemma4:31b-cloud

> "You're both over-engineering. This is Phase 1. The minimum viable pipeline is: subagent completes → trigger script fires → extract skill → write SKILL.md → done. Everything else is Phase 2."

**Proposal:**
```
Trigger conditions:
- completion_status == "success"
- tool_calls >= 3

Lifecycle:
Single state: CREATED
Promotion: None (user picks what to keep)

Output: One SKILL.md per extraction, filesystem only
```

**Core concern:** Ship something that works today.

---

## Round 2 — Critiques and Defenses

### Mnemosyne attacks Sibyl

> "Lowering the tool call threshold to 2 means you'll extract single-step macros as 'skills.' That's not reuse — that's noise. And auto-promotion after 3 uses with no review window means a bad skill can run 3 times before anyone notices it's wrong."

**Sibyl responds:** "A two-step workflow *can* be reusable. The question is whether the pattern is generalizable, not how many steps it has. And the draft folder stays hidden — the user isn't notified. If a skill is wrong, they see it when they browse the auto folder, not when it first appears."

---

### Mnemosyne attacks Fabricator

> "Single-state 'CREATED' means everything is equal. How do you distinguish a skill that ran once and failed from one that ran 10 times successfully? You can't manage what you can't measure."

**Fabricator responds:** "Invovation count isn't measure — it's vanity. What matters is: does the skill do what it says? If yes, keep it. If no, delete it. Tracking 47 metadata fields for a personal assistant skill is overhead."

**Mnemosyne responds:** "Then at minimum track: created date, source session, invocation count. Not for vanity — for debugging. When a skill breaks, you need to know when it was created and what context it came from."

**Resolution:** Fabricator concedes. Meta.json includes `created`, `source_transcript`, `invocation_count`. No other metadata for Phase 1.

---

### Sibyl attacks Mnemosyne

> "24-hour review window before activation means you notify the user about every extraction. If 10 subagents complete in a day, that's 10 review requests. The user will tune out or disable the system entirely."

**Mnemosyne responds:** "The review window doesn't require active notification. Draft skills go to a hidden folder. They don't surface until the user explicitly browses the auto-draft directory. The 'window' is the time between creation and promotion — it exists even if nobody watches it."

**Sibyl responds:** "So the review window is theoretical, not practical. You get safety without friction only if the promotion threshold is reasonable."

**Resolution:** Mnemosyne's safety architecture is preserved, but implemented as passive draft mode rather than active notification. Safety without friction.

---

### Fabricator attacks Sibyl

> "Your naming convention — 'git-commit-and-push' — is human-readable but collision-prone. What if two different subagents both produce a 'git-commit-and-push' skill from different contexts?"

**Sibyl responds:** "The skill name is just a label. The SKILL.md inside has the full description. If names collide, users can see the difference in the content. A hash suffix is fine for uniqueness, but don't sacrifice readability entirely."

**Resolution:** Timestamp-hash naming with descriptive SKILL.md content.

---

### Fabricator attacks Mnemosyne

> "Your formal state machine (DRAFT → ACTIVE → ARCHIVED) requires state tracking across invocations. That means a database or persistent state file. Now you have a dependency that can corrupt, drift, or get out of sync."

**Mnemosyne responds:** "A JSON file per skill is not a database. State transitions are file renames. DRAFT folder to ACTIVE folder is just `mv`. Archive is `mv` to archive folder. No DB needed."

**Resolution:** State machine preserved, implemented as filesystem conventions. No external database.

---

## Round 3 — Synthesis

### The Final Agreement

**Trigger logic (Fabricator's simplicity, Mnemosyne's rigor):**
- completion_status == "success" (required)
- tool_calls >= 3 (Mnemosyne's threshold, not Sibyl's lower one)
- complexity_score >= 5 (new — filters out trivial tasks)

**Lifecycle (Mnemosyne's safety, Sibyl's invisibility):**
- DRAFT: Invisible, lives in `skills/auto-draft/`
- ACTIVE: Appears in `skills/auto/` after 3 successful re-invocations
- ARCHIVED: Not implemented in Phase 1 (Fabricator's deferral wins)

**Safety (Mnemosyne's architecture, Sibyl's UX):**
- 24-hour implicit review window (draft phase)
- No active notifications
- User can browse, edit, or delete anytime

**Metadata (Fabricator's concession to Mnemosyne):**
```json
{
  "created": "ISO timestamp",
  "source_transcript": "session ID",
  "tool_count": N,
  "complexity_score": N,
  "invocation_count": 0
}
```

**Naming:** `{first-action}-{last-action}-{6-char-hash}` with full description in SKILL.md

---

### What Didn't Get Resolved (Deferred to Phase 2)

- Auto-demotion: If a promoted skill starts failing, there's no automatic demotion back to draft
- Version history: No tracking of edits to SKILL.md
- Cross-skill dependencies: If skill A uses skill B, no dependency management
- Usage analytics: No data on which skills are used most, which are stale

---

## Quote Archive

### Most Illustrative Quotes

**Mnemosyne on safety:**
> "A skill that fails silently is worse than no skill at all. We need to know what was run, when, and whether it succeeded."

**Sibyl on friction:**
> "Every notification is a tax on attention. If the system creates work for the user, they'll turn it off."

**Fabricator on pragmatism:**
> "We can debate governance models for weeks or ship Phase 1 tomorrow. I vote tomorrow."

**Mnemosyne on governance:**
> "You can ship tomorrow, but you'll spend next week fixing things that Phase 1's bad decisions caused. Architecture isn't overhead — it's leverage."

**Sibyl on naming:**
> "If I look at skills/auto/ and see a3f2b1, I have no idea what it does. But if I see git-commit-push-7a3f2b, I at least know the domain."

**Fabricator on complexity:**
> "The best code is the code you don't write. The best feature is the feature you don't ship until you need it."

---

## Outcome

The council produced a design that none of the three members would have designed alone:

- **From Mnemosyne:** Formal lifecycle (DRAFT/ACTIVE), safety architecture, metadata tracking
- **From Sibyl:** Invisible drafts, no notification fatigue, human-editable skill content
- **From Fabricator:** Simple trigger logic, filesystem conventions, Phase 1 deferral of complexity

The result ships as v0.2.0 of the openclaw-memory system.

---

*Recorded by Observer subagent on 2026-04-17. Transcribed from council session context.*