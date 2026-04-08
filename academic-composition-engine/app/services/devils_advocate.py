from __future__ import annotations

import json
import re
from pathlib import Path


def load_anti_prompt_snapshot(*, stage: str, snapshot_dir: str = "app/knowledge/anti_prompts") -> dict:
    path = Path(snapshot_dir) / f"{stage}.json"
    if not path.exists():
        return {"stage": stage, "entries": [], "source": str(path), "missing": True}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", []) if isinstance(data, dict) else []
    active_entries = [e for e in entries if str(e.get("status", "active")).lower() == "active"]
    return {
        "stage": stage,
        "entries": active_entries,
        "source": str(path),
        "generated_at": data.get("generated_at") if isinstance(data, dict) else None,
        "missing": False,
    }


def _contains_any(text: str, candidates: list[str]) -> list[str]:
    haystack = text.lower()
    hits = []
    for item in candidates:
        token = str(item).strip().lower()
        if token and token in haystack:
            hits.append(item)
    return hits


def evaluate_stage(
    *,
    section_id: str,
    stage: str,
    draft_markdown: str,
    evidence_pack: dict,
    citation_resolution: dict,
    snapshot_dir: str = "app/knowledge/anti_prompts",
) -> dict:
    snapshot = load_anti_prompt_snapshot(stage=stage, snapshot_dir=snapshot_dir)
    corpus = "\n".join(
        [
            draft_markdown or "",
            json.dumps(evidence_pack or {}, ensure_ascii=False),
            json.dumps(citation_resolution or {}, ensure_ascii=False),
        ]
    )

    matched_patterns = []
    red_flags = []
    required_actions = []

    for entry in snapshot.get("entries", []):
        symptom_hits = _contains_any(corpus, entry.get("symptoms", []))
        reject_hits = _contains_any(corpus, entry.get("reject_conditions", []))
        if not symptom_hits and not reject_hits:
            continue

        severity = str(entry.get("severity", "medium"))
        if reject_hits:
            red_flags.extend([f"{entry.get('id')}: reject_condition={v}" for v in reject_hits])
        if severity in {"high", "critical"}:
            required_actions.append(entry.get("counter_instruction", ""))

        matched_patterns.append(
            {
                "id": entry.get("id"),
                "severity": severity,
                "problem_pattern": entry.get("problem_pattern"),
                "matched_symptoms": symptom_hits,
                "matched_reject_conditions": reject_hits,
                "counter_instruction": entry.get("counter_instruction"),
                "devil_advocate_checks": entry.get("devil_advocate_checks", []),
            }
        )

    recommendation = "ok"
    if red_flags:
        recommendation = "manual_review_required"
    elif matched_patterns:
        recommendation = "proceed_with_caution"

    dedup_required_actions = [a for a in dict.fromkeys([a for a in required_actions if a])]

    return {
        "section_id": section_id,
        "stage": stage,
        "matched_patterns": matched_patterns,
        "red_flags": red_flags,
        "recommendation": recommendation,
        "required_actions": dedup_required_actions,
        "snapshot_source": snapshot.get("source"),
        "snapshot_generated_at": snapshot.get("generated_at"),
    }


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-ZăâîșțĂÂÎȘȚ0-9]{3,}", text.lower())}


def _overlap_ratio(a: str, b: str) -> float:
    at = _tokenize(a)
    bt = _tokenize(b)
    if not at or not bt:
        return 0.0
    return len(at.intersection(bt)) / max(1, len(at.union(bt)))


