---
entry_kind: anti_prompt
id: APD-002
stage: drafting
severity: critical
tags: [drafting, claims, unsupported]
status: active
problem_pattern: Afirmații ferme formulate ca adevăruri, fără suport explicit.
symptoms:
  - este evident ca
  - fara indoiala
  - demonstreaza clar
why_this_is_bad: Creează risc de halucinație academică și reduce credibilitatea textului.
devil_advocate_checks:
  - Fiecare claim ferm are chunk suport asociat?
  - Formularea poate fi moderată fără pierdere de sens?
counter_instruction: Convertește certitudinea absolută în formulare calibrată și adaugă citare.
reject_conditions:
  - claim ferm fara chunk suport
---

Aplică mai ales la secțiuni cu multe concluzii sintetice.
