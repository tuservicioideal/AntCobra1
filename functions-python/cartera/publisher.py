"""Publicación de cartera a un store (Firestore o InMemoryStore)."""

from __future__ import annotations

from typing import Any, Callable

from .client_lookup import (
    campaign_section_keys,
    index_clients_by_codigo,
    lookup_existing_client,
)
from .config import BATCH_LIMIT, CAMPAIGN_ID_DEFAULT, MOTIVO_BAJA_EXCEL_BANCO
from .diff_engine import ChangeReport
from .excel_parser import get_hierarchy
from .store import InMemoryStore  # tipo de referencia; FirestoreStore es duck-typed
from .visit_merge import apply_visit_fields, extract_visit_fields


ProgressCb = Callable[[int, int, str], None]


def _strip_internal(client: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in client.items() if not str(k).startswith("_")}
    out.pop("contactos_seed", None)
    return out


def _lifecycle(*, activo: bool, motivo_baja: str = "", ultimo_excel: str = "") -> dict[str, Any]:
    fields: dict[str, Any] = {
        "activo_en_cartera": activo,
        "motivo_baja": motivo_baja if not activo else "",
    }
    if ultimo_excel:
        fields["ultimo_excel"] = ultimo_excel
    if not activo:
        fields["fecha_baja"] = "SERVER_TIMESTAMP"
    return fields


def _section_totals(clients: list[dict[str, Any]]) -> dict[str, Any]:
    sample = clients[0] if clients else {}
    deuda_total = sum(float(c.get("importe_deuda_asignada", 0) or 0) for c in clients)
    deuda_pendiente = sum(float(c.get("importe_deuda_pendiente", 0) or 0) for c in clients)
    con_coords = sum(
        1
        for c in clients
        if float(c.get("coordenada_y", 0) or 0) != 0
        and float(c.get("coordenada_x", 0) or 0) != 0
    )
    return {
        "seccion_key": sample.get("seccion_key", ""),
        "seccion": sample.get("seccion", ""),
        "region": sample.get("region", ""),
        "zona": sample.get("zona", ""),
        "num_clientes": len(clients),
        "clientes_con_coordenadas": con_coords,
        "deuda_asignada_total": round(deuda_total, 2),
        "deuda_pendiente_total": round(deuda_pendiente, 2),
        "estado": "pendiente",
    }


