from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.integrations.obsidian.client import list_markdown_notes
from app.integrations.obsidian.parser import parse_note_file
from app.integrations.obsidian.schemas import (
    AntiPromptNote,
    SecondBrainNote,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SyncStats:
    vault_dir: str
    notes_scanned: int
    anti_prompts_compiled: int
    second_brain_compiled: int
    rejected_notes: int
    output_dir: str


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_tags(raw_tags) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        return [raw_tags]
    if isinstance(raw_tags, list):
        return [str(t) for t in raw_tags]
    return []


def compile_obsidian_knowledge(
    *,
    vault_dir: str,
    output_dir: str = "app/knowledge",
    include_glob: str = "**/*.md",
    strict: bool = False,
) -> SyncStats:
    notes = list_markdown_notes(vault_dir=vault_dir, include=include_glob)

    anti_prompt_entries: list[AntiPromptNote] = []
    second_brain_entries: list[SecondBrainNote] = []
    rejected = 0

    for note_path in notes:
        parsed = parse_note_file(note_path)
        fm = parsed["frontmatter"]
        body = parsed["body"]

        entry_kind = str(fm.get("entry_kind", "")).strip().lower()
        source_note = str(note_path)

        try:
            if entry_kind == "anti_prompt":
                anti_prompt_entries.append(
                    AntiPromptNote(
                        id=str(fm.get("id") or note_path.stem),
                        stage=str(fm.get("stage") or "drafting"),
                        severity=str(fm.get("severity") or "medium"),
                        tags=_normalize_tags(fm.get("tags")),
                        status=str(fm.get("status") or "active"),
                        problem_pattern=str(fm.get("problem_pattern") or body[:160]),
                        symptoms=[str(v) for v in (fm.get("symptoms") or [])],
                        why_this_is_bad=str(fm.get("why_this_is_bad") or ""),
                        devil_advocate_checks=[str(v) for v in (fm.get("devil_advocate_checks") or [])],
                        counter_instruction=str(fm.get("counter_instruction") or ""),
                        reject_conditions=[str(v) for v in (fm.get("reject_conditions") or [])],
                        source_note=source_note,
                    )
                )
            elif entry_kind == "second_brain":
                second_brain_entries.append(
                    SecondBrainNote(
                        id=str(fm.get("id") or note_path.stem),
                        type=str(fm.get("type") or "decision"),
                        tags=_normalize_tags(fm.get("tags")),
                        status=str(fm.get("status") or "active"),
                        context=str(fm.get("context") or body[:180]),
                        decision=str(fm.get("decision") or ""),
                        why=str(fm.get("why") or ""),
                        alternatives_considered=[str(v) for v in (fm.get("alternatives_considered") or [])],
                        impact=str(fm.get("impact") or ""),
                        related_files=[str(v) for v in (fm.get("related_files") or [])],
                        source_note=source_note,
                    )
                )
        except Exception:
            rejected += 1
            if strict:
                raise

    output_root = Path(output_dir)
    anti_root = output_root / "anti_prompts"
    brain_root = output_root / "second_brain"

    anti_by_stage = {"outline": [], "evidence": [], "drafting": [], "citation": []}
    for entry in anti_prompt_entries:
        anti_by_stage[entry.stage].append(entry.model_dump())

    for stage, items in anti_by_stage.items():
        _write_json(
            anti_root / f"{stage}.json",
            {
                "generated_at": _utc_now(),
                "stage": stage,
                "entries": items,
            },
        )

    second_by_type = {"decisions": [], "playbooks": [], "bugs": [], "release_history": []}
    for entry in second_brain_entries:
        if entry.type == "decision":
            second_by_type["decisions"].append(entry.model_dump())
        elif entry.type == "playbook":
            second_by_type["playbooks"].append(entry.model_dump())
        elif entry.type == "bug":
            second_by_type["bugs"].append(entry.model_dump())
        elif entry.type == "release_history":
            second_by_type["release_history"].append(entry.model_dump())

    for key, items in second_by_type.items():
        _write_json(
            brain_root / f"{key}.json",
            {
                "generated_at": _utc_now(),
                "type": key,
                "entries": items,
            },
        )

    return SyncStats(
        vault_dir=vault_dir,
        notes_scanned=len(notes),
        anti_prompts_compiled=len(anti_prompt_entries),
        second_brain_compiled=len(second_brain_entries),
        rejected_notes=rejected,
        output_dir=str(output_root),
    )
