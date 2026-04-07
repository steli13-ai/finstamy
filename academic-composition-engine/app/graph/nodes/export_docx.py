from pathlib import Path
import subprocess
from app.graph.state import ProjectState


def run(state: ProjectState) -> ProjectState:
    project_dir = Path(state["project_dir"])
    sid = state["target_section_id"]
    md = state.get("drafted_sections", {}).get(sid, {}).get("draft_markdown", "")

    sections_dir = project_dir / "sections"
    exports_dir = project_dir / "exports"
    sections_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    md_path = sections_dir / f"{sid}.md"
    md_path.write_text(md, encoding="utf-8")

    docx_path = exports_dir / f"{sid}.docx"
    bib = state.get("bibliography_snapshot_path", "")
    cmd = ["pandoc", str(md_path), "-o", str(docx_path), "--citeproc"]
    if bib:
        cmd += ["--bibliography", bib]

    try:
        subprocess.run(cmd, check=True)
        return {"export_path": str(docx_path)}
    except Exception:
        # fallback: păstrează markdown exportat
        return {"export_path": str(md_path)}