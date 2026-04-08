from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def search_reddit(
    *,
    query: str,
    subreddit: str | None = None,
    sort: str | None = None,
    time_window: str | None = None,
    limit: int = 10,
) -> list[dict]:
    base = "https://www.reddit.com"
    path = f"/r/{subreddit}/search.json" if subreddit else "/search.json"
    params = {
        "q": query,
        "restrict_sr": "1" if subreddit else "0",
        "limit": max(1, min(limit, 50)),
        "sort": sort or "relevance",
        "t": time_window or "all",
    }
    url = f"{base}{path}?{urlencode(params)}"

    req = Request(
        url,
        headers={
            "User-Agent": "academic-composition-engine/0.1.0 research-mcp",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    children = payload.get("data", {}).get("children", [])
    return [c.get("data", {}) for c in children]
