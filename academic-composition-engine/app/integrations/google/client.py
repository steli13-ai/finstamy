from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GoogleSearchProvider(ABC):
    @abstractmethod
    def search(self, *, query: str, locale: str | None, top_k: int) -> list[dict]:
        raise NotImplementedError


class SerperGoogleProvider(GoogleSearchProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, *, query: str, locale: str | None, top_k: int) -> list[dict]:
        body = {"q": query, "num": max(1, min(top_k, 20))}
        if locale:
            body["gl"] = locale
        req = Request(
            "https://google.serper.dev/search",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("organic", [])


class NoopGoogleProvider(GoogleSearchProvider):
    def search(self, *, query: str, locale: str | None, top_k: int) -> list[dict]:
        params = urlencode({"q": query})
        return [
            {
                "title": "Google provider not configured",
                "link": f"https://www.google.com/search?{params}",
                "snippet": (
                    "Setează SERPER_API_KEY pentru rezultate API reale. "
                    "Acest fallback rămâne read-only și returnează doar link de discovery."
                ),
                "position": 1,
            }
        ]


def build_google_provider() -> GoogleSearchProvider:
    api_key = os.getenv("SERPER_API_KEY")
    if api_key:
        return SerperGoogleProvider(api_key=api_key)
    return NoopGoogleProvider()
