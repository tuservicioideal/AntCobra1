"""Helpers for hierarchical territorial section keys (region_zona_seccion)."""
from __future__ import annotations

from typing import Iterable


def parse_composite_section_key(key: str) -> tuple[str, str, str] | None:
    """Parse `01_1211_H` into (region, zona, seccion). Returns None if invalid."""
    trimmed = (key or "").strip()
    if not trimmed:
        return None
    parts = trimmed.split("_")
    if len(parts) != 3:
        return None
    region, zona, seccion = parts[0].strip(), parts[1].strip(), parts[2].strip().upper()
    if not region or not zona or not seccion:
        return None
    return region, zona, seccion


def build_composite_section_key(region: str, zona: str, seccion: str) -> str:
    """Build composite key; empty string if any part missing."""
    r = (region or "").strip()
    z = (zona or "").strip()
    s = (seccion or "").strip().upper()
    if not r or not z or not s:
        return ""
    return f"{r}_{z}_{s}"


def group_secciones_by_hierarchy(
    keys: Iterable[str],
) -> dict[str, dict[str, list[str]]]:
    """Group composite keys as Región → Zona → [composite keys]. Skips non-composite."""
    result: dict[str, dict[str, list[str]]] = {}
    for raw in keys:
        parsed = parse_composite_section_key(str(raw))
        if not parsed:
            continue
        region, zona, seccion = parsed
        key = build_composite_section_key(region, zona, seccion)
        if not key:
            continue
        zonas = result.setdefault(region, {})
        secs = zonas.setdefault(zona, [])
        if key not in secs:
            secs.append(key)
    for zonas in result.values():
        for secs in zonas.values():
            secs.sort()
    return dict(sorted(result.items(), key=lambda item: item[0]))


def remove_region(keys: list[str], region: str) -> list[str]:
    """Remove every composite key belonging to region."""
    r = (region or "").strip()
    out: list[str] = []
    for k in keys:
        parsed = parse_composite_section_key(k)
        if parsed is None or parsed[0] != r:
            out.append(k)
    return out


def remove_zona(keys: list[str], region: str, zona: str) -> list[str]:
    """Remove every composite key belonging to region+zona."""
    r = (region or "").strip()
    z = (zona or "").strip()
    out: list[str] = []
    for k in keys:
        parsed = parse_composite_section_key(k)
        if parsed is None or parsed[0] != r or parsed[1] != z:
            out.append(k)
    return out


def remove_seccion(keys: list[str], key: str) -> list[str]:
    """Remove a single composite (or exact) key."""
    target = (key or "").strip()
    return [k for k in keys if (k or "").strip() != target]


def count_secciones_in_region(keys: Iterable[str], region: str) -> int:
    r = (region or "").strip()
    n = 0
    for k in keys:
        parsed = parse_composite_section_key(str(k))
        if parsed and parsed[0] == r:
            n += 1
    return n


def count_secciones_in_zona(keys: Iterable[str], region: str, zona: str) -> int:
    r = (region or "").strip()
    z = (zona or "").strip()
    n = 0
    for k in keys:
        parsed = parse_composite_section_key(str(k))
        if parsed and parsed[0] == r and parsed[1] == z:
            n += 1
    return n


def legacy_fields_from_secciones(keys: Iterable[str]) -> tuple[str, str, str]:
    """Derive legacy (region, zona, seccion) from the first remaining composite key."""
    for raw in keys:
        parsed = parse_composite_section_key(str(raw))
        if parsed:
            return parsed
    return "", "", ""
