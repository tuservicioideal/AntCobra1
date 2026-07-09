"""
Call Center Service — reparto equitativo de cuentas tramo 1 por monto.

Algoritmo LPT (Longest Processing Time / greedy):
  - Ordena cuentas por importe_deuda_pendiente descendente.
  - Asigna cada cuenta al gestor de call con menor monto acumulado
    (desempate: menor cantidad de cuentas).
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any

from sqlalchemy.orm import Session

from .database import (
    Cliente,
    TramoEnum,
    FASE_GESTION_CALL,
    FASE_GESTION_CAMPO,
    make_call_section_key,
)
from .excel_parser import make_seccion_key
from .tramo_engine import UMBRAL_MINIMO_GESTION, load_config

logger = logging.getLogger(__name__)

RAZON_LPT_NUEVAS = (
    "Algoritmo LPT: asignación al gestor call con menor monto acumulado"
)
RAZON_LPT_REEQUILIBRIO = (
    "Re-equilibrio LPT: redistribución para equilibrar montos entre operadores"
)
RAZON_REASIGNACION_MANUAL = "Reasignación manual a {nombre_destino}"

MOTIVO_REPARTO_INICIAL = "Reparto automático tramo 1 — cuentas sin asignar"
MOTIVO_REEQUILIBRIO = "Re-equilibrio total de cartera call tramo 1"
MOTIVO_REASIGNACION_MANUAL = "Reasignación manual por supervisor"


@dataclass
class CallAssignmentChange:
    codigo_cliente: str
    nombre: str
    importe: float
    gestor_anterior_uid: str = ""
    gestor_anterior_nombre: str = ""
    gestor_nuevo_uid: str = ""
    gestor_nuevo_nombre: str = ""
    razon: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GestorCallBalance:
    uid: str
    nombre: str
    num_cuentas: int = 0
    monto_total: float = 0.0
    nuevas_asignadas: int = 0
    monto_nuevo: float = 0.0
    pendientes: int = 0
    gestionados: int = 0
    promesas: int = 0
    monto_pendiente: float = 0.0

    @property
    def pct_avance(self) -> float:
        if self.num_cuentas <= 0:
            return 0.0
        return round(self.gestionados / self.num_cuentas * 100, 1)


@dataclass
class DistributionResult:
    campana_id: str
    gestores: list[GestorCallBalance] = field(default_factory=list)
    cuentas_asignadas: int = 0
    monto_asignado: float = 0.0
    errores: list[str] = field(default_factory=list)
    tipo: str = ""  # reparto_inicial | reequilibrio
    cambios: list[CallAssignmentChange] = field(default_factory=list)
    firebase_publish: dict[str, Any] | None = None

    @property
    def desviacion_monto(self) -> float:
        montos = [g.monto_total for g in self.gestores if g.num_cuentas > 0]
        if len(montos) < 2:
            return 0.0
        return float(statistics.pstdev(montos))

    @property
    def motivo(self) -> str:
        if self.tipo == "reequilibrio":
            return MOTIVO_REEQUILIBRIO
        return MOTIVO_REPARTO_INICIAL


def _cliente_display_name(cliente: Cliente) -> str:
    full = (cliente.nombre_completo or "").strip()
    if full:
        return full
    return f"{cliente.nombres or ''} {cliente.apellido_paterno or ''}".strip()


def get_territorial_seccion_key(cliente: Cliente) -> str:
    return make_seccion_key(
        cliente.region or "",
        cliente.zona or "",
        cliente.seccion or "SIN_SECCION",
    )


def get_effective_firestore_section(cliente: Cliente) -> str:
    """Sección Firestore donde debe vivir el documento del cliente."""
    if (
        getattr(cliente, "fase_gestion", FASE_GESTION_CAMPO) == FASE_GESTION_CALL
        and cliente.call_gestor_uid
    ):
        return make_call_section_key(cliente.call_gestor_uid)
    return get_territorial_seccion_key(cliente)


def filter_call_gestores(gestores: list[dict]) -> list[dict]:
    """Gestores activos con canal call."""
    result = []
    for g in gestores:
        if g.get("rol") != "gestor":
            continue
        if not g.get("activo", True):
            continue
        if g.get("canal") == "call":
            uid = g.get("uid") or g.get("id", "")
            if uid:
                result.append(g)
    return result


def is_call_gestor_active(uid: str, gestores_call: list[dict]) -> bool:
    """True si el uid pertenece a un gestor call activo."""
    if not uid:
        return False
    return any((g.get("uid") or g.get("id")) == uid for g in gestores_call)


def _empty_balances(gestores_call: list[dict]) -> dict[str, GestorCallBalance]:
    balances: dict[str, GestorCallBalance] = {}
    for g in gestores_call:
        uid = g.get("uid") or g.get("id", "")
        if not uid:
            continue
        nombre = g.get("nombre", g.get("email", uid))
        balances[uid] = GestorCallBalance(uid=uid, nombre=nombre)
    return balances


def _apply_fixed_assignments(
    balances: dict[str, GestorCallBalance],
    fixed_assignments: dict[str, tuple[str, str, float]],
) -> None:
    """Precarga balances con clientes que mantienen afinidad (carga fija LPT)."""
    for _codigo, (uid, nombre, monto) in fixed_assignments.items():
        if uid not in balances:
            balances[uid] = GestorCallBalance(uid=uid, nombre=nombre)
        b = balances[uid]
        b.num_cuentas += 1
        b.monto_total += monto


def run_affinity_lpt(
    gestores_call: list[dict],
    fixed_assignments: dict[str, tuple[str, str, float]],
    pending_clients: list[Cliente],
) -> dict[str, tuple[str, str]]:
    """
    LPT greedy sobre pending_clients con carga fija pre-cargada.

    Returns:
        dict codigo_cliente -> (gestor_uid, gestor_nombre) para los pending.
    """
    balances = _empty_balances(gestores_call)
    _apply_fixed_assignments(balances, fixed_assignments)

    assignments: dict[str, tuple[str, str]] = {}
    sorted_pending = sorted(
        pending_clients,
        key=lambda c: float(c.importe_deuda_pendiente or 0),
        reverse=True,
    )
    for cliente in sorted_pending:
        if not balances:
            break
        target = _pick_gestor(balances)
        monto = float(cliente.importe_deuda_pendiente or 0)
        codigo = cliente.codigo_cliente or str(cliente.id)
        assignments[codigo] = (target.uid, target.nombre)
        target.num_cuentas += 1
        target.monto_total += monto
        target.nuevas_asignadas += 1
        target.monto_nuevo += monto
    return assignments


def _eligible_tramo1_clients(
    session: Session,
    campana_id: str,
    *,
    only_unassigned: bool,
) -> list[Cliente]:
    load_config()
    q = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.activo_en_cartera.is_(True),
            Cliente.tramo_actual == TramoEnum.TRAMO_1.value,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.importe_deuda_pendiente >= UMBRAL_MINIMO_GESTION,
        )
    )
    if only_unassigned:
        q = q.filter(
            (Cliente.call_gestor_uid.is_(None)) | (Cliente.call_gestor_uid == "")
        )
    return q.order_by(Cliente.importe_deuda_pendiente.desc()).all()


def _snapshot_call_assignments(
    session: Session,
    campana_id: str,
) -> dict[str, tuple[str, str]]:
    rows = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.activo_en_cartera.is_(True),
            Cliente.call_gestor_uid.isnot(None),
            Cliente.call_gestor_uid != "",
        )
        .all()
    )
    out: dict[str, tuple[str, str]] = {}
    for c in rows:
        key = c.codigo_cliente or str(c.id)
        out[key] = (c.call_gestor_uid or "", c.call_gestor_nombre or "")
    return out


def _apply_client_stats(balance: GestorCallBalance, cliente: Cliente) -> None:
    monto = float(cliente.importe_deuda_pendiente or 0)
    estado = cliente.estado_gestion or "pendiente"
    if estado == "pendiente":
        balance.pendientes += 1
        balance.monto_pendiente += monto
    else:
        balance.gestionados += 1
    if (cliente.monto_promesa_pago or 0) > 0 or (cliente.fecha_promesa_pago or "").strip():
        balance.promesas += 1


def _build_balances(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
    *,
    with_progress: bool = False,
) -> dict[str, GestorCallBalance]:
    balances: dict[str, GestorCallBalance] = {}
    for g in gestores_call:
        uid = g.get("uid") or g.get("id", "")
        nombre = g.get("nombre", g.get("email", uid))
        balances[uid] = GestorCallBalance(uid=uid, nombre=nombre)

    assigned = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.call_gestor_uid.isnot(None),
            Cliente.call_gestor_uid != "",
            Cliente.activo_en_cartera.is_(True),
        )
        .all()
    )
    for c in assigned:
        uid = c.call_gestor_uid or ""
        if uid not in balances:
            balances[uid] = GestorCallBalance(
                uid=uid,
                nombre=c.call_gestor_nombre or uid,
            )
        b = balances[uid]
        b.num_cuentas += 1
        b.monto_total += float(c.importe_deuda_pendiente or 0)
        if with_progress:
            _apply_client_stats(b, c)
    return balances


def _pick_gestor(balances: dict[str, GestorCallBalance]) -> GestorCallBalance:
    return min(
        balances.values(),
        key=lambda b: (b.monto_total, b.num_cuentas, b.uid),
    )


def preview_distribution(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
    *,
    only_unassigned: bool = True,
    fixed_assignments: dict[str, tuple[str, str, float]] | None = None,
    pending_clients: list[Cliente] | None = None,
) -> DistributionResult:
    """Simula el reparto sin persistir cambios."""
    result = DistributionResult(campana_id=campana_id)
    if not gestores_call:
        result.errores.append("No hay gestores de call center activos.")
        return result

    use_affinity_mode = fixed_assignments is not None and pending_clients is not None
    if use_affinity_mode:
        balances = _empty_balances(gestores_call)
        _apply_fixed_assignments(balances, fixed_assignments)
        pending = pending_clients
    else:
        balances = _build_balances(session, campana_id, gestores_call)
        if fixed_assignments:
            _apply_fixed_assignments(balances, fixed_assignments)
        pending = (
            pending_clients
            if pending_clients is not None
            else _eligible_tramo1_clients(
                session, campana_id, only_unassigned=only_unassigned,
            )
        )

    for cliente in pending:
        target = _pick_gestor(balances)
        monto = float(cliente.importe_deuda_pendiente or 0)
        target.num_cuentas += 1
        target.monto_total += monto
        target.nuevas_asignadas += 1
        target.monto_nuevo += monto
        result.cuentas_asignadas += 1
        result.monto_asignado += monto

    result.gestores = sorted(
        balances.values(),
        key=lambda b: b.nombre.lower(),
    )
    result.tipo = "reparto_inicial" if only_unassigned else "reequilibrio"
    return result


def distribute_tramo1(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
    *,
    only_unassigned: bool = True,
) -> DistributionResult:
    """
    Reparte cuentas tramo 1 entre gestores de call (LPT por monto).

    Args:
        only_unassigned: Si True, solo asigna cuentas sin call_gestor_uid.
                         Si False, re-equilibra todas las cuentas en call.
    """
    result = DistributionResult(campana_id=campana_id)
    result.tipo = "reparto_inicial" if only_unassigned else "reequilibrio"
    razon = RAZON_LPT_NUEVAS if only_unassigned else RAZON_LPT_REEQUILIBRIO

    if not gestores_call:
        result.errores.append("No hay gestores de call center activos.")
        return result

    snapshot = (
        _snapshot_call_assignments(session, campana_id)
        if not only_unassigned
        else {}
    )

    if not only_unassigned:
        session.query(Cliente).filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
        ).update(
            {Cliente.call_gestor_uid: None, Cliente.call_gestor_nombre: None},
            synchronize_session=False,
        )
        session.flush()

    if only_unassigned:
        balances = _build_balances(session, campana_id, gestores_call)
        pending = _eligible_tramo1_clients(session, campana_id, only_unassigned=True)
        for cliente in pending:
            target = _pick_gestor(balances)
            monto = float(cliente.importe_deuda_pendiente or 0)
            codigo = cliente.codigo_cliente or str(cliente.id)
            prev_uid, prev_nombre = snapshot.get(codigo, ("", ""))

            cliente.call_gestor_uid = target.uid
            cliente.call_gestor_nombre = target.nombre
            cliente.fecha_actualizacion = __import__("datetime").datetime.now()

            target.num_cuentas += 1
            target.monto_total += monto
            target.nuevas_asignadas += 1
            target.monto_nuevo += monto
            result.cuentas_asignadas += 1
            result.monto_asignado += monto

            if target.uid != prev_uid:
                result.cambios.append(CallAssignmentChange(
                    codigo_cliente=codigo,
                    nombre=_cliente_display_name(cliente),
                    importe=monto,
                    gestor_anterior_uid=prev_uid,
                    gestor_anterior_nombre=prev_nombre,
                    gestor_nuevo_uid=target.uid,
                    gestor_nuevo_nombre=target.nombre,
                    razon=razon,
                ))
    else:
        balances = _empty_balances(gestores_call)
        pending = _eligible_tramo1_clients(session, campana_id, only_unassigned=True)
        lpt_map = run_affinity_lpt(gestores_call, {}, pending)
        for cliente in pending:
            codigo = cliente.codigo_cliente or str(cliente.id)
            if codigo not in lpt_map:
                continue
            new_uid, new_nombre = lpt_map[codigo]
            monto = float(cliente.importe_deuda_pendiente or 0)
            prev_uid, prev_nombre = snapshot.get(codigo, ("", ""))

            cliente.call_gestor_uid = new_uid
            cliente.call_gestor_nombre = new_nombre
            cliente.fecha_actualizacion = __import__("datetime").datetime.now()
            result.cuentas_asignadas += 1
            result.monto_asignado += monto

            if new_uid != prev_uid:
                result.cambios.append(CallAssignmentChange(
                    codigo_cliente=codigo,
                    nombre=_cliente_display_name(cliente),
                    importe=monto,
                    gestor_anterior_uid=prev_uid,
                    gestor_anterior_nombre=prev_nombre,
                    gestor_nuevo_uid=new_uid,
                    gestor_nuevo_nombre=new_nombre,
                    razon=razon,
                ))
        balances = _build_balances(session, campana_id, gestores_call)

    session.commit()
    result.gestores = sorted(balances.values(), key=lambda b: b.nombre.lower())
    logger.info(
        "Call center distribution: %d accounts, S/ %.2f across %d gestores",
        result.cuentas_asignadas,
        result.monto_asignado,
        len(result.gestores),
    )
    return result


def get_call_center_summary(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
) -> dict[str, Any]:
    """Resumen actual de cartera call por gestor."""
    return get_call_center_dashboard(session, campana_id, gestores_call)


def get_call_center_dashboard(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
) -> dict[str, Any]:
    """Panel completo: reparto, avance y métricas por gestor de call."""
    balances = _build_balances(
        session, campana_id, gestores_call, with_progress=True,
    )
    unassigned = len(
        _eligible_tramo1_clients(session, campana_id, only_unassigned=True)
    )
    call_clients = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.activo_en_cartera.is_(True),
            Cliente.tramo_actual == TramoEnum.TRAMO_1.value,
        )
        .all()
    )
    total_call = len(call_clients)
    monto_total = sum(float(c.importe_deuda_pendiente or 0) for c in call_clients)
    pendientes_global = sum(1 for c in call_clients if (c.estado_gestion or "pendiente") == "pendiente")
    gestionados_global = total_call - pendientes_global
    promesas_global = sum(
        1 for c in call_clients
        if (c.monto_promesa_pago or 0) > 0 or (c.fecha_promesa_pago or "").strip()
    )
    gestores_sorted = sorted(balances.values(), key=lambda x: x.nombre.lower())
    montos = [b.monto_total for b in gestores_sorted if b.num_cuentas > 0]
    cuentas = [b.num_cuentas for b in gestores_sorted if b.num_cuentas > 0]

    def _gestor_dict(b: GestorCallBalance) -> dict[str, Any]:
        d = dict(b.__dict__)
        d["pct_avance"] = b.pct_avance
        return d

    return {
        "gestores": [_gestor_dict(b) for b in gestores_sorted],
        "sin_asignar": unassigned,
        "total_tramo1_call": total_call,
        "monto_total_call": monto_total,
        "pendientes_global": pendientes_global,
        "gestionados_global": gestionados_global,
        "promesas_global": promesas_global,
        "gestores_activos": len([g for g in gestores_call if g.get("activo", True)]),
        "desviacion_monto": float(statistics.pstdev(montos)) if len(montos) >= 2 else 0.0,
        "desviacion_cuentas": float(statistics.pstdev(cuentas)) if len(cuentas) >= 2 else 0.0,
        "max_cuentas": max(cuentas) if cuentas else 1,
        "max_monto": max(montos) if montos else 1.0,
        "pct_avance_global": round(gestionados_global / total_call * 100, 1) if total_call else 0.0,
    }


def get_clients_for_call_gestor(
    session: Session,
    campana_id: str,
    gestor_uid: str,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Clientes asignados a un gestor de call (para tabla en admin)."""
    rows = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.call_gestor_uid == gestor_uid,
            Cliente.activo_en_cartera.is_(True),
        )
        .order_by(Cliente.importe_deuda_pendiente.desc())
        .limit(limit)
        .all()
    )
    result: list[dict[str, Any]] = []
    for c in rows:
        result.append({
            "id": c.id,
            "codigo_cliente": c.codigo_cliente or "",
            "nombre": _cliente_display_name(c),
            "dni": c.numero_documento or "",
            "telefono": c.telefono_movil or "",
            "distrito": c.distrito or "",
            "estado_gestion": c.estado_gestion or "pendiente",
            "importe_deuda_pendiente": float(c.importe_deuda_pendiente or 0),
            "importe_deuda_asignada": float(c.importe_deuda_asignada or 0),
            "fecha_gestion": (c.fecha_gestion or "")[:10] if c.fecha_gestion else "",
            "fecha_promesa_pago": (c.fecha_promesa_pago or "")[:10] if c.fecha_promesa_pago else "",
            "monto_promesa_pago": float(c.monto_promesa_pago or 0),
            "region": c.region or "",
            "zona": c.zona or "",
            "seccion": c.seccion or "",
            "call_gestor_uid": c.call_gestor_uid or "",
            "call_gestor_nombre": c.call_gestor_nombre or "",
            "campana_banco": c.campana_banco or "",
        })
    return result


