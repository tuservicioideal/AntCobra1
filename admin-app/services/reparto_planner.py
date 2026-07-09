"""
Plan de reparto con preservación de afinidad cliente-asesor (campo + call).

Construye un RepartoPlan sin persistir, reutilizando LPT de call_center_service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from .database import Cliente, TramoEnum, FASE_GESTION_CALL
from .excel_parser import make_seccion_key
from .call_center_service import (
    GestorCallBalance,
    filter_call_gestores,
    is_call_gestor_active,
    run_affinity_lpt,
    get_territorial_seccion_key,
    _cliente_display_name,
)
from .tramo_engine import UMBRAL_MINIMO_GESTION, load_config

# Estados de afinidad
MANTIENE = "MANTIENE"
NUEVO = "NUEVO"
REASIGNADO_HUERFANO = "REASIGNADO_HUERFANO"
AFINIDAD_ROTA_CAMPO = "AFINIDAD_ROTA_CAMPO"
SIN_GESTOR_CAMPO = "SIN_GESTOR_CAMPO"
OVERRIDE_MANUAL = "OVERRIDE_MANUAL"
NA_CAMPO = "NA_CAMPO"  # cliente en fase campo (tramo > 1)


@dataclass
class ClienteReparto:
    codigo_cliente: str
    nombre: str
    seccion_key: str
    gestor_campo_uid: str
    gestor_campo_nombre: str
    fase_gestion: str
    call_gestor_uid: str
    call_gestor_nombre: str
    estado_afinidad: str
    importe: float
    tramo_actual: int = 1


@dataclass
class RepartoPlan:
    campana_id: str
    clientes: list[ClienteReparto] = field(default_factory=list)
    resumen_campo: dict[str, dict[str, Any]] = field(default_factory=dict)
    resumen_call: list[GestorCallBalance] = field(default_factory=list)
    sin_gestor_campo: list[str] = field(default_factory=list)
    conflictos_campo: list[str] = field(default_factory=list)
    overrides: dict[str, str] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)

    @property
    def total_clientes(self) -> int:
        return len(self.clientes)

    @property
    def pct_mantiene(self) -> float:
        if not self.clientes:
            return 0.0
        n = sum(1 for c in self.clientes if c.estado_afinidad == MANTIENE)
        return round(n / len(self.clientes) * 100, 1)


def _resolve_campo_gestor(
    seccion_key: str,
    assignment_index: dict[str, dict[str, Any]],
) -> tuple[str, str, str]:
    """Retorna (uid, nombre, status) donde status es assigned|conflict|missing."""
    info = assignment_index.get(seccion_key)
    if info is None:
        return "", "", "missing"
    if info.get("status") == "conflict":
        return "", "", "conflict"
    return (
        info.get("gestor_uid", ""),
        info.get("gestor_nombre", ""),
        "assigned",
    )


def _is_call_eligible(cliente: Cliente) -> bool:
    load_config()
    return (
        cliente.tramo_actual == TramoEnum.TRAMO_1.value
        and cliente.fase_gestion == FASE_GESTION_CALL
        and float(cliente.importe_deuda_pendiente or 0) >= UMBRAL_MINIMO_GESTION
    )


def build_reparto_plan(
    session: Session,
    campana_id: str,
    gestores_firestore: list[dict],
    *,
    overrides: dict[str, str] | None = None,
    seccion_keys_anteriores: dict[str, str] | None = None,
) -> RepartoPlan:
    """
    Construye el plan de reparto sin persistir.

    Args:
        seccion_keys_anteriores: snapshot codigo_cliente -> seccion_key antes de
            aplicar Excel (para detectar AFINIDAD_ROTA_CAMPO).
    """
    from .campaign_manager import campaign_manager

    plan = RepartoPlan(campana_id=campana_id)
    plan.overrides = dict(overrides or {})
    prev_sections = seccion_keys_anteriores or {}

    gestores_call = filter_call_gestores(gestores_firestore or [])
    if not gestores_call:
        plan.errores.append("No hay gestores de call center activos.")

    assignment_index = campaign_manager._build_section_assignment_index(
        gestores_firestore or []
    )

    conflictos: set[str] = set()
    sin_gestor: set[str] = set()
    for sk, info in assignment_index.items():
        if info.get("status") == "conflict":
            conflictos.add(sk)
    plan.conflictos_campo = sorted(conflictos)

    clientes_activos = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.activo_en_cartera.is_(True),
        )
        .all()
    )

    fixed_assignments: dict[str, tuple[str, str, float]] = {}
    pending_call: list[Cliente] = []
    cliente_rows: list[ClienteReparto] = []

    gestor_call_names = {
        (g.get("uid") or g.get("id", "")): g.get("nombre", g.get("email", ""))
        for g in gestores_call
    }

    for cliente in clientes_activos:
        codigo = cliente.codigo_cliente or str(cliente.id)
        seccion_key = get_territorial_seccion_key(cliente)
        gestor_uid, gestor_nombre, campo_status = _resolve_campo_gestor(
            seccion_key, assignment_index,
        )

        estado_campo = ""
        if campo_status == "missing":
            sin_gestor.add(seccion_key)
            estado_campo = SIN_GESTOR_CAMPO
        elif campo_status == "conflict":
            estado_campo = SIN_GESTOR_CAMPO

        prev_sk = prev_sections.get(codigo, "")
        section_changed = bool(prev_sk and prev_sk != seccion_key)

        if section_changed:
            estado_afinidad = AFINIDAD_ROTA_CAMPO
        elif estado_campo == SIN_GESTOR_CAMPO:
            estado_afinidad = SIN_GESTOR_CAMPO
        elif not _is_call_eligible(cliente):
            estado_afinidad = estado_campo or NA_CAMPO
        else:
            uid_prev = (cliente.call_gestor_uid or "").strip()
            if codigo in plan.overrides:
                estado_afinidad = OVERRIDE_MANUAL
            elif uid_prev and is_call_gestor_active(uid_prev, gestores_call):
                estado_afinidad = MANTIENE
            elif uid_prev:
                estado_afinidad = REASIGNADO_HUERFANO
            else:
                estado_afinidad = NUEVO

        call_uid = ""
        call_nombre = ""

        if _is_call_eligible(cliente):
            if codigo in plan.overrides:
                call_uid = plan.overrides[codigo]
                call_nombre = gestor_call_names.get(call_uid, call_uid)
            elif estado_afinidad == MANTIENE:
                call_uid = cliente.call_gestor_uid or ""
                call_nombre = cliente.call_gestor_nombre or ""
                monto = float(cliente.importe_deuda_pendiente or 0)
                fixed_assignments[codigo] = (call_uid, call_nombre, monto)
            elif estado_afinidad in (NUEVO, REASIGNADO_HUERFANO):
                pending_call.append(cliente)
            elif estado_afinidad == OVERRIDE_MANUAL:
                call_uid = plan.overrides[codigo]
                call_nombre = gestor_call_names.get(call_uid, call_uid)

        cliente_rows.append(ClienteReparto(
            codigo_cliente=codigo,
            nombre=_cliente_display_name(cliente),
            seccion_key=seccion_key,
            gestor_campo_uid=gestor_uid,
            gestor_campo_nombre=gestor_nombre,
            fase_gestion=cliente.fase_gestion or "",
            call_gestor_uid=call_uid,
            call_gestor_nombre=call_nombre,
            estado_afinidad=estado_afinidad if estado_afinidad else (estado_campo or NA_CAMPO),
            importe=float(cliente.importe_deuda_pendiente or 0),
            tramo_actual=int(cliente.tramo_actual or 1),
        ))

    plan.sin_gestor_campo = sorted(sin_gestor)

    if pending_call and gestores_call:
        lpt_map = run_affinity_lpt(gestores_call, fixed_assignments, pending_call)
        row_by_codigo = {r.codigo_cliente: r for r in cliente_rows}
        for cliente in pending_call:
            codigo = cliente.codigo_cliente or str(cliente.id)
            if codigo not in lpt_map:
                continue
            uid, nombre = lpt_map[codigo]
            row = row_by_codigo.get(codigo)
            if row:
                row.call_gestor_uid = uid
                row.call_gestor_nombre = nombre

    plan.clientes = cliente_rows
    plan.resumen_campo = _build_resumen_campo(cliente_rows)
    plan.resumen_call = _build_resumen_call(cliente_rows, gestores_call)
    return plan


def _build_resumen_campo(clientes: list[ClienteReparto]) -> dict[str, dict[str, Any]]:
    resumen: dict[str, dict[str, Any]] = {}
    for c in clientes:
        key = c.gestor_campo_uid or "_sin_gestor"
        if key not in resumen:
            resumen[key] = {
                "gestor_uid": c.gestor_campo_uid,
                "gestor_nombre": c.gestor_campo_nombre or "(sin gestor)",
                "n": 0,
                "monto": 0.0,
                "mantiene": 0,
                "rotos": 0,
                "sin_gestor": 0,
            }
        r = resumen[key]
        r["n"] += 1
        r["monto"] += c.importe
        if c.estado_afinidad == AFINIDAD_ROTA_CAMPO:
            r["rotos"] += 1
        elif c.estado_afinidad == SIN_GESTOR_CAMPO:
            r["sin_gestor"] += 1
        elif c.estado_afinidad == MANTIENE:
            r["mantiene"] += 1
    return resumen


def _build_resumen_call(
    clientes: list[ClienteReparto],
    gestores_call: list[dict],
) -> list[GestorCallBalance]:
    balances: dict[str, GestorCallBalance] = {}
    for g in gestores_call:
        uid = g.get("uid") or g.get("id", "")
        balances[uid] = GestorCallBalance(
            uid=uid,
            nombre=g.get("nombre", g.get("email", uid)),
        )

    for c in clientes:
        if c.fase_gestion != FASE_GESTION_CALL or c.tramo_actual != 1:
            continue
        uid = c.call_gestor_uid
        if not uid:
            continue
        if uid not in balances:
            balances[uid] = GestorCallBalance(
                uid=uid, nombre=c.call_gestor_nombre or uid,
            )
        b = balances[uid]
        b.num_cuentas += 1
        b.monto_total += c.importe
        if c.estado_afinidad == NUEVO:
            b.nuevas_asignadas += 1
            b.monto_nuevo += c.importe
        elif c.estado_afinidad in (REASIGNADO_HUERFANO, OVERRIDE_MANUAL):
            b.nuevas_asignadas += 1
            b.monto_nuevo += c.importe

    return sorted(balances.values(), key=lambda b: b.nombre.lower())


def snapshot_seccion_keys(session: Session, campana_id: str) -> dict[str, str]:
    """Snapshot territorial seccion_key por codigo_cliente (pre-update Excel)."""
    rows = (
        session.query(Cliente)
        .filter(Cliente.campana_id == campana_id)
        .all()
    )
    return {
        (c.codigo_cliente or str(c.id)): get_territorial_seccion_key(c)
        for c in rows
    }
