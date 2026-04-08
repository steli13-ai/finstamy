from __future__ import annotations

from pathlib import Path


def list_markdown_notes(vault_dir: str, include: str = "**/*.md") -> list[Path]:
    root = Path(vault_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Vault inexistent sau invalid: {vault_dir}")
    return sorted([p for p in root.glob(include) if p.is_file()])
