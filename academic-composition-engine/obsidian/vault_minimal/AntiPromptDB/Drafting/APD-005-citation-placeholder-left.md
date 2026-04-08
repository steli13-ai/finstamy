---
entry_kind: anti_prompt
id: APD-005
stage: drafting
severity: critical
tags: [drafting, citations, unresolved]
status: active
problem_pattern: Rămân tokeni CITE nereziolvați în textul final.
symptoms:
  - "[CITE:"
  - "TODO citation"
why_this_is_bad: Face secțiunea nepublicabilă și blochează exportul final curat.
devil_advocate_checks:
  - Toți tokenii [CITE:*] au chei rezolvate?
  - Există intrări unresolved în citation_resolution?
counter_instruction: Rulează citation resolver și remediază explicit intrările nereziolvate.
reject_conditions:
  - token cite ramas in draft final
---

Reject hard dacă apare în pre-export.
