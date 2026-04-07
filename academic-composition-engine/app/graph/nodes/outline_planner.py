from app.graph.state import ProjectState


def run(state: ProjectState) -> ProjectState:
    outline = {
        "sections": [
            {"id": "s1", "title": "Introducere", "goal": "Definește contextul, problema și obiectivul secțiunii."},
            {"id": "s2", "title": "Discuție", "goal": "Analizează rezultate și limitări."},
        ]
    }
    return {"outline": outline}