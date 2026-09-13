"""
Plan de reparto con preservación de afinidad cliente-asesor (campo + call).

Construye un RepartoPlan sin persistir, usando:
  - Matriz de fase call/campo (fase_reparto)
  - LPT por pool de etapa (call_codigo E1-1 … E3-1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from .database import Cliente, FASE_GESTION_CALL, FASE_GESTION_CAMPO
from .excel_parser import make_seccion_key
from .call_center_service import (
    GestorCallBalance,
    filter_call_gestores,
    is_call_gestor_active,
    run_bucketed_call_assignment,
    get_territorial_seccion_key,
    classify_call_slot_pool,
    _cliente_display_name,
    _gestor_uid,
    _gestor_call_codigo,
)
from .fase_reparto import (
    evaluate_fases_batch,
    is_call_eligible_for_lpt,
    resolve_campo_seccion_for_decision,
    MOTIVO_SEGUNDA_CUENTA_CAMPO,
    MOTIVO_PASA_CAMPO_MONTO,
    MOTIVO_QUEDA_CALL_HABIDO,
    MOTIVO_QUEDA_CALL_BAJO_MONTO,
    MOTIVO_CAMBIO_SLOT_ETAPA,
    MOTIVO_ETAPA1_CALL,
    MOTIVO_YA_EN_CAMPO,
)

# Estados de afinidad
MANTIENE = "MANTIENE"
NUEVO = "NUEVO"
REASIGNADO_HUERFANO = "REASIGNADO_HUERFANO"
AFINIDAD_ROTA_CAMPO = "AFINIDAD_ROTA_CAMPO"
SIN_GESTOR_CAMPO = "SIN_GESTOR_CAMPO"
OVERRIDE_MANUAL = "OVERRIDE_MANUAL"
NA_CAMPO = "NA_CAMPO"
SEGUNDA_CUENTA_CAMPO = MOTIVO_SEGUNDA_CUENTA_CAMPO
PASA_CAMPO_MONTO = MOTIVO_PASA_CAMPO_MONTO
QUEDA_CALL_HABIDO = MOTIVO_QUEDA_CALL_HABIDO
QUEDA_CALL_BAJO_MONTO = MOTIVO_QUEDA_CALL_BAJO_MONTO
CAMBIO_SLOT_ETAPA = MOTIVO_CAMBIO_SLOT_ETAPA


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
    motivo_fase: str = ""


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
    preview_fases: dict[str, int] = field(default_factory=dict)

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
    return is_call_eligible_for_lpt(cliente)


def _gestor_matches_pool(gestor: dict | None, pool: tuple[str, ...]) -> bool:
    if not gestor:
        return False
    code = _gestor_call_codigo(gestor)
    # Legacy: sin call_codigo, cualquier gestor call activo es válido en el pool
    if not code:
        return True
    if not pool:
        return False
    return code in pool


def build_reparto_plan(
    session: Session,
    campana_id: str,
    gestores_firestore: list[dict],
    *,
    overrides: dict[str, str] | None = None,
    seccion_keys_anteriores: dict[str, str] | None = None,
    allow_return_to_call: bool = False,
) -> RepartoPlan:
    """
    Construye el plan de reparto sin persistir.

    Args:
        seccion_keys_anteriores: snapshot codigo_cliente -> seccion_key antes de
            aplicar Excel (para detectar AFINIDAD_ROTA_CAMPO).
        allow_return_to_call: si True, preview de migración puede devolver a call
            cuentas que nunca debieron estar en campo (saldo ≤ 40 sin ancla).
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

    fase_batch = evaluate_fases_batch(
        clientes_activos,
        assignment_index=assignment_index,
        allow_return_to_call=allow_return_to_call,
    )
    fase_by_codigo = {
        d.codigo_cliente: d for d in fase_batch.decisiones
    }
    plan.preview_fases = {
        "call": sum(1 for d in fase_batch.decisiones if d.fase == FASE_GESTION_CALL),
        "campo": sum(1 for d in fase_batch.decisiones if d.fase == FASE_GESTION_CAMPO),
        "arrastre_dni": sum(1 for d in fase_batch.decisiones if d.arrastre_dni),
        "pasa_campo_monto": sum(
            1 for d in fase_batch.decisiones if d.motivo == MOTIVO_PASA_CAMPO_MONTO
        ),
    }

    fixed_assignments: dict[str, tuple[str, str, float]] = {}
    pending_call: list[Cliente] = []
    cliente_rows: list[ClienteReparto] = []

    gestor_call_names = {
        (g.get("uid") or g.get("id", "")): g.get("nombre", g.get("email", ""))
        for g in gestores_call
    }
    gestores_by_uid = {
        _gestor_uid(g): g for g in gestores_call if _gestor_uid(g)
    }

    for cliente in clientes_activos:
        codigo = cliente.codigo_cliente or str(cliente.id)
        dec = fase_by_codigo.get(codigo)
        fase_objetivo = (
            dec.fase if dec else (cliente.fase_gestion or FASE_GESTION_CAMPO)
        )
        motivo_fase = dec.motivo if dec else ""

        seccion_key = get_territorial_seccion_key(cliente)
        if dec and dec.fase == FASE_GESTION_CAMPO:
            seccion_destino = resolve_campo_seccion_for_decision(dec) or seccion_key
        else:
            seccion_destino = seccion_key

        gestor_uid, gestor_nombre, campo_status = _resolve_campo_gestor(
            seccion_destino, assignment_index,
        )
        if dec and dec.gestor_ancla_uid and not dec.gestor_ancla_uid.startswith("_sec:"):
            gestor_uid = dec.gestor_ancla_uid
            gestor_nombre = dec.gestor_ancla_nombre or gestor_nombre

        estado_campo = ""
        if campo_status == "missing":
            sin_gestor.add(seccion_destino)
            estado_campo = SIN_GESTOR_CAMPO
        elif campo_status == "conflict":
            estado_campo = SIN_GESTOR_CAMPO

        prev_sk = prev_sections.get(codigo, "")
        section_changed = bool(prev_sk and prev_sk != seccion_key)

        # Badges de fase especiales
        if motivo_fase == MOTIVO_SEGUNDA_CUENTA_CAMPO:
            estado_afinidad = SEGUNDA_CUENTA_CAMPO
        elif motivo_fase == MOTIVO_PASA_CAMPO_MONTO and fase_objetivo == FASE_GESTION_CAMPO:
            estado_afinidad = PASA_CAMPO_MONTO
        elif section_changed:
            estado_afinidad = AFINIDAD_ROTA_CAMPO
        elif estado_campo == SIN_GESTOR_CAMPO:
            estado_afinidad = SIN_GESTOR_CAMPO
        elif fase_objetivo != FASE_GESTION_CALL:
            estado_afinidad = estado_campo or NA_CAMPO
        else:
            # Call: afinidad + pool de etapa
            uid_prev = (cliente.call_gestor_uid or "").strip()
            pool = classify_call_slot_pool(cliente) if dec is None else (dec.call_pool or ())
            if not pool:
                pool = classify_call_slot_pool(cliente)
            g_prev = gestores_by_uid.get(uid_prev) if uid_prev else None
            in_pool = _gestor_matches_pool(g_prev, pool) if pool else (
                is_call_gestor_active(uid_prev, gestores_call) if uid_prev else False
            )

            if codigo in plan.overrides:
                estado_afinidad = OVERRIDE_MANUAL
            elif uid_prev and in_pool:
                estado_afinidad = MANTIENE
            elif uid_prev and is_call_gestor_active(uid_prev, gestores_call) and not in_pool:
                estado_afinidad = CAMBIO_SLOT_ETAPA
            elif uid_prev:
                estado_afinidad = REASIGNADO_HUERFANO
            elif motivo_fase == MOTIVO_QUEDA_CALL_HABIDO:
                estado_afinidad = QUEDA_CALL_HABIDO
            elif motivo_fase == MOTIVO_QUEDA_CALL_BAJO_MONTO:
                estado_afinidad = QUEDA_CALL_BAJO_MONTO
            else:
                estado_afinidad = NUEVO

        call_uid = ""
        call_nombre = ""

        if fase_objetivo == FASE_GESTION_CALL and is_call_eligible_for_lpt(
            # Usar tramo/fase objetivo en un proxy ligero
            _ClienteProxy(cliente, fase_objetivo)
        ):
            if codigo in plan.overrides:
                call_uid = plan.overrides[codigo]
                call_nombre = gestor_call_names.get(call_uid, call_uid)
            elif estado_afinidad == MANTIENE:
                call_uid = cliente.call_gestor_uid or ""
                call_nombre = cliente.call_gestor_nombre or ""
                monto = float(cliente.importe_deuda_pendiente or 0)
                fixed_assignments[codigo] = (call_uid, call_nombre, monto)
            elif estado_afinidad in (
                NUEVO, REASIGNADO_HUERFANO, CAMBIO_SLOT_ETAPA,
                QUEDA_CALL_HABIDO, QUEDA_CALL_BAJO_MONTO, MOTIVO_ETAPA1_CALL,
            ):
                pending_call.append(cliente)
            elif estado_afinidad == OVERRIDE_MANUAL:
                call_uid = plan.overrides[codigo]
                call_nombre = gestor_call_names.get(call_uid, call_uid)

        cliente_rows.append(ClienteReparto(
            codigo_cliente=codigo,
            nombre=_cliente_display_name(cliente),
            seccion_key=seccion_destino,
            gestor_campo_uid=gestor_uid,
            gestor_campo_nombre=gestor_nombre,
            fase_gestion=fase_objetivo,
            call_gestor_uid=call_uid,
            call_gestor_nombre=call_nombre,
            estado_afinidad=estado_afinidad if estado_afinidad else (estado_campo or NA_CAMPO),
            importe=float(cliente.importe_deuda_pendiente or 0),
            tramo_actual=int(cliente.tramo_actual or 1),
            motivo_fase=motivo_fase,
        ))

    plan.sin_gestor_campo = sorted(sin_gestor)

    if pending_call and gestores_call:
        # Ajustar tramo en proxy no es necesario: classify usa cliente.tramo_actual
        assign_map = run_bucketed_call_assignment(
            gestores_call, fixed_assignments, pending_call,
        )
        row_by_codigo = {r.codigo_cliente: r for r in cliente_rows}
        for cliente in pending_call:
            codigo = cliente.codigo_cliente or str(cliente.id)
            if codigo not in assign_map:
                continue
            uid, nombre, _razon = assign_map[codigo]
            row = row_by_codigo.get(codigo)
            if row:
                row.call_gestor_uid = uid
                row.call_gestor_nombre = nombre

    plan.clientes = cliente_rows
    plan.resumen_campo = _build_resumen_campo(cliente_rows)
    plan.resumen_call = _build_resumen_call(cliente_rows, gestores_call)
    return plan


