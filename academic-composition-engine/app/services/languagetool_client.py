from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request


def _context_window(text: str, offset: int, length: int, window: int = 40) -> str:
    start = max(0, offset - window)
    end = min(len(text), offset + length + window)
    return text[start:end]


def _citation_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    patterns = [
        r"\[@[^\]]+\]",
        r"\([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+,\s*\d{4}[a-z]?\)",
        r"\([A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț\-]+\s+et\s+al\.,\s*\d{4}[a-z]?\)",
        r"\[[0-9,\s\-]+\]",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            spans.append((m.start(), m.end()))
    return spans


def _overlaps_span(offset: int, length: int, spans: list[tuple[int, int]]) -> bool:
    end = offset + max(length, 1)
    for s, e in spans:
        if offset < e and end > s:
            return True
    return False


def _severity_from_rule(category_id: str, issue_type: str, rule_id: str) -> str:
    key = f"{category_id}|{issue_type}|{rule_id}".upper()
    if any(x in key for x in ["GRAMMAR", "AGREEMENT", "TYPOS", "SPELL", "MORFOLOG"]):
        return "high"
    if any(x in key for x in ["PUNCT", "STYLE", "REDUNDANC", "CASING", "WHITESPACE"]):
        return "medium"
    return "low"


def _score(counts: dict) -> int:
    raw = 100 - (counts["high"] * 12 + counts["medium"] * 5 + counts["low"] * 1)
    return max(0, min(100, raw))


def _heuristic_issues(text: str) -> list[dict]:
    issues = []

    for m in re.finditer(r"\s+[,.;:!?]", text):
        issues.append(
            {
                "rule_id": "COMMA_PARENTHESIS_WHITESPACE",
                "severity": "low",
                "message": "Spațiere incorectă înainte de semn de punctuație.",
                "offset": m.start(),
                "length": len(m.group(0)),
                "context": _context_window(text, m.start(), len(m.group(0))),
                "suggestions": [m.group(0).strip()],
            }
        )

    for m in re.finditer(r" {2,}", text):
        issues.append(
            {
                "rule_id": "DOUBLE_WHITESPACE",
                "severity": "medium",
                "message": "Spații multiple consecutive.",
                "offset": m.start(),
                "length": len(m.group(0)),
                "context": _context_window(text, m.start(), len(m.group(0))),
                "suggestions": [" "],
            }
        )

    if text.count("(") != text.count(")"):
        idx = text.find("(") if text.count("(") > text.count(")") else text.find(")")
        idx = max(0, idx)
        issues.append(
            {
                "rule_id": "UNBALANCED_PARENTHESES",
                "severity": "high",
                "message": "Paranteze dezechilibrate în text.",
                "offset": idx,
                "length": 1,
                "context": _context_window(text, idx, 1),
                "suggestions": [],
            }
        )

    return issues


def _call_languagetool(text: str, language: str, host: str) -> list[dict] | None:
    endpoint = f"{host.rstrip('/')}/v2/check"
    payload = urllib.parse.urlencode({"text": text, "language": language}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None

    matches = data.get("matches", []) if isinstance(data, dict) else []
    spans = _citation_spans(text)
    issues: list[dict] = []

    for m in matches:
        offset = int(m.get("offset", 0))
        length = int(m.get("length", 0))
        if _overlaps_span(offset, length, spans):
            continue

        rule = m.get("rule", {}) if isinstance(m.get("rule"), dict) else {}
        category = rule.get("category", {}) if isinstance(rule.get("category"), dict) else {}
        category_id = str(category.get("id", ""))
        issue_type = str(rule.get("issueType", ""))
        rule_id = str(rule.get("id", "LT_UNKNOWN"))
        severity = _severity_from_rule(category_id, issue_type, rule_id)
        replacements = m.get("replacements", []) if isinstance(m.get("replacements"), list) else []

        issues.append(
            {
                "rule_id": rule_id,
                "severity": severity,
                "message": str(m.get("message", "Problemă lingvistică detectată.")),
                "offset": offset,
                "length": length,
                "context": _context_window(text, offset, length),
                "suggestions": [str(r.get("value")) for r in replacements[:5] if isinstance(r, dict) and r.get("value")],
            }
        )

    return issues


def analyze_text(text: str, language: str = "ro", host: str = "http://localhost:8081") -> dict:
    lt_issues = _call_languagetool(text, language=language, host=host)
    issues = lt_issues if lt_issues is not None else _heuristic_issues(text)

    counts = {"low": 0, "medium": 0, "high": 0}
    for issue in issues:
        sev = issue.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

    score = _score(counts)
    status = "ok" if counts["high"] == 0 else "needs_review"

    return {
        "status": status,
        "language": language,
        "issues": issues,
        "counts": counts,
        "score": score,
    }
