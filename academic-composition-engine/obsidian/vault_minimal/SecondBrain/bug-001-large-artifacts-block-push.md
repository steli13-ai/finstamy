---
entry_kind: second_brain
id: SB-BUG-001
type: bug
tags: [git, artifacts, workaround]
status: active
context: Push blocat de GitHub file size limits (>100MB).
decision: Excludere fermă a artefactelor generate (`runs`, `checkpoints`, `*.sqlite`) din tracking.
why: Artefactele runtime trebuie regenerate, nu versionate.
alternatives_considered:
  - Git LFS pentru toate artefactele
impact: Repo curat, push stabil, release fără blocaje de dimensiune.
related_files:
  - .gitignore
---

Workaround validat: amend commit + retag când apar fișiere mari în istoric local.
