from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def section_run_dir(project_dir: str, run_id: str, section_id: str) -> Path:
    path = Path(project_dir) / "runs" / run_id / "sections" / section_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_root_dir(project_dir: str, run_id: str) -> Path:
    root = Path(project_dir) / "runs" / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_metrics(result: dict, section_id: str) -> dict:
    validation = result.get("validation_reports", {}).get(section_id, {})
    citations = result.get("citation_resolutions", {}).get(section_id, {})
    retrieval_runs = result.get("retrieval_runs", [])
    parser_diag = result.get("parser_diagnostics", [])
    export_path = result.get("export_path") or ""
    language_report = result.get("language_qa_reports", {}).get(section_id, {})

    candidates = []
    reranked = []
    for run in retrieval_runs:
        if run.get("section_id") != section_id:
            continue
        if isinstance(run.get("candidates"), list):
            candidates = run["candidates"]
        if isinstance(run.get("reranked"), list):
            reranked = run["reranked"]

    precision_at_k = None
    if reranked:
        k = min(10, len(reranked))
        good = sum(1 for row in reranked[:k] if float(row.get("score", 0.0)) > 0)
        precision_at_k = good / k if k else None

    fallback_count = sum(1 for item in parser_diag if item.get("parser") != "docling")
    fallback_rate = (fallback_count / len(parser_diag)) if parser_diag else 0.0

    first_pass_acceptance_rate = 1.0 if validation.get("status") == "ok" else 0.0
    unresolved = citations.get("unresolved", [])
    resolved = citations.get("resolved_citations", [])
    total_citations = len(unresolved) + len(resolved)
    language_counts = language_report.get("counts", {})
    language_issue_count = int(language_counts.get("low", 0)) + int(language_counts.get("medium", 0)) + int(language_counts.get("high", 0))
    high_severity_count = int(language_counts.get("high", 0))
    language_score = language_report.get("score")
    devils_report = result.get("devils_advocate_evidence_reports", {}).get(section_id) or result.get("devils_advocate_reports", {}).get(section_id, {})
    devils_score_total = devils_report.get("score_total") if isinstance(devils_report, dict) else None
    devils_recommendation = devils_report.get("recommendation") if isinstance(devils_report, dict) else None
    devils_material_issue = devils_report.get("is_material_issue") if isinstance(devils_report, dict) else None

    return {
        "unsupported_claim_rate": validation.get("unsupported_claim_rate"),
        "citation_resolution_rate": validation.get("citation_resolution_rate"),
        "source_precision_at_k": precision_at_k,
        "fallback_rate": fallback_rate,
        "first_pass_acceptance_rate": first_pass_acceptance_rate,
        "human_edit_minutes_per_section": None,
        "docx_export_defects": 0 if export_path.endswith(".docx") else 1,
        "retrieved_candidates": len(candidates),
        "reranked_candidates": len(reranked),
        "total_citations": total_citations,
        "language_issue_count": language_issue_count,
        "high_severity_count": high_severity_count,
        "language_score": language_score,
        "devils_advocate_score_total": devils_score_total,
        "devils_advocate_recommendation": devils_recommendation,
        "devils_advocate_is_material_issue": devils_material_issue,
    }


def _red_flags_count(report: dict) -> int:
    red_flags = report.get("red_flags", []) if isinstance(report, dict) else []
    if isinstance(red_flags, list):
        return len(red_flags)
    return 0


def persist_devils_advocate_feedback(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    stage: str,
    confirmed_useful: int,
    false_positive: int,
    ignored: int,
    notes: str | None = None,
    issue_feedback: list[dict] | None = None,
    actor: str | None = None,
) -> Path:
    out_dir = section_run_dir(project_dir, run_id, section_id)
    feedback_path = out_dir / "devils_advocate_feedback.json"

    report_file = "devils_advocate_evidence_report.json" if stage == "evidence" else "devils_advocate_report.json"
    report = _read_json(out_dir / report_file) or {}
    total_red_flags = _red_flags_count(report)
    total_marked = int(confirmed_useful) + int(false_positive) + int(ignored)
    if total_red_flags > 0 and total_marked > total_red_flags:
        raise ValueError("Suma confirmed_useful + false_positive + ignored depășește total_red_flags.")

    payload = _read_json(feedback_path)
    if not isinstance(payload, dict):
        payload = {
            "run_id": run_id,
            "section_id": section_id,
            "updated_at": utc_now_iso(),
            "stages": {},
        }

    stages = payload.get("stages", {}) if isinstance(payload.get("stages"), dict) else {}
    stages[stage] = {
        "updated_at": utc_now_iso(),
        "actor": actor,
        "total_red_flags": total_red_flags,
        "confirmed_useful": int(confirmed_useful),
        "false_positive": int(false_positive),
        "ignored": int(ignored),
        "notes": notes,
        "issue_feedback": issue_feedback or [],
        "feedback_status": "provided",
    }

    payload["stages"] = stages
    payload["updated_at"] = utc_now_iso()
    _write_json(feedback_path, payload)
    return feedback_path


