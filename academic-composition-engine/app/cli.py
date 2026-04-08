from pathlib import Path
import json
from importlib.metadata import version as pkg_version
import typer
from langgraph.types import Command

from app.graph.graph import build_graph
from app.services.run_artifacts import (
    build_devils_advocate_kpi_summary,
    build_language_qa_summary,
    create_run_id,
    persist_devils_advocate_feedback,
    persist_devils_advocate_kpi_summary,
    persist_pending_review,
    persist_run_language_summary,
    persist_review_decision,
    persist_run_artifacts,
    persist_candidate_source_artifacts,
)
from app.services.candidate_sources import (
    build_candidate_entry,
    build_report as build_candidate_report,
    ingest_accepted_candidates,
    load_queue,
    save_queue,
    save_report,
    triage_candidate,
)
from app.services.languagetool_client import analyze_text
from app.services.devils_advocate import evaluate_stage, load_anti_prompt_snapshot
from app.integrations.obsidian.sync import compile_obsidian_knowledge
from app.mcp.servers.research_server import google_search, youtube_search, reddit_search
from app.eval.runner import run_eval_cases
from app.eval.history import load_kpi_history
from app.eval.reporting import (
    compare_reports,
    evaluate_comparison_gate,
    load_report,
    promote_baseline,
    promote_release_kpis,
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


def _parse_channels(raw: str) -> list[str]:
    channels = [c.strip().lower() for c in raw.split(",") if c.strip()]
    allowed = {"google", "youtube", "reddit"}
    invalid = [c for c in channels if c not in allowed]
    if invalid:
        raise ValueError(f"Canale invalide: {invalid}. Permise: google,youtube,reddit")
    return channels or ["google"]


@app.command("discover-sources")
def discover_sources(
    project_id: str,
    section_id: str = typer.Option("s1", help="Section ID."),
    query: str = typer.Option(..., help="Query de discovery."),
    channels: str = typer.Option("google,youtube,reddit", help="Canale CSV: google,youtube,reddit."),
    top_k: int = typer.Option(5, help="Limită rezultate per canal."),
    mapped_questions: str = typer.Option("", help="Întrebări mapate, separate prin |"),
    run_id: str | None = typer.Option(None, help="Run ID existent; dacă lipsește se creează unul nou."),
):
    p = _project_dir(project_id)
    for d in ["sources", "parsed", "retrieval", "evidence", "sections", "citations", "qa", "exports"]:
        (p / d).mkdir(parents=True, exist_ok=True)

    run_id = run_id or create_run_id()
    chosen_channels = _parse_channels(channels)
    mapped = [x.strip() for x in mapped_questions.split("|") if x.strip()]

    queue = load_queue(project_dir=str(p), run_id=run_id, section_id=section_id)
    discovered = 0

    for channel in chosen_channels:
        try:
            if channel == "google":
                results = google_search(query=query, top_k=top_k)
            elif channel == "youtube":
                results = youtube_search(query=query, max_results=top_k)
            else:
                results = reddit_search(query=query, limit=top_k)
        except Exception as exc:
            results = [
                {
                    "title": f"{channel} search failed",
                    "url": "",
                    "snippet": str(exc),
                    "source": channel,
                    "raw_metadata": {"error": str(exc)},
                }
            ]

        for row in results:
            queue.append(
                build_candidate_entry(
                    section_id=section_id,
                    discovery_channel=channel,
                    result=row,
                    mapped_questions=mapped,
                )
            )
            discovered += 1

    queue_path = save_queue(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue)
    report = build_candidate_report(section_id=section_id, queue=queue)
    report_path = save_report(project_dir=str(p), run_id=run_id, section_id=section_id, report=report)
    persist_candidate_source_artifacts(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue, report=report)

    typer.echo(
        f"OK discover-sources: run={run_id} section={section_id} discovered={discovered} "
        f"queue={queue_path} report={report_path}"
    )


@app.command("triage-source")
def triage_source(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
    section_id: str = typer.Option("s1", help="Section ID."),
    candidate_id: str = typer.Option(..., help="Candidate ID."),
    decision: str = typer.Option(..., help="accept|reject"),
    reason: str = typer.Option(..., help="Motiv explicit keep/reject."),
):
    p = _project_dir(project_id)
    normalized_decision = "accepted" if decision.strip().lower() == "accept" else "rejected"
    if decision.strip().lower() not in {"accept", "reject"}:
        typer.echo("decision trebuie să fie accept sau reject")
        raise typer.Exit(1)

    queue = load_queue(project_dir=str(p), run_id=run_id, section_id=section_id)
    try:
        queue = triage_candidate(
            queue=queue,
            candidate_id=candidate_id,
            decision=normalized_decision,
            reason=reason,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    queue_path = save_queue(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue)
    report = build_candidate_report(section_id=section_id, queue=queue)
    report_path = save_report(project_dir=str(p), run_id=run_id, section_id=section_id, report=report)
    persist_candidate_source_artifacts(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue, report=report)

    typer.echo(
        f"OK triage-source: run={run_id} section={section_id} candidate_id={candidate_id} "
        f"decision={normalized_decision} queue={queue_path} report={report_path}"
    )


@app.command("ingest-accepted-sources")
def ingest_accepted_sources_cmd(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
    section_id: str = typer.Option("s1", help="Section ID."),
):
    p = _project_dir(project_id)
    queue = load_queue(project_dir=str(p), run_id=run_id, section_id=section_id)
    written = ingest_accepted_candidates(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue)
    report = build_candidate_report(section_id=section_id, queue=queue)
    report_path = save_report(project_dir=str(p), run_id=run_id, section_id=section_id, report=report)
    persist_candidate_source_artifacts(project_dir=str(p), run_id=run_id, section_id=section_id, queue=queue, report=report)

    typer.echo(
        f"OK ingest-accepted-sources: run={run_id} section={section_id} ingested={len(written)} report={report_path}"
    )


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


@app.command("sync-obsidian-knowledge")
def sync_obsidian_knowledge(
    vault_dir: str = typer.Option(..., help="Directorul vault/folder Obsidian."),
    output_dir: str = typer.Option("app/knowledge", help="Output snapshot-uri compilate pentru runtime."),
    include_glob: str = typer.Option("**/*.md", help="Pattern note markdown incluse."),
    strict: bool = typer.Option(False, help="Eșuează la prima notă invalidă."),
):
    stats = compile_obsidian_knowledge(
        vault_dir=vault_dir,
        output_dir=output_dir,
        include_glob=include_glob,
        strict=strict,
    )
    typer.echo(
        "\n".join(
            [
                f"vault_dir={stats.vault_dir}",
                f"notes_scanned={stats.notes_scanned}",
                f"anti_prompts_compiled={stats.anti_prompts_compiled}",
                f"second_brain_compiled={stats.second_brain_compiled}",
                f"rejected_notes={stats.rejected_notes}",
                f"output_dir={stats.output_dir}",
            ]
        )
    )


@app.command("inspect-anti-prompts")
def inspect_anti_prompts(
    stage: str = typer.Option("drafting", help="outline | evidence | drafting | citation"),
    snapshot_dir: str = typer.Option("app/knowledge/anti_prompts", help="Director snapshot AntiPrompt DB."),
):
    snapshot = load_anti_prompt_snapshot(stage=stage, snapshot_dir=snapshot_dir)
    typer.echo(
        "\n".join(
            [
                f"stage={snapshot.get('stage')}",
                f"entries={len(snapshot.get('entries', []))}",
                f"source={snapshot.get('source')}",
                f"missing={snapshot.get('missing', False)}",
            ]
        )
    )


@app.command("run-devils-advocate")
def run_devils_advocate(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
    section_id: str = typer.Option("s1", help="Section ID."),
    stage: str = typer.Option("drafting", help="outline | evidence | drafting | citation"),
    snapshot_dir: str = typer.Option("app/knowledge/anti_prompts", help="Director snapshot AntiPrompt DB."),
):
    p = _project_dir(project_id)
    section_dir = p / "runs" / run_id / "sections" / section_id
    if not section_dir.exists():
        typer.echo(f"Section artifacts inexistente: {section_dir}")
        raise typer.Exit(1)

    draft_path = section_dir / "draft.md"
    evidence_path = section_dir / "evidence_pack.json"
    citation_path = section_dir / "citation_resolution.json"

    draft_text = draft_path.read_text(encoding="utf-8") if draft_path.exists() else ""
    evidence_pack = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else {}
    citation_resolution = json.loads(citation_path.read_text(encoding="utf-8")) if citation_path.exists() else {}

    report = evaluate_stage(
        section_id=section_id,
        stage=stage,
        draft_markdown=draft_text,
        evidence_pack=evidence_pack,
        citation_resolution=citation_resolution,
        snapshot_dir=snapshot_dir,
    )
    out_path = section_dir / "devils_advocate_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"OK run-devils-advocate: {out_path}")


@app.command("review-devils-advocate")
def review_devils_advocate(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
    section_id: str = typer.Option("s1", help="Section ID."),
    stage: str = typer.Option("evidence", help="evidence | drafting"),
    confirmed_useful: int = typer.Option(0, help="Număr semnale confirmate utile/reale."),
    false_positive: int = typer.Option(0, help="Număr semnale false positive."),
    ignored: int = typer.Option(0, help="Număr semnale ignorate."),
    notes: str | None = typer.Option(None, help="Notițe opționale operator."),
):
    normalized_stage = stage.strip().lower()
    if normalized_stage not in {"evidence", "drafting"}:
        typer.echo("stage trebuie să fie evidence sau drafting")
        raise typer.Exit(1)
    if min(confirmed_useful, false_positive, ignored) < 0:
        typer.echo("confirmed_useful/false_positive/ignored trebuie să fie >= 0")
        raise typer.Exit(1)

    p = _project_dir(project_id)
    try:
        feedback_path = persist_devils_advocate_feedback(
            project_dir=str(p),
            run_id=run_id,
            section_id=section_id,
            stage=normalized_stage,
            confirmed_useful=confirmed_useful,
            false_positive=false_positive,
            ignored=ignored,
            notes=notes,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)

    summary_path = persist_devils_advocate_kpi_summary(project_dir=str(p), run_id=run_id)
    typer.echo(
        f"OK review-devils-advocate: run={run_id} section={section_id} stage={normalized_stage} "
        f"feedback={feedback_path} summary={summary_path}"
    )


@app.command("summarize-devils-advocate-kpis")
def summarize_devils_advocate_kpis(
    project_id: str,
    run_id: str = typer.Option(..., help="Run ID existent."),
):
    p = _project_dir(project_id)
    summary = build_devils_advocate_kpi_summary(project_dir=str(p), run_id=run_id)
    out_path = persist_devils_advocate_kpi_summary(project_dir=str(p), run_id=run_id)

    recommendation_distribution = summary.get("recommendation_distribution", {})
    typer.echo(
        "\n".join(
            [
                f"run_id={summary.get('run_id')}",
                f"reports_total={summary.get('reports_total')}",
                f"reports_with_material_issue={summary.get('reports_with_material_issue')}",
                f"avg_score_total={summary.get('avg_score_total')}",
                f"total_red_flags={summary.get('total_red_flags')}",
                f"useful_red_flags={summary.get('useful_red_flags')}",
                f"false_positives={summary.get('false_positives')}",
                f"useful_red_flag_rate={summary.get('useful_red_flag_rate')}",
                f"false_positive_rate={summary.get('false_positive_rate')}",
                f"feedback_status={summary.get('feedback_status')}",
                f"recommendation_distribution={recommendation_distribution}",
                f"output={out_path}",
            ]
        )
    )


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
    enable_devils_advocate: bool = typer.Option(
        False,
        help="Flag legacy pentru verificări consultative manuale; integrarea în graph folosește --enable-devils-advocate-evidence.",
    ),
    enable_devils_advocate_evidence: bool = typer.Option(
        False,
        "--enable-devils-advocate-evidence",
        help="Activează verificare consultativă anti-prompt după evidence_builder (feature-flag).",
    ),
    anti_prompt_snapshot_dir: str = typer.Option(
        "app/knowledge/anti_prompts",
        help="Director snapshot compilat pentru AntiPrompt DB.",
    ),
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
        "enable_devils_advocate": enable_devils_advocate,
        "enable_devils_advocate_evidence": enable_devils_advocate_evidence,
        "anti_prompt_snapshot_dir": anti_prompt_snapshot_dir,
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
                f"avg_devils_advocate_score_total={summary.get('avg_devils_advocate_score_total')}",
                f"reports_with_material_issue={summary.get('reports_with_material_issue')}",
                f"recommendation_distribution={summary.get('recommendation_distribution')}",
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


@app.command("eval-promote-release-kpis")
def eval_promote_release_kpis(
    report: str = typer.Option(..., help="Raport de promovat (id/path/latest)."),
    version: str = typer.Option(..., help="Versiune release, ex: v0.1.5"),
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
):
    try:
        out = promote_release_kpis(report=report, version=version, reports_dir=reports_dir)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1)
    typer.echo(f"OK eval-promote-release-kpis: {out}")


@app.command("eval-history")
def eval_history(
    reports_dir: str = typer.Option("eval/reports", help="Directorul cu rapoarte."),
    limit: int = typer.Option(5, help="Număr snapshot-uri afișate (ultimele N)."),
):
    history = load_kpi_history(reports_dir=reports_dir)
    if not history:
        typer.echo("Nu există KPI history încă.")
        return

    latest_entries = history[-max(1, limit):]
    lines = [f"history_total={len(history)}", f"showing_last={len(latest_entries)}"]
    for row in latest_entries:
        rid = row.get("report_id")
        created = row.get("created_at")
        useful_rate = row.get("useful_red_flag_rate")
        fp_rate = row.get("false_positive_rate")
        language = row.get("avg_language_score")
        unsupported = row.get("unsupported_claim_rate")
        lines.append(
            (
                f"report_id={rid} created_at={created} "
                f"avg_language_score={language} unsupported_claim_rate={unsupported} "
                f"useful_red_flag_rate={useful_rate} false_positive_rate={fp_rate}"
            )
        )

    typer.echo("\n".join(lines))


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