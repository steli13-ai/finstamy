from operator import add
from typing import Annotated, TypedDict


class ProjectState(TypedDict, total=False):
    project_id: str
    project_dir: str
    run_id: str
    run_dir: str
    target_section_id: str
    auto_approve_gates: bool
    enable_devils_advocate: bool
    enable_devils_advocate_evidence: bool
    anti_prompt_snapshot_dir: str
    use_ollama: bool
    ollama_model: str
    ollama_host: str
    embedding_model: str
    docling_host: str
    grobid_host: str
    languagetool_host: str

    brief_raw: str
    brief_structured: dict
    outline: dict

    source_manifest: dict
    bibliography_snapshot_path: str
    parser_diagnostics: list[dict]

    parsed_sources: list[dict]
    chunk_manifest: list[dict]
    retrieval_runs: list[dict]
    evidence_packs: dict
    claim_plans: dict

    drafted_sections: dict
    citation_resolutions: dict
    validation_reports: dict
    node_traces: Annotated[list[dict], add]

    pending_review: dict | None
    last_review_decision: dict | None
    human_decisions: list[dict]
    edited_state_patches: list[dict]
    language_qa_reports: dict
    language_qa_summary: dict
    section_status: dict
    quality_scores: dict
    devils_advocate_reports: dict
    devils_advocate_evidence_reports: dict

    artifact_hashes: dict
    export_path: str | None