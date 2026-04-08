from __future__ import annotations

from app.integrations.google.client import build_google_provider
from app.integrations.google.normalize import normalize_google_results
from app.integrations.reddit.client import search_reddit
from app.integrations.reddit.normalize import normalize_reddit_results
from app.integrations.youtube.client import search_youtube
from app.integrations.youtube.normalize import normalize_youtube_results
from app.mcp.schemas.research_tools import (
    GoogleSearchInput,
    RedditSearchInput,
    YouTubeSearchInput,
)


def google_search(*, query: str, locale: str | None = None, top_k: int = 10) -> list[dict]:
    payload = GoogleSearchInput(query=query, locale=locale, top_k=top_k)
    provider = build_google_provider()
    raw = provider.search(query=payload.query, locale=payload.locale, top_k=payload.top_k)
    return [r.model_dump() for r in normalize_google_results(raw)]


def youtube_search(
    *,
    query: str,
    max_results: int = 10,
    order: str | None = None,
    published_after: str | None = None,
) -> list[dict]:
    payload = YouTubeSearchInput(
        query=query,
        max_results=max_results,
        order=order,
        published_after=published_after,
    )
    raw = search_youtube(
        query=payload.query,
        max_results=payload.max_results,
        order=payload.order,
        published_after=payload.published_after,
    )
    return [r.model_dump() for r in normalize_youtube_results(raw)]


def reddit_search(
    *,
    query: str,
    subreddit: str | None = None,
    sort: str | None = None,
    time_window: str | None = None,
    limit: int = 10,
) -> list[dict]:
    payload = RedditSearchInput(
        query=query,
        subreddit=subreddit,
        sort=sort,
        time_window=time_window,
        limit=limit,
    )
    raw = search_reddit(
        query=payload.query,
        subreddit=payload.subreddit,
        sort=payload.sort,
        time_window=payload.time_window,
        limit=payload.limit,
    )
    return [r.model_dump() for r in normalize_reddit_results(raw)]


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:
        raise RuntimeError(
            "Pachetul MCP nu este instalat. Instalează dependența `mcp` pentru a porni research-mcp server."
        ) from exc

    server = FastMCP("research-mcp")
    server.tool(name="google_search")(google_search)
    server.tool(name="youtube_search")(youtube_search)
    server.tool(name="reddit_search")(reddit_search)
    return server


def main():
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
