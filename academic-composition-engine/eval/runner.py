from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

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
        }

        result = graph.invoke(input_snapshot)
        persist_run_artifacts(
            project_dir=str(project_dir),
            run_id=run_id,
            section_id=section_id,
            input_snapshot=input_snapshot,
            result=result,
        )

        metrics = build_metrics(result, section_id)
        rows.append(
            {
                "case_id": case.get("case_id", case_file.stem),
                "project_id": project_id,
                "section_id": section_id,
                "run_id": run_id,
                "metrics": metrics,
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
    }

    report = {"summary": summary, "cases": rows}
    report_path = reports_path / f"eval_report_{summary['generated_at'].replace(':', '').replace('-', '')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path
