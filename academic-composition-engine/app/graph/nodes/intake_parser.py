from app.graph.state import ProjectState
from app.contracts import Intake
from app.services.ollama_client import generate_structured_json


def run(state: ProjectState) -> ProjectState:
    brief = state.get("brief_raw", "").strip()
    use_ollama = state.get("use_ollama", False)

    intake: Intake | None = None
    if use_ollama:
        schema = Intake.model_json_schema()
        response = generate_structured_json(
            model=state.get("ollama_model", "qwen3:8b"),
            host=state.get("ollama_host", "http://localhost:11434"),
            system_prompt="Extragi un intake academic strict JSON valid conform schema. Nu inventa informații absente.",
            user_prompt=f"Brief:\n{brief}",
            schema=schema,
        )
        if response:
            try:
                intake = Intake.model_validate(response)
            except Exception:
                intake = None

    if intake is None:
        title = brief.split("\n")[0][:120] if brief else "Untitled"
        intake = Intake(
            title=title,
            domain="unknown",
            academic_level="licenta",
            required_length_pages=8,
            language="ro",
            citation_style="APA",
            notes=brief[:2000],
        )

    return {"brief_structured": intake.model_dump()}