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
- `ace qa-section`
- `ace qa-run`
- `ace run-eval`
- `ace eval-report`
- `ace eval-promote-baseline`
- `ace eval-compare`
- `ace eval-gate`
- `ace --version`

## 9) Troubleshooting
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
