from app.graph.state import ProjectState
from app.contracts import EvidencePack, CandidatePassage


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    sections = {s["id"]: s for s in state.get("outline", {}).get("sections", [])}
    goal = sections.get(sid, {}).get("goal", "")
    last = next((r for r in reversed(state.get("retrieval_runs", [])) if r.get("reranked")), {"reranked": []})

    passages = []
    for c in last["reranked"][:10]:
        passages.append(
            CandidatePassage(
                source_id=c["source_id"],
                chunk_id=c["chunk_id"],
                passage_text=c["text"],
                passage_type="context",
            )
        )

    pack = EvidencePack(
        section_id=sid,
        section_goal=goal,
        questions_to_answer=["Care este problema?", "Care este obiectivul?"],
        candidate_passages=passages,
        allowed_claims=["Problema este relevantă în domeniu.", "Secțiunea definește obiectivul lucrării."],
        unsupported_claims=[],
    )
    packs = state.get("evidence_packs", {})
    packs[sid] = pack.model_dump()
    return {"evidence_packs": packs}