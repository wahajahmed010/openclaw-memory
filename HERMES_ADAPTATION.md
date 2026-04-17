# Hermes Adaptation — Auto-Skill Pipeline

## Overview
Adapting Hermes Agent's self-improving skill system to Buck.

## Council Decision
Three LLMs analyzed Hermes and negotiated this implementation:
- Mnemosyne (kimi-k2.5): Architecture and safety guardrails
- Sibyl (minimax-m2.7): UX and automation principles
- Fabricator (gemma4:31b): Implementation feasibility

## Phase 1: Auto-Skill Pipeline (Current)

### Features
- Auto-extract skills from subagent completion
- DRAFT → ACTIVE lifecycle
- Promotion after 3 successful re-invocations
- User control: confirm / edit / dismiss

### How It Works
1. Subagent completes task (3+ tool calls)
2. Skill Extractor analyzes transcript
3. DRAFT skill created in skills/auto-draft/
4. On 3 re-invocations: promoted to skills/auto/
5. User can browse, edit, or delete anytime

### Usage
```bash
# List auto-created skills
ls skills/auto/

# Review draft skills
ls skills/auto-draft/

# Manual promotion
./scripts/skill-lifecycle.py promote {skill-name}
```

### Safety
- 24-hour review window for subagent-created skills
- DRAFT mode prevents clutter
- Auto-archive after 7 days unused
- User always curates final skill library

## Future Phases
- Phase 2: Memory compression, Progressive Manifest
- Phase 3: Usage pattern learning, skill pruning
- Phase 4: True progressive disclosure (pending OpenClaw core)

## Credits
Inspired by [Hermes Agent](https://github.com/NousResearch/Hermes-Agent) by Nous Research.
