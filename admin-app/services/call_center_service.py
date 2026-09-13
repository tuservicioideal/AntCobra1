"""
Call Center Service — reparto de cuentas call entre 6 operadores fijos.

Plantilla de slots (``call_codigo`` en Firestore):
  E1-1, E1-2, E1-3  → cuentas tramo/etapa 1
  E2-1, E2-2        → cuentas tramo/etapa 2 que quedan en call
  E3-1              → cuentas tramo/etapa 3 que quedan en call

Dentro de cada pool: afinidad (mismo operador si sigue en el pool de la etapa)
+ LPT greedy por monto para nuevas / huérfanas / cambio de etapa.
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
from .fase_reparto import (
    CALL_CODIGOS_TODOS,
    CALL_SLOTS_MAX,
    call_codigos_for_tramo,
    etapa_for_call_codigo,
    filter_call_gestores_by_codigo,
    is_call_eligible_for_lpt,
    normalize_call_codigo,
    validate_call_slots,
)
from .tramo_engine import UMBRAL_MINIMO_GESTION, load_config

logger = logging.getLogger(__name__)

# Compat: aliases legacy (UI/tests antiguos pueden importarlos)
CALL_ROL_R6 = "r6"
CALL_ROL_R6_ETAPA2 = "r6_etapa2"
CALL_ROL_GENERAL = "general"

RAZON_LPT_NUEVAS = (
    "Algoritmo LPT: asignación al gestor call con menor monto acumulado"
)
RAZON_LPT_REEQUILIBRIO = (
    "Re-equilibrio LPT: redistribución para equilibrar montos entre operadores"
)
RAZON_SLOT_ETAPA = "Pool etapa {etapa}: LPT entre operadores {codigos}"
RAZON_CAMBIO_SLOT = "Cambio de slot por avance de etapa → pool {codigos}"
RAZON_R6 = "Región 6: asignación a gestora dedicada R6"  # legacy
RAZON_R6_ETAPA2 = "Región 6 etapa 2: asignación a gestora dedicada"  # legacy
RAZON_REASIGNACION_MANUAL = "Reasignación manual a {nombre_destino}"

MOTIVO_REPARTO_INICIAL = "Reparto automático call — cuentas sin asignar / nuevo pool"
MOTIVO_REEQUILIBRIO = "Re-equilibrio total de cartera call por etapa"
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
    bucket_counts: dict[str, int] = field(default_factory=dict)

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


def _gestor_uid(gestor: dict) -> str:
    return str(gestor.get("uid") or gestor.get("id") or "").strip()


def _gestor_nombre(gestor: dict) -> str:
    uid = _gestor_uid(gestor)
    return str(gestor.get("nombre") or gestor.get("email") or uid)


def normalize_call_reparto_rol(raw: Any) -> str:
    """Legacy: normaliza call_reparto_rol. Preferir call_codigo."""
    value = str(raw or CALL_ROL_GENERAL).strip().lower().replace("-", "_")
    aliases = {
        "r6": CALL_ROL_R6,
        "region6": CALL_ROL_R6,
        "region_6": CALL_ROL_R6,
        "r6_etapa2": CALL_ROL_R6_ETAPA2,
        "r6_e2": CALL_ROL_R6_ETAPA2,
        "etapa2": CALL_ROL_R6_ETAPA2,
        "e2": CALL_ROL_R6_ETAPA2,
        "general": CALL_ROL_GENERAL,
        "": CALL_ROL_GENERAL,
    }
    return aliases.get(value, CALL_ROL_GENERAL)


def split_call_gestores_by_rol(
    gestores_call: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Legacy: separa por call_reparto_rol. Preferir split por call_codigo."""
    r6: list[dict] = []
    r6_etapa2: list[dict] = []
    general: list[dict] = []
    for g in gestores_call:
        rol = normalize_call_reparto_rol(g.get("call_reparto_rol"))
        if rol == CALL_ROL_R6:
            r6.append(g)
        elif rol == CALL_ROL_R6_ETAPA2:
            r6_etapa2.append(g)
        else:
            general.append(g)
    return r6, r6_etapa2, general


def normalize_region_code(region: Any) -> str:
    """Normaliza '06', '6', 'R6', 'Región 6' → '6'."""
    raw = str(region or "").strip().upper().replace(" ", "")
    raw = raw.replace("REGIÓN", "R").replace("REGION", "R")
    if raw.startswith("R") and raw[1:].lstrip("0").isdigit():
        return raw[1:].lstrip("0") or "0"
    digits = raw.lstrip("0")
    if digits.isdigit():
        return digits
    if raw.isdigit():
        return raw.lstrip("0") or "0"
    return raw


