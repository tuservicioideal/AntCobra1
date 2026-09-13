"""Serialización del parse intermedio (JSON gzip)."""

from __future__ import annotations

import gzip
import json
from typing import Any


def dumps_parsed(parse_result: dict[str, Any]) -> bytes:
    payload = {
        "by_seccion": parse_result["by_seccion"],
        "summary": parse_result.get("summary") or {},
        "headers": parse_result.get("headers") or [],
    }
    return gzip.compress(
        json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    )


def loads_parsed(raw: bytes) -> dict[str, Any]:
    return json.loads(gzip.decompress(raw).decode("utf-8"))
