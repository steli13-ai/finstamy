from app.graph.state import ProjectState
from app.contracts import ClaimPlan, ClaimUnit
from app.services.ollama_client import generate_structured_json


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    pack = state.get("evidence_packs", {}).get(sid, {})
    chunks = [p["chunk_id"] for p in pack.get("candidate_passages", [])[:3]]

    plan: ClaimPlan | None = None
    if state.get("use_ollama", False):
        schema = ClaimPlan.model_json_schema()
        response = generate_structured_json(
            model=state.get("ollama_model", "qwen3:8b"),
            host=state.get("ollama_host", "http://localhost:11434"),
            system_prompt="Generezi un claim plan strict JSON valid. Folosește doar chunk-urile furnizate.",
            user_prompt=(
                f"section_id={sid}\n"
                f"section_goal={pack.get('section_goal', '')}\n"
                f"allowed_claims={pack.get('allowed_claims', [])}\n"
                f"candidate_chunk_ids={chunks}"
            ),
            schema=schema,
        )
        if response:
            response["section_id"] = sid
            try:
                plan = ClaimPlan.model_validate(response)
            except Exception:
                plan = None

    if plan is None:
        plan = ClaimPlan(
            section_id=sid,
            argument_order=["context", "problem", "objective"],
            claim_units=[
                ClaimUnit(claim_id=f"{sid}_c1", text="Contextul temei este definit pe baza surselor.", supporting_chunks=chunks[:1]),
                ClaimUnit(claim_id=f"{sid}_c2", text="Problema principală este formulată explicit.", supporting_chunks=chunks[:2]),
                ClaimUnit(claim_id=f"{sid}_c3", text="Obiectivul secțiunii este justificat.", supporting_chunks=chunks[:3]),
            ],
        )

    plans = state.get("claim_plans", {})
    plans[sid] = plan.model_dump()
    return {"claim_plans": plans}