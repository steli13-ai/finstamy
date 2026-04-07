from __future__ import annotations

from app.graph.state import ProjectState
from app.services.languagetool_client import analyze_text


def _summarize(reports: dict) -> dict:
    section_ids = sorted(reports.keys())
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
    for section_id in section_ids:
        report = reports.get(section_id, {})
        score = report.get("score")
        if isinstance(score, (int, float)):
            scores.append(score)
        counts = report.get("counts", {})
        high = int(counts.get("high", 0))
        low = int(counts.get("low", 0))
        medium = int(counts.get("medium", 0))
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


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    language = state.get("brief_structured", {}).get("language", "ro")
    host = state.get("languagetool_host", "http://localhost:8081")
    draft = state.get("drafted_sections", {}).get(sid, {}).get("draft_markdown", "")

    report = analyze_text(draft, language=language, host=host)
    section_report = {
        "section_id": sid,
        **report,
    }

    all_reports = dict(state.get("language_qa_reports", {}))
    all_reports[sid] = section_report
    summary = _summarize(all_reports)

    return {
        "language_qa_reports": all_reports,
        "language_qa_summary": summary,
    }
