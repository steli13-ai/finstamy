---
entry_kind: second_brain
id: SB-PLAY-002
type: playbook
tags: [eval, baseline, policy]
status: active
context: Controlul regresiilor între iterații.
decision: Baseline oficial se promovează doar după run validat și gate pass.
why: Evită drift-ul accidental al standardului de calitate.
alternatives_considered:
  - baseline automat după fiecare run
impact: Stabilitate în comparații și semnal clar pentru regresii.
related_files:
  - app/eval/reporting.py
  - eval/reports/baseline.json
---

Policy: `run-eval` + `eval-gate` pentru orice schimbare nouă.
