from pathlib import Path
from app.graph.state import ProjectState
from app.services.io_utils import write_json
from app.services.lancedb_store import index_chunks


def run(state: ProjectState) -> ProjectState:
    project_dir = Path(state["project_dir"])
    chunks = state.get("chunk_manifest", [])
    write_json(project_dir / "retrieval" / "chunks.json", chunks)

    index_info = index_chunks(
        project_dir=str(project_dir),
        chunks=chunks,
        ollama_host=state.get("ollama_host", "http://localhost:11434"),
        embedding_model=state.get("embedding_model", "nomic-embed-text"),
    )

    manifest = state.get("source_manifest", {})
    manifest["index"] = index_info
    return {"source_manifest": manifest}