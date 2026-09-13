"""Orquestación parse → diff → preview (sin Firebase)."""

from __future__ import annotations

from typing import Any

from .diff_engine import ChangeReport, compare_cartera
from .excel_parser import parse_excel
from .preview import build_preview
from .visit_merge import reindex_cartera_for_diff


def parse_to_preview(
    excel_bytes: bytes,
    *,
    old_raw_cartera: dict[str, dict[str, dict]] | None = None,
    usuarios: list[dict[str, Any]] | None = None,
    archivo_nombre: str = "",
) -> tuple[dict[str, Any], ChangeReport, dict[str, Any], str]:
    parse_result = parse_excel(excel_bytes)
    raw = old_raw_cartera or {}
    indexed = reindex_cartera_for_diff(raw)
    report = compare_cartera(indexed, parse_result["by_seccion"])
    modo = "actualizacion" if any(raw.values()) else "inicial"
    preview = build_preview(
        parse_result=parse_result,
        change_report=report,
        usuarios=usuarios or [],
        modo=modo,
        archivo_nombre=archivo_nombre,
    )
    return parse_result, report, preview, modo