def reassign_call_client(
    session: Session,
    campana_id: str,
    cliente_id: int,
    new_uid: str,
    new_nombre: str,
) -> tuple[bool, str, CallAssignmentChange | None]:
    """Reasigna manualmente un cliente a otro gestor de call."""
    cliente = (
        session.query(Cliente)
        .filter(Cliente.id == cliente_id, Cliente.campana_id == campana_id)
        .first()
    )
    if cliente is None:
        return False, "Cliente no encontrado.", None
    if cliente.fase_gestion != FASE_GESTION_CALL:
        return False, "El cliente no está en fase call.", None
    if not new_uid:
        return False, "Gestor destino inválido.", None

    prev_uid = cliente.call_gestor_uid or ""
    prev_nombre = cliente.call_gestor_nombre or ""
    if prev_uid == new_uid:
        return False, "El cliente ya está asignado a ese gestor.", None

    monto = float(cliente.importe_deuda_pendiente or 0)
    cliente.call_gestor_uid = new_uid
    cliente.call_gestor_nombre = new_nombre
    cliente.fecha_actualizacion = __import__("datetime").datetime.now()
    session.commit()

    change = CallAssignmentChange(
        codigo_cliente=cliente.codigo_cliente or str(cliente.id),
        nombre=_cliente_display_name(cliente),
        importe=monto,
        gestor_anterior_uid=prev_uid,
        gestor_anterior_nombre=prev_nombre,
        gestor_nuevo_uid=new_uid,
        gestor_nuevo_nombre=new_nombre,
        razon=RAZON_REASIGNACION_MANUAL.format(nombre_destino=new_nombre),
    )
    return True, "Cliente reasignado.", change