def is_region_6(region: Any) -> bool:
    return normalize_region_code(region) == "6"


def is_etapa_2(cliente: Cliente) -> bool:
    """Etapa 2 del ciclo (tramo 2) o etiqueta de deuda equivalente."""
    try:
        if int(getattr(cliente, "tramo_actual", 0) or 0) == 2:
            return True
    except (TypeError, ValueError):
        pass
    raw = str(getattr(cliente, "etapa_deuda", "") or "").strip().upper()
    compact = (
        raw.replace(" ", "")
        .replace("É", "E")
        .replace("Á", "A")
        .replace("-", "")
        .replace("_", "")
    )
    if compact in {"2", "E2", "ETAPA2", "II"}:
        return True
    if compact.startswith("ETAPA2") or compact.endswith("ETAPA2"):
        return True
    return False


def classify_call_bucket(cliente: Cliente) -> str:
    """Legacy bucket R6. El reparto nuevo usa classify_call_slot_pool."""
    if is_region_6(getattr(cliente, "region", "")):
        if is_etapa_2(cliente):
            return CALL_ROL_R6_ETAPA2
        return CALL_ROL_R6
    return CALL_ROL_GENERAL


def classify_call_slot_pool(cliente: Cliente) -> tuple[str, ...]:
    """Códigos de operador call que pueden recibir esta cuenta."""
    try:
        tramo = int(getattr(cliente, "tramo_actual", 0) or 0)
    except (TypeError, ValueError):
        tramo = 0
    return call_codigos_for_tramo(tramo)


def _gestor_call_codigo(gestor: dict) -> str:
    return normalize_call_codigo(gestor.get("call_codigo"))


def _gestor_in_pool(gestor: dict, pool: tuple[str, ...]) -> bool:
    code = _gestor_call_codigo(gestor)
    return bool(code) and code in pool


def run_slot_call_assignment(
    gestores_call: list[dict],
    fixed_assignments: dict[str, tuple[str, str, float]],
    pending_clients: list[Cliente],
    *,
    lpt_razon: str = RAZON_LPT_NUEVAS,
) -> dict[str, tuple[str, str, str]]:
    """
    Asigna pending_clients por pool de etapa (call_codigo).

    Returns:
        codigo_cliente -> (gestor_uid, gestor_nombre, razon)
    """
    assignments: dict[str, tuple[str, str, str]] = {}
    if not gestores_call or not pending_clients:
        return assignments

    # Índice uid → gestor y código
    by_uid = {
        _gestor_uid(g): g for g in gestores_call if _gestor_uid(g)
    }

    # Agrupar pending por pool de etapa
    by_pool: dict[tuple[str, ...], list[Cliente]] = {}
    for cliente in pending_clients:
        pool = classify_call_slot_pool(cliente)
        if not pool:
            continue
        by_pool.setdefault(pool, []).append(cliente)

    for pool, clients in by_pool.items():
        pool_gestores = filter_call_gestores_by_codigo(gestores_call, pool)
        if not pool_gestores:
            # Fallback: todos los call activos (migración / plantilla incompleta)
            pool_gestores = list(gestores_call)
        pool_uids = {_gestor_uid(g) for g in pool_gestores if _gestor_uid(g)}
        pool_fixed = {
            codigo: values
            for codigo, values in (fixed_assignments or {}).items()
            if values and values[0] in pool_uids
        }
        codigos_label = ", ".join(pool)
        etapa = etapa_for_call_codigo(pool[0]) if pool else 0
        razon = RAZON_SLOT_ETAPA.format(etapa=etapa, codigos=codigos_label)
        if lpt_razon == RAZON_LPT_REEQUILIBRIO:
            razon = f"{RAZON_LPT_REEQUILIBRIO} (etapa {etapa}: {codigos_label})"

        lpt_map = run_affinity_lpt(pool_gestores, pool_fixed, clients)
        for codigo, (uid, nombre) in lpt_map.items():
            # Marcar cambio de slot si el fixed anterior no estaba en este pool
            prev = (fixed_assignments or {}).get(codigo)
            if prev and prev[0] and prev[0] not in pool_uids:
                assignments[codigo] = (
                    uid,
                    nombre,
                    RAZON_CAMBIO_SLOT.format(codigos=codigos_label),
                )
            else:
                assignments[codigo] = (uid, nombre, razon)
    return assignments


