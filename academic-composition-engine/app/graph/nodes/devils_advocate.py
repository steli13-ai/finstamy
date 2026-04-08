from app.graph.state import ProjectState
from app.services.devils_advocate import evaluate_evidence_stage


def run(state: ProjectState) -> ProjectState:
    if not state.get("enable_devils_advocate_evidence", False):
        return {
            "devils_advocate_evidence_reports": state.get("devils_advocate_evidence_reports", {})
        }

    section_id = state["target_section_id"]
    evidence_pack = state.get("evidence_packs", {}).get(section_id, {})
    retrieval_trace = [
        row for row in state.get("retrieval_runs", []) if row.get("section_id") == section_id
    ]

    report = evaluate_evidence_stage(
        section_id=section_id,
        questions_to_answer=evidence_pack.get("questions_to_answer", []),
        candidate_passages=evidence_pack.get("candidate_passages", []),
        allowed_claims=evidence_pack.get("allowed_claims", []),
        unsupported_claims=evidence_pack.get("unsupported_claims", []),
        retrieval_trace=retrieval_trace,
        evidence_pack=evidence_pack,
        snapshot_dir=state.get("anti_prompt_snapshot_dir", "app/knowledge/anti_prompts"),
    )

    reports = state.get("devils_advocate_evidence_reports", {})
    reports[section_id] = report
    return {"devils_advocate_evidence_reports": reports}
