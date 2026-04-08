# Academic Composition Engine (MVP)

## 1) Ce este proiectul
Academic Composition Engine este un pipeline local-first pentru compunere academică orientată pe dovezi.
Primește brief + surse, construiește evidence packs pe secțiuni, generează draft cu citări rezolvate și exportă artefacte auditabile.
Produce atât output de secțiune, cât și rapoarte de evaluare/comparație între rulări.

## 2) Cerințe
- Python: `>=3.11`
- Ollama local (opțional, pentru writing/embeddings): `http://localhost:11434`
- Pandoc (opțional, pentru `.docx`; altfel fallback la `.md`)
- LanguageTool server (opțional, QA consultativ): `http://localhost:8081`

Dependențe Python sunt gestionate prin `pip install -e .` din `pyproject.toml`.

## 3) Quick Start (golden path)
```bash
cd /Users/Mary/Desktop/langgraf/academic-composition-engine

# 1) setup env + install
python3 -m venv /Users/Mary/Desktop/langgraf/.venv
source /Users/Mary/Desktop/langgraf/.venv/bin/activate
pip install -U pip
pip install -e .

# 2) init project
ace init demo

# 3) run section (fără gate-uri manuale)
ace run-section demo --section-id s1 --auto-approve-gates

# 4) QA pe run (înlocuiește RUN_ID cu valoarea din output-ul run-section)
ace qa-run demo --run-id <RUN_ID>

# 5) eval
ace run-eval
ace eval-report --latest
ace eval-gate --use-baseline --target latest --threshold-config eval/thresholds.json

# 6) baseline + compare
ace eval-promote-baseline --report <REPORT_ID_OR_latest>
ace eval-compare --use-baseline --target <REPORT_ID>
```

## 4) Human review flow (HITL)
Gate-urile sunt: `after_outline`, `after_evidence`, `pre_export`.

```bash
# pornește run-ul cu review manual
ace run-section demo --section-id s1

# rulează review până când nu mai apare "REVIEW REQUIRED"
ace review demo <RUN_ID> s1 --decision approve
ace review demo <RUN_ID> s1 --decision approve
ace review demo <RUN_ID> s1 --decision approve
```

Notă: comanda `review` folosește același `run_id` (thread_id/checkpoint) și reia exact execuția întreruptă.

## 5) Structura artefactelor
- Project data: `data/projects/<project_id>/`
- Run artifacts: `data/projects/<project_id>/runs/<run_id>/sections/<section_id>/`
- Exemple artefacte secțiune:
  - `input_snapshot.json`
  - `parser_diagnostics.json`
  - `retrieval_trace.json`
  - `evidence_pack.json`
  - `claim_plan.json`
  - `draft.md`
  - `citation_resolution.json`
  - `validation_report.json`
  - `language_qa_report.json`
  - `metrics.json`
  - `artifact_hashes.json`
- Summary QA per run: `data/projects/<project_id>/runs/<run_id>/language_qa_summary.json`
- Eval reports: `eval/reports/`
  - `<report_id>/summary.json`
  - `<report_id>/cases.json`
  - `latest.json`
  - `baseline.json`
  - `compare_<base>_vs_<target>.json`

## 6) Eval workflow
```bash
# raport curent
ace eval-report --latest

# raport baseline
ace eval-report --use-baseline

# compare cu prag global
ace eval-compare --use-baseline --target <REPORT_ID> --threshold 0.01

# compare cu praguri per metric
ace eval-compare --use-baseline --target <REPORT_ID> --threshold 0.01 --threshold-config eval/thresholds.json

# regression gate (pass/fail operațional)
ace eval-gate --use-baseline --target <REPORT_ID> --threshold-config eval/thresholds.json
```

Reguli compare:
- `unchanged` dacă delta este sub prag
- `improved` dacă depășește pragul în direcția bună
- `regressed` dacă depășește pragul în direcția rea

## 7) Release v0.1.0 checklist
- Flux complet validat: `init -> run-section -> review -> qa-run -> run-eval -> eval-gate`
- `eval-gate` trece cu baseline-ul promovat curent
- `eval/thresholds.json` este înghețat pentru release
- Smoke tests trec: `pytest -q tests/test_smoke_cli.py tests/test_eval_baseline.py`
- Artefactele de run sunt complete în `data/projects/<id>/runs/<run_id>/...`
- `README.md`, `CHANGELOG.md` și release notes sunt actualizate

## 8) Main commands
- `ace init`
- `ace run-section`
- `ace review`
- `ace sync-obsidian-knowledge`
- `ace inspect-anti-prompts`
- `ace run-devils-advocate`
- `ace discover-sources`
- `ace triage-source`
- `ace ingest-accepted-sources`
- `ace qa-section`
- `ace qa-run`
- `ace run-eval`
- `ace eval-report`
- `ace eval-promote-baseline`
- `ace eval-compare`
- `ace eval-gate`
- `ace --version`

## 9) Obsidian Authoring Layer (AntiPrompt DB + Second Brain)
Obsidian este strat de authoring, nu state store de runtime.
Runtime-ul consumă snapshot-uri JSON compilate în `app/knowledge/*`, nu citește direct vault-ul la fiecare execuție.

### 9.1 Structura notelor
Fiecare notă trebuie să aibă frontmatter YAML și `entry_kind`:
- `entry_kind: anti_prompt`
- `entry_kind: second_brain`