def plan_and_apply(
    store: InMemoryStore,
    *,
    by_seccion: dict[str, list[dict[str, Any]]],
    change_report: ChangeReport,
    campaign_id: str = CAMPAIGN_ID_DEFAULT,
    ultimo_excel: str = "",
    progress_callback: ProgressCb | None = None,
    existing_cartera: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any]:
    """Aplica el diff. Visitas desde existing_cartera en memoria (nunca N get por sección)."""
    written = 0
    preserved = 0
    archived = 0
    total_to_write = (
        change_report.total_new + change_report.total_updated + change_report.total_removed
    )
    pending_ops = 0
    if existing_cartera is None:
        existing_cartera = read_current_cartera(store, campaign_id)
    by_code = index_clients_by_codigo(existing_cartera)

    for seccion_key, section in change_report.sections.items():
        if not section.has_changes:
            continue

        new_map = {
            c.get("codigo_cliente", ""): c for c in by_seccion.get(seccion_key, [])
        }

        def write_client(codigo: str, data: dict[str, Any], merge: bool = False) -> None:
            nonlocal pending_ops
            store.set(
                "campañas",
                campaign_id,
                "gestores",
                seccion_key,
                "clientes",
                str(codigo),
                data=data,
                merge=merge,
            )
            pending_ops += 1
            if pending_ops >= BATCH_LIMIT:
                pending_ops = 0

        for client_data in section.new_clients:
            codigo = str(client_data.get("codigo_cliente") or "")
            if not codigo:
                continue
            full = _strip_internal(dict(new_map.get(codigo) or client_data))
            preferred = str(client_data.get("_firestore_seccion") or seccion_key)
            _sec, existing = lookup_existing_client(by_code, codigo, preferred)
            prev = extract_visit_fields(existing)
            doc = {
                **full,
                "estado_gestion": full.get("estado_gestion", "pendiente"),
                "fecha_subida": "SERVER_TIMESTAMP",
                "seccion_key": seccion_key,
                **_lifecycle(activo=True, ultimo_excel=ultimo_excel),
            }
            if prev:
                doc = apply_visit_fields(doc, prev)
                preserved += 1
            write_client(codigo, doc, merge=False)
            written += 1
            if progress_callback:
                progress_callback(written, total_to_write, f"Nuevo: {full.get('nombre_completo', '')}")

        for change in section.updated_clients:
            codigo = str(change.codigo_cliente)
            raw = new_map.get(codigo)
            if not raw:
                continue
            full = _strip_internal(dict(raw))
            firestore_sec, existing = lookup_existing_client(by_code, codigo, seccion_key)
            prev = extract_visit_fields(existing)
            doc = {
                **full,
                "estado_gestion": full.get("estado_gestion", "pendiente"),
                "fecha_subida": "SERVER_TIMESTAMP",
                "seccion_key": seccion_key,
                **_lifecycle(activo=True, ultimo_excel=ultimo_excel),
            }
            if prev:
                doc = apply_visit_fields(doc, prev)
                preserved += 1
            target = firestore_sec or seccion_key
            store.set(
                "campañas",
                campaign_id,
                "gestores",
                target,
                "clientes",
                codigo,
                data=doc,
                merge=False,
            )
            pending_ops += 1
            written += 1
            if progress_callback:
                progress_callback(
                    written, total_to_write, f"Actualizado: {full.get('nombre_completo', '')}"
                )

        for removed_data in section.removed_clients:
            codigo = str(removed_data.get("codigo_cliente") or "").strip()
            if not codigo:
                continue
            target = str(removed_data.get("_firestore_seccion") or seccion_key)
            _sec, existing = lookup_existing_client(by_code, codigo, target)
            prev = extract_visit_fields(existing)
            doc = {
                **_strip_internal(removed_data),
                "seccion_key": seccion_key,
                **_lifecycle(
                    activo=False,
                    motivo_baja=MOTIVO_BAJA_EXCEL_BANCO,
                    ultimo_excel=ultimo_excel,
                ),
            }
            if prev:
                doc = apply_visit_fields(doc, prev)
                preserved += 1
            store.set(
                "campañas",
                campaign_id,
                "gestores",
                target,
                "clientes",
                codigo,
                data=doc,
                merge=True,
            )
            pending_ops += 1
            written += 1
            archived += 1
            if progress_callback:
                progress_callback(
                    written,
                    total_to_write,
                    f"Archivado: {removed_data.get('nombre_completo', codigo)}",
                )

        excel_clients = by_seccion.get(seccion_key, [])
        totals = _section_totals(excel_clients)
        if not excel_clients and section.removed_clients:
            sample = section.removed_clients[0]
            totals["seccion_key"] = seccion_key
            totals["seccion"] = sample.get("seccion", "")
            totals["region"] = sample.get("region", "")
            totals["zona"] = sample.get("zona", "")
            totals["num_clientes"] = 0
        totals["fecha_actualizacion"] = "SERVER_TIMESTAMP"
        store.set(
            "campañas",
            campaign_id,
            "gestores",
            seccion_key,
            data=totals,
            merge=True,
        )

    all_clients = [c for clients in by_seccion.values() for c in clients]
    hierarchy = get_hierarchy(all_clients)
    regiones_map: dict[str, Any] = {}
    total_zonas = 0
    total_secciones = 0
    for region_key, region_data in hierarchy.get("regions", {}).items():
        zonas_map: dict[str, Any] = {}
        for zona_key, zona_data in region_data.get("zonas", {}).items():
            secciones_list = sorted(zona_data.get("secciones", {}).keys())
            zonas_map[zona_key] = {"secciones": secciones_list}
            total_secciones += len(secciones_list)
            total_zonas += 1
        regiones_map[region_key] = {"zonas": zonas_map}

    store.set(
        "estructura_territorial",
        "catalogo",
        data={
            "regiones": regiones_map,
            "fecha_actualizacion": "SERVER_TIMESTAMP",
            "total_regiones": len(regiones_map),
            "total_zonas": total_zonas,
            "total_secciones": total_secciones,
        },
        merge=False,
    )

    con_coords = sum(
        1
        for c in all_clients
        if float(c.get("coordenada_y", 0) or 0) != 0
        and float(c.get("coordenada_x", 0) or 0) != 0
    )
    secciones = campaign_section_keys(by_seccion, list(existing_cartera.keys()))
    store.set(
        "campañas",
        campaign_id,
        data={
            "total_clientes": len(all_clients),
            "total_secciones": len(secciones),
            "secciones": secciones,
            "total_clientes_con_coordenadas": con_coords,
            "fecha_actualizacion": "SERVER_TIMESTAMP",
            "fecha_distribucion": "SERVER_TIMESTAMP",
            "estado": "distribuida",
            "publisher": "web",
        },
        merge=True,
    )
    if hasattr(store, "commit"):
        store.commit()

    return {
        "campaign_id": campaign_id,
        "total_written": written,
        "preserved_visits": preserved,
        "archived_clients": archived,
        "success": True,
    }


def read_current_cartera(store: InMemoryStore, campaign_id: str = CAMPAIGN_ID_DEFAULT) -> dict[str, dict[str, dict]]:
    raw: dict[str, dict[str, dict]] = {}
    for sec_id, _meta in store.list_children("campañas", campaign_id, "gestores"):
        clients = store.list_clientes(campaign_id, sec_id)
        if clients:
            raw[sec_id] = clients
    return raw
