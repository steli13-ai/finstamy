from app.graph.state import ProjectState
from app.services.lancedb_store import hybrid_search


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    last = next((r for r in reversed(state.get("retrieval_runs", [])) if r["section_id"] == sid), None)
    queries = last["queries"] if last else []
    candidates = hybrid_search(
        project_dir=state["project_dir"],
        chunks=state.get("chunk_manifest", []),
        queries=queries,
        top_k=20,
        ollama_host=state.get("ollama_host", "http://localhost:11434"),
        embedding_model=state.get("embedding_model", "nomic-embed-text"),
    )
    runs = state.get("retrieval_runs", [])
    runs.append({"section_id": sid, "candidates": candidates})
    return {"retrieval_runs": runs}