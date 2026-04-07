from __future__ import annotations
import re


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out = []
    i = 0
    while i < len(text):
        out.append(text[i : i + chunk_size])
        i += max(1, chunk_size - overlap)
    return out


def lexical_score(query: str, text: str) -> float:
    q = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    t = text.lower()
    if not q:
        return 0.0
    hits = sum(1 for w in q if w in t)
    return hits / len(q)


def hybrid_retrieve(chunks: list[dict], queries: list[str], top_k: int = 12) -> list[dict]:
    scored = []
    for c in chunks:
        score = max((lexical_score(q, c["text"]) for q in queries), default=0.0)
        if score > 0:
            scored.append({**c, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def rerank(candidates: list[dict], section_goal: str) -> list[dict]:
    # MVP rerank: boost simplu pe goal terms
    g = section_goal.lower()
    for c in candidates:
        c["rerank_score"] = c["score"] + (0.2 if any(w in c["text"].lower() for w in g.split()) else 0.0)
    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)