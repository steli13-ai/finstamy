#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/Mary/Desktop/langgraf/academic-composition-engine"
VENV_ACTIVATE="/Users/Mary/Desktop/langgraf/.venv/bin/activate"

cd "$PROJECT_ROOT"
source "$VENV_ACTIVATE"

echo "[1/7] Version"
ace --version

echo "[2/7] Syntax compile check"
python -m compileall app

echo "[3/7] Git whitespace check"
git diff --check

echo "[4/7] Tests"
pytest -q tests/test_smoke_cli.py tests/test_eval_baseline.py

echo "[5/7] Generate eval report"
ace run-eval

echo "[6/7] Resolve latest report id"
REPORT_ID=$(python - <<'PY'
import json
from pathlib import Path
p = Path('eval/reports/latest.json')
if not p.exists():
    raise SystemExit('latest.json missing after run-eval')
print(json.loads(p.read_text(encoding='utf-8'))['report_id'])
PY
)
echo "latest report_id=$REPORT_ID"

echo "[7/7] Eval gate"
ace eval-gate --use-baseline --target "$REPORT_ID" --threshold-config eval/thresholds.json

echo "Pre-flight PASSED for v0.1.0"

echo "--- Next manual release steps ---"
echo "git status --short"
echo "git add . && git commit -m 'release: v0.1.0'"
echo "git tag -a v0.1.0 -m 'v0.1.0'"
echo "git push origin <branch_curent> && git push origin v0.1.0"