def _ensure_devils_advocate_feedback_template(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    drafting_report: dict,
    evidence_report: dict,
) -> Path:
    out_dir = section_run_dir(project_dir, run_id, section_id)
    feedback_path = out_dir / "devils_advocate_feedback.json"
    existing = _read_json(feedback_path)
    if isinstance(existing, dict):
        return feedback_path

    stages = {}
    if isinstance(drafting_report, dict) and drafting_report:
        stages["drafting"] = {
            "updated_at": utc_now_iso(),
            "total_red_flags": _red_flags_count(drafting_report),
            "confirmed_useful": None,
            "false_positive": None,
            "ignored": None,
            "notes": None,
            "issue_feedback": [],
            "feedback_status": "pending_feedback",
        }
    if isinstance(evidence_report, dict) and evidence_report:
        stages["evidence"] = {
            "updated_at": utc_now_iso(),
            "total_red_flags": _red_flags_count(evidence_report),
            "confirmed_useful": None,
            "false_positive": None,
            "ignored": None,
            "notes": None,
            "issue_feedback": [],
            "feedback_status": "pending_feedback",
        }

    template = {
        "run_id": run_id,
        "section_id": section_id,
        "updated_at": utc_now_iso(),
        "stages": stages,
    }
    _write_json(feedback_path, template)
    return feedback_path


