from pathlib import Path
import json
from importlib.metadata import version as pkg_version
import typer
from langgraph.types import Command

from app.graph.graph import build_graph
from app.services.run_artifacts import (
    build_language_qa_summary,
    create_run_id,
    persist_pending_review,
    persist_run_language_summary,
    persist_review_decision,
    persist_run_artifacts,
)
from app.services.languagetool_client import analyze_text
from app.eval.runner import run_eval_cases
from app.eval.reporting import (
    compare_reports,
    evaluate_comparison_gate,
    load_report,
    promote_baseline,
    resolve_base_report,
)

app = typer.Typer(no_args_is_help=True, invoke_without_command=True)


@app.callback()
def app_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Afișează versiunea CLI și oprește execuția."),
):
    if version:
        typer.echo(f"academic-composition-engine {pkg_version('academic-composition-engine')}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        raise typer.Exit(0)


def _project_dir(project_id: str) -> Path:
    return Path("data/projects") / project_id


def _thread_config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _extract_interrupt_payload(result: dict) -> dict | None:
    raw = result.get("__interrupt__")
    if not raw:
        return None
    first = raw[0]
    if isinstance(first, dict):
        return first
    value = getattr(first, "value", None)
    return value if isinstance(value, dict) else None


@app.command("init")
def init_project(project_id: str):
    p = _project_dir(project_id)
    for d in ["sources", "parsed", "retrieval", "evidence", "sections", "citations", "qa", "exports"]:
        (p / d).mkdir(parents=True, exist_ok=True)

    brief = p / "brief.md"
    if not brief.exists():
        brief.write_text("# Brief\n\nDescrie tema aici.\n", encoding="utf-8")

    refs = p / "references.json"
    if not refs.exists():
        refs.write_text(json.dumps([{"id": "smith2020"}, {"id": "doe2021"}], indent=2), encoding="utf-8")

    eval_cases = Path("eval/cases")
    eval_cases.mkdir(parents=True, exist_ok=True)
    sample_case = eval_cases / "case_demo_s1.json"
    if not sample_case.exists():
        sample_case.write_text(
            json.dumps(
                {
                    "case_id": "case_demo_s1",
                    "project_id": project_id,
                    "section_id": "s1",
                    "use_ollama": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    typer.echo(f"OK init: {p}")


@app.command("run-section")
def run_section(
    project_id: str,
    section_id: str = "s1",
    use_ollama: bool = typer.Option(False, help="Activează generarea cu Ollama pentru nodurile de planning/writing."),
    ollama_model: str = typer.Option("qwen3:8b", help="Modelul Ollama folosit când use_ollama=true."),
    ollama_host: str = typer.Option("http://localhost:11434", help="Host Ollama local."),
    embedding_model: str = typer.Option("nomic-embed-text", help="Modelul de embedding folosit pentru indexare/retrieval."),
    docling_host: str = typer.Option("http://localhost:5001", help="Host pentru serviciul Docling."),
    grobid_host: str = typer.Option("http://localhost:8070", help="Host pentru serviciul GROBID."),
    languagetool_host: str = typer.Option("http://localhost:8081", help="Host pentru LanguageTool."),
    auto_approve_gates: bool = typer.Option(False, help="Aprobă automat toate gate-urile umane."),
):
    p = _project_dir(project_id)
    for d in ["sources", "parsed", "retrieval", "evidence", "sections", "citations", "qa", "exports"]:
        (p / d).mkdir(parents=True, exist_ok=True)
    brief_path = p / "brief.md"
    brief_raw = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    run_id = create_run_id()

    graph = build_graph()
    input_snapshot = {
        "project_id": project_id,
        "project_dir": str(p),
        "run_id": run_id,
        "target_section_id": section_id,
        "brief_raw": brief_raw,
        "bibliography_snapshot_path": str(p / "references.json"),
        "use_ollama": use_ollama,
        "ollama_model": ollama_model,
        "ollama_host": ollama_host,
        "embedding_model": embedding_model,
        "docling_host": docling_host,
        "grobid_host": grobid_host,
        "languagetool_host": languagetool_host,
        "auto_approve_gates": auto_approve_gates,
    }

    result = graph.invoke(input_snapshot, config=_thread_config(run_id))

    (p / "intake.json").write_text(json.dumps(result.get("brief_structured", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "outline.json").write_text(json.dumps(result.get("outline", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "evidence" / f"{section_id}.json").write_text(json.dumps(result.get("evidence_packs", {}).get(section_id, {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "sections" / f"{section_id}.json").write_text(json.dumps(result.get("drafted_sections", {}).get(section_id, {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "sections" / f"{section_id}.md").write_text(result.get("drafted_sections", {}).get(section_id, {}).get("draft_markdown", ""), encoding="utf-8")
    (p / "citations" / f"{section_id}.json").write_text(json.dumps(result.get("citation_resolutions", {}).get(section_id, {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (p / "qa" / f"{section_id}.json").write_text(json.dumps(result.get("validation_reports", {}).get(section_id, {}), ensure_ascii=False, indent=2), encoding="utf-8")

    run_path = persist_run_artifacts(
        project_dir=str(p),
        run_id=run_id,
        section_id=section_id,
        input_snapshot=input_snapshot,
        result=result,
    )

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload:
        pending_path = persist_pending_review(
            project_dir=str(p),
            run_id=run_id,
            section_id=section_id,
            payload=interrupt_payload,
        )
        gate_name = interrupt_payload.get("gate_name", "unknown")
        typer.echo(
            f"REVIEW REQUIRED gate={gate_name} run={run_id} pending={pending_path} "
            f"next: ace review {project_id} {run_id} {section_id} --decision approve"
        )
        return

    typer.echo(f"OK run-section: export={result.get('export_path')} run={run_id} artifacts={run_path}")


@app.command("review")
def review_run(
    project_id: str,
    run_id: str,
    section_id: str,
    decision: str = typer.Option(..., help="approve | reject | edit_state"),
    patch_file: str | None = typer.Option(None, help="JSON patch file pentru decision=edit_state."),
    comment: str | None = typer.Option(None, help="Comentariu uman pentru gate."),
):
    p = _project_dir(project_id)
    graph = build_graph()

    patch = {}
    if decision == "edit_state" and patch_file:
        patch = json.loads(Path(patch_file).read_text(encoding="utf-8"))

    resume_payload = {
        "decision": decision,
        "patch": patch,
        "comment": comment,
    }

    result = graph.invoke(Command(resume=resume_payload), config=_thread_config(run_id))

    gate_name = (result.get("last_review_decision") or {}).get("gate_name", "unknown")
    decision_path = persist_review_decision(
        project_dir=str(p),
        run_id=run_id,
        section_id=section_id,
        gate_name=gate_name,
        decision_payload=resume_payload,
    )

    run_path = persist_run_artifacts(
        project_dir=str(p),
        run_id=run_id,
        section_id=section_id,
        input_snapshot={"resume": True, "project_id": project_id, "run_id": run_id},
        result=result,
    )

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload:
        pending_path = persist_pending_review(
            project_dir=str(p),
            run_id=run_id,
            section_id=section_id,
            payload=interrupt_payload,
        )
        next_gate = interrupt_payload.get("gate_name", "unknown")
        typer.echo(
            f"REVIEW REQUIRED gate={next_gate} run={run_id} pending={pending_path} decision_saved={decision_path}"
        )
        return

    typer.echo(f"OK review: run={run_id} decision_saved={decision_path} artifacts={run_path} export={result.get('export_path')}")


@app.command("export-docx")
def export_docx(project_id: str, section_id: str = "s1"):
    p = _project_dir(project_id)
    md = p / "sections" / f"{section_id}.md"
    if not md.exists():
        typer.echo("Lipsește markdown-ul secțiunii. Rulează `ace run-section`.")
        raise typer.Exit(1)
    typer.echo(f"Fișier disponibil: {md} (DOCX este creat în run-section dacă pandoc există).")


@app.command("run-eval")
def run_eval(cases_dir: str = "eval/cases", reports_dir: str = "eval/reports"):
    report = run_eval_cases(cases_dir=cases_dir, reports_dir=reports_dir)
    typer.echo(f"OK run-eval: {report}")


@app.command("eval-report")
def eval_report(
    latest: bool = typer.Option(False, "--latest", help="Încarcă ultimul raport disponibil."),
    use_baseline: bool = typer.Option(
        False,
        "--use-baseline",
        help="Shortcut: afișează raportul promovat în eval/reports/baseline.json.",
    ),
    report: str | None = typer.Option(None, help="ID/path raport dacă nu folosești --latest."),
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
):
    if latest and use_baseline:
        typer.echo("Conflict: folosește fie --latest, fie --use-baseline, nu ambele.")
        raise typer.Exit(1)

    if latest and report:
        typer.echo("Conflict: folosește fie --latest, fie --report <id>, nu ambele.")
        raise typer.Exit(1)

    report_ref = None
    if report:
        if use_baseline:
            typer.echo("Ai furnizat și --report; --use-baseline este ignorat.")
        report_ref = report
    elif use_baseline:
        try:
            report_ref, _, _ = resolve_base_report(
                base_report=None,
                use_baseline=True,
                reports_dir=reports_dir,
            )
        except FileNotFoundError:
            typer.echo(
                "Lipsește baseline valid. Rulează mai întâi: ace eval-promote-baseline --report <id>"
            )
            raise typer.Exit(1)
    elif latest:
        report_ref = "latest"
    else:
        report_ref = "latest"

    data = load_report(report_ref, reports_dir=reports_dir)
    summary = data["summary"]
    typer.echo(
        "\n".join(
            [
                f"report_id={data['report_id']}",
                f"report_dir={data['report_dir']}",
                f"cases_total={summary.get('cases_total')}",
                f"unsupported_claim_rate={summary.get('unsupported_claim_rate')}",
                f"citation_resolution_rate={summary.get('citation_resolution_rate')}",
                f"avg_language_score={summary.get('avg_language_score')}",
                f"fallback_rate={summary.get('fallback_rate')}",
                f"first_pass_acceptance_rate={summary.get('first_pass_acceptance_rate')}",
            ]
        )
    )


@app.command("eval-compare")
def eval_compare(
    base: str | None = typer.Option(None, help="Raport baseline (id/path/latest)."),
    use_baseline: bool = typer.Option(
        False,
        "--use-baseline",
        help="Shortcut: folosește baseline-ul curent din eval/reports/baseline.json.",
    ),
    target: str = typer.Option(..., help="Raport target (id/path/latest)."),
    threshold: float = typer.Option(0.01, help="Prag global pentru material change."),
    threshold_config: str | None = typer.Option(None, help="Fișier JSON cu praguri per metric."),
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
):
    try:
        resolved_base, base_source, warning = resolve_base_report(
            base_report=base,
            use_baseline=use_baseline,
            reports_dir=reports_dir,
        )
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    if warning:
        typer.echo(warning)

    cmp = compare_reports(
        base_report=resolved_base,
        target_report=target,
        reports_dir=reports_dir,
        threshold=threshold,
        threshold_config=threshold_config,
    )
    reg = cmp.get("regressions_summary", {})
    thresholds_used = cmp.get("thresholds_used", {})
    typer.echo(
        "\n".join(
            [
                f"compare={cmp.get('compare_path')}",
                f"base_source={base_source}",
                f"threshold_default={thresholds_used.get('default_threshold')}",
                f"threshold_config={thresholds_used.get('config_path')}",
                f"improved={reg.get('improved', [])}",
                f"unchanged={reg.get('unchanged', [])}",
                f"regressed={reg.get('regressed', [])}",
                f"material_case_changes={reg.get('material_case_changes', 0)}",
            ]
        )
    )


@app.command("eval-promote-baseline")
def eval_promote_baseline(
    report: str = typer.Option(..., help="Raport de promovat (id/path/latest)."),
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
):
    out = promote_baseline(report=report, reports_dir=reports_dir)
    typer.echo(f"OK eval-promote-baseline: {out}")


@app.command("eval-gate")
def eval_gate(
    base: str | None = typer.Option(None, help="Raport baseline (id/path/latest)."),
    use_baseline: bool = typer.Option(
        True,
        "--use-baseline",
        help="Implicit activ: folosește baseline-ul promovat dacă --base nu este dat.",
    ),
    target: str = typer.Option("latest", help="Raport target (id/path/latest)."),
    threshold: float = typer.Option(0.01, help="Prag global pentru material change."),
    threshold_config: str | None = typer.Option(None, help="Fișier JSON cu praguri per metric."),
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
    fail_on_material_case_changes: bool = typer.Option(
        True,
        help="Eșuează și la case-level material changes, nu doar la summary regressions.",
    ),
):
    try:
        resolved_base, base_source, warning = resolve_base_report(
            base_report=base,
            use_baseline=use_baseline,
            reports_dir=reports_dir,
        )
    except (ValueError, FileNotFoundError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    if warning:
        typer.echo(warning)

    cmp = compare_reports(
        base_report=resolved_base,
        target_report=target,
        reports_dir=reports_dir,
        threshold=threshold,
        threshold_config=threshold_config,
    )
    gate = evaluate_comparison_gate(
        cmp,
        fail_on_material_case_changes=fail_on_material_case_changes,
    )

    typer.echo(
        "\n".join(
            [
                f"gate_passed={gate.get('passed')}",
                f"base_source={base_source}",
                f"base={cmp.get('base_report')}",
                f"target={cmp.get('target_report')}",
                f"compare={cmp.get('compare_path')}",
                f"reasons={gate.get('reasons')}",
            ]
        )
    )

    if not gate.get("passed"):
        raise typer.Exit(2)


@app.command("qa-section")
def qa_section(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
    section_id: str = typer.Option(..., help="Section ID."),
    language: str = typer.Option("ro", help="Limba pentru verificare."),
    languagetool_host: str = typer.Option("http://localhost:8081", help="Host pentru LanguageTool."),
):
    p = _project_dir(project_id)
    section_dir = p / "runs" / run_id / "sections" / section_id
    draft_path = section_dir / "draft.md"
    if not draft_path.exists():
        fallback = p / "sections" / f"{section_id}.md"
        if fallback.exists():
            draft_path = fallback
        else:
            typer.echo(f"Draft inexistent pentru section={section_id} în run={run_id}.")
            raise typer.Exit(1)

    text = draft_path.read_text(encoding="utf-8")
    report = analyze_text(text, language=language, host=languagetool_host)
    report_payload = {"section_id": section_id, **report}

    section_dir.mkdir(parents=True, exist_ok=True)
    out_path = section_dir / "language_qa_report.json"
    out_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    typer.echo(f"OK qa-section: {out_path}")


@app.command("qa-run")
def qa_run(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
):
    p = _project_dir(project_id)
    sections_root = p / "runs" / run_id / "sections"
    if not sections_root.exists():
        typer.echo(f"Run inexistent: {sections_root}")
        raise typer.Exit(1)

    reports: dict[str, dict] = {}
    for section_dir in sorted([d for d in sections_root.iterdir() if d.is_dir()]):
        rp = section_dir / "language_qa_report.json"
        if rp.exists():
            data = json.loads(rp.read_text(encoding="utf-8"))
            reports[section_dir.name] = data

    summary = build_language_qa_summary(reports)
    out_path = persist_run_language_summary(project_dir=str(p), run_id=run_id, summary=summary)
    typer.echo(f"OK qa-run: {out_path}")