from __future__ import annotations

import json
import re
from pathlib import Path


DEFAULT_SCORING_CONFIG = {
    "enabled": True,
    "scoring_version": "v0.1.3",
    "thresholds": {
        "pass_max": 2,
        "review_max": 5,
    },
    "severity_weights": {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "moderate": 2,
        "low": 1,
    },
    "limits": {"top_issues": 3},
}


def _resolve_scoring_config_path(scoring_config_path: str | None = None) -> Path:
    if scoring_config_path:
        return Path(scoring_config_path)
    return Path(__file__).resolve().parents[1] / "config" / "devils_advocate_scoring.json"


def _deep_merge_dict(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_scoring_config(scoring_config_path: str | None = None) -> tuple[dict, str | None]:
    path = _resolve_scoring_config_path(scoring_config_path)
    if not path.exists():
        return DEFAULT_SCORING_CONFIG, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("scoring config must be an object")
        return _deep_merge_dict(DEFAULT_SCORING_CONFIG, raw), None
    except Exception as exc:
        return DEFAULT_SCORING_CONFIG, f"scoring_config_error:{exc}"


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


def _severity_weight(severity: str, config: dict) -> int:
    weights = config.get("severity_weights", {})
    return int(weights.get(str(severity).lower(), weights.get("low", 1)))


def _recommendation_from_thresholds(score_total: int, config: dict) -> str:
    thresholds = config.get("thresholds", {})
    pass_max = int(thresholds.get("pass_max", 2))
    review_max = int(thresholds.get("review_max", 5))
    if score_total <= pass_max:
        return "pass"
    if score_total <= review_max:
        return "review"
    return "revise"


def _build_top_issues(
    *,
    matched_patterns: list[dict],
    coverage_gaps: list[str],
    weak_passages: list[dict],
    config: dict,
) -> list[dict]:
    issue_pool: list[tuple[int, dict]] = []

    for row in matched_patterns:
        severity = str(row.get("severity", "medium")).lower()
        weight = _severity_weight(severity, config)
        issue_pool.append(
            (
                weight,
                {
                    "issue_type": "matched_pattern",
                    "severity": severity,
                    "message": f"{row.get('id', 'unknown')}: {row.get('problem_pattern', 'Pattern matched')}",
                },
            )
        )

    for gap in coverage_gaps:
        message = str(gap)
        severity = "medium"
        if "missing_" in message or "unsupported" in message:
            severity = "high"
        issue_pool.append(
            (
                _severity_weight(severity, config),
                {
                    "issue_type": "coverage_gap",
                    "severity": severity,
                    "message": message,
                },
            )
        )

    for row in weak_passages:
        severity = str(row.get("severity", "medium")).lower()
        issue_pool.append(
            (
                _severity_weight(severity, config),
                {
                    "issue_type": "weak_passage",
                    "severity": severity,
                    "message": str(row.get("reason", "weak_passage_detected")),
                },
            )
        )

    issue_pool.sort(key=lambda item: item[0], reverse=True)
    cap = int(config.get("limits", {}).get("top_issues", 3))
    return [payload for _, payload in issue_pool[:cap]]


def _score_report(
    *,
    stage: str,
    matched_patterns: list[dict],
    red_flags: list[str],
    coverage_gaps: list[str],
    weak_passages: list[dict],
    confidence_signals: list[str],
    config: dict,
) -> dict:
    severity_weight_score = sum(_severity_weight(str(row.get("severity", "medium")), config) for row in matched_patterns)

    coverage_gap_score = 0
    for gap in coverage_gaps:
        gap_text = str(gap).lower()
        coverage_gap_score += 1
        if "missing_" in gap_text or "unsupported" in gap_text:
            coverage_gap_score += 1

    weak_passage_score = 0
    for row in weak_passages:
        severity = str(row.get("severity", "medium")).lower()
        weak_passage_score += _severity_weight(severity, config)
        reason = str(row.get("reason", "")).lower()
        if "redund" in reason or "generic" in reason:
            weak_passage_score += 1

    confidence_signal_score = max(0, len(confidence_signals))
    score_total = severity_weight_score + coverage_gap_score + weak_passage_score - confidence_signal_score

    recommendation = _recommendation_from_thresholds(score_total, config)
    scoring_version = str(config.get("scoring_version", "v0.1.3"))
    top_issues = _build_top_issues(
        matched_patterns=matched_patterns,
        coverage_gaps=coverage_gaps,
        weak_passages=weak_passages,
        config=config,
    )
    recommendation_reason = (
        f"score_total={score_total} thresholds={config.get('thresholds', {})} "
        f"stage={stage} top_issues={len(top_issues)} red_flags={len(red_flags)}"
    )

    return {
        "score_total": score_total,
        "score_breakdown": {
            "severity_weight_score": severity_weight_score,
            "coverage_gap_score": coverage_gap_score,
            "weak_passage_score": weak_passage_score,
            "confidence_signal_score": confidence_signal_score,
            "stage": stage,
            "matched_patterns_count": len(matched_patterns),
            "coverage_gaps_count": len(coverage_gaps),
            "weak_passages_count": len(weak_passages),
            "confidence_signals": confidence_signals,
        },
        "top_issues": top_issues,
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "scoring_version": scoring_version,
    }


def _legacy_recommendation_for_stage(*, stage: str, red_flags: list[str], matched_patterns: list[dict]) -> str:
    if stage == "evidence":
        if red_flags:
            return "revise"
        if matched_patterns:
            return "review"
        return "pass"
    if red_flags:
        return "manual_review_required"
    if matched_patterns:
        return "proceed_with_caution"
    return "ok"


def evaluate_stage(
    *,
    section_id: str,
    stage: str,
    draft_markdown: str,
    evidence_pack: dict,
    citation_resolution: dict,
    snapshot_dir: str = "app/knowledge/anti_prompts",
    scoring_config_path: str | None = None,
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

    candidate_passages = evidence_pack.get("candidate_passages", []) if isinstance(evidence_pack, dict) else []
    unresolved = citation_resolution.get("unresolved", []) if isinstance(citation_resolution, dict) else []

    coverage_gaps: list[str] = []
    if not candidate_passages:
        coverage_gaps.append("missing_evidence_support_passages")
    if unresolved:
        coverage_gaps.append("unresolved_citations_present")

    weak_passages: list[dict] = []
    draft_text = str(draft_markdown or "")
    if len(draft_text.strip()) < 280:
        weak_passages.append({"severity": "medium", "reason": "draft_too_short"})

    generic_markers = ["important", "relevant", "in general", "overview", "generic"]
    generic_hits = _contains_any(draft_text, generic_markers)
    if len(generic_hits) >= 2:
        weak_passages.append({"severity": "moderate", "reason": "generic_language_signal"})

    confidence_signals: list[str] = []
    if candidate_passages:
        confidence_signals.append("has_candidate_passages")
    if not unresolved:
        confidence_signals.append("all_citations_resolved_or_absent")
    if not weak_passages:
        confidence_signals.append("draft_specificity_ok")
    if not red_flags:
        confidence_signals.append("no_reject_condition_hits")

    scoring_config, scoring_error = load_scoring_config(scoring_config_path)
    scoring_enabled = bool(scoring_config.get("enabled", True)) and not scoring_error

    if scoring_enabled:
        scoring_payload = _score_report(
            stage=stage,
            matched_patterns=matched_patterns,
            red_flags=red_flags,
            coverage_gaps=coverage_gaps,
            weak_passages=weak_passages,
            confidence_signals=confidence_signals,
            config=scoring_config,
        )
        recommendation = scoring_payload["recommendation"]
        recommendation_reason = scoring_payload["recommendation_reason"]
    else:
        recommendation = _legacy_recommendation_for_stage(stage=stage, red_flags=red_flags, matched_patterns=matched_patterns)
        scoring_payload = {
            "score_total": None,
            "score_breakdown": None,
            "top_issues": [],
            "recommendation": recommendation,
            "recommendation_reason": scoring_error or "scoring_disabled",
            "scoring_version": str(scoring_config.get("scoring_version", "v0.1.3")),
        }
        recommendation_reason = scoring_payload["recommendation_reason"]

    dedup_required_actions = [a for a in dict.fromkeys([a for a in required_actions if a])]

    return {
        "section_id": section_id,
        "stage": stage,
        "matched_patterns": matched_patterns,
        "red_flags": red_flags,
        "coverage_gaps": coverage_gaps,
        "weak_passages": weak_passages,
        "score_total": scoring_payload["score_total"],
        "score_breakdown": scoring_payload["score_breakdown"],
        "top_issues": scoring_payload["top_issues"],
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "scoring_version": scoring_payload["scoring_version"],
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
    scoring_config_path: str | None = None,
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

    has_critical_weak = any(str(w.get("severity", "")).lower() == "critical" for w in weak_passages)
    has_high_weak = any(str(w.get("severity", "")).lower() == "high" for w in weak_passages)
    has_material_gap = bool(coverage_gaps)

    confidence_signals: list[str] = []
    if len(set(source_ids)) >= 2:
        confidence_signals.append("source_diversity_good")
    if not unsupported_claims:
        confidence_signals.append("claims_supported")
    if not has_high_weak and not has_critical_weak:
        confidence_signals.append("passages_relevance_ok")
    if not has_material_gap and not red_flags:
        confidence_signals.append("no_material_red_flags")

    scoring_config, scoring_error = load_scoring_config(scoring_config_path)
    scoring_enabled = bool(scoring_config.get("enabled", True)) and not scoring_error

    if scoring_enabled:
        scoring_payload = _score_report(
            stage="evidence",
            matched_patterns=matched_patterns,
            red_flags=red_flags,
            coverage_gaps=coverage_gaps,
            weak_passages=weak_passages,
            confidence_signals=confidence_signals,
            config=scoring_config,
        )
        recommendation = scoring_payload["recommendation"]
        recommendation_reason = scoring_payload["recommendation_reason"]
    else:
        recommendation = _legacy_recommendation_for_stage(
            stage="evidence", red_flags=red_flags, matched_patterns=matched_patterns
        )
        scoring_payload = {
            "score_total": None,
            "score_breakdown": None,
            "top_issues": [],
            "recommendation": recommendation,
            "recommendation_reason": scoring_error or "scoring_disabled",
            "scoring_version": str(scoring_config.get("scoring_version", "v0.1.3")),
        }
        recommendation_reason = scoring_payload["recommendation_reason"]

    if has_material_gap:
        required_actions.append("Consolidează acoperirea evidence pentru claim-uri și întrebări.")
    if has_high_weak or has_critical_weak:
        required_actions.append("Elimină sau înlocuiește pasajele slabe/irelevante.")

    required_actions = [item for item in dict.fromkeys([a for a in required_actions if a])]

    summary = (
        f"coverage_gaps={len(coverage_gaps)} weak_passages={len(weak_passages)} "
        f"red_flags={len(red_flags)} recommendation={recommendation} score_total={scoring_payload['score_total']}"
    )

    return {
        "section_id": section_id,
        "stage": "evidence",
        "matched_patterns": matched_patterns,
        "red_flags": red_flags,
        "coverage_gaps": coverage_gaps,
        "weak_passages": weak_passages,
        "score_total": scoring_payload["score_total"],
        "score_breakdown": scoring_payload["score_breakdown"],
        "top_issues": scoring_payload["top_issues"],
        "recommendation": recommendation,
        "recommendation_reason": recommendation_reason,
        "scoring_version": scoring_payload["scoring_version"],
        "required_actions": required_actions,
        "summary": summary,
        "is_material_issue": has_material_gap or has_critical_weak,
        "snapshot_source": snapshot.get("source"),
        "snapshot_generated_at": snapshot.get("generated_at"),
    }
