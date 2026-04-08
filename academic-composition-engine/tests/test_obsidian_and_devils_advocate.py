from __future__ import annotations

import json
from pathlib import Path

from app.integrations.obsidian.parser import parse_frontmatter
from app.integrations.obsidian.sync import compile_obsidian_knowledge
from app.graph.nodes import devils_advocate as evidence_da_node
from app.services.devils_advocate import evaluate_evidence_stage, evaluate_stage
from app.services.run_artifacts import persist_run_artifacts


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


def test_evidence_devils_advocate_report_schema_and_recommendation(tmp_path: Path):
    snapshot_dir = tmp_path / "anti"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "evidence.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-08T00:00:00Z",
                "stage": "evidence",
                "entries": [
                    {
                        "id": "ape_001",
                        "stage": "evidence",
                        "severity": "high",
                        "status": "active",
                        "problem_pattern": "Evidence generic",
                        "symptoms": ["important", "relevant"],
                        "why_this_is_bad": "Low argumentative value",
                        "devil_advocate_checks": ["check evidence specificity"],
                        "counter_instruction": "Select concrete passages",
                        "reject_conditions": ["unsupported_claims_present"],
                        "source_note": "vault/ape_001.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_evidence_stage(
        section_id="s1",
        questions_to_answer=["What method was used?", "What are key results?"],
        candidate_passages=[
            {
                "source_id": "sA",
                "chunk_id": "c1",
                "passage_text": "This is important and relevant context without method details.",
            }
        ],
        allowed_claims=["The method is robust", "Results show improvement"],
        unsupported_claims=["Claim without support"],
        retrieval_trace=[{"section_id": "s1", "reranked": []}],
        evidence_pack={"section_id": "s1"},
        snapshot_dir=str(snapshot_dir),
    )

    for key in [
        "section_id",
        "stage",
        "matched_patterns",
        "red_flags",
        "coverage_gaps",
        "weak_passages",
        "recommendation",
        "required_actions",
        "summary",
        "is_material_issue",
    ]:
        assert key in report

    assert report["stage"] == "evidence"
    assert report["recommendation"] in {"pass", "review", "revise"}
    assert report["recommendation"] == "revise"
    assert report["is_material_issue"] is True


def test_evidence_devils_advocate_node_off_has_no_side_effects():
    initial = {"devils_advocate_evidence_reports": {"s1": {"recommendation": "pass"}}}
    out = evidence_da_node.run(
        {
            "target_section_id": "s1",
            "enable_devils_advocate_evidence": False,
            **initial,
        }
    )
    assert out["devils_advocate_evidence_reports"] == initial["devils_advocate_evidence_reports"]


def test_persist_run_artifacts_writes_evidence_devils_advocate_file(tmp_path: Path):
    project_dir = tmp_path / "p"
    project_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "retrieval_runs": [],
        "evidence_packs": {"s1": {}},
        "claim_plans": {"s1": {}},
        "drafted_sections": {"s1": {"draft_markdown": "x"}},
        "citation_resolutions": {"s1": {}},
        "validation_reports": {"s1": {"status": "ok", "unsupported_claim_rate": 0.0, "citation_resolution_rate": 1.0}},
        "parser_diagnostics": [],
        "node_traces": [],
        "language_qa_reports": {"s1": {"counts": {"low": 0, "medium": 0, "high": 0}, "score": 1.0}},
        "devils_advocate_evidence_reports": {
            "s1": {
                "section_id": "s1",
                "stage": "evidence",
                "matched_patterns": [],
                "red_flags": [],
                "coverage_gaps": [],
                "weak_passages": [],
                "recommendation": "pass",
                "required_actions": [],
                "summary": "ok",
                "is_material_issue": False,
            }
        },
    }

    out_dir = persist_run_artifacts(
        project_dir=str(project_dir),
        run_id="run_test",
        section_id="s1",
        input_snapshot={"x": 1},
        result=result,
    )
    assert (out_dir / "devils_advocate_evidence_report.json").exists()
