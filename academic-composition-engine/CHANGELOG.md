# Changelog

## [0.1.1-unreleased]

### Added
- Obsidian authoring integration layer (`client/parser/schemas/sync`) with compiled runtime snapshots in `app/knowledge/*`
- Consultative devil’s advocate service and optional graph integration (feature-flagged)
- Calibrated devil’s advocate scoring (`score_total`, `score_breakdown`, `top_issues`, `recommendation_reason`, `scoring_version`) with config-backed thresholds in `app/config/devils_advocate_scoring.json`
- Devil’s advocate KPI tracking (`useful_red_flags`, `total_red_flags`, `false_positives`, `useful_red_flag_rate`, `false_positive_rate`, `recommendation_distribution`, `reports_with_material_issue`, `avg_score_total`) via section feedback + run summary artifacts
- CLI commands: `review-devils-advocate`, `summarize-devils-advocate-kpis`
- `research-mcp` server with read-only tools: `google_search`, `youtube_search`, `reddit_search`
- VS Code MCP example configuration in `.vscode/mcp.json`
- CLI commands: `sync-obsidian-knowledge`, `inspect-anti-prompts`, `run-devils-advocate`
- Controlled Research Intake pipeline with candidate queue + explicit triage + accepted-only ingest (`discover-sources`, `triage-source`, `ingest-accepted-sources`)

## [0.1.0] - 2026-04-07

### Added
- End-to-end section workflow via LangGraph
- CLI commands for `init`, `run-section`, `review`, `export-docx`
- Docling-first ingestion with GROBID/local fallbacks
- LanceDB indexing and retrieval with lexical fallback
- Claim planning and section writing with optional Ollama runtime
- Deterministic citation resolution and evidence validation
- Run artifact persistence and provenance tracking
- Human review gates with pause/resume via persistent checkpointer
- Final language QA reports per section and per run (consultative)
- Eval harness with report generation (`summary.json`, `cases.json`)
- Baseline promotion and comparison workflow
- Regression gate command (`eval-gate`) and CI integration
- Golden fixture (`demo_golden`) and smoke tests for CLI flow

### Changed
- Runtime architecture aligned to evidence-grounded section flow
- Evaluation reports moved to directory-based format with summary and case breakdown
- Compare flow supports thresholds, baseline shortcuts, and material-change classification
- `eval-report` supports `--use-baseline` shortcut with conflict handling

### Fixed
- Packaging issue for eval runner in editable installs
- CLI conflict handling for `latest` / `report` / `baseline` combinations
- Baseline resolution for both legacy and directory-based report formats
- Concurrent state update issue on `node_traces` in LangGraph state channels

### Notes
- This release is the first daily-usable MVP.
- Obsidian is not part of runtime path in `0.1.0`.
- GROBID remains a fallback parser in the MVP.
