from __future__ import annotations

from app.mcp.schemas.research_tools import ResearchResult


def normalize_google_results(items: list[dict]) -> list[ResearchResult]:
    out: list[ResearchResult] = []
    for row in items:
        out.append(
            ResearchResult(
                title=str(row.get("title", "")),
                url=str(row.get("link", "")),
                snippet=str(row.get("snippet", "")),
                source="google",
                published_at=row.get("date") or None,
                author=None,
                score=float(row.get("position")) if row.get("position") is not None else None,
                raw_metadata=row,
            )
        )
    return out
