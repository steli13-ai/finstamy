from __future__ import annotations

import json
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
