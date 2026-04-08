from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source: str
    published_at: str | None = None
    author: str | None = None
    score: float | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class GoogleSearchInput(BaseModel):
    query: str
    locale: str | None = None
    top_k: int = 10


class YouTubeSearchInput(BaseModel):
    query: str
    max_results: int = 10
    order: str | None = None
    published_after: str | None = None


class RedditSearchInput(BaseModel):
    query: str
    subreddit: str | None = None
    sort: str | None = None
    time_window: str | None = None
    limit: int = 10
