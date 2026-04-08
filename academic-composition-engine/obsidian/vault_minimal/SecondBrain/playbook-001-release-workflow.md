---
entry_kind: second_brain
id: SB-PLAY-001
type: playbook
tags: [release, operations, checklist]
status: active
context: Publicare release stabilă fără regresii.
decision: Rulează preflight + eval gate înainte de tag/push release.
why: Reduce riscul de publish cu regressions sau artefacte generate.
alternatives_considered:
  - release rapid fără gate
impact: Predictibilitate operațională și calitate constantă.
related_files:
  - scripts/release_preflight_v0.1.0.sh
  - eval/thresholds.json
  - README.md
---

Playbook minim: compile/test/eval/gate înainte de publicare.
