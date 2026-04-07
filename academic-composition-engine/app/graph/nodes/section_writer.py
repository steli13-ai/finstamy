from app.graph.state import ProjectState
from app.contracts import SectionDraft
from app.services.ollama_client import generate_structured_json


def run(state: ProjectState) -> ProjectState:
    sid = state["target_section_id"]
    sections = {s["id"]: s for s in state.get("outline", {}).get("sections", [])}
    title = sections.get(sid, {}).get("title", sid)
    plan = state.get("claim_plans", {}).get(sid, {})
    claims = plan.get("claim_units", [])

    paragraphs = []
    citations_needed = []
    used_chunks = []

    for cu in claims:
        cid = cu["claim_id"]
        txt = cu["text"]
        paragraphs.append(f"{txt} [CITE:{cid}]")
        citations_needed.append(cid)
        used_chunks.extend(cu.get("supporting_chunks", []))

    md = f"## {title}\n\n" + "\n\n".join(paragraphs) + "\n"

    draft: SectionDraft | None = None
    if state.get("use_ollama", False):
        schema = {
            "type": "object",
            "properties": {
                "draft_markdown": {"type": "string"},
                "citations_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["draft_markdown", "citations_needed"],
        }
        llm_response = generate_structured_json(
            model=state.get("ollama_model", "qwen3:8b"),
            host=state.get("ollama_host", "http://localhost:11434"),
            system_prompt=(
                "Scrii secțiunea academică strict pe baza claim-urilor furnizate. "
                "Păstrează tokenii [CITE:claim_id] în text pentru fiecare claim relevant."
            ),
            user_prompt=(
                f"section_title={title}\n"
                f"claim_units={claims}\n"
                f"draft_template={md}"
            ),
            schema=schema,
        )
        if llm_response:
            llm_md = llm_response.get("draft_markdown", "")
            llm_citations = llm_response.get("citations_needed", [])
            valid_citations = [c for c in llm_citations if c in citations_needed]
            if llm_md:
                draft = SectionDraft(
                    section_id=sid,
                    title=title,
                    draft_markdown=llm_md if llm_md.endswith("\n") else f"{llm_md}\n",
                    used_chunks=sorted(set(used_chunks)),
                    citations_needed=valid_citations or citations_needed,
                )

    if draft is None:
        draft = SectionDraft(
            section_id=sid,
            title=title,
            draft_markdown=md,
            used_chunks=sorted(set(used_chunks)),
            citations_needed=citations_needed,
        )

    drafted = state.get("drafted_sections", {})
    drafted[sid] = draft.model_dump()
    return {"drafted_sections": drafted}