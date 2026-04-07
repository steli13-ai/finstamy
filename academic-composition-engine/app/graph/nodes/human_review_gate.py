from __future__ import annotations

from pathlib import Path

from langgraph.types import Command, interrupt

from app.graph.state import ProjectState


def _append_decision(state: ProjectState, decision_record: dict) -> list[dict]:
    decisions = list(state.get("human_decisions", []))
    decisions.append(decision_record)
    return decisions


def _append_patch(state: ProjectState, patch: dict) -> list[dict]:
    patches = list(state.get("edited_state_patches", []))
    patches.append(patch)
    return patches


def _build_summary(state: ProjectState, gate_name: str) -> str:
    section_id = state.get("target_section_id", "")
    if gate_name == "after_outline":
        outline = state.get("outline", {}).get("sections", [])
        return f"Outline generated with {len(outline)} sections for target {section_id}."
    if gate_name == "after_evidence":
        pack = state.get("evidence_packs", {}).get(section_id, {})
        passages = pack.get("candidate_passages", [])
        claims = pack.get("allowed_claims", [])
        return f"Evidence pack has {len(passages)} passages and {len(claims)} allowed claims."
    if gate_name == "pre_export":
        report = state.get("validation_reports", {}).get(section_id, {})
        status = report.get("status", "unknown")
        rate = report.get("citation_resolution_rate")
        return f"Validation status={status}, citation_resolution_rate={rate}."
    return "Human review required."


def _artifact_paths(state: ProjectState, gate_name: str) -> list[str]:
    project_dir = Path(state.get("project_dir", ""))
    run_id = state.get("run_id", "")
    section_id = state.get("target_section_id", "")
    base = project_dir / "runs" / run_id / "sections" / section_id
    paths = [str(base)]
    if gate_name == "after_outline":
        paths.append(str(project_dir / "outline.json"))
    elif gate_name == "after_evidence":
        paths.append(str(base / "evidence_pack.json"))
    elif gate_name == "pre_export":
        paths.extend([str(base / "validation_report.json"), str(base / "draft.md")])
    return paths


def run_gate(
    state: ProjectState,
    *,
    gate_name: str,
    suggested_next_node: str,
    reject_goto: str,
) -> Command:
    section_id = state.get("target_section_id", "")
    project_id = state.get("project_id", "")

    if state.get("auto_approve_gates", False):
        decision_record = {
            "gate_name": gate_name,
            "project_id": project_id,
            "section_id": section_id,
            "decision": "approve",
            "mode": "auto",
        }
        return Command(
            update={
                "pending_review": None,
                "last_review_decision": decision_record,
                "human_decisions": _append_decision(state, decision_record),
            },
            goto=suggested_next_node,
        )

    payload = {
        "gate_name": gate_name,
        "project_id": project_id,
        "section_id": section_id,
        "summary": _build_summary(state, gate_name),
        "artifact_paths": _artifact_paths(state, gate_name),
        "suggested_next_node": suggested_next_node,
        "allowed_actions": ["approve", "reject", "edit_state"],
    }

    resume_value = interrupt(payload)
    resume_value = resume_value or {}
    decision = str(resume_value.get("decision", "approve"))
    patch = resume_value.get("patch", {})

    decision_record = {
        "gate_name": gate_name,
        "project_id": project_id,
        "section_id": section_id,
        "decision": decision,
        "comment": resume_value.get("comment"),
    }

    if decision == "approve":
        return Command(
            update={
                "pending_review": None,
                "last_review_decision": decision_record,
                "human_decisions": _append_decision(state, decision_record),
            },
            goto=suggested_next_node,
        )

    if decision == "reject":
        return Command(
            update={
                "pending_review": None,
                "last_review_decision": decision_record,
                "human_decisions": _append_decision(state, decision_record),
            },
            goto=reject_goto,
        )

    if decision == "edit_state":
        if not isinstance(patch, dict):
            patch = {}
        update_payload = {
            "pending_review": None,
            "last_review_decision": decision_record,
            "human_decisions": _append_decision(state, decision_record),
            "edited_state_patches": _append_patch(state, patch),
            **patch,
        }
        goto_node = str(resume_value.get("goto") or suggested_next_node)
        return Command(update=update_payload, goto=goto_node)

    decision_record["decision"] = "approve"
    return Command(
        update={
            "pending_review": None,
            "last_review_decision": decision_record,
            "human_decisions": _append_decision(state, decision_record),
        },
        goto=suggested_next_node,
    )


def review_after_outline(state: ProjectState) -> Command:
    return run_gate(
        state,
        gate_name="after_outline",
        suggested_next_node="source_ingest",
        reject_goto="outline_planner",
    )


def review_after_evidence(state: ProjectState) -> Command:
    return run_gate(
        state,
        gate_name="after_evidence",
        suggested_next_node="claim_planner",
        reject_goto="evidence_builder",
    )


def review_pre_export(state: ProjectState) -> Command:
    return run_gate(
        state,
        gate_name="pre_export",
        suggested_next_node="export_docx",
        reject_goto="section_writer",
    )
