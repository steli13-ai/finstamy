from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _history_root(reports_dir: Path | str = "eval/reports") -> Path:
    reports_root = Path(reports_dir)
    return reports_root.parent / "history"


def _history_file(reports_dir: Path | str = "eval/reports") -> Path:
    root = _history_root(reports_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "kpi_history.json"


def load_kpi_history(reports_dir: Path | str = "eval/reports") -> list[dict]:
    path = _history_file(reports_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return []


def append_kpi_history(snapshot: dict, reports_dir: Path | str = "eval/reports") -> Path:
    path = _history_file(reports_dir)
    history = load_kpi_history(reports_dir)

    snapshot_report_id = str(snapshot.get("report_id", ""))
    if snapshot_report_id and any(str(row.get("report_id", "")) == snapshot_report_id for row in history):
        return path

    compact = {
        "report_id": snapshot.get("report_id"),
        "created_at": snapshot.get("created_at"),
        "git_commit": snapshot.get("git_commit"),
        "git_ref": snapshot.get("git_ref"),
        "scoring_version": snapshot.get("scoring_version"),
        "thresholds_version": snapshot.get("thresholds_version"),
        "cases_count": snapshot.get("cases_count"),
        "unsupported_claim_rate": snapshot.get("unsupported_claim_rate"),
        "citation_resolution_rate": snapshot.get("citation_resolution_rate"),
        "avg_language_score": snapshot.get("avg_language_score"),
        "fallback_rate": snapshot.get("fallback_rate"),
        "first_pass_acceptance_rate": snapshot.get("first_pass_acceptance_rate"),
        "useful_red_flags": snapshot.get("useful_red_flags"),
        "total_red_flags": snapshot.get("total_red_flags"),
        "false_positives": snapshot.get("false_positives"),
        "useful_red_flag_rate": snapshot.get("useful_red_flag_rate"),
        "false_positive_rate": snapshot.get("false_positive_rate"),
        "recommendation_distribution": snapshot.get("recommendation_distribution"),
        "reports_with_material_issue": snapshot.get("reports_with_material_issue"),
        "avg_score_total": snapshot.get("avg_score_total"),
        "feedback_status": snapshot.get("feedback_status"),
    }

    history.append(compact)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def promote_release_snapshot(*, snapshot: dict, version: str, reports_dir: Path | str = "eval/reports") -> Path:
    clean_version = version.strip()
    if not clean_version:
        raise ValueError("version nu poate fi gol")

    root = _history_root(reports_dir)
    releases_dir = root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    out = releases_dir / f"{clean_version}.json"

    payload = {
        "version": clean_version,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": snapshot,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
