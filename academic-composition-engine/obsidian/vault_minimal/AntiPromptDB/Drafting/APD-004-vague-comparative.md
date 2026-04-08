---
entry_kind: anti_prompt
id: APD-004
stage: drafting
severity: medium
tags: [drafting, vagueness, comparative]
status: active
problem_pattern: Comparații vagi (mai bun, mai eficient, mai relevant) fără criterii.
symptoms:
  - mai bun
  - mai eficient
  - mai relevant
why_this_is_bad: Introduce ambiguitate și reduce verificabilitatea concluziilor.
devil_advocate_checks:
  - Comparația are metrică, dimensiune sau context clar?
  - Există sursă pentru comparație?
counter_instruction: Înlocuiește comparativele vagi cu metrică și context.
reject_conditions:
  - comparatie fara criteriu
---

Preferă afirmații cu unități măsurabile sau delimitări metodologice.
