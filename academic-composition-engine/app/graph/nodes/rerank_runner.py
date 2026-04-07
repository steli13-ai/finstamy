from app.graph.state import ProjectState
from app.services.lancedb_store import vector_rerank


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    sections = {s["id"]: s for s in state.get("outline", {}).get("sections", [])}
    goal = sections.get(sid, {}).get("goal", "context")
    last = next((r for r in reversed(state.get("retrieval_runs", [])) if r.get("candidates")), {"candidates": []})
    ranked = vector_rerank(
        last["candidates"],
        section_goal=goal,
        ollama_host=state.get("ollama_host", "http://localhost:11434"),
        embedding_model=state.get("embedding_model", "nomic-embed-text"),
    )[:15]
    runs = state.get("retrieval_runs", [])
    runs.append({"section_id": sid, "reranked": ranked})
    return {"retrieval_runs": runs}
