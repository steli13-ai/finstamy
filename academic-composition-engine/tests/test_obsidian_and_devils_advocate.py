from __future__ import annotations

import json
from pathlib import Path

from app.integrations.obsidian.parser import parse_frontmatter
from app.integrations.obsidian.sync import compile_obsidian_knowledge
from app.services.devils_advocate import evaluate_stage


def test_parse_frontmatter_extracts_yaml_and_body():
    text = """---
id: ap_outline_001
entry_kind: anti_prompt
stage: outline
---
Corpul notei.
"""
    fm, body = parse_frontmatter(text)
    assert fm["id"] == "ap_outline_001"
    assert fm["stage"] == "outline"
    assert "Corpul notei" in body


def test_compile_obsidian_knowledge_builds_snapshots(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)

    anti_note = vault / "anti_outline.md"
    anti_note.write_text(
        """---
entry_kind: anti_prompt
id: anti_outline_01
stage: outline
severity: high
status: active
problem_pattern: Outline generic
symptoms: [generic, superficial]
why_this_is_bad: Nu ghidează corect scrierea
devil_advocate_checks: [Verifică granularitatea secțiunilor]
counter_instruction: Cere outline concret pe obiective
reject_conditions: [fără evidență]
---
Detalii.
""",
        encoding="utf-8",
    )

    second_note = vault / "decision.md"
    second_note.write_text(
        """---
entry_kind: second_brain
id: dec_001
type: decision
status: active
context: MVP architecture
decision: Keep LangGraph as core
why: deterministic orchestration
alternatives_considered: [Obsidian runtime]
impact: stable critical path
related_files: [app/graph/graph.py]
---
Decizie arhitecturală.
""",
        encoding="utf-8",
    )

    out = tmp_path / "knowledge"
    stats = compile_obsidian_knowledge(vault_dir=str(vault), output_dir=str(out))

    assert stats.notes_scanned == 2
    assert stats.anti_prompts_compiled == 1
    assert stats.second_brain_compiled == 1

    outline = json.loads((out / "anti_prompts" / "outline.json").read_text(encoding="utf-8"))
    decisions = json.loads((out / "second_brain" / "decisions.json").read_text(encoding="utf-8"))
    assert len(outline["entries"]) == 1
    assert len(decisions["entries"]) == 1


def test_devils_advocate_uses_active_stage_entries(tmp_path: Path):
    snapshot_dir = tmp_path / "anti"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "drafting.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-08T00:00:00Z",
                "stage": "drafting",
                "entries": [
                    {
                        "id": "ap_draft_1",
                        "stage": "drafting",
                        "severity": "high",
                        "tags": ["generic"],
                        "status": "active",
                        "problem_pattern": "Text generic",
                        "symptoms": ["generic", "vag"],
                        "why_this_is_bad": "Scade rigoarea academică",
                        "devil_advocate_checks": ["identifică propoziții vagi"],
                        "counter_instruction": "Leagă fiecare paragraf de evidence pack",
                        "reject_conditions": ["fără trasabilitate"],
                        "source_note": "vault/ap_draft_1.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_stage(
        section_id="s1",
        stage="drafting",
        draft_markdown="Acesta este un text generic și vag.",
        evidence_pack={"candidate_passages": []},
        citation_resolution={"resolved_citations": []},
        snapshot_dir=str(snapshot_dir),
    )

    assert report["section_id"] == "s1"
    assert report["stage"] == "drafting"
    assert len(report["matched_patterns"]) == 1
    assert report["recommendation"] in {"manual_review_required", "proceed_with_caution"}
