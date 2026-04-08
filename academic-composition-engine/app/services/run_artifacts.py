from __future__ import annotations

import hashlib
import json
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
    }


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
