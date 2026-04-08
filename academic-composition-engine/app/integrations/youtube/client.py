from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def search_youtube(
    *,
    query: str,
    max_results: int = 10,
    order: str | None = None,
    published_after: str | None = None,
) -> list[dict]:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return [
            {
                "id": {"videoId": ""},
                "snippet": {
                    "title": "YouTube provider not configured",
                    "description": "Setează YOUTUBE_API_KEY pentru rezultate reale.",
                    "publishedAt": None,
                    "channelTitle": None,
                },
                "_fallback_url": f"https://www.youtube.com/results?search_query={query}",
            }
        ]

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max(1, min(max_results, 50)),
        "key": api_key,
    }
    if order:
        params["order"] = order
    if published_after:
        params["publishedAfter"] = published_after

    url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("items", [])
