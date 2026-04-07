# v0.1.0 — First daily-usable MVP

This release marks the first usable MVP of the Evidence-Grounded Academic Composition Engine.

## What’s included

- End-to-end workflow for generating a section from brief + sources
- Persistent LangGraph execution with pause/resume and human review gates
- Docling-first ingestion with fallback parsers
- Retrieval, evidence packing, claim planning, drafting, citation resolution, validation, and export
- Run artifact persistence with provenance per section
- Language QA reports per section and per run (consultative)
- Evaluation reports, baseline promotion, comparison, and regression gating
- CI checks including eval execution and regression protection

## Why this matters

The system is no longer just a writing workflow. It is now a reproducible, evidence-grounded pipeline with:
- observable artifacts,
- measurable quality,
- protected regressions,
- operator-friendly CLI flows.

## Main commands

- `ace init`
- `ace run-section`
- `ace review`
- `ace qa-section`
- `ace qa-run`
- `ace run-eval`
- `ace eval-report`
- `ace eval-promote-baseline`
- `ace eval-compare`
- `ace eval-gate`

## Known limits in v0.1.0

- Language QA is consultative only
- No UI beyond CLI
- No MCP runtime layer
- No critic model in the default MVP flow
- Export polish still depends on template quality and Pandoc availability
