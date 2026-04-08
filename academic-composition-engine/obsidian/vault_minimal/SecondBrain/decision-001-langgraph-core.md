---
entry_kind: second_brain
id: SB-DEC-001
type: decision
tags: [architecture, langgraph, runtime]
status: active
context: Definirea motorului principal al pipeline-ului academic.
decision: LangGraph rămâne motorul principal pentru orchestration + checkpoint + HITL.
why: Oferă flux determinist, persistent state și reluare sigură.
alternatives_considered:
  - orchestrare ad-hoc în CLI
  - mutare orchestration în Obsidian plugin
impact: Stabilitate ridicată și auditabilitate pentru run artifacts.
related_files:
  - app/graph/graph.py
  - app/graph/state.py
---

Decizie de bază pentru continuitatea roadmap-ului v0.1.x.