def run_bucketed_call_assignment(
    gestores_call: list[dict],
    fixed_assignments: dict[str, tuple[str, str, float]],
    pending_clients: list[Cliente],
    *,
    lpt_razon: str = RAZON_LPT_NUEVAS,
) -> dict[str, tuple[str, str, str]]:
    """
    Punto de entrada de asignación call.

    Si hay ``call_codigo`` en los gestores, usa pools por etapa.
    Si no (legacy), cae al LPT global (comportamiento sin buckets R6).
    """
    has_slots = any(normalize_call_codigo(g.get("call_codigo")) for g in gestores_call)
    if has_slots:
        return run_slot_call_assignment(
            gestores_call,
            fixed_assignments,
            pending_clients,
            lpt_razon=lpt_razon,
        )

    # Legacy sin call_codigo: LPT entre todos
    assignments: dict[str, tuple[str, str, str]] = {}
    if not gestores_call or not pending_clients:
        return assignments
    lpt_map = run_affinity_lpt(gestores_call, fixed_assignments or {}, pending_clients)
    for codigo, (uid, nombre) in lpt_map.items():
        assignments[codigo] = (uid, nombre, lpt_razon)
    return assignments


def _eligible_call_clients(
    session: Session,
    campana_id: str,
    *,
    only_unassigned: bool,
    tramo: int | None = None,
) -> list[Cliente]:
    """Cuentas en fase call elegibles para LPT (todas las etapas o una)."""
    load_config()
    q = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.activo_en_cartera.is_(True),
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.importe_deuda_pendiente >= UMBRAL_MINIMO_GESTION,
            Cliente.tramo_actual.in_([
                TramoEnum.TRAMO_1.value,
                TramoEnum.TRAMO_2.value,
                TramoEnum.TRAMO_3.value,
            ]),
        )
    )
    if tramo is not None:
        q = q.filter(Cliente.tramo_actual == tramo)
    if only_unassigned:
        q = q.filter(
            (Cliente.call_gestor_uid.is_(None)) | (Cliente.call_gestor_uid == "")
        )
    return q.order_by(Cliente.importe_deuda_pendiente.desc()).all()


def _eligible_tramo1_clients(
    session: Session,
    campana_id: str,
    *,
    only_unassigned: bool,
) -> list[Cliente]:
    """Compat: solo etapa 1. Preferir ``_eligible_call_clients``."""
    return _eligible_call_clients(
        session, campana_id, only_unassigned=only_unassigned, tramo=TramoEnum.TRAMO_1.value,
    )


def _clients_needing_slot_reassign(
    session: Session,
    campana_id: str,
    gestores_call: list[dict],
) -> list[Cliente]:
    """
    Cuentas call cuyo gestor actual no pertenece al pool de su etapa
    (p. ej. avanzó de E1 a E2 y sigue con operador E1-*).
    """
    by_uid = {
        _gestor_uid(g): g for g in gestores_call if _gestor_uid(g)
    }
    rows = _eligible_call_clients(session, campana_id, only_unassigned=False)
    out: list[Cliente] = []
    for c in rows:
        uid = (c.call_gestor_uid or "").strip()
        pool = classify_call_slot_pool(c)
        if not pool:
            continue
        if not uid:
            out.append(c)
            continue
        g = by_uid.get(uid)
        if g is None or not _gestor_in_pool(g, pool):
            out.append(c)
    return out


