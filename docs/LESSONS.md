# Lessons — Hermes Adaptation

What we learned about running a council, adapting external systems, and building things that actually ship.

---

## Meta-Lessons: How to Run an LLM Council

### Lesson 1: Roles need teeth, not just labels

We labeled Mnemosyne as "Architect" and Sibyl as "UX Designer" — but those labels only worked because we gave each role a *perspective that couldn't be reduced to the others*.

Mnemosyne genuinely cared about safety guarantees that Sibyl would have traded away for UX. Sibyl genuinely cared about friction costs that Fabricator would have dismissed as overhead. The labels were meaningful because each role had irreducible preferences.

**If you run a council:** Give members distinct philosophies, not just distinct expertise. "This one is the database expert, this one is the frontend expert" produces collaboration. "This one values safety, this one values speed, this one values simplicity" produces *synthesis*.

---

### Lesson 2: Round 2 is where the magic happens

Round 1 is posturing. Each council member writes their proposal, puts their best foot forward, makes it sound reasonable. Round 2 is where the real design happens — when they have to defend against attacks.

The graph store vs. flat store debate (from the memory system council) only resolved because Mnemosyne had to defend against Fabricator's "operational complexity" critique. The defense forcedMnemosyne to articulate *why* structure matters, which led to the dual-filesystem compromise.

**If you run a council:** Don't truncate Round 2. That's where proposals get stress-tested. Cut Round 3 if you must, but not Round 2.

---

### Lesson 3: Synthesis requires a moderator with opinions

The council produced better design than any single member — but only because someone pushed for synthesis when the debate was running long.

In Round 2, Mnemosyne and Fabricator got stuck debating state machine implementation details for 15 minutes. Neither would concede because each saw the other's point as valid but the debate as unproductive. The main agent (acting as Buck) had to step in and say: "Defer state machine complexity to Phase 2. Make a decision now."

**If you run a council:** The moderator isn't just a facilitator — they're a decision-maker when consensus is elusive. Give them authority to cut debates and make calls.

---

### Lesson 4: Document the why, not just the what

The COUNCIL.md file is the most valuable artifact of this process. It captures not just what was decided, but *why each decision was made* and *what was rejected and why*.

Future maintainers (that's future-you, or a different subagent who wasn't in the room) need to understand the reasoning to make good changes. If a decision seems wrong, the rationale explains why it was made. If circumstances have changed, the rationale shows what assumptions might be obsolete.

**Always:** Write decisions as "We chose X because Y. We rejected Z because W." Not just "We chose X."

---

## System-Building Lessons

### Lesson 5: Trigger logic and extraction logic are different

We initially thought about building one "skill extractor" that did everything: evaluated completions, extracted workflows, wrote SKILL.md files, managed promotion.

We ended up splitting into:
- `auto-skill-trigger.py` — fast, deterministic, evaluates completion data
- `skill-extractor` skill — creative, handles extraction, writes SKILL.md

This separation is good architecture. The trigger runs on every subagent completion (fast path). The extractor runs only when triggered (slower path). If extraction logic needs to change, you edit a skill, not a script.

**Application:** When you find yourself writing code that mixes "should I do X?" with "how do I do X?" — split them. Gates from execution.

---

### Lesson 6: Draft mode > notification mode

The original question was: "How do we let users review skills before they go live?"

The naive answer: show a notification when a skill is created, require approval before it activates. This is how enterprise software handles review workflows.

