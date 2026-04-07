from __future__ import annotations
from pathlib import Path


def parse_source_file(path: Path) -> dict:
    # MVP: parse text/markdown direct; alte formate => fallback text gol + diagnostic
    ext = path.suffix.lower()
    if ext in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return {"source_id": path.stem, "format": ext[1:], "text": text}
    return {"source_id": path.stem, "format": ext[1:], "text": ""}