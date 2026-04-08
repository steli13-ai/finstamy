from __future__ import annotations

import sys
import types

from app.integrations.google.normalize import normalize_google_results
from app.integrations.reddit.normalize import normalize_reddit_results
from app.integrations.youtube.normalize import normalize_youtube_results
from app.mcp.servers import research_server


def test_normalize_google_results_schema_fields():
    rows = [{"title": "T", "link": "https://x", "snippet": "S", "position": 1}]
    out = normalize_google_results(rows)
    assert len(out) == 1
    item = out[0].model_dump()
    for key in ["title", "url", "snippet", "source", "published_at", "author", "score", "raw_metadata"]:
        assert key in item
    assert item["source"] == "google"


def test_normalize_youtube_results_schema_fields():
    rows = [
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "Video",
                "description": "Descriere",
                "publishedAt": "2026-04-08T00:00:00Z",
                "channelTitle": "Canal",
            },
        }
    ]
    out = normalize_youtube_results(rows)
    assert out[0].source == "youtube"
    assert "youtube.com" in out[0].url


def test_normalize_reddit_results_schema_fields():
    rows = [{"title": "Post", "url": "https://reddit.com/x", "selftext": "Body", "author": "u1", "score": 4}]
    out = normalize_reddit_results(rows)
    assert out[0].source == "reddit"
    assert out[0].author == "u1"


def test_research_server_registers_exact_three_tools(monkeypatch):
    captured_tools: list[str] = []

    class FakeMCP:
        def __init__(self, name: str):
            self.name = name

        def tool(self, name: str):
            captured_tools.append(name)

            def decorator(fn):
                return fn

            return decorator

        def run(self):
            return None

    fake_fastmcp_module = types.SimpleNamespace(FastMCP=FakeMCP)
    fake_server_module = types.SimpleNamespace(fastmcp=fake_fastmcp_module)
    fake_mcp_module = types.SimpleNamespace(server=fake_server_module)

    monkeypatch.setitem(sys.modules, "mcp", fake_mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.server", fake_server_module)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fake_fastmcp_module)

    server = research_server.build_server()
    assert getattr(server, "name", "") == "research-mcp"
    assert captured_tools == ["google_search", "youtube_search", "reddit_search"]


def test_research_tool_functions_return_common_shape(monkeypatch):
    monkeypatch.setattr(
        research_server,
        "build_google_provider",
        lambda: types.SimpleNamespace(search=lambda **_: [{"title": "G", "link": "https://g", "snippet": "s", "position": 1}]),
    )
    monkeypatch.setattr(
        research_server,
        "search_youtube",
        lambda **_: [
            {
                "id": {"videoId": "v1"},
                "snippet": {"title": "Y", "description": "d", "publishedAt": None, "channelTitle": None},
            }
        ],
    )
    monkeypatch.setattr(
        research_server,
        "search_reddit",
        lambda **_: [{"title": "R", "url": "https://r", "selftext": "t", "author": "u", "score": 2}],
    )

    for payload in [
        research_server.google_search(query="x", top_k=1),
        research_server.youtube_search(query="x", max_results=1),
        research_server.reddit_search(query="x", limit=1),
    ]:
        assert len(payload) == 1
        row = payload[0]
        for key in ["title", "url", "snippet", "source", "published_at", "author", "score", "raw_metadata"]:
            assert key in row
