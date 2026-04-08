from __future__ import annotations

from pathlib import Path

import yaml


def parse_frontmatter(markdown_text: str) -> tuple[dict, str]:
    lines = markdown_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown_text

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, markdown_text

    raw_frontmatter = "\n".join(lines[1:end_idx]).strip()
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    parsed = yaml.safe_load(raw_frontmatter) if raw_frontmatter else {}
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter-ul trebuie să fie un obiect YAML (mapping).")
    return parsed, body


def parse_note_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    return {
        "path": str(path),
        "frontmatter": frontmatter,
        "body": body,
    }
