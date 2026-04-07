from pathlib import Path
from app.graph.state import ProjectState
from app.services.source_parser import parse_source_file
from app.services.docling_client import parse_file_with_docling
from app.services.grobid_client import parse_pdf_with_grobid


def _is_scholarly_pdf(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    name = path.name.lower()
    return any(marker in name for marker in ["paper", "article", "journal", "conference", "doi", "ieee", "acm"])


def run(state: ProjectState) -> ProjectState:
    project_dir = Path(state["project_dir"])
    src_dir = project_dir / "sources"
    parsed, diagnostics = [], []
    docling_host = state.get("docling_host", "http://localhost:5001")
    grobid_host = state.get("grobid_host", "http://localhost:8070")

    for p in sorted(src_dir.glob("*")):
        if p.is_file():
            parser_used = "local"
            parser_chain = []

            doc = parse_file_with_docling(p, host=docling_host)
            parser_chain.append("docling")

            if not doc or not doc.get("text"):
                if p.suffix.lower() == ".pdf" and _is_scholarly_pdf(p):
                    doc = parse_pdf_with_grobid(p, host=grobid_host)
                    parser_chain.append("grobid")
                    if doc and doc.get("text"):
                        parser_used = "grobid"

            if not doc or not doc.get("text"):
                doc = parse_source_file(p)
                parser_chain.append("local")
                parser_used = "local"
            else:
                parser_used = doc.get("parser", "docling")

            parsed.append(doc)
            diagnostics.append(
                {
                    "source_id": doc["source_id"],
                    "parser": parser_used,
                    "parser_chain": parser_chain,
                    "ok": bool(doc.get("text")),
                    "format": doc.get("format", p.suffix.lower().lstrip(".")),
                }
            )

    return {"parsed_sources": parsed, "parser_diagnostics": diagnostics}