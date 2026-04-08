from __future__ import annotations

from app.mcp.schemas.research_tools import ResearchResult


def normalize_youtube_results(items: list[dict]) -> list[ResearchResult]:
    out: list[ResearchResult] = []
    for idx, row in enumerate(items, start=1):
        snippet = row.get("snippet", {})
        video_id = ((row.get("id") or {}).get("videoId") or "").strip()
        fallback_url = row.get("_fallback_url")
        video_url = fallback_url or (f"https://www.youtube.com/watch?v={video_id}" if video_id else "")
        out.append(
            ResearchResult(
                title=str(snippet.get("title", "")),
                url=video_url,
                snippet=str(snippet.get("description", "")),
                source="youtube",
                published_at=snippet.get("publishedAt") or None,
                author=snippet.get("channelTitle") or None,
                score=float(idx),
                raw_metadata=row,
            )
        )
    return out
