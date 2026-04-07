from app.graph.state import ProjectState
from app.services.retrieval import chunk_text


def run(state: ProjectState) -> ProjectState:
    out = []
    for s in state.get("parsed_sources", []):
        chunks = chunk_text(s.get("text", ""))
        for i, c in enumerate(chunks):
            out.append(
                {
                    "source_id": s["source_id"],
                    "chunk_id": f"{s['source_id']}::c{i}",
                    "text": c,
                }
            )
    return {"chunk_manifest": out}