"""Índice en memoria de clientes ya publicados. Evita get() por sección."""

from __future__ import annotations

from typing import Any

from .visit_merge import is_call_section


def index_clients_by_codigo(
    raw_by_seccion: dict[str, dict[str, dict]],
) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    index: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for sec, clients in raw_by_seccion.items():
        for code, doc in clients.items():
            cid = str(doc.get("codigo_cliente") or code)
            if not cid:
                continue
            index.setdefault(cid, []).append((str(sec), doc))
    return index


def lookup_existing_client(
    index: dict[str, list[tuple[str, dict[str, Any]]]],
    codigo: str,
    preferred_sec: str,
) -> tuple[str, dict[str, Any] | None]:
    """Prefiere la sección territorial; si no, una _CALL_; si no, cualquier copia."""
    rows = index.get(str(codigo)) or []
    for sec, doc in rows:
        if sec == preferred_sec:
            return sec, doc
    for sec, doc in rows:
        if is_call_section(sec):
            return sec, doc
    if rows:
        return rows[0]
    return preferred_sec, None


def campaign_section_keys(
    excel_by_seccion: dict[str, list],
    existing_gestor_ids: list[str],
) -> list[str]:
    """Excel territorial + secciones call ya publicadas (no pisa el índice call)."""
    keys = set(excel_by_seccion.keys())
    for gid in existing_gestor_ids:
        if is_call_section(gid):
            keys.add(gid)
    return sorted(keys)
