from __future__ import annotations
from pathlib import Path
import json
import re


def load_reference_keys(snapshot_path: str) -> list[str]:
    p = Path(snapshot_path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x.get("id", "") for x in data if isinstance(x, dict) and x.get("id")]
    if isinstance(data, dict) and "items" in data:
        return [x.get("id", "") for x in data["items"] if x.get("id")]
    return []


def resolve_needed_citations(citations_needed: list[str], available_keys: list[str]) -> dict:
    resolved, unresolved = [], []
    for i, claim_id in enumerate(citations_needed):
        if i < len(available_keys):
            resolved.append({"claim_id": claim_id, "citation_key": available_keys[i], "source_id": available_keys[i]})
        else:
            unresolved.append({"claim_id": claim_id, "reason": "no_key_available"})
    return {"resolved_citations": resolved, "unresolved": unresolved}


def inject_keys_in_markdown(md: str, resolved: list[dict]) -> str:
    # replace token [CITE:claim_id] -> [@key]
    out = md
    for r in resolved:
        token = f"[CITE:{r['claim_id']}]"
        out = out.replace(token, f"[@{r['citation_key']}]")
    out = re.sub(r"\s+", " ", out).replace(" ##", "\n##").replace(" .", ".")
    return out.strip() + "\n"