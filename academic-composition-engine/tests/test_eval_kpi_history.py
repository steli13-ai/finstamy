from __future__ import annotations

import json
from pathlib import Path

from app.eval.history import load_kpi_history
from app.eval.reporting import load_kpi_snapshot, promote_release_kpis, save_eval_report


def _sample_summary(**overrides):
    payload = {
        "generated_at": "2026-04-08T00:00:00Z",
        "cases_total": 2,
        "unsupported_claim_rate": 0.02,
        "citation_resolution_rate": 0.97,
        "avg_language_score": 0.91,
        "fallback_rate": 0.1,
        "first_pass_acceptance_rate": 0.5,
        "useful_red_flags": None,
        "total_red_flags": 6,
        "false_positives": None,
        "useful_red_flag_rate": None,
        "false_positive_rate": None,
        "recommendation_distribution": {"pass": 1, "review": 1, "revise": 0},
        "reports_with_material_issue": 1,
        "avg_score_total": 3.5,
        "devils_advocate_feedback_status": "pending_feedback",
    }
    payload.update(overrides)
    return payload


def test_save_eval_report_writes_kpi_snapshot_and_history(tmp_path: Path):
    reports_dir = tmp_path / "eval" / "reports"
    report_dir = save_eval_report(
        summary=_sample_summary(),
        cases=[{"case_id": "c1", "metrics": {}}, {"case_id": "c2", "metrics": {}}],
        reports_dir=reports_dir,
    )

    snapshot_path = report_dir / "kpi_snapshot.json"
    assert snapshot_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["report_id"] == report_dir.name
    assert snapshot["cases_count"] == 2
    assert snapshot["useful_red_flags"] is None
    assert snapshot["false_positive_rate"] is None

    history = load_kpi_history(reports_dir=reports_dir)
    assert len(history) == 1
    assert history[0]["report_id"] == report_dir.name


def test_load_kpi_snapshot_is_stable_and_history_is_not_duplicated(tmp_path: Path):
    reports_dir = tmp_path / "eval" / "reports"
    report_dir = save_eval_report(
        summary=_sample_summary(),
        cases=[{"case_id": "c1", "metrics": {}}],
        reports_dir=reports_dir,
    )
    report_id = report_dir.name

    first = load_kpi_snapshot(report_id, reports_dir=reports_dir)
    second = load_kpi_snapshot(report_id, reports_dir=reports_dir)

    assert first["report_id"] == second["report_id"]
    history = load_kpi_history(reports_dir=reports_dir)
    assert len(history) == 1


def test_promote_release_kpis_writes_version_file(tmp_path: Path):
    reports_dir = tmp_path / "eval" / "reports"
    report_dir = save_eval_report(
        summary=_sample_summary(),
        cases=[{"case_id": "c1", "metrics": {}}],
        reports_dir=reports_dir,
    )

    out = promote_release_kpis(report=report_dir.name, version="v0.1.5", reports_dir=reports_dir)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["version"] == "v0.1.5"
    assert payload["snapshot"]["report_id"] == report_dir.name
