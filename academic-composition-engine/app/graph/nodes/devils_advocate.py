from app.graph.state import ProjectState
from app.services.devils_advocate import evaluate_stage


def run(state: ProjectState) -> ProjectState:
    if not state.get("enable_devils_advocate", False):
        return {"devils_advocate_reports": state.get("devils_advocate_reports", {})}

    section_id = state["target_section_id"]
    drafted = state.get("drafted_sections", {}).get(section_id, {})
    evidence_pack = state.get("evidence_packs", {}).get(section_id, {})
    citation_resolution = state.get("citation_resolutions", {}).get(section_id, {})

    report = evaluate_stage(
        section_id=section_id,
        stage="drafting",
        draft_markdown=drafted.get("draft_markdown", ""),
        evidence_pack=evidence_pack,
        citation_resolution=citation_resolution,
        snapshot_dir=state.get("anti_prompt_snapshot_dir", "app/knowledge/anti_prompts"),
    )

    reports = state.get("devils_advocate_reports", {})
    reports[section_id] = report
    return {"devils_advocate_reports": reports}
