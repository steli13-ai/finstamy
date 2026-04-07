from app.graph.state import ProjectState


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    draft = state.get("drafted_sections", {}).get(sid, {})
    cit = state.get("citation_resolutions", {}).get(sid, {})
    unresolved = len(cit.get("unresolved", []))
    claims = len(draft.get("citations_needed", []))

    report = {
        "section_id": sid,
        "unsupported_claim_rate": (unresolved / claims) if claims else 0.0,
        "citation_resolution_rate": ((claims - unresolved) / claims) if claims else 1.0,
        "status": "ok" if unresolved == 0 else "needs_review",
    }
    vr = state.get("validation_reports", {})
    vr[sid] = report
    return {"validation_reports": vr}