from app.graph.state import ProjectState
from app.services.citations import load_reference_keys, resolve_needed_citations, inject_keys_in_markdown


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    draft = state.get("drafted_sections", {}).get(sid, {})
    needed = draft.get("citations_needed", [])
    keys = load_reference_keys(state.get("bibliography_snapshot_path", ""))

    res = resolve_needed_citations(needed, keys)
    resolved_md = inject_keys_in_markdown(draft.get("draft_markdown", ""), res["resolved_citations"])

    citation_map = state.get("citation_resolutions", {})
    citation_map[sid] = {"section_id": sid, **res}

    drafted = state.get("drafted_sections", {})
    drafted[sid]["draft_markdown"] = resolved_md
    return {"citation_resolutions": citation_map, "drafted_sections": drafted}