from __future__ import annotations

from datetime import datetime, timezone

from app.mcp.schemas.research_tools import ResearchResult


def _to_iso_utc(ts) -> str | None:
    if ts is None:
        return None
    try:
        value = float(ts)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def normalize_reddit_results(items: list[dict]) -> list[ResearchResult]:
    out: list[ResearchResult] = []
    for row in items:
        permalink = row.get("permalink") or ""
        url = row.get("url") or (f"https://www.reddit.com{permalink}" if permalink else "")
        out.append(
            ResearchResult(
                title=str(row.get("title", "")),
                url=url,
                snippet=str(row.get("selftext", ""))[:500],
                source="reddit",
                published_at=_to_iso_utc(row.get("created_utc")),
                author=row.get("author") or None,
                score=float(row.get("score")) if row.get("score") is not None else None,
                raw_metadata=row,
            )
        )
    return out
