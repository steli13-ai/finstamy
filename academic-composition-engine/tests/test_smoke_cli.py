from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    ace_path = Path(sys.executable).parent / "ace"
    cmd = [str(ace_path), *args]
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def _extract_run_id(output: str) -> str | None:
    match = re.search(r"run=([A-Za-z0-9_:\-\.\+]+)", output)
    return match.group(1) if match else None


def _latest_eval_report_id(reports_dir: Path) -> str:
    latest = reports_dir / "latest.json"
    if latest.exists():
        data = json.loads(latest.read_text(encoding="utf-8"))
        rid = data.get("report_id")
        if isinstance(rid, str) and rid:
            return rid
    candidates = sorted([p.name for p in reports_dir.iterdir() if p.is_dir() and p.name.startswith("eval_")])
    assert candidates, "Nu există raport eval disponibil"
    return candidates[-1]


def test_1_init_creates_project_structure():
    repo = Path(__file__).resolve().parents[1]
    project_id = f"demo_smoke_{int(time.time())}"

    proc = _run_cli(["init", project_id], cwd=repo)
    assert proc.returncode == 0, proc.stderr

    project_dir = repo / "data" / "projects" / project_id
    assert project_dir.exists()
    for folder in ["sources", "parsed", "retrieval", "evidence", "sections", "citations", "qa", "exports"]:
        assert (project_dir / folder).exists(), f"Lipsește folder: {folder}"


def test_2_run_section_autoapproved_golden():
    repo = Path(__file__).resolve().parents[1]
    project_id = "demo_golden"

    init_proc = _run_cli(["init", project_id], cwd=repo)
    assert init_proc.returncode == 0, init_proc.stderr

    proc = _run_cli(["run-section", project_id, "--section-id", "s1", "--auto-approve-gates"], cwd=repo)
    assert proc.returncode == 0, proc.stderr

    run_id = _extract_run_id(proc.stdout)
    assert run_id, f"Nu am putut extrage run_id din output:\n{proc.stdout}"

    section_dir = repo / "data" / "projects" / project_id / "runs" / run_id / "sections" / "s1"
    assert section_dir.exists()

    expected_required = json.loads(
        (repo / "data" / "projects" / project_id / "expected" / "expected_sections.json").read_text(encoding="utf-8")
    )["required_artifacts"]
    for filename in expected_required:
        assert (section_dir / filename).exists(), f"Lipsește artefact: {filename}"

    citation_data = json.loads((section_dir / "citation_resolution.json").read_text(encoding="utf-8"))
    min_citations = json.loads(
        (repo / "data" / "projects" / project_id / "expected" / "expected_citation_keys.json").read_text(encoding="utf-8")
    )["minimum_resolved_citations"]
    assert len(citation_data.get("resolved_citations", [])) >= min_citations

    metrics = json.loads((section_dir / "metrics.json").read_text(encoding="utf-8"))
    threshold = json.loads(
        (repo / "data" / "projects" / project_id / "expected" / "expected_min_metrics.json").read_text(encoding="utf-8")
    )

    assert float(metrics.get("citation_resolution_rate", 0.0)) >= float(threshold["citation_resolution_rate_min"])
    assert float(metrics.get("unsupported_claim_rate", 1.0)) <= float(threshold["unsupported_claim_rate_max"])
    assert float(metrics.get("language_score", 0.0)) >= float(threshold["language_score_min"])
    assert float(metrics.get("fallback_rate", 1.0)) <= float(threshold["fallback_rate_max"])


def test_3_review_flow_manual_pause_resume():
    repo = Path(__file__).resolve().parents[1]
    project_id = "demo_golden"

    proc = _run_cli(["run-section", project_id, "--section-id", "s1"], cwd=repo)
    assert proc.returncode == 0, proc.stderr
    assert "REVIEW REQUIRED" in proc.stdout

    run_id = _extract_run_id(proc.stdout)
    assert run_id, f"Nu am putut extrage run_id din output:\n{proc.stdout}"

    section_dir = repo / "data" / "projects" / project_id / "runs" / run_id / "sections" / "s1"
    assert (section_dir / "pending_review.json").exists()

    for _ in range(4):
        review_proc = _run_cli(["review", project_id, run_id, "s1", "--decision", "approve"], cwd=repo)
        assert review_proc.returncode == 0, review_proc.stderr
        if "OK review:" in review_proc.stdout:
            break

    reviews_dir = section_dir / "reviews"
    assert reviews_dir.exists()
    decisions = list(reviews_dir.glob("*.decision.json"))
    assert len(decisions) >= 1


def test_4_run_eval_writes_reports():
    repo = Path(__file__).resolve().parents[1]
    reports_dir = repo / "eval" / "reports"

    proc = _run_cli(["run-eval"], cwd=repo)
    assert proc.returncode == 0, proc.stderr

    report_id = _latest_eval_report_id(reports_dir)
    report_dir = reports_dir / report_id
    assert (report_dir / "summary.json").exists()
    assert (report_dir / "cases.json").exists()
    assert (reports_dir / "latest.json").exists()


def test_5_baseline_and_compare_outputs():
    repo = Path(__file__).resolve().parents[1]
    reports_dir = repo / "eval" / "reports"
    target_id = _latest_eval_report_id(reports_dir)

    promote = _run_cli(["eval-promote-baseline", "--report", target_id], cwd=repo)
    assert promote.returncode == 0, promote.stderr
    assert (reports_dir / "baseline.json").exists()

    compare = _run_cli(["eval-compare", "--use-baseline", "--target", target_id], cwd=repo)
    assert compare.returncode == 0, compare.stderr

    compare_files = sorted(reports_dir.glob("compare_*.json"))
    assert compare_files, "Nu s-a generat compare report"
    payload = json.loads(compare_files[-1].read_text(encoding="utf-8"))

    assert "summary_delta" in payload
    assert "regressions_summary" in payload
    assert "case_level_diff" in payload
