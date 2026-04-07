from __future__ import annotations

import mimetypes
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _build_multipart(field_name: str, file_path: Path, content_type: str | None = None) -> tuple[bytes, str]:
    boundary = f"----ACEBoundary{uuid.uuid4().hex}"
    ctype = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    content = file_path.read_bytes()

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"{field_name}\"; filename=\"{file_path.name}\"\r\n"
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def _tei_to_text(tei_xml: str) -> str:
    if not tei_xml.strip():
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", tei_xml)
    normalized = re.sub(r"\s+", " ", no_tags).strip()
    return normalized


def parse_pdf_with_grobid(path: Path, host: str = "http://localhost:8070") -> dict | None:
    if path.suffix.lower() != ".pdf":
        return None

    host = host.rstrip("/")
    endpoint = f"{host}/api/processFulltextDocument"
    body, boundary = _build_multipart("input", path, content_type="application/pdf")

    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            tei_xml = response.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    text = _tei_to_text(tei_xml)
    if not text:
        return None

    return {
        "source_id": path.stem,
        "format": "pdf",
        "text": text,
        "parser": "grobid",
        "endpoint": endpoint,
    }
