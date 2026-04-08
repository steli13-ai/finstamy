---
entry_kind: anti_prompt
id: APD-001
stage: drafting
severity: high
tags: [drafting, generic-writing, opener]
status: active
problem_pattern: Paragraful începe cu formulări academice goale, fără conținut verificabil.
symptoms:
  - in contextul actual
  - este important de mentionat
  - de-a lungul timpului
why_this_is_bad: Consumă spațiu fără valoare argumentativă și maschează lipsa dovezilor.
devil_advocate_checks:
  - Primul paragraf include cel puțin o afirmație ancorată în evidence pack?
  - Există un CITE token în primele două propoziții?
counter_instruction: Înlocuiește opener-ul generic cu afirmație specifică + dovadă trasabilă.
reject_conditions:
  - introducere fara niciun cite
  - paragraful 1 este 100% generic
---

Semnalează drafturile care par academice, dar nu spun nimic concret.