The better answer (Sibyl's insight): don't notify. Just put the skill in a hidden folder. It stays invisible until it's proven useful (3 re-invocations). Only then does it appear in the visible auto folder.

**The difference:** Notification mode creates work. Draft mode creates optional work. Users who care can browse drafts. Users who don't aren't bothered. Safety without friction.

---

### Lesson 7: Phase 1 is always a prototype

We told ourselves: Phase 1 is minimal viable. We're deferring complexity to Phase 2. And that's correct — but we also told ourselves Phase 1 was complete, production-ready, ship-it-and-forget.

It's not. Phase 1 is a prototype that proved the hypothesis ("does auto-skill extraction work?"). Phase 2 is where we handle what we learned.

**Reality check:** Every "Phase 1" will have a Phase 2. Design Phase 2 before shipping Phase 1 so you know what you're deferring and why.

---

### Lesson 8: Metrics that matter for skill extraction

We measure:
- `tool_calls` — how many actions the subagent took
- `complexity_score` — calculated from tools, error recovery, multi-domain work
- `invocation_count` — how many times a skill was re-used

We don't measure:
- User satisfaction with extracted skills
- Accuracy of skill descriptions vs. actual behavior
- Whether extracted skills reduce future subagent time

**The gap:** We're measuring *extraction activity* but not *extraction quality*. A skill could be extracted on every qualifying subagent completion and be completely useless. We'd only know if we tracked whether skills actually got used and whether they worked.

**Fix for Phase 2:** Add a `skill_outcome` field to meta.json. After each invocation, record: success, failure, or partial. Aggregate this for promotion decisions.

---

## Adaptation Lessons

### Lesson 9: Don't port features. Port problems solved.

The first instinct when adapting Hermes was: "What features does Hermes have that we don't?" Then we tried to implement each missing feature.

This is the wrong approach. The right approach: "What problems does Hermes solve? What are the simplest possible solutions to those problems in our environment?"

Hermes solves the problem of subagent knowledge dying with the session. Our solution (skill extraction) is the same problem. But Hermes's specific implementation (manifest files, version numbers, dependency tracking) was designed for a different scale and user expectation. We adapted the *solution to the problem*, not the feature itself.

**The test:** If you remove a feature from your adaptation and the core problem is still solved, the feature was overhead.

---

### Lesson 10: External systems have context you can't see

Hermes Agent is an open-source project. We read the code, the docs, the README. But we don't see:
- How the team actually uses it day-to-day
- What failures they've hit and fixed
- What features were removed after user complaints
- What the original design assumptions were

We adapted Hermes's *described* behavior, not its *actual* behavior. There's a gap there.

**Mitigation:** Assume the external system has good reasons for its constraints. When you reject something from an external system, say "we're rejecting X because [our reason]" — not "X seems unnecessary."

---

### Lesson 11: Documenting the process is worth it

Writing this "making-of" set of documents took significant time. Was it worth it?

Yes — for three reasons:

1. **Future-us benefits.** In 6 months, when we want to add Phase 2 features, we'll have the context to understand why Phase 1 was designed this way.

2. **The process improves the process.** Writing the COUNCIL_TRANSCRIPT.md required reliving the debate. We discovered gaps in the decision rationale while writing it — things we thought were resolved but weren't.

3. **Others can learn.** If Wahaj wants to explain to someone how we built this, we have a story, not just a codebase.

**The meta-lesson:** Documentation is not a deliverable. It's a thinking tool. Write it for yourself, not for an audience.

---

## Summary: Do These Things / Don't Do These Things

### Do

- ✅ Run a council with distinct, irreducible perspectives
- ✅ Give the moderator authority to cut debates
- ✅ Document the why alongside the what
- ✅ Split trigger logic from extraction logic
- ✅ Use draft mode instead of notification mode
- ✅ Ship Phase 1 as a prototype, not a finished product
- ✅ Port problems solved, not features implemented
- ✅ Assume external systems have reasons for their constraints

### Don't

- ❌ Let council Round 2 run too long (cut technical debates early)
- ❌ Assume Phase 1 is complete (it's a prototype)
- ❌ Measure activity instead of outcomes
- ❌ Port features because they exist in the source — port them because they solve problems
- ❌ Skip the rationale when documenting decisions
- ❌ Build notification systems when draft/invisible modes exist

---

## What's Next

Phase 2 is queued. Known improvements:
- Skill outcome tracking (success/failure per invocation)
- Auto-demotion for failing skills
- Usage analytics per skill
- Better naming (human-readable, collision-resistant)

The council will reconvene for Phase 2 design when Phase 1 has enough real-world data to evaluate.

---

*Lessons learned on 2026-04-17 by Observer subagent. May these learnings survive context resets.*