class _ClienteProxy:
    """Proxy mínimo para is_call_eligible_for_lpt con fase objetivo."""

    def __init__(self, cliente: Cliente, fase: str):
        self._c = cliente
        self.fase_gestion = fase
        self.activo_en_cartera = getattr(cliente, "activo_en_cartera", True)
        self.tramo_actual = getattr(cliente, "tramo_actual", 1)
        self.importe_deuda_pendiente = getattr(cliente, "importe_deuda_pendiente", 0)

    def __getattr__(self, name: str):
        return getattr(self._c, name)


def _build_resumen_campo(clientes: list[ClienteReparto]) -> dict[str, dict[str, Any]]:
    resumen: dict[str, dict[str, Any]] = {}
    for c in clientes:
        if c.fase_gestion != FASE_GESTION_CAMPO:
            continue
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
        code = _gestor_call_codigo(g)
        nombre = g.get("nombre", g.get("email", uid))
        label = f"{nombre} ({code})" if code else nombre
        balances[uid] = GestorCallBalance(uid=uid, nombre=label)

    for c in clientes:
        if c.fase_gestion != FASE_GESTION_CALL:
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
        if c.estado_afinidad in (
            NUEVO, REASIGNADO_HUERFANO, OVERRIDE_MANUAL, CAMBIO_SLOT_ETAPA,
            QUEDA_CALL_HABIDO, QUEDA_CALL_BAJO_MONTO,
        ):
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