def _bucket_counts(clients: list[Cliente]) -> dict[str, int]:
    counts = {code: 0 for code in CALL_CODIGOS_TODOS}
    counts["sin_pool"] = 0
    for cliente in clients:
        pool = classify_call_slot_pool(cliente)
        if not pool:
            counts["sin_pool"] += 1
            continue
        # Contar en la clave del primer código del pool (agrupa por etapa)
        key = f"E{_tramo_safe(cliente)}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _tramo_safe(cliente: Cliente) -> int:
    try:
        return int(getattr(cliente, "tramo_actual", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _empty_balances(gestores_call: list[dict]) -> dict[str, GestorCallBalance]:
    balances: dict[str, GestorCallBalance] = {}
    for g in gestores_call:
        uid = g.get("uid") or g.get("id", "")
        if not uid:
            continue
        nombre = g.get("nombre", g.get("email", uid))
        code = _gestor_call_codigo(g)
        label = f"{nombre} ({code})" if code else nombre
        balances[uid] = GestorCallBalance(uid=uid, nombre=label)
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
        # Nombre sin sufijo de código para persistencia limpia
        raw_nombre = _gestor_nombre(
            next(
                (g for g in gestores_call if _gestor_uid(g) == target.uid),
                {"nombre": target.nombre, "uid": target.uid},
            )
        )
        assignments[codigo] = (target.uid, raw_nombre)
        target.num_cuentas += 1
        target.monto_total += monto
        target.nuevas_asignadas += 1
        target.monto_nuevo += monto
    return assignments


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
        code = _gestor_call_codigo(g)
        label = f"{nombre} ({code})" if code else nombre
        balances[uid] = GestorCallBalance(uid=uid, nombre=label)

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


def _current_fixed_assignments(
    session: Session,
    campana_id: str,
    *,
    gestores_call: list[dict] | None = None,
    only_valid_pool: bool = False,
) -> dict[str, tuple[str, str, float]]:
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
    by_uid = {}
    if gestores_call:
        by_uid = {_gestor_uid(g): g for g in gestores_call if _gestor_uid(g)}
    out: dict[str, tuple[str, str, float]] = {}
    for c in rows:
        codigo = c.codigo_cliente or str(c.id)
        uid = c.call_gestor_uid or ""
        if only_valid_pool and by_uid:
            pool = classify_call_slot_pool(c)
            g = by_uid.get(uid)
            if pool and (g is None or not _gestor_in_pool(g, pool)):
                continue  # no contar como fixed: irá a pending
        out[codigo] = (
            uid,
            c.call_gestor_nombre or "",
            float(c.importe_deuda_pendiente or 0),
        )
    return out


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


def _ensure_balance(
    balances: dict[str, GestorCallBalance],
    uid: str,
    nombre: str,
) -> GestorCallBalance:
    if uid not in balances:
        balances[uid] = GestorCallBalance(uid=uid, nombre=nombre)
    return balances[uid]


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
    lpt_razon = RAZON_LPT_NUEVAS if only_unassigned else RAZON_LPT_REEQUILIBRIO
    if use_affinity_mode:
        balances = _empty_balances(gestores_call)
        _apply_fixed_assignments(balances, fixed_assignments)
        pending = pending_clients or []
        fixed = fixed_assignments or {}
    else:
        pending = (
            pending_clients
            if pending_clients is not None
            else _eligible_call_clients(
                session, campana_id, only_unassigned=only_unassigned,
            )
        )
        if only_unassigned:
            # Incluir también las que necesitan cambio de slot
            needing = _clients_needing_slot_reassign(
                session, campana_id, gestores_call,
            )
            seen = {c.codigo_cliente or str(c.id) for c in pending}
            for c in needing:
                key = c.codigo_cliente or str(c.id)
                if key not in seen:
                    pending.append(c)
                    seen.add(key)
            balances = _build_balances(session, campana_id, gestores_call)
            fixed = fixed_assignments if fixed_assignments is not None else (
                _current_fixed_assignments(
                    session, campana_id,
                    gestores_call=gestores_call,
                    only_valid_pool=True,
                )
            )
            if fixed_assignments:
                _apply_fixed_assignments(balances, fixed_assignments)
        else:
            balances = _empty_balances(gestores_call)
            fixed = fixed_assignments or {}
            if fixed:
                _apply_fixed_assignments(balances, fixed)

    assign_map = run_bucketed_call_assignment(
        gestores_call, fixed, pending, lpt_razon=lpt_razon,
    )
    result.bucket_counts = _bucket_counts(pending)

    for cliente in pending:
        codigo = cliente.codigo_cliente or str(cliente.id)
        if codigo not in assign_map:
            continue
        uid, nombre, _razon = assign_map[codigo]
        target = _ensure_balance(balances, uid, nombre)
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
    Reparte cuentas call entre gestores por pool de etapa (call_codigo).

    Args:
        only_unassigned: Si True, asigna sin uid + las que deben cambiar de slot.
                         Si False, re-equilibra por pool (limpia uids del pool
                         y vuelve a repartir esa etapa).
    """
    result = DistributionResult(campana_id=campana_id)
    result.tipo = "reparto_inicial" if only_unassigned else "reequilibrio"
    lpt_razon = RAZON_LPT_NUEVAS if only_unassigned else RAZON_LPT_REEQUILIBRIO

    if not gestores_call:
        result.errores.append("No hay gestores de call center activos.")
        return result

    snapshot = _snapshot_call_assignments(session, campana_id)

    if not only_unassigned:
        # Re-equilibrio por pool: solo limpia uids de cuentas call elegibles
        session.query(Cliente).filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.activo_en_cartera.is_(True),
            Cliente.tramo_actual.in_([
                TramoEnum.TRAMO_1.value,
                TramoEnum.TRAMO_2.value,
                TramoEnum.TRAMO_3.value,
            ]),
        ).update(
            {Cliente.call_gestor_uid: None, Cliente.call_gestor_nombre: None},
            synchronize_session=False,
        )
        session.flush()
        fixed: dict[str, tuple[str, str, float]] = {}
        pending = _eligible_call_clients(session, campana_id, only_unassigned=True)
    else:
        needing = _clients_needing_slot_reassign(session, campana_id, gestores_call)
        # Liberar uid de las que cambian de slot para que entren al LPT del pool
        needing_ids = {c.id for c in needing if c.call_gestor_uid}
        for c in needing:
            if c.call_gestor_uid:
                c.call_gestor_uid = None
                c.call_gestor_nombre = None
        if needing_ids:
            session.flush()
        fixed = _current_fixed_assignments(
            session, campana_id,
            gestores_call=gestores_call,
            only_valid_pool=True,
        )
        pending = _eligible_call_clients(session, campana_id, only_unassigned=True)

    result.bucket_counts = _bucket_counts(pending)
    assign_map = run_bucketed_call_assignment(
        gestores_call, fixed, pending, lpt_razon=lpt_razon,
    )

    for cliente in pending:
        codigo = cliente.codigo_cliente or str(cliente.id)
        if codigo not in assign_map:
            continue
        new_uid, new_nombre, razon = assign_map[codigo]
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

    session.commit()
    balances = _build_balances(session, campana_id, gestores_call)
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
        _eligible_call_clients(session, campana_id, only_unassigned=True)
    )
    needing_slot = len(
        _clients_needing_slot_reassign(session, campana_id, gestores_call)
    )
    call_clients = (
        session.query(Cliente)
        .filter(
            Cliente.campana_id == campana_id,
            Cliente.fase_gestion == FASE_GESTION_CALL,
            Cliente.activo_en_cartera.is_(True),
            Cliente.tramo_actual.in_([
                TramoEnum.TRAMO_1.value,
                TramoEnum.TRAMO_2.value,
                TramoEnum.TRAMO_3.value,
            ]),
        )
        .all()
    )
    total_call = len(call_clients)
    by_etapa = {1: 0, 2: 0, 3: 0}
    for c in call_clients:
        t = _tramo_safe(c)
        if t in by_etapa:
            by_etapa[t] += 1
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

    slot_status = []
    assigned_codes = {
        normalize_call_codigo(g.get("call_codigo")): g
        for g in gestores_call
        if normalize_call_codigo(g.get("call_codigo"))
    }
    for code in CALL_CODIGOS_TODOS:
        g = assigned_codes.get(code)
        slot_status.append({
            "codigo": code,
            "ocupado": g is not None,
            "uid": _gestor_uid(g) if g else "",
            "nombre": _gestor_nombre(g) if g else "",
            "etapa": etapa_for_call_codigo(code),
        })

    def _gestor_dict(b: GestorCallBalance) -> dict[str, Any]:
        d = dict(b.__dict__)
        d["pct_avance"] = b.pct_avance
        g = next((x for x in gestores_call if _gestor_uid(x) == b.uid), None)
        d["call_codigo"] = _gestor_call_codigo(g) if g else ""
        return d

    return {
        "gestores": [_gestor_dict(b) for b in gestores_sorted],
        "sin_asignar": unassigned,
        "necesitan_cambio_slot": needing_slot,
        "total_tramo1_call": by_etapa[1],  # compat
        "total_call": total_call,
        "por_etapa": by_etapa,
        "monto_total_call": monto_total,
        "pendientes_global": pendientes_global,
        "gestionados_global": gestionados_global,
        "promesas_global": promesas_global,
        "gestores_activos": len([g for g in gestores_call if g.get("activo", True)]),
        "slots": slot_status,
        "slots_faltantes": [
            s["codigo"] for s in slot_status if not s["ocupado"]
        ],
        "desviacion_monto": float(statistics.pstdev(montos)) if len(montos) >= 2 else 0.0,
        "desviacion_cuentas": float(statistics.pstdev(cuentas)) if len(cuentas) >= 2 else 0.0,
        "max_cuentas": max(cuentas) if cuentas else 1,
        "max_monto": max(montos) if montos else 1.0,
        "pct_avance_global": round(gestionados_global / total_call * 100, 1) if total_call else 0.0,
        "plantilla_errores": validate_call_slots(gestores_call),
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
            "tramo_actual": int(c.tramo_actual or 0),
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
