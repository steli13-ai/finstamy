from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from pathlib import Path

from app.services.retrieval import hybrid_retrieve, lexical_score

try:
    import lancedb
except Exception:
    lancedb = None


def _post_json(url: str, payload: dict, timeout_seconds: int = 90) -> dict | None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _embed_many(texts: list[str], host: str, model: str) -> list[list[float]] | None:
    if not texts:
        return []

    host = host.rstrip("/")
    data = _post_json(f"{host}/api/embed", {"model": model, "input": texts})
    if data and isinstance(data.get("embeddings"), list):
        emb = data["embeddings"]
        if len(emb) == len(texts):
            return emb

    vectors: list[list[float]] = []
    for text in texts:
        one = _post_json(f"{host}/api/embeddings", {"model": model, "prompt": text})
        if not one or not isinstance(one.get("embedding"), list):
            return None
        vectors.append(one["embedding"])
    return vectors


def _embed_one(text: str, host: str, model: str) -> list[float] | None:
    result = _embed_many([text], host=host, model=model)
    if not result:
        return None
    return result[0]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def index_chunks(
    *,
    project_dir: str,
    chunks: list[dict],
    ollama_host: str,
    embedding_model: str,
) -> dict:
    if not chunks:
        return {"backend": "empty", "indexed": 0}

    retrieval_dir = Path(project_dir) / "retrieval"
    retrieval_dir.mkdir(parents=True, exist_ok=True)

    texts = [c.get("text", "") for c in chunks]
    vectors = _embed_many(texts, host=ollama_host, model=embedding_model)

    if lancedb is None or vectors is None:
        (retrieval_dir / "chunks.json").write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "backend": "json-fallback",
            "indexed": len(chunks),
            "reason": "lancedb_or_embedding_unavailable",
        }

    table_rows = []
    for chunk, vec in zip(chunks, vectors):
        table_rows.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "text": chunk["text"],
                "vector": vec,
            }
        )

    db = lancedb.connect(str(retrieval_dir / "lancedb"))
    db.create_table("chunks", data=table_rows, mode="overwrite")
    return {"backend": "lancedb", "indexed": len(chunks), "table": "chunks"}


def hybrid_search(
    *,
    project_dir: str,
    chunks: list[dict],
    queries: list[str],
    top_k: int,
    ollama_host: str,
    embedding_model: str,
) -> list[dict]:
    if not queries:
        return []

    retrieval_dir = Path(project_dir) / "retrieval"
    db_path = retrieval_dir / "lancedb"

    if lancedb is None or not db_path.exists():
        return hybrid_retrieve(chunks, queries, top_k=top_k)

    query_vectors = _embed_many(queries, host=ollama_host, model=embedding_model)
    if not query_vectors:
        return hybrid_retrieve(chunks, queries, top_k=top_k)

    try:
        db = lancedb.connect(str(db_path))
        table = db.open_table("chunks")
    except Exception:
        return hybrid_retrieve(chunks, queries, top_k=top_k)

    merged: dict[str, dict] = {}
    for query, q_vec in zip(queries, query_vectors):
        try:
            rows = table.search(q_vec).limit(top_k * 2).to_list()
        except Exception:
            return hybrid_retrieve(chunks, queries, top_k=top_k)

        for row in rows:
            distance = float(row.get("_distance", 1.0))
            vector_score = 1.0 / (1.0 + max(distance, 0.0))
            text = row.get("text", "")
            lex_score = lexical_score(query, text)
            score = 0.75 * vector_score + 0.25 * lex_score
            key = row["chunk_id"]

            existing = merged.get(key)
            if not existing or score > existing["score"]:
                merged[key] = {
                    "chunk_id": row["chunk_id"],
                    "source_id": row["source_id"],
                    "text": text,
                    "score": score,
                    "vector_score": vector_score,
                    "lexical_score": lex_score,
                }

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:top_k]


def vector_rerank(candidates: list[dict], section_goal: str, ollama_host: str, embedding_model: str) -> list[dict]:
    goal_vec = _embed_one(section_goal, host=ollama_host, model=embedding_model)
    if goal_vec is None:
        for c in candidates:
            c["rerank_score"] = c.get("score", 0.0)
        return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

    reranked = []
    for candidate in candidates:
        text = candidate.get("text", "")
        cand_vec = _embed_one(text[:1000], host=ollama_host, model=embedding_model)
        semantic = _cosine(goal_vec, cand_vec) if cand_vec else 0.0
        rerank_score = 0.8 * semantic + 0.2 * candidate.get("score", 0.0)
        reranked.append({**candidate, "rerank_score": rerank_score, "semantic_score": semantic})

    return sorted(reranked, key=lambda x: x["rerank_score"], reverse=True)
