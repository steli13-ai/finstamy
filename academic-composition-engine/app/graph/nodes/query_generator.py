from app.graph.state import ProjectState


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    sections = {s["id"]: s for s in state.get("outline", {}).get("sections", [])}
    goal = sections.get(sid, {}).get("goal", "context")
    queries = [goal, "definiție", "metodă", "rezultat", "limitări"]
    runs = state.get("retrieval_runs", [])
    runs.append({"section_id": sid, "queries": queries})
    return {"retrieval_runs": runs}