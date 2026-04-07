from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from app.eval.reporting import save_eval_report
from app.graph.graph import build_graph
from app.services.run_artifacts import build_metrics, create_run_id, persist_run_artifacts, utc_now_iso


def run_eval_cases(cases_dir: Path | str = "eval/cases", reports_dir: Path | str = "eval/reports") -> Path:
    cases_path = Path(cases_dir)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    case_files = sorted(cases_path.glob("*.json"))
    graph = build_graph()
    rows = []

    for case_file in case_files:
        case = json.loads(case_file.read_text(encoding="utf-8"))
        project_id = case.get("project_id", "demo")
        section_id = case.get("section_id", "s1")
        project_dir = Path("data/projects") / project_id

        brief_path = project_dir / "brief.md"
        brief_raw = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
        run_id = create_run_id()

        input_snapshot = {
            "project_id": project_id,
            "project_dir": str(project_dir),
            "run_id": run_id,
            "target_section_id": section_id,
            "brief_raw": brief_raw,
            "bibliography_snapshot_path": str(project_dir / "references.json"),
            "use_ollama": bool(case.get("use_ollama", False)),
            "ollama_model": case.get("ollama_model", "qwen3:8b"),
            "ollama_host": case.get("ollama_host", "http://localhost:11434"),
            "embedding_model": case.get("embedding_model", "nomic-embed-text"),
            "docling_host": case.get("docling_host", "http://localhost:5001"),
            "grobid_host": case.get("grobid_host", "http://localhost:8070"),
            "languagetool_host": case.get("languagetool_host", "http://localhost:8081"),
            "auto_approve_gates": True,
        }

        result = graph.invoke(input_snapshot, config={"configurable": {"thread_id": run_id}})
        persist_run_artifacts(
            project_dir=str(project_dir),
            run_id=run_id,
            section_id=section_id,
            input_snapshot=input_snapshot,
            result=result,
        )

        metrics = build_metrics(result, section_id)
        grouped_metrics = {
            "evidence_metrics": {
                "unsupported_claim_rate": metrics.get("unsupported_claim_rate"),
                "source_precision_at_k": metrics.get("source_precision_at_k"),
            },
            "citation_metrics": {
                "citation_resolution_rate": metrics.get("citation_resolution_rate"),
                "total_citations": metrics.get("total_citations"),
            },
            "language_qa_metrics": {
                "language_score": metrics.get("language_score"),
                "language_issue_count": metrics.get("language_issue_count"),
                "high_severity_count": metrics.get("high_severity_count"),
            },
            "fallback_usage": {
                "fallback_rate": metrics.get("fallback_rate"),
                "first_pass_acceptance_rate": metrics.get("first_pass_acceptance_rate"),
            },
        }
        rows.append(
            {
                "case_id": case.get("case_id", case_file.stem),
                "project_id": project_id,
                "section_id": section_id,
                "run_id": run_id,
                "metrics": metrics,
                "metric_groups": grouped_metrics,
            }
        )

    def avg(metric_name: str):
        values = [r["metrics"].get(metric_name) for r in rows]
        numeric = [v for v in values if isinstance(v, (int, float))]
        return mean(numeric) if numeric else None

    summary = {
        "generated_at": utc_now_iso(),
        "cases_total": len(rows),
        "unsupported_claim_rate": avg("unsupported_claim_rate"),
        "citation_resolution_rate": avg("citation_resolution_rate"),
        "source_precision_at_k": avg("source_precision_at_k"),
        "fallback_rate": avg("fallback_rate"),
        "first_pass_acceptance_rate": avg("first_pass_acceptance_rate"),
        "human_edit_minutes_per_section": avg("human_edit_minutes_per_section"),
        "docx_export_defects": avg("docx_export_defects"),
        "avg_language_score": avg("language_score"),
        "sections_with_high_issues": avg("high_severity_count"),
        "total_language_issues": avg("language_issue_count"),
    }

    report_path = save_eval_report(summary=summary, cases=rows, reports_dir=reports_path)
    return report_path
