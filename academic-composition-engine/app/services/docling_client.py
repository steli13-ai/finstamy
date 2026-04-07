from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


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


def _extract_text(data: dict) -> str:
    if not data:
        return ""
    for key in ("text", "markdown", "content", "md"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    if isinstance(data.get("result"), dict):
        return _extract_text(data["result"])
    return ""


def parse_file_with_docling(path: Path, host: str = "http://localhost:5001") -> dict | None:
    host = host.rstrip("/")
    payload = {"path": str(path)}
    candidate_urls = [
        f"{host}/parse",
        f"{host}/v1/parse",
        f"{host}/api/parse",
    ]

    for url in candidate_urls:
        data = _post_json(url, payload)
        text = _extract_text(data or {})
        if text.strip():
            return {
                "source_id": path.stem,
                "format": path.suffix.lower().lstrip("."),
                "text": text,
                "parser": "docling",
                "endpoint": url,
            }
    return None
