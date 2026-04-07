from __future__ import annotations

import json
import urllib.error
import urllib.request


def _extract_json_object(raw: str) -> dict | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = raw[start : end + 1]
    try:
        parsed = json.loads(snippet)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def generate_structured_json(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    host: str = "http://localhost:11434",
    timeout_seconds: int = 90,
) -> dict | None:
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "format": schema,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {"temperature": 0.2},
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    try:
        envelope = json.loads(raw_body)
    except json.JSONDecodeError:
        return None

    content = envelope.get("message", {}).get("content", "")
    return _extract_json_object(content)
