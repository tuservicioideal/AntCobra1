"""Preserva campos de gestión del gestor al re-subir el Excel."""

from __future__ import annotations

from typing import Any

from .config import CALL_SECTION_PREFIX

VISIT_FIELDS = (
    "estado_gestion",
    "fecha_gestion",
    "nota_gestor",
    "gps_gestor",
    "ubicacion_verificada",
    "ubicacion_verificada_lat",
    "ubicacion_verificada_lng",
    "ubicacion_verificada_fecha",
    "ubicacion_verificada_gestor",
    "historial_zona",
    "gps_latitud",
    "gps_longitud",
    "gps_timestamp",
    "nivel_1",
    "nivel_2",
    "nivel_3",
    "nivel_4",
    "canal_gestion",
    "fecha_promesa_pago",
    "monto_promesa_pago",
    "direccion",
    "telefono_movil",
    "ultima_nota_contacto",
    "fecha_actualizacion_contacto_iso",
    "actualizado_por_uid",
    "actualizado_por_nombre",
    "actualizado_por_email",
    "origen_actualizacion",
    "etiquetas",
    "semaforo",
    "tramo_actual",
    "fase_gestion",
    "call_gestor_uid",
    "call_gestor_nombre",
)

# Campos de clasificación de campo: se preservan aunque no haya visita/contacto.
_ALWAYS_PRESERVE_FIELDS = ("etiquetas", "semaforo")


def extract_visit_fields(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not doc:
        return {}
    has_visit = doc.get("estado_gestion") and doc.get("estado_gestion") != "pendiente"
    has_contact = bool(doc.get("fecha_actualizacion_contacto_iso"))
    if not has_visit and not has_contact:
        # Sin gestión: igual preservar semáforo/etiquetas asignados en campo.
        return {
            k: doc.get(k)
            for k in _ALWAYS_PRESERVE_FIELDS
            if k in doc and doc.get(k) not in (None, "", [])
        }
    return {k: doc.get(k) for k in VISIT_FIELDS}


def apply_visit_fields(doc: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    if not prev:
        return doc
    merged = dict(doc)
    merged.update(prev)
    return merged


def is_call_section(seccion_key: str) -> bool:
    return str(seccion_key or "").startswith(CALL_SECTION_PREFIX)


def reindex_cartera_for_diff(
    raw_by_seccion: dict[str, dict[str, dict]],
) -> dict[str, dict[str, dict]]:
    """Reubica clientes de _CALL_* bajo su seccion_key territorial para el diff."""
    territorial: dict[str, dict[str, dict]] = {}
    call_overlay: dict[str, dict[str, dict]] = {}

    for sec, clients in raw_by_seccion.items():
        target_map = call_overlay if is_call_section(sec) else territorial
        for code, data in clients.items():
            tagged = dict(data)
            tagged["codigo_cliente"] = tagged.get("codigo_cliente") or code
            tagged["_firestore_seccion"] = sec
            if is_call_section(sec):
                bucket = (
                    tagged.get("seccion_key_origen")
                    or tagged.get("seccion_key")
                    or sec
                )
            else:
                bucket = sec
            target_map.setdefault(str(bucket), {})[code] = tagged

    merged: dict[str, dict[str, dict]] = {}
    for bucket, clients in territorial.items():
        merged.setdefault(bucket, {}).update(clients)
    for bucket, clients in call_overlay.items():
        merged.setdefault(bucket, {}).update(clients)
    return merged
