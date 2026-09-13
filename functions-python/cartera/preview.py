"""Índice de gestores y preview del job (sin I/O)."""

from __future__ import annotations

from typing import Any

from .config import SAMPLE_LIMIT
from .diff_engine import ChangeReport
from .excel_parser import get_seccion_summary


def index_section_gestores(usuarios: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """seccion_key → {uid, nombre}. Si hay conflicto, marca conflict=1."""
    index: dict[str, dict[str, str]] = {}
    conflicts: set[str] = set()
    for user in usuarios:
        if user.get("activo") is False:
            continue
        uid = str(user.get("uid") or "")
        nombre = str(user.get("nombre") or user.get("email") or uid)
        for key in user.get("secciones") or []:
            key = str(key).strip()
            if not key:
                continue
            if key in index and index[key]["uid"] != uid:
                conflicts.add(key)
            index[key] = {"uid": uid, "nombre": nombre}
    for key in conflicts:
        index[key]["conflict"] = "1"
    return index


def _sample_clients(items: list[dict], limit: int = SAMPLE_LIMIT) -> list[dict[str, str]]:
    out = []
    for item in items[:limit]:
        out.append(
            {
                "codigo_cliente": str(item.get("codigo_cliente") or ""),
                "nombre_completo": str(item.get("nombre_completo") or ""),
                "seccion_key": str(item.get("seccion_key") or ""),
            }
        )
    return out


def build_preview(
    *,
    parse_result: dict[str, Any],
    change_report: ChangeReport,
    usuarios: list[dict[str, Any]],
    modo: str,
    archivo_nombre: str = "",
) -> dict[str, Any]:
    assignment = index_section_gestores(usuarios)
    excel_sections = list(parse_result.get("by_seccion", {}).keys())
    sin_gestor = sorted(k for k in excel_sections if k not in assignment)
    conflictos = sorted(k for k, v in assignment.items() if v.get("conflict") and k in excel_sections)

    nuevos: list[dict] = []
    removidos: list[dict] = []
    actualizados: list[dict] = []
    for section in change_report.sections.values():
        nuevos.extend(section.new_clients)
        removidos.extend(section.removed_clients)
        actualizados.extend(c.to_sample() for c in section.updated_clients)

    return {
        "modo": modo,
        "archivo_nombre": archivo_nombre,
        "resumen": parse_result.get("summary") or {},
        "diff": change_report.summary_dict(),
        "secciones": get_seccion_summary(parse_result.get("by_seccion") or {}),
        "secciones_sin_gestor": sin_gestor,
        "conflictos_seccion": conflictos,
        "muestras": {
            "nuevos": _sample_clients(nuevos),
            "removidos": _sample_clients(removidos),
            "actualizados": actualizados[:SAMPLE_LIMIT],
        },
    }
