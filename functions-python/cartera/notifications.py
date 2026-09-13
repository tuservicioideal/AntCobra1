"""Notificaciones de actualización de base (espejo de firebase_service.py)."""

from __future__ import annotations

from typing import Any

from .diff_engine import ChangeReport, SectionChanges
from .preview import index_section_gestores


def _section_detalles(section: SectionChanges) -> list[dict[str, str]]:
    detalles: list[dict[str, str]] = []
    for client in section.removed_clients:
        detalles.append(
            {
                "codigo_cliente": str(client.get("codigo_cliente") or ""),
                "nombre": str(client.get("nombre_completo") or ""),
                "tipo": "removido",
            }
        )
    for client in section.new_clients:
        detalles.append(
            {
                "codigo_cliente": str(client.get("codigo_cliente") or ""),
                "nombre": str(client.get("nombre_completo") or ""),
                "tipo": "nuevo",
            }
        )
    for change in section.updated_clients:
        detalles.append(
            {
                "codigo_cliente": change.codigo_cliente,
                "nombre": change.nombre_completo,
                "tipo": "actualizado",
            }
        )
    return detalles[:80]


def build_notifications(
    *,
    change_report: ChangeReport,
    usuarios: list[dict[str, Any]],
    campaign_id: str,
) -> dict[str, Any]:
    assignment = index_section_gestores(usuarios)
    gestor_notifs: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    sin_gestor: list[str] = []

    for seccion_key, section in change_report.sections.items():
        if not section.has_changes:
            continue
        dest = assignment.get(seccion_key)
        if not dest:
            sin_gestor.append(seccion_key)
            alerts.append(
                {
                    "tipo": "seccion_sin_gestor",
                    "titulo": f"Sección sin gestor: {seccion_key}",
                    "mensaje": (
                        "Hay cambios de cartera en esta sección pero ningún "
                        "usuario activo tiene esa sección en su perfil."
                    ),
                    "seccion": seccion_key,
                    "campaign_id": campaign_id,
                }
            )
            continue
        n_rem = len(section.removed_clients)
        n_new = len(section.new_clients)
        n_upd = len(section.updated_clients)
        parts = []
        if n_rem:
            parts.append(f"{n_rem} removidos")
        if n_new:
            parts.append(f"{n_new} nuevos")
        if n_upd:
            parts.append(f"{n_upd} actualizados")
        mensaje = ", ".join(parts)
        if n_rem:
            mensaje = (
                f"{n_rem} cliente(s) ya no están en el Excel del banco. {mensaje}"
            )
        gestor_notifs.append(
            {
                "tipo": "base_actualizada",
                "seccion_key": seccion_key,
                "destinatario_uid": dest["uid"],
                "titulo": "Base de datos actualizada",
                "mensaje": mensaje,
                "detalles": _section_detalles(section),
                "leida": False,
                "campaign_id": campaign_id,
            }
        )

    admin_notif = {
        "tipo": "base_actualizada_admin",
        "titulo": "Cartera actualizada",
        "mensaje": (
            f"{change_report.total_new} nuevos, "
            f"{change_report.total_updated} actualizados, "
            f"{change_report.total_removed} removidos"
        ),
        "leida": False,
        "campaign_id": campaign_id,
        "detalles": {
            "nuevos": change_report.total_new,
            "actualizados": change_report.total_updated,
            "removidos": change_report.total_removed,
            "secciones_sin_gestor": sin_gestor,
        },
    }

    return {
        "gestor": gestor_notifs,
        "admin": admin_notif,
        "alertas": alerts,
        "secciones_sin_gestor": sin_gestor,
    }
