from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.run_artifacts import (
    build_devils_advocate_kpi_summary,
    persist_devils_advocate_feedback,
    persist_devils_advocate_kpi_summary,
    section_run_dir,
)


def _write_report(path: Path, *, recommendation: str, score_total: int, red_flags: list[str], material: bool):
    path.write_text(
        json.dumps(
            {
                "section_id": "s1",
                "recommendation": recommendation,
                "score_total": score_total,
                "red_flags": red_flags,
                "is_material_issue": material,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_devils_advocate_kpi_summary_pending_feedback(tmp_path: Path):
    project_dir = tmp_path / "project"
    out_dir = section_run_dir(str(project_dir), "run_1", "s1")
    _write_report(
        out_dir / "devils_advocate_evidence_report.json",
        recommendation="review",
        score_total=4,
        red_flags=["rf1", "rf2"],
        material=True,
    )

    summary = build_devils_advocate_kpi_summary(project_dir=str(project_dir), run_id="run_1")

    assert summary["reports_total"] == 1
    assert summary["total_red_flags"] == 2
    assert summary["feedback_status"] == "pending_feedback"
    assert summary["useful_red_flags"] is None
    assert summary["false_positive_rate"] is None
    assert summary["recommendation_distribution"]["review"] == 1


def test_build_devils_advocate_kpi_summary_with_feedback_rates(tmp_path: Path):
    project_dir = tmp_path / "project"
    out_dir = section_run_dir(str(project_dir), "run_2", "s1")
    _write_report(
        out_dir / "devils_advocate_evidence_report.json",
        recommendation="revise",
        score_total=7,
        red_flags=["rf1", "rf2", "rf3", "rf4"],
        material=True,
    )

    persist_devils_advocate_feedback(
        project_dir=str(project_dir),
        run_id="run_2",
        section_id="s1",
        stage="evidence",
        confirmed_useful=2,
        false_positive=1,
        ignored=1,
        notes="operator feedback",
    )

    summary = build_devils_advocate_kpi_summary(project_dir=str(project_dir), run_id="run_2")

    assert summary["feedback_status"] == "complete"
    assert summary["useful_red_flags"] == 2
    assert summary["false_positives"] == 1
    assert summary["total_red_flags"] == 4
    assert summary["useful_red_flag_rate"] == 0.5
    assert summary["false_positive_rate"] == 0.25
    assert summary["recommendation_distribution"]["revise"] == 1


def test_persist_devils_advocate_feedback_validates_totals(tmp_path: Path):
    project_dir = tmp_path / "project"
    out_dir = section_run_dir(str(project_dir), "run_3", "s1")
    _write_report(
        out_dir / "devils_advocate_report.json",
        recommendation="review",
        score_total=3,
        red_flags=["rf1"],
        material=False,
    )

    with pytest.raises(ValueError):
        persist_devils_advocate_feedback(
            project_dir=str(project_dir),
            run_id="run_3",
            section_id="s1",
            stage="drafting",
            confirmed_useful=1,
            false_positive=1,
            ignored=0,
        )


def test_persist_devils_advocate_kpi_summary_writes_file(tmp_path: Path):
    project_dir = tmp_path / "project"
    out_dir = section_run_dir(str(project_dir), "run_4", "s1")
    _write_report(
        out_dir / "devils_advocate_evidence_report.json",
        recommendation="pass",
        score_total=1,
        red_flags=[],
        material=False,
    )

    path = persist_devils_advocate_kpi_summary(project_dir=str(project_dir), run_id="run_4")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["reports_total"] == 1
    assert payload["recommendation_distribution"]["pass"] == 1