#### AntiPrompt DB (minim)
Frontmatter suportat:
- `id`, `stage`, `severity`, `tags`, `status`
- `problem_pattern`, `symptoms`, `why_this_is_bad`
- `devil_advocate_checks`, `counter_instruction`, `reject_conditions`

#### Second Brain (minim)
Frontmatter suportat:
- `id`, `type`, `tags`, `status`
- `context`, `decision`, `why`
- `alternatives_considered`, `impact`, `related_files`

### 9.2 Sync Obsidian -> snapshots
```bash
ace sync-obsidian-knowledge --vault-dir /path/catre/obsidian-vault
```

Pentru bootstrap rapid există un vault minim versionat în:
- `obsidian/vault_minimal/AntiPromptDB/Drafting` (10 note AntiPrompt)
- `obsidian/vault_minimal/SecondBrain` (5 note operaționale)

Template-uri concrete pentru authoring:
- `obsidian/templates/AntiPrompt-note-template.md`
- `obsidian/templates/Decision-note-template.md`
- `obsidian/templates/Playbook-note-template.md`
- `obsidian/templates/Bug-postmortem-template.md`

Output-uri compilate:
- `app/knowledge/anti_prompts/outline.json`
- `app/knowledge/anti_prompts/evidence.json`
- `app/knowledge/anti_prompts/drafting.json`
- `app/knowledge/anti_prompts/citation.json`
- `app/knowledge/second_brain/decisions.json`
- `app/knowledge/second_brain/playbooks.json`
- `app/knowledge/second_brain/bugs.json`
- `app/knowledge/second_brain/release_history.json`

## 10) Devil's Advocate (consultativ, gate-aware)
Devil’s advocate folosește AntiPrompt DB compilată și produce raport structurat auditabil.

Scoring calibrat (`v0.1.3`) este comun pentru `drafting` și `evidence`:
- `score_total = severity_weight_score + coverage_gap_score + weak_passage_score - confidence_signal_score`
- Praguri implicite: `pass <= 2`, `review 3..5`, `revise >= 6`
- Config stabil: `app/config/devils_advocate_scoring.json`
- Câmpuri noi în raport: `score_total`, `score_breakdown`, `top_issues`, `recommendation_reason`, `scoring_version`

- Activare în pipeline pe etapa evidence (feature-flag):
```bash
ace run-section demo --section-id s1 --enable-devils-advocate-evidence --anti-prompt-snapshot-dir app/knowledge/anti_prompts
```
- Rulare punctuală pe un run existent:
```bash
ace run-devils-advocate demo --run-id <RUN_ID> --section-id s1 --stage drafting
```

Artefact generat:
- `data/projects/<project_id>/runs/<run_id>/sections/<section_id>/devils_advocate_evidence_report.json`

## 11) Research MCP server (read-only)
Serverul MCP intern este `research-mcp` și expune exact 3 tool-uri:
- `google_search`
- `youtube_search`
- `reddit_search`

Pornire locală:
```bash
research-mcp
```

Alternativ:
```bash
python -m app.mcp.servers.research_server
```

Config VS Code exemplu: `.vscode/mcp.json` (fără secrete hardcodate).

Env vars opționale:
- `SERPER_API_KEY` pentru `google_search`
- `YOUTUBE_API_KEY` pentru `youtube_search`

Notă: toate tool-urile sunt read-only și orientate pe research/discovery.

## 11.2 Controlled Research Intake (v0.1.2)
Flux explicit (nu intră automat în `run-section`):

`discover -> normalize -> candidate queue -> triage -> accept/reject -> ingest accepted only`

Comenzi:
```bash
ace discover-sources demo --section-id s1 --query "evidence grounded writing" --channels google,youtube,reddit
ace triage-source demo --run-id <RUN_ID> --section-id s1 --candidate-id <CAND_ID> --decision accept --reason "relevant to RQ1"
ace ingest-accepted-sources demo --run-id <RUN_ID> --section-id s1
```

Artifacte per run/secțiune:
- `candidate_sources_queue.json` (starea completă)
- `candidate_sources_report.json` (sumar operațional)

Contract minim candidat:
- `candidate_id`, `section_id`, `source_type`, `discovery_channel`
- `citable_status` (`non_citable|needs_verification|candidate_academic`)
- `decision` (`pending|accepted|rejected`)
- `reason_for_keep_reject`, `mapped_questions`
- `title`, `url`, `snippet`, `source`, `raw_metadata`
- `created_at`, `triaged_at`

Reguli business în cod:
- `google`: de regulă `needs_verification` sau `candidate_academic`
- `youtube`: implicit `non_citable`
- `reddit`: implicit `non_citable`

Sursele YouTube/Reddit sunt tratate ca discovery/context, nu bibliografie directă.

## 11.1 Ritual de sync recomandat
Rulează sync-ul obligatoriu:
- după sesiuni importante în Obsidian;
- înainte de testarea `devil's advocate`;
- înainte de release.

Document operațional: `docs/obsidian_sync_ritual.md`.

## 12) Troubleshooting
- Baseline lipsă:
  - rulează `ace eval-promote-baseline --report <id>`
- Conflict flag-uri:
  - `eval-report --latest --use-baseline` este invalid (alege una)
- Pandoc lipsă:
  - exportul cade pe `.md` în loc de `.docx`
- Ollama indisponibil:
  - pipeline-ul continuă cu fallback-uri deterministe
- Fallback-uri active:
  - verifică `parser_diagnostics.json`, `metrics.json`, `node_trace.json`
