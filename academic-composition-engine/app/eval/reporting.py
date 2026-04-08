from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.eval.history import append_kpi_history, promote_release_snapshot


CORE_METRICS = {
    "unsupported_claim_rate": {"direction": "lower"},
    "citation_resolution_rate": {"direction": "higher"},
    "avg_language_score": {"direction": "higher"},
    "fallback_rate": {"direction": "lower"},
    "first_pass_acceptance_rate": {"direction": "higher"},
}

DEFAULT_METRIC_THRESHOLDS = {
    "unsupported_claim_rate": 0.005,
    "citation_resolution_rate": 0.01,
    "avg_language_score": 1.0,
    "fallback_rate": 0.02,
    "first_pass_acceptance_rate": 0.01,
}


def make_report_id() -> str:
    return datetime.now(timezone.utc).strftime("eval_%Y%m%dT%H%M%SZ")


def _reports_root(reports_dir: Path | str = "eval/reports") -> Path:
    root = Path(reports_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_eval_report(*, summary: dict, cases: list[dict], reports_dir: Path | str = "eval/reports") -> Path:
    root = _reports_root(reports_dir)
    report_id = make_report_id()
    report_dir = root / report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    kpi_snapshot_path = report_dir / "kpi_snapshot.json"
    if not kpi_snapshot_path.exists():
        kpi_snapshot = build_kpi_snapshot(
            report_id=report_id,
            summary=summary,
            reports_dir=reports_dir,
        )
        kpi_snapshot_path.write_text(json.dumps(kpi_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        append_kpi_history(kpi_snapshot, reports_dir=reports_dir)

    latest_meta = {
        "report_id": report_id,
        "generated_at": summary.get("generated_at"),
        "path": str(report_dir),
    }
    (root / "latest.json").write_text(json.dumps(latest_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_dir


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_git(command: list[str]) -> str | None:
    try:
        value = subprocess.check_output(command, stderr=subprocess.DEVNULL, text=True).strip()
        return value or None
    except Exception:
        return None


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_baseline_reference(reports_dir: Path | str = "eval/reports") -> str | None:
    root = _reports_root(reports_dir)
    baseline_path = root / "baseline.json"
    if not baseline_path.exists():
        return None
    try:
        payload = _load_json(baseline_path)
    except Exception:
        return None
    baseline_id = payload.get("baseline_report_id")
    baseline_ref_path = payload.get("path")
    if isinstance(baseline_id, str) and baseline_id:
        return baseline_id
    if isinstance(baseline_ref_path, str) and baseline_ref_path:
        return baseline_ref_path
    return None


def _resolve_scoring_version() -> str | None:
    config_path = Path("app/config/devils_advocate_scoring.json")
    if not config_path.exists():
        return None
    try:
        payload = _load_json(config_path)
        value = payload.get("scoring_version")
        return str(value) if value is not None else None
    except Exception:
        return None


def _resolve_thresholds_version() -> str | None:
    threshold_path = Path("eval/thresholds.json")
    digest = _sha256_file(threshold_path)
    if not digest:
        return None
    return f"sha256:{digest[:12]}"


def build_kpi_snapshot(*, report_id: str, summary: dict, reports_dir: Path | str = "eval/reports") -> dict:
    return {
        "report_id": report_id,
        "created_at": summary.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "baseline_reference": _resolve_baseline_reference(reports_dir),
        "git_commit": _safe_git(["git", "rev-parse", "HEAD"]),
        "git_ref": _safe_git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "scoring_version": _resolve_scoring_version(),
        "thresholds_version": _resolve_thresholds_version(),
        "cases_count": summary.get("cases_total"),
        "unsupported_claim_rate": summary.get("unsupported_claim_rate"),
        "citation_resolution_rate": summary.get("citation_resolution_rate"),
        "avg_language_score": summary.get("avg_language_score"),
        "fallback_rate": summary.get("fallback_rate"),
        "first_pass_acceptance_rate": summary.get("first_pass_acceptance_rate"),
        "useful_red_flags": summary.get("useful_red_flags"),
        "total_red_flags": summary.get("total_red_flags"),
        "false_positives": summary.get("false_positives"),
        "useful_red_flag_rate": summary.get("useful_red_flag_rate"),
        "false_positive_rate": summary.get("false_positive_rate"),
        "recommendation_distribution": summary.get("recommendation_distribution"),
        "reports_with_material_issue": summary.get("reports_with_material_issue"),
        "avg_score_total": summary.get("avg_score_total", summary.get("avg_devils_advocate_score_total")),
        "feedback_status": summary.get("devils_advocate_feedback_status"),
    }


def load_kpi_snapshot(report: str, reports_dir: Path | str = "eval/reports") -> dict:
    report_dir = resolve_report_dir(report, reports_dir=reports_dir)
    path = report_dir / "kpi_snapshot.json"
    if not path.exists():
        loaded = load_report(report, reports_dir=reports_dir)
        snapshot = build_kpi_snapshot(
            report_id=loaded.get("report_id", report_dir.name),
            summary=loaded.get("summary", {}),
            reports_dir=reports_dir,
        )
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        append_kpi_history(snapshot, reports_dir=reports_dir)
        return snapshot
    return _load_json(path)


def resolve_report_dir(report: str, reports_dir: Path | str = "eval/reports") -> Path:
    root = _reports_root(reports_dir)
    report_path = Path(report)
    if report == "latest":
        latest = root / "latest.json"
        if not latest.exists():
            raise FileNotFoundError("Nu există latest.json în eval/reports.")
        return Path(_load_json(latest)["path"])
    if report_path.exists() and report_path.is_dir():
        return report_path
    candidate = root / report
    if candidate.exists() and candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"Raport inexistent: {report}")


def load_report(report: str, reports_dir: Path | str = "eval/reports") -> dict:
    report_path = Path(report)
    root = _reports_root(reports_dir)

    legacy_file = None
    if report_path.exists() and report_path.is_file():
        legacy_file = report_path
    else:
        candidate = root / report
        if candidate.exists() and candidate.is_file():
            legacy_file = candidate

    if legacy_file is not None:
        data = _load_json(legacy_file)
        if not isinstance(data, dict) or "summary" not in data or "cases" not in data:
            raise FileNotFoundError(f"Raport legacy invalid: {legacy_file}")
        return {
            "report_dir": str(legacy_file.parent),
            "report_id": legacy_file.stem,
            "summary": data.get("summary", {}),
            "cases": data.get("cases", []),
        }

    report_dir = resolve_report_dir(report, reports_dir=reports_dir)
    summary_path = report_dir / "summary.json"
    cases_path = report_dir / "cases.json"
    if not summary_path.exists() or not cases_path.exists():
        raise FileNotFoundError(f"Raport invalid (lipsesc summary/cases): {report_dir}")
    return {
        "report_dir": str(report_dir),
        "report_id": report_dir.name,
        "summary": _load_json(summary_path),
        "cases": _load_json(cases_path),
    }


def _delta(old, new):
    if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
        return None
    return new - old


def _load_threshold_config(threshold_config: str | None) -> dict:
    if not threshold_config:
        return {}
    path = Path(threshold_config)
    if not path.exists():
        return {}
    try:
        data = _load_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _resolve_thresholds(*, threshold: float, threshold_config: str | None) -> dict:
    config = _load_threshold_config(threshold_config)
    default_threshold = float(config.get("default_threshold", threshold))
    raw_metric_thresholds = config.get("metric_thresholds", {})
    metric_thresholds: dict[str, float] = {}
    if isinstance(raw_metric_thresholds, dict):
        for key, value in raw_metric_thresholds.items():
            if isinstance(value, (int, float)):
                metric_thresholds[str(key)] = float(value)

    for metric, default_value in DEFAULT_METRIC_THRESHOLDS.items():
        metric_thresholds.setdefault(metric, float(default_value))

    return {
        "default_threshold": default_threshold,
        "metric_thresholds": metric_thresholds,
        "config_path": threshold_config,
    }


def _threshold_for_metric(metric: str, thresholds: dict) -> float:
    metric_thresholds = thresholds.get("metric_thresholds", {}) if isinstance(thresholds, dict) else {}
    if metric in metric_thresholds:
        return float(metric_thresholds[metric])
    return float(thresholds.get("default_threshold", 0.01))


def _label_change(metric: str, delta_value: float | None, threshold_value: float) -> tuple[str, bool]:
    if delta_value is None or abs(delta_value) <= threshold_value:
        return "unchanged", False
    direction = CORE_METRICS.get(metric, {}).get("direction", "higher")
    if direction == "higher":
        return ("improved", True) if delta_value > 0 else ("regressed", True)
    return ("improved", True) if delta_value < 0 else ("regressed", True)


def _case_main_reason(base_metrics: dict, target_metrics: dict, thresholds: dict) -> tuple[str, bool]:
    watched = [
        "unsupported_claim_rate",
        "citation_resolution_rate",
        "language_score",
        "fallback_rate",
        "first_pass_acceptance_rate",
    ]
    best_metric = None
    best_abs_delta = -1.0
    best_label = "unchanged"
    has_material = False

    for metric in watched:
        d = _delta(base_metrics.get(metric), target_metrics.get(metric))
        if d is None:
            continue
        compare_metric = metric if metric != "language_score" else "avg_language_score"
        threshold_value = _threshold_for_metric(compare_metric, thresholds)
        label, is_material = _label_change(compare_metric, d, threshold_value)
        if is_material:
            has_material = True
        if abs(d) > best_abs_delta:
            best_abs_delta = abs(d)
            best_metric = metric
            best_label = label

    if best_metric is None:
        return "no_numeric_delta", False
    return f"{best_label}:{best_metric}", has_material


def compare_reports(
    *,
    base_report: str,
    target_report: str,
    reports_dir: Path | str = "eval/reports",
    threshold: float = 0.01,
    threshold_config: str | None = None,
) -> dict:
    base = load_report(base_report, reports_dir=reports_dir)
    target = load_report(target_report, reports_dir=reports_dir)
    thresholds = _resolve_thresholds(threshold=threshold, threshold_config=threshold_config)

    summary_delta = {}
    buckets = {"improved": [], "unchanged": [], "regressed": []}
    for metric in CORE_METRICS:
        old = base["summary"].get(metric)
        new = target["summary"].get(metric)
        d = _delta(old, new)
        threshold_value = _threshold_for_metric(metric, thresholds)
        label, is_material = _label_change(metric, d, threshold_value)
        summary_delta[metric] = {
            "base": old,
            "target": new,
            "delta": d,
            "status": label,
            "threshold": threshold_value,
            "is_material_change": is_material,
        }
        buckets[label].append(metric)

    base_by_case = {c.get("case_id"): c for c in base["cases"]}
    target_by_case = {c.get("case_id"): c for c in target["cases"]}
    case_ids = sorted(set(base_by_case.keys()) | set(target_by_case.keys()))

    case_diffs = []
    for case_id in case_ids:
        b = base_by_case.get(case_id)
        t = target_by_case.get(case_id)
        if not b or not t:
            case_diffs.append(
                {
                    "case_id": case_id,
                    "status": "added_or_removed",
                    "base": b,
                    "target": t,
                    "main_reason": "case_set_changed",
                }
            )
            continue

        b_metrics = b.get("metrics", {})
        t_metrics = t.get("metrics", {})
        main_reason, is_material_change = _case_main_reason(b_metrics, t_metrics, thresholds)
        case_diffs.append(
            {
                "case_id": case_id,
                "base_score": b_metrics.get("language_score"),
                "target_score": t_metrics.get("language_score"),
                "metric_delta": {
                    "unsupported_claim_rate": _delta(b_metrics.get("unsupported_claim_rate"), t_metrics.get("unsupported_claim_rate")),
                    "citation_resolution_rate": _delta(b_metrics.get("citation_resolution_rate"), t_metrics.get("citation_resolution_rate")),
                    "fallback_rate": _delta(b_metrics.get("fallback_rate"), t_metrics.get("fallback_rate")),
                    "first_pass_acceptance_rate": _delta(b_metrics.get("first_pass_acceptance_rate"), t_metrics.get("first_pass_acceptance_rate")),
                    "language_score": _delta(b_metrics.get("language_score"), t_metrics.get("language_score")),
                },
                "main_reason": main_reason,
                "is_material_change": is_material_change,
            }
        )

    material_case_changes = sum(1 for c in case_diffs if c.get("is_material_change") is True)

    comparison = {
        "base_report": base["report_id"],
        "target_report": target["report_id"],
        "thresholds_used": thresholds,
        "summary_delta": summary_delta,
        "regressions_summary": {
            "improved": buckets["improved"],
            "unchanged": buckets["unchanged"],
            "regressed": buckets["regressed"],
            "material_case_changes": material_case_changes,
        },
        "case_level_diff": case_diffs,
    }

    root = _reports_root(reports_dir)
    base_id = base["report_id"].replace("/", "_")
    target_id = target["report_id"].replace("/", "_")
    out = root / f"compare_{base_id}_vs_{target_id}.json"
    out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    comparison["compare_path"] = str(out)
    return comparison


def evaluate_comparison_gate(
    comparison: dict,
    *,
    fail_on_material_case_changes: bool = True,
) -> dict:
    reg = comparison.get("regressions_summary", {}) if isinstance(comparison, dict) else {}
    regressed_metrics = list(reg.get("regressed", [])) if isinstance(reg.get("regressed", []), list) else []
    material_case_changes = int(reg.get("material_case_changes", 0) or 0)

    reasons: list[str] = []
    if regressed_metrics:
        reasons.append(f"regressed_metrics={regressed_metrics}")
    if fail_on_material_case_changes and material_case_changes > 0:
        reasons.append(f"material_case_changes={material_case_changes}")

    passed = len(reasons) == 0
    return {
        "passed": passed,
        "reasons": reasons,
        "regressed_metrics": regressed_metrics,
        "material_case_changes": material_case_changes,
    }


def promote_baseline(report: str, reports_dir: Path | str = "eval/reports") -> Path:
    loaded = load_report(report, reports_dir=reports_dir)
    root = _reports_root(reports_dir)
    payload = {
        "baseline_report_id": loaded.get("report_id"),
        "path": loaded.get("report_dir"),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    out = root / "baseline.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def promote_release_kpis(*, report: str, version: str, reports_dir: Path | str = "eval/reports") -> Path:
    snapshot = load_kpi_snapshot(report, reports_dir=reports_dir)
    return promote_release_snapshot(snapshot=snapshot, version=version, reports_dir=reports_dir)


def resolve_base_report(
    *,
    base_report: str | None,
    use_baseline: bool,
    reports_dir: Path | str = "eval/reports",
) -> tuple[str, str, str | None]:
    if base_report:
        warning = None
        if use_baseline:
            warning = "Ai furnizat și --base; --use-baseline este ignorat."
        return base_report, "explicit", warning

    if not use_baseline:
        raise ValueError("Trebuie să furnizezi --base sau --use-baseline.")

    root = _reports_root(reports_dir)
    baseline_path = root / "baseline.json"
    if not baseline_path.exists():
        raise FileNotFoundError(
            "Lipsește eval/reports/baseline.json. Rulează mai întâi: ace eval-promote-baseline --report <id>"
        )

    payload = _load_json(baseline_path)
    baseline_id = payload.get("baseline_report_id")
    baseline_path_value = payload.get("path")

    if isinstance(baseline_path_value, str) and baseline_path_value:
        return baseline_path_value, "baseline", None
    if isinstance(baseline_id, str) and baseline_id:
        return baseline_id, "baseline", None

    raise FileNotFoundError(
        "baseline.json este invalid. Rulează din nou: ace eval-promote-baseline --report <id>"
    )
