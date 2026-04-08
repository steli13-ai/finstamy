from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from app.services.io_utils import read_json, write_json


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _section_dir(project_dir: str, run_id: str, section_id: str) -> Path:
    path = Path(project_dir) / "runs" / run_id / "sections" / section_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def queue_path(project_dir: str, run_id: str, section_id: str) -> Path:
    return _section_dir(project_dir, run_id, section_id) / "candidate_sources_queue.json"


def report_path(project_dir: str, run_id: str, section_id: str) -> Path:
    return _section_dir(project_dir, run_id, section_id) / "candidate_sources_report.json"


def derive_source_type(*, discovery_channel: str, url: str) -> str:
    if discovery_channel == "youtube":
        return "video"
    if discovery_channel == "reddit":
        return "discussion"
    host = (urlparse(url).hostname or "").lower()
    if any(x in host for x in ["arxiv.org", "doi.org", "pubmed", "ieee", "acm", "springer", "sciencedirect"]):
        return "paper"
    return "web"


def infer_citable_status(*, discovery_channel: str, url: str) -> str:
    if discovery_channel == "reddit":
        return "non_citable"
    if discovery_channel == "youtube":
        return "non_citable"
    host = (urlparse(url).hostname or "").lower()
    if any(x in host for x in ["arxiv.org", "doi.org", "pubmed", "ieee", "acm", "springer", "sciencedirect"]):
        return "candidate_academic"
    return "needs_verification"


def build_candidate_entry(
    *,
    section_id: str,
    discovery_channel: str,
    result: dict,
    mapped_questions: list[str],
) -> dict:
    url = str(result.get("url", ""))
    created_at = utc_now_iso()
    return {
        "candidate_id": f"cand_{uuid4().hex[:12]}",
        "section_id": section_id,
        "source_type": derive_source_type(discovery_channel=discovery_channel, url=url),
        "discovery_channel": discovery_channel,
        "citable_status": infer_citable_status(discovery_channel=discovery_channel, url=url),
        "decision": "pending",
        "reason_for_keep_reject": "",
        "mapped_questions": mapped_questions,
        "title": str(result.get("title", "")),
        "url": url,
        "snippet": str(result.get("snippet", "")),
        "source": str(result.get("source", discovery_channel)),
        "raw_metadata": result.get("raw_metadata", {}),
        "created_at": created_at,
        "triaged_at": None,
    }


def load_queue(*, project_dir: str, run_id: str, section_id: str) -> list[dict]:
    path = queue_path(project_dir, run_id, section_id)
    if not path.exists():
        return []
    data = read_json(path)
    if not isinstance(data, list):
        return []
    return data


def save_queue(*, project_dir: str, run_id: str, section_id: str, queue: list[dict]) -> Path:
    path = queue_path(project_dir, run_id, section_id)
    write_json(path, queue)
    return path


def build_report(*, section_id: str, queue: list[dict]) -> dict:
    by_channel: dict[str, int] = {}
    by_citable_status: dict[str, int] = {}
    reasons: dict[str, int] = {}

    accepted = 0
    rejected = 0
    pending = 0
    for row in queue:
        channel = str(row.get("discovery_channel", "unknown"))
        status = str(row.get("citable_status", "unknown"))
        decision = str(row.get("decision", "pending"))
        reason = str(row.get("reason_for_keep_reject", "")).strip()

        by_channel[channel] = by_channel.get(channel, 0) + 1
        by_citable_status[status] = by_citable_status.get(status, 0) + 1

        if decision == "accepted":
            accepted += 1
        elif decision == "rejected":
            rejected += 1
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
        else:
            pending += 1

    return {
        "section_id": section_id,
        "generated_at": utc_now_iso(),
        "total_candidates": len(queue),
        "accepted": accepted,
        "rejected": rejected,
        "pending": pending,
        "by_channel": by_channel,
        "by_citable_status": by_citable_status,
        "reasons_summary": reasons,
    }


def save_report(*, project_dir: str, run_id: str, section_id: str, report: dict) -> Path:
    path = report_path(project_dir, run_id, section_id)
    write_json(path, report)
    return path


def triage_candidate(*, queue: list[dict], candidate_id: str, decision: str, reason: str) -> list[dict]:
    if decision not in {"accepted", "rejected"}:
        raise ValueError("decision trebuie să fie accepted sau rejected")

    found = False
    for row in queue:
        if row.get("candidate_id") == candidate_id:
            row["decision"] = decision
            row["reason_for_keep_reject"] = reason
            row["triaged_at"] = utc_now_iso()
            found = True
            break
    if not found:
        raise ValueError(f"candidate_id inexistent: {candidate_id}")
    return queue


def accepted_candidates(queue: list[dict]) -> list[dict]:
    return [row for row in queue if str(row.get("decision", "pending")) == "accepted"]


def ingest_accepted_candidates(*, project_dir: str, run_id: str, section_id: str, queue: list[dict]) -> list[Path]:
    accepted = accepted_candidates(queue)
    sources_dir = Path(project_dir) / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for row in accepted:
        cid = str(row.get("candidate_id"))
        safe_id = cid.replace("/", "_")
        path = sources_dir / f"candidate_{safe_id}.md"
        content = "\n".join(
            [
                f"# {row.get('title', '')}",
                "",
                f"- url: {row.get('url', '')}",
                f"- discovery_channel: {row.get('discovery_channel', '')}",
                f"- citable_status: {row.get('citable_status', '')}",
                f"- run_id: {run_id}",
                f"- section_id: {section_id}",
                "",
                str(row.get("snippet", "")),
            ]
        )
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