def build_devils_advocate_kpi_summary(*, project_dir: str, run_id: str) -> dict:
    root = run_root_dir(project_dir, run_id)
    sections_root = root / "sections"

    summary = {
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "reports_total": 0,
        "reports_with_material_issue": 0,
        "avg_score_total": None,
        "recommendation_distribution": {"pass": 0, "review": 0, "revise": 0},
        "useful_red_flags": None,
        "total_red_flags": 0,
        "false_positives": None,
        "useful_red_flag_rate": None,
        "false_positive_rate": None,
        "feedback_status": "pending_feedback",
        "feedback_reports_count": 0,
        "reports_without_feedback": 0,
        "stage_breakdown": {},
    }

    if not sections_root.exists():
        return summary

    stages = {
        "drafting": "devils_advocate_report.json",
        "evidence": "devils_advocate_evidence_report.json",
    }

    score_values: list[float] = []
    recommendation_counter: Counter = Counter()
    stage_acc = {
        stage: {
            "reports_total": 0,
            "reports_with_material_issue": 0,
            "recommendation_distribution": {"pass": 0, "review": 0, "revise": 0},
            "avg_score_total": None,
            "score_values": [],
        }
        for stage in stages
    }

    total_red_flags_all = 0
    useful_sum = 0
    false_positive_sum = 0
    red_flags_with_feedback = 0
    feedback_reports_count = 0
    reports_without_feedback = 0

    for section_dir in sorted(sections_root.iterdir()):
        if not section_dir.is_dir():
            continue
        feedback_payload = _read_json(section_dir / "devils_advocate_feedback.json") or {}
        stage_feedback = feedback_payload.get("stages", {}) if isinstance(feedback_payload, dict) else {}

        for stage, report_name in stages.items():
            report = _read_json(section_dir / report_name)
            if not isinstance(report, dict) or not report:
                continue

            summary["reports_total"] += 1
            stage_acc[stage]["reports_total"] += 1

            total_red_flags = _red_flags_count(report)
            total_red_flags_all += total_red_flags

            recommendation = str(report.get("recommendation", "")).lower()
            if recommendation in {"pass", "review", "revise"}:
                recommendation_counter[recommendation] += 1
                stage_acc[stage]["recommendation_distribution"][recommendation] += 1

            if bool(report.get("is_material_issue")):
                summary["reports_with_material_issue"] += 1
                stage_acc[stage]["reports_with_material_issue"] += 1

            score_total = report.get("score_total")
            if isinstance(score_total, (int, float)):
                score_values.append(float(score_total))
                stage_acc[stage]["score_values"].append(float(score_total))

            feedback = stage_feedback.get(stage, {}) if isinstance(stage_feedback, dict) else {}
            if feedback.get("feedback_status") == "provided":
                feedback_reports_count += 1
                confirmed = feedback.get("confirmed_useful")
                false_positive = feedback.get("false_positive")
                if isinstance(confirmed, int):
                    useful_sum += confirmed
                if isinstance(false_positive, int):
                    false_positive_sum += false_positive
                red_flags_with_feedback += total_red_flags
            else:
                reports_without_feedback += 1

    summary["total_red_flags"] = total_red_flags_all
    summary["avg_score_total"] = (sum(score_values) / len(score_values)) if score_values else None
    summary["recommendation_distribution"] = {
        "pass": recommendation_counter.get("pass", 0),
        "review": recommendation_counter.get("review", 0),
        "revise": recommendation_counter.get("revise", 0),
    }

    summary["feedback_reports_count"] = feedback_reports_count
    summary["reports_without_feedback"] = reports_without_feedback

    if feedback_reports_count == 0:
        summary["feedback_status"] = "pending_feedback"
        summary["useful_red_flags"] = None
        summary["false_positives"] = None
        summary["useful_red_flag_rate"] = None
        summary["false_positive_rate"] = None
    else:
        summary["feedback_status"] = "complete" if reports_without_feedback == 0 else "partial_feedback"
        summary["useful_red_flags"] = useful_sum
        summary["false_positives"] = false_positive_sum
        denom = red_flags_with_feedback
        summary["useful_red_flag_rate"] = (useful_sum / denom) if denom > 0 else None
        summary["false_positive_rate"] = (false_positive_sum / denom) if denom > 0 else None

    stage_breakdown = {}
    for stage, payload in stage_acc.items():
        scores = payload.pop("score_values")
        payload["avg_score_total"] = (sum(scores) / len(scores)) if scores else None
        stage_breakdown[stage] = payload
    summary["stage_breakdown"] = stage_breakdown
    return summary


def persist_devils_advocate_kpi_summary(*, project_dir: str, run_id: str) -> Path:
    summary = build_devils_advocate_kpi_summary(project_dir=project_dir, run_id=run_id)
    root = run_root_dir(project_dir, run_id)
    path = root / "devils_advocate_kpi_summary.json"
    _write_json(path, summary)
    return path


def build_language_qa_summary(language_reports: dict) -> dict:
    section_ids = sorted(language_reports.keys())
    if not section_ids:
        return {
            "sections": 0,
            "avg_language_score": None,
            "sections_with_high_issues": 0,
            "total_language_issues": 0,
        }

    scores = []
    sections_with_high = 0
    total_issues = 0
    for sid in section_ids:
        report = language_reports.get(sid, {})
        score = report.get("score")
        if isinstance(score, (int, float)):
            scores.append(score)
        counts = report.get("counts", {})
        low = int(counts.get("low", 0))
        medium = int(counts.get("medium", 0))
        high = int(counts.get("high", 0))
        if high > 0:
            sections_with_high += 1
        total_issues += low + medium + high

    avg_score = (sum(scores) / len(scores)) if scores else None
    return {
        "sections": len(section_ids),
        "avg_language_score": avg_score,
        "sections_with_high_issues": sections_with_high,
        "total_language_issues": total_issues,
    }


def persist_run_language_summary(*, project_dir: str, run_id: str, summary: dict) -> Path:
    root = run_root_dir(project_dir, run_id)
    path = root / "language_qa_summary.json"
    _write_json(path, summary)
    return path


def persist_run_artifacts(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    input_snapshot: dict,
    result: dict,
) -> Path:
    out_dir = section_run_dir(project_dir, run_id, section_id)

    retrieval_trace = [
        r for r in result.get("retrieval_runs", []) if r.get("section_id") == section_id
    ]
    evidence_pack = result.get("evidence_packs", {}).get(section_id, {})
    claim_plan = result.get("claim_plans", {}).get(section_id, {})
    drafted = result.get("drafted_sections", {}).get(section_id, {})
    citation_resolution = result.get("citation_resolutions", {}).get(section_id, {})
    validation_report = result.get("validation_reports", {}).get(section_id, {})
    parser_diagnostics = result.get("parser_diagnostics", [])
    node_trace = result.get("node_traces", [])
    language_report = result.get("language_qa_reports", {}).get(section_id, {})
    devils_advocate_report = result.get("devils_advocate_reports", {}).get(section_id, {})
    devils_advocate_evidence_report = result.get("devils_advocate_evidence_reports", {}).get(section_id, {})
    language_summary = result.get("language_qa_summary") or build_language_qa_summary(result.get("language_qa_reports", {}))
    metrics = build_metrics(result, section_id)

    _write_json(out_dir / "input_snapshot.json", input_snapshot)
    _write_json(out_dir / "parser_diagnostics.json", parser_diagnostics)
    _write_json(out_dir / "retrieval_trace.json", retrieval_trace)
    _write_json(out_dir / "evidence_pack.json", evidence_pack)
    _write_json(out_dir / "claim_plan.json", claim_plan)
    _write_text(out_dir / "draft.md", drafted.get("draft_markdown", ""))
    _write_json(out_dir / "citation_resolution.json", citation_resolution)
    _write_json(out_dir / "validation_report.json", validation_report)
    _write_json(out_dir / "metrics.json", metrics)
    _write_json(out_dir / "node_trace.json", node_trace)
    _write_json(out_dir / "human_decisions.json", result.get("human_decisions", []))
    _write_json(out_dir / "edited_state_patches.json", result.get("edited_state_patches", []))
    _write_json(out_dir / "language_qa_report.json", language_report)
    _write_json(out_dir / "devils_advocate_report.json", devils_advocate_report)
    _write_json(out_dir / "devils_advocate_evidence_report.json", devils_advocate_evidence_report)
    _ensure_devils_advocate_feedback_template(
        project_dir=project_dir,
        run_id=run_id,
        section_id=section_id,
        drafting_report=devils_advocate_report,
        evidence_report=devils_advocate_evidence_report,
    )
    persist_devils_advocate_kpi_summary(project_dir=project_dir, run_id=run_id)
    persist_run_language_summary(project_dir=project_dir, run_id=run_id, summary=language_summary)

    hashes = {}
    for file_name in [
        "input_snapshot.json",
        "parser_diagnostics.json",
        "retrieval_trace.json",
        "evidence_pack.json",
        "claim_plan.json",
        "draft.md",
        "citation_resolution.json",
        "validation_report.json",
        "metrics.json",
        "node_trace.json",
        "human_decisions.json",
        "edited_state_patches.json",
        "language_qa_report.json",
        "devils_advocate_report.json",
        "devils_advocate_evidence_report.json",
        "devils_advocate_feedback.json",
    ]:
        p = out_dir / file_name
        hashes[file_name] = _sha256(p)

    _write_json(out_dir / "artifact_hashes.json", hashes)
    return out_dir


def persist_pending_review(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    payload: dict,
) -> Path:
    out_dir = section_run_dir(project_dir, run_id, section_id)
    path = out_dir / "pending_review.json"
    _write_json(path, payload)
    return path


def persist_review_decision(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    gate_name: str,
    decision_payload: dict,
) -> Path:
    out_dir = section_run_dir(project_dir, run_id, section_id)
    reviews_dir = out_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    path = reviews_dir / f"{gate_name}.decision.json"
    _write_json(path, decision_payload)
    return path


def persist_candidate_source_artifacts(
    *,
    project_dir: str,
    run_id: str,
    section_id: str,
    queue: list[dict],
    report: dict,
) -> tuple[Path, Path]:
    out_dir = section_run_dir(project_dir, run_id, section_id)
    queue_path = out_dir / "candidate_sources_queue.json"
    report_path = out_dir / "candidate_sources_report.json"
    _write_json(queue_path, queue)
    _write_json(report_path, report)
    return queue_path, report_path
