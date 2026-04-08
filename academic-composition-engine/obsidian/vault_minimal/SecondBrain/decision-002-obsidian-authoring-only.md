---
entry_kind: second_brain
id: SB-DEC-002
type: decision
tags: [obsidian, knowledge, boundaries]
status: active
context: Introducerea layer-ului Obsidian fără destabilizare runtime.
decision: Obsidian este authoring layer; runtime consumă doar snapshot-uri compilate.
why: Evităm dependențe haotice de vault și menținem reproducibilitatea.
alternatives_considered:
  - runtime direct pe markdown-uri din vault
impact: Critical path rămâne stabil, local-first și testabil.
related_files:
  - app/integrations/obsidian/sync.py
  - app/knowledge/anti_prompts/drafting.json
---

Separare strictă authoring vs execution.
