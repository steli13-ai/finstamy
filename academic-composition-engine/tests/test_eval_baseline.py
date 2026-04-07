from pathlib import Path
import json

import pytest

from app.eval.reporting import resolve_base_report, load_report, evaluate_comparison_gate


def test_resolve_base_missing_baseline(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileNotFoundError):
        resolve_base_report(base_report=None, use_baseline=True, reports_dir=reports_dir)


def test_resolve_base_explicit_overrides_use_baseline(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "baseline.json").write_text(
        json.dumps({"baseline_report_id": "eval_a", "path": str(reports_dir / "eval_a")}),
        encoding="utf-8",
    )

    base, source, warning = resolve_base_report(
        base_report="eval_explicit",
        use_baseline=True,
        reports_dir=reports_dir,
    )

    assert base == "eval_explicit"
    assert source == "explicit"
    assert warning is not None


def test_load_report_supports_legacy_and_directory(tmp_path: Path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    legacy = reports_dir / "eval_report_legacy.json"
    legacy.write_text(
        json.dumps(
            {
                "summary": {"cases_total": 1},
                "cases": [{"case_id": "c1", "metrics": {}}],
            }
        ),
        encoding="utf-8",
    )

    directory = reports_dir / "eval_new"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps({"cases_total": 1}), encoding="utf-8")
    (directory / "cases.json").write_text(json.dumps([{"case_id": "c2", "metrics": {}}]), encoding="utf-8")

    loaded_legacy = load_report(str(legacy), reports_dir=reports_dir)
    loaded_dir = load_report("eval_new", reports_dir=reports_dir)

    assert loaded_legacy["report_id"] == "eval_report_legacy"
    assert loaded_dir["report_id"] == "eval_new"


def test_evaluate_comparison_gate_passes_on_no_regression():
    comparison = {
        "regressions_summary": {
            "improved": ["citation_resolution_rate"],
            "unchanged": ["fallback_rate"],
            "regressed": [],
            "material_case_changes": 0,
        }
    }
    result = evaluate_comparison_gate(comparison)
    assert result["passed"] is True
    assert result["reasons"] == []


def test_evaluate_comparison_gate_fails_on_regression():
    comparison = {
        "regressions_summary": {
            "improved": [],
            "unchanged": [],
            "regressed": ["avg_language_score"],
            "material_case_changes": 1,
        }
    }
    result = evaluate_comparison_gate(comparison)
    assert result["passed"] is False
    assert "regressed_metrics=['avg_language_score']" in result["reasons"][0]