def evaluate_evidence_stage(
    *,
    section_id: str,
    questions_to_answer: list[str],
    candidate_passages: list[dict],
    allowed_claims: list[str],
    unsupported_claims: list[str],
    retrieval_trace: list[dict] | None = None,
    evidence_pack: dict | None = None,
    snapshot_dir: str = "app/knowledge/anti_prompts",
) -> dict:
    snapshot = load_anti_prompt_snapshot(stage="evidence", snapshot_dir=snapshot_dir)
    retrieval_trace = retrieval_trace or []
    evidence_pack = evidence_pack or {}

    corpus = "\n".join(
        [
            json.dumps(questions_to_answer, ensure_ascii=False),
            json.dumps(candidate_passages, ensure_ascii=False),
            json.dumps(allowed_claims, ensure_ascii=False),
            json.dumps(unsupported_claims, ensure_ascii=False),
            json.dumps(retrieval_trace, ensure_ascii=False),
            json.dumps(evidence_pack, ensure_ascii=False),
        ]
    )

    matched_patterns = []
    red_flags = []
    required_actions: list[str] = []

    for entry in snapshot.get("entries", []):
        symptom_hits = _contains_any(corpus, entry.get("symptoms", []))
        reject_hits = _contains_any(corpus, entry.get("reject_conditions", []))
        if not symptom_hits and not reject_hits:
            continue

        severity = str(entry.get("severity", "medium"))
        if reject_hits:
            red_flags.extend([f"{entry.get('id')}: reject_condition={v}" for v in reject_hits])
        if severity in {"high", "critical"} and entry.get("counter_instruction"):
            required_actions.append(str(entry.get("counter_instruction")))

        matched_patterns.append(
            {
                "id": entry.get("id"),
                "severity": severity,
                "problem_pattern": entry.get("problem_pattern"),
                "matched_symptoms": symptom_hits,
                "matched_reject_conditions": reject_hits,
                "counter_instruction": entry.get("counter_instruction"),
            }
        )

    coverage_gaps: list[str] = []
    weak_passages: list[dict] = []

    if allowed_claims and len(candidate_passages) < max(2, len(allowed_claims) // 2):
        coverage_gaps.append("insufficient_candidate_passages_for_allowed_claims")

    if unsupported_claims:
        coverage_gaps.append("unsupported_claims_present")

    generic_markers = [
        "important",
        "relevant",
        "in general",
        "in context",
        "descriptive overview",
    ]

    for idx, passage in enumerate(candidate_passages):
        passage_text = str(passage.get("passage_text") or passage.get("text") or "")
        if not passage_text.strip():
            weak_passages.append(
                {
                    "index": idx,
                    "reason": "empty_passage_text",
                    "severity": "critical",
                    "source_id": passage.get("source_id"),
                }
            )
            continue

        best_question_overlap = max((_overlap_ratio(passage_text, q) for q in questions_to_answer), default=0.0)
        best_claim_overlap = max((_overlap_ratio(passage_text, c) for c in allowed_claims), default=0.0)
        generic_hits = _contains_any(passage_text, generic_markers)

        severity = None
        reason = None
        if best_question_overlap < 0.03 and best_claim_overlap < 0.03:
            severity = "high"
            reason = "likely_irrelevant_to_questions_and_claims"
        elif generic_hits and best_claim_overlap < 0.05:
            severity = "moderate"
            reason = "generic_evidence_signal"

        if severity:
            weak_passages.append(
                {
                    "index": idx,
                    "severity": severity,
                    "reason": reason,
                    "source_id": passage.get("source_id"),
                    "chunk_id": passage.get("chunk_id"),
                    "generic_markers": generic_hits,
                    "question_overlap": round(best_question_overlap, 4),
                    "claim_overlap": round(best_claim_overlap, 4),
                }
            )

    source_ids = [str(p.get("source_id", "")) for p in candidate_passages if p.get("source_id")]
    unique_sources = len(set(source_ids))
    if len(source_ids) >= 4 and unique_sources / max(1, len(source_ids)) < 0.5:
        coverage_gaps.append("low_source_diversity_high_overlap")

    lower_q = " ".join(questions_to_answer).lower()
    has_method_need = any(k in lower_q for k in ["metod", "method", "procedur"])
    has_result_need = any(k in lower_q for k in ["rezultat", "result", "outcome"])
    has_limit_need = any(k in lower_q for k in ["limit", "bias", "constraint"])
    all_passages_text = " ".join(str(p.get("passage_text") or p.get("text") or "") for p in candidate_passages).lower()

    if has_method_need and not any(k in all_passages_text for k in ["metod", "method", "protocol"]):
        coverage_gaps.append("missing_method_support_passages")
    if has_result_need and not any(k in all_passages_text for k in ["rezultat", "result", "finding"]):
        coverage_gaps.append("missing_result_support_passages")
    if has_limit_need and not any(k in all_passages_text for k in ["limit", "bias", "constraint"]):
        coverage_gaps.append("missing_limitations_support_passages")

    has_critical_weak = any(w.get("severity") == "critical" for w in weak_passages)
    has_high_weak = any(w.get("severity") == "high" for w in weak_passages)
    has_material_gap = bool(coverage_gaps)

    if not has_material_gap and not has_critical_weak and not has_high_weak:
        recommendation = "pass"
    elif has_material_gap or has_critical_weak:
        recommendation = "revise"
    else:
        recommendation = "review"

    if has_material_gap:
        required_actions.append("Consolidează acoperirea evidence pentru claim-uri și întrebări.")
    if has_high_weak or has_critical_weak:
        required_actions.append("Elimină sau înlocuiește pasajele slabe/irelevante.")

    required_actions = [item for item in dict.fromkeys([a for a in required_actions if a])]

    summary = (
        f"coverage_gaps={len(coverage_gaps)} weak_passages={len(weak_passages)} "
        f"red_flags={len(red_flags)} recommendation={recommendation}"
    )

    return {
        "section_id": section_id,
        "stage": "evidence",
        "matched_patterns": matched_patterns,
        "red_flags": red_flags,
        "coverage_gaps": coverage_gaps,
        "weak_passages": weak_passages,
        "recommendation": recommendation,
        "required_actions": required_actions,
        "summary": summary,
        "is_material_issue": has_material_gap or has_critical_weak,
        "snapshot_source": snapshot.get("source"),
        "snapshot_generated_at": snapshot.get("generated_at"),
    }
