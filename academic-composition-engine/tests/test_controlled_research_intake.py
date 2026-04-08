from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    ace_path = Path(sys.executable).parent / "ace"
    return subprocess.run([str(ace_path), *args], cwd=str(cwd), text=True, capture_output=True)


def _extract_run_id(output: str) -> str | None:
    match = re.search(r"run=([A-Za-z0-9_:\-\.\+]+)", output)
    return match.group(1) if match else None


def test_controlled_intake_discover_builds_queue_and_report():
    repo = Path(__file__).resolve().parents[1]
    project_id = f"intake_demo_{int(time.time())}"

    init_proc = _run_cli(["init", project_id], cwd=repo)
    assert init_proc.returncode == 0, init_proc.stderr

    discover = _run_cli(
        [
            "discover-sources",
            project_id,
            "--section-id",
            "s1",
            "--query",
            "evidence grounded writing",
            "--channels",
            "google,youtube",
            "--top-k",
            "2",
            "--mapped-questions",
            "Care este problema?|Care este obiectivul?",
        ],
        cwd=repo,
    )
    assert discover.returncode == 0, discover.stderr
    run_id = _extract_run_id(discover.stdout)
    assert run_id, discover.stdout

    section_dir = repo / "data" / "projects" / project_id / "runs" / run_id / "sections" / "s1"
    queue_path = section_dir / "candidate_sources_queue.json"
    report_path = section_dir / "candidate_sources_report.json"
    assert queue_path.exists()
    assert report_path.exists()

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert len(queue) >= 2
    required = {
        "candidate_id",
        "section_id",
        "source_type",
        "discovery_channel",
        "citable_status",
        "decision",
        "reason_for_keep_reject",
        "mapped_questions",
        "title",
        "url",
        "snippet",
        "source",
        "raw_metadata",
        "created_at",
        "triaged_at",
    }
    for row in queue:
        assert required.issubset(set(row.keys()))
        assert row["decision"] == "pending"


def test_controlled_intake_triage_persists_decision_and_ingest_filters_accepted():
    repo = Path(__file__).resolve().parents[1]
    project_id = f"intake_demo_{int(time.time())}_triage"

    init_proc = _run_cli(["init", project_id], cwd=repo)
    assert init_proc.returncode == 0, init_proc.stderr

    discover = _run_cli(
        [
            "discover-sources",
            project_id,
            "--section-id",
            "s1",
            "--query",
            "academic writing pitfalls",
            "--channels",
            "google,youtube",
            "--top-k",
            "2",
        ],
        cwd=repo,
    )
    assert discover.returncode == 0, discover.stderr
    run_id = _extract_run_id(discover.stdout)
    assert run_id

    section_dir = repo / "data" / "projects" / project_id / "runs" / run_id / "sections" / "s1"
    queue_path = section_dir / "candidate_sources_queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert len(queue) >= 2

    first = queue[0]["candidate_id"]
    second = queue[1]["candidate_id"]

    t1 = _run_cli(
        [
            "triage-source",
            project_id,
            "--run-id",
            run_id,
            "--section-id",
            "s1",
            "--candidate-id",
            first,
            "--decision",
            "accept",
            "--reason",
            "relevant to RQ1",
        ],
        cwd=repo,
    )
    assert t1.returncode == 0, t1.stderr

    t2 = _run_cli(
        [
            "triage-source",
            project_id,
            "--run-id",
            run_id,
            "--section-id",
            "s1",
            "--candidate-id",
            second,
            "--decision",
            "reject",
            "--reason",
            "non-citable context only",
        ],
        cwd=repo,
    )
    assert t2.returncode == 0, t2.stderr

    queue_after = json.loads(queue_path.read_text(encoding="utf-8"))
    lookup = {row["candidate_id"]: row for row in queue_after}
    assert lookup[first]["decision"] == "accepted"
    assert lookup[first]["reason_for_keep_reject"] == "relevant to RQ1"
    assert lookup[first]["triaged_at"] is not None
    assert lookup[second]["decision"] == "rejected"

    ingest = _run_cli(
        [
            "ingest-accepted-sources",
            project_id,
            "--run-id",
            run_id,
            "--section-id",
            "s1",
        ],
        cwd=repo,
    )
    assert ingest.returncode == 0, ingest.stderr

    sources_dir = repo / "data" / "projects" / project_id / "sources"
    accepted_file = sources_dir / f"candidate_{first}.md"
    rejected_file = sources_dir / f"candidate_{second}.md"
    assert accepted_file.exists()
    assert not rejected_file.exists()

    report = json.loads((section_dir / "candidate_sources_report.json").read_text(encoding="utf-8"))
    assert report["accepted"] >= 1
    assert report["rejected"] >= 1
