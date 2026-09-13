"""
Motor de fase call/campo y slots de operadores call (E1-1 … E3-1).

Reglas:
  1. Arrastre por DNI: si otra cuenta activa del mismo DNI ya está en campo,
     esta cuenta va a campo con el gestor ancla (incluso en etapa 1).
  2. Etapa 1 → call.
  3. Etapa 2/3 → campo solo si saldo > umbral carta (S/ 40) y sin habido;
     si no, call (pools E2-* / E3-1).
  4. No retorno automático campo→call cuando baja el saldo.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from .database import (
    Cliente,
    EstadoGestion,
    FASE_GESTION_CALL,
    FASE_GESTION_CAMPO,
    TramoEnum,
    make_call_section_key,
)
from .excel_parser import make_seccion_key
from .tramo_engine import UMBRAL_CARTA_FISICA, UMBRAL_MINIMO_GESTION, load_config

# ── Códigos estáticos de operadores call ─────────────────────────

CALL_CODIGOS_E1 = ("E1-1", "E1-2", "E1-3")
CALL_CODIGOS_E2 = ("E2-1", "E2-2")
CALL_CODIGOS_E3 = ("E3-1",)
CALL_CODIGOS_TODOS = CALL_CODIGOS_E1 + CALL_CODIGOS_E2 + CALL_CODIGOS_E3
CALL_SLOTS_MAX = len(CALL_CODIGOS_TODOS)  # 6

CALL_CODIGO_POR_ETAPA: dict[int, tuple[str, ...]] = {
    TramoEnum.TRAMO_1.value: CALL_CODIGOS_E1,
    TramoEnum.TRAMO_2.value: CALL_CODIGOS_E2,
    TramoEnum.TRAMO_3.value: CALL_CODIGOS_E3,
}

# Motivos / badges de afinidad y fase
MOTIVO_ETAPA1_CALL = "ETAPA1_CALL"
MOTIVO_PASA_CAMPO_MONTO = "PASA_CAMPO_MONTO"
MOTIVO_QUEDA_CALL_HABIDO = "QUEDA_CALL_HABIDO"
MOTIVO_QUEDA_CALL_BAJO_MONTO = "QUEDA_CALL_BAJO_MONTO"
MOTIVO_SEGUNDA_CUENTA_CAMPO = "SEGUNDA_CUENTA_CAMPO"
MOTIVO_CAMBIO_SLOT_ETAPA = "CAMBIO_SLOT_ETAPA"
MOTIVO_YA_EN_CAMPO = "YA_EN_CAMPO"
MOTIVO_FUERA_GESTION = "FUERA_GESTION"


@dataclass
class FaseDecision:
    codigo_cliente: str
    fase: str  # call | campo
    motivo: str
    tramo: int
    arrastre_dni: bool = False
    gestor_ancla_uid: str = ""
    gestor_ancla_nombre: str = ""
    seccion_ancla: str = ""
    seccion_territorial: str = ""
    call_pool: tuple[str, ...] = ()


@dataclass
class FaseBatchResult:
    decisiones: list[FaseDecision] = field(default_factory=list)
    pasos_a_campo: list[dict[str, Any]] = field(default_factory=list)
    pasos_a_call: list[dict[str, Any]] = field(default_factory=list)
    cambios_slot: list[dict[str, Any]] = field(default_factory=list)

    def decision_for(self, codigo: str) -> Optional[FaseDecision]:
        for d in self.decisiones:
            if d.codigo_cliente == codigo:
                return d
        return None


def normalize_call_codigo(raw: Any) -> str:
    value = str(raw or "").strip().upper().replace("_", "-")
    if value in CALL_CODIGOS_TODOS:
        return value
    return ""


def etapa_for_call_codigo(codigo: str) -> int:
    code = normalize_call_codigo(codigo)
    if code in CALL_CODIGOS_E1:
        return 1
    if code in CALL_CODIGOS_E2:
        return 2
    if code in CALL_CODIGOS_E3:
        return 3
    return 0


def call_codigos_for_tramo(tramo: int) -> tuple[str, ...]:
    try:
        t = int(tramo or 0)
    except (TypeError, ValueError):
        t = 0
    return CALL_CODIGO_POR_ETAPA.get(t, ())


def filter_call_gestores_by_codigo(
    gestores_call: list[dict],
    codigos: Iterable[str],
) -> list[dict]:
    wanted = {normalize_call_codigo(c) for c in codigos if normalize_call_codigo(c)}
    if not wanted:
        return []
    out: list[dict] = []
    for g in gestores_call:
        code = normalize_call_codigo(g.get("call_codigo"))
        if code in wanted:
            out.append(g)
    return out


def validate_call_slots(gestores_call: list[dict]) -> list[str]:
    """Errores de plantilla: códigos inválidos, duplicados, más de 6."""
    errors: list[str] = []
    seen: dict[str, str] = {}
    activos = [
        g for g in gestores_call
        if g.get("rol") == "gestor"
        and g.get("canal") == "call"
        and g.get("activo", True)
    ]
    if len(activos) > CALL_SLOTS_MAX:
        errors.append(
            f"Hay {len(activos)} operadores call activos; el máximo es {CALL_SLOTS_MAX}."
        )
    for g in activos:
        uid = str(g.get("uid") or g.get("id") or "")
        nombre = str(g.get("nombre") or g.get("email") or uid)
        code = normalize_call_codigo(g.get("call_codigo"))
        if not code:
            errors.append(f"Operador call sin código válido: {nombre}")
            continue
        if code in seen:
            errors.append(
                f"Código {code} duplicado: {seen[code]} y {nombre}"
            )
        else:
            seen[code] = nombre
    for code in CALL_CODIGOS_TODOS:
        if code not in seen:
            errors.append(f"Falta operador call con código {code}")
    return errors


def _territorial_key(cliente: Cliente) -> str:
    return make_seccion_key(
        cliente.region or "",
        cliente.zona or "",
        cliente.seccion or "SIN_SECCION",
    )


def _dni_key(cliente: Cliente) -> str:
    return str(getattr(cliente, "numero_documento", "") or "").strip()


def _is_habido(cliente: Cliente) -> bool:
    return (
        str(getattr(cliente, "estado_gestion", "") or "")
        == EstadoGestion.VISITADO_HABIDO.value
    )


def _saldo(cliente: Cliente) -> float:
    try:
        return float(cliente.importe_deuda_pendiente or 0)
    except (TypeError, ValueError):
        return 0.0


def _tramo(cliente: Cliente) -> int:
    try:
        return int(getattr(cliente, "tramo_actual", 0) or 0)
    except (TypeError, ValueError):
        return 0


def decide_fase_organic(
    cliente: Cliente,
    *,
    umbral_campo: float | None = None,
) -> tuple[str, str]:
    """
    Decisión call/campo SIN arrastre DNI.

    Returns:
        (fase, motivo)
    """
    load_config()
    umbral = float(umbral_campo if umbral_campo is not None else UMBRAL_CARTA_FISICA)
    tramo = _tramo(cliente)
    saldo = _saldo(cliente)
    habido = _is_habido(cliente)

    if tramo == TramoEnum.TRAMO_1.value:
        return FASE_GESTION_CALL, MOTIVO_ETAPA1_CALL

    if tramo in (TramoEnum.TRAMO_2.value, TramoEnum.TRAMO_3.value):
        if saldo > umbral and not habido:
            return FASE_GESTION_CAMPO, MOTIVO_PASA_CAMPO_MONTO
        if habido:
            return FASE_GESTION_CALL, MOTIVO_QUEDA_CALL_HABIDO
        return FASE_GESTION_CALL, MOTIVO_QUEDA_CALL_BAJO_MONTO

    # tramo 0 / desconocido: conservar call si ya lo era, si no campo
    fase_actual = getattr(cliente, "fase_gestion", FASE_GESTION_CAMPO) or FASE_GESTION_CAMPO
    return fase_actual, MOTIVO_FUERA_GESTION


def _pick_ancla_from_campo_rows(
    campo_rows: list[Cliente],
    *,
    assignment_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, str, str]:
    """
    Elige gestor ancla entre cuentas ya en campo del mismo DNI.

    Preferencia: más cuentas por gestor (vía sección → assignment_index),
    empate por mayor saldo acumulado, luego uid.
    """
    if not campo_rows:
        return "", "", ""

    # Agrupar por gestor resuelto vía sección territorial (o seccion_origen)
    by_gestor: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "monto": 0.0, "nombre": "", "seccion": ""}
    )

    for row in campo_rows:
        sk = _territorial_key(row)
        uid = ""
        nombre = ""
        if assignment_index:
            info = assignment_index.get(sk) or {}
            if info.get("status") == "assigned":
                uid = str(info.get("gestor_uid") or "")
                nombre = str(info.get("gestor_nombre") or "")
        if not uid:
            # Sin índice: usar la sección como clave de agrupación
            uid = f"_sec:{sk}"
            nombre = sk
        bucket = by_gestor[uid]
        bucket["n"] += 1
        bucket["monto"] += _saldo(row)
        bucket["nombre"] = nombre or bucket["nombre"]
        if not bucket["seccion"]:
            bucket["seccion"] = sk

    best_uid = ""
    best = None
    for uid, data in by_gestor.items():
        key = (data["n"], data["monto"], uid)
        if best is None or key > (
            best["n"],
            best["monto"],
            best_uid,
        ):
            best = data
            best_uid = uid

    if not best or best_uid.startswith("_sec:"):
        # Fallback: sección de la cuenta con mayor saldo
        top = max(campo_rows, key=lambda c: (_saldo(c), c.codigo_cliente or ""))
        sk = _territorial_key(top)
        if assignment_index:
            info = assignment_index.get(sk) or {}
            if info.get("status") == "assigned":
                return (
                    str(info.get("gestor_uid") or ""),
                    str(info.get("gestor_nombre") or ""),
                    sk,
                )
        return "", "", sk

    return best_uid, str(best["nombre"]), str(best["seccion"])


def build_dni_campo_index(
    clientes: list[Cliente],
) -> dict[str, list[Cliente]]:
    """DNI → cuentas activas actualmente en fase campo."""
    index: dict[str, list[Cliente]] = defaultdict(list)
    for c in clientes:
        if not getattr(c, "activo_en_cartera", True):
            continue
        fase = getattr(c, "fase_gestion", "") or ""
        if fase != FASE_GESTION_CAMPO:
            continue
        dni = _dni_key(c)
        if dni:
            index[dni].append(c)
    return index


def decide_fase_for_cliente(
    cliente: Cliente,
    *,
    dni_campo_index: dict[str, list[Cliente]] | None = None,
    assignment_index: dict[str, dict[str, Any]] | None = None,
    exclude_self: bool = True,
    umbral_campo: float | None = None,
    allow_return_to_call: bool = False,
) -> FaseDecision:
    """
    Decide fase para una cuenta.

    Si allow_return_to_call=False (default), una cuenta ya en campo no vuelve
    a call solo por bajar el saldo (salvo que se recalcule migración explícita
    con allow_return_to_call=True para casos que nunca debieron estar en campo).
    """
    codigo = cliente.codigo_cliente or str(cliente.id)
    tramo = _tramo(cliente)
    seccion_terr = _territorial_key(cliente)
    dni = _dni_key(cliente)
    fase_actual = getattr(cliente, "fase_gestion", FASE_GESTION_CAMPO) or FASE_GESTION_CAMPO

    # Arrastre DNI
    if dni and dni_campo_index:
        hermanos = list(dni_campo_index.get(dni) or [])
        if exclude_self:
            hermanos = [
                h for h in hermanos
                if (h.codigo_cliente or str(h.id)) != codigo
            ]
        if hermanos:
            uid, nombre, seccion_ancla = _pick_ancla_from_campo_rows(
                hermanos, assignment_index=assignment_index,
            )
            return FaseDecision(
                codigo_cliente=codigo,
                fase=FASE_GESTION_CAMPO,
                motivo=MOTIVO_SEGUNDA_CUENTA_CAMPO,
                tramo=tramo,
                arrastre_dni=True,
                gestor_ancla_uid=uid,
                gestor_ancla_nombre=nombre,
                seccion_ancla=seccion_ancla or seccion_terr,
                seccion_territorial=seccion_terr,
                call_pool=(),
            )

    fase, motivo = decide_fase_organic(cliente, umbral_campo=umbral_campo)

    # No retorno automático campo → call
    if (
        not allow_return_to_call
        and fase_actual == FASE_GESTION_CAMPO
        and fase == FASE_GESTION_CALL
        and motivo != MOTIVO_SEGUNDA_CUENTA_CAMPO
    ):
        return FaseDecision(
            codigo_cliente=codigo,
            fase=FASE_GESTION_CAMPO,
            motivo=MOTIVO_YA_EN_CAMPO,
            tramo=tramo,
            seccion_territorial=seccion_terr,
            call_pool=(),
        )

    pool = call_codigos_for_tramo(tramo) if fase == FASE_GESTION_CALL else ()
    return FaseDecision(
        codigo_cliente=codigo,
        fase=fase,
        motivo=motivo,
        tramo=tramo,
        seccion_territorial=seccion_terr,
        call_pool=pool,
    )


def evaluate_fases_batch(
    clientes: list[Cliente],
    *,
    assignment_index: dict[str, dict[str, Any]] | None = None,
    umbral_campo: float | None = None,
    allow_return_to_call: bool = False,
) -> FaseBatchResult:
    """
    Evalúa fases en dos pasadas:
      1) orgánicas / ya en campo
      2) arrastre DNI tras materializar quién queda en campo
    Luego unifica gestor ancla cuando varias cuentas del mismo DNI entran a campo.
    """
    load_config()
    result = FaseBatchResult()
    if not clientes:
        return result

    # Pasada 1: decisiones orgánicas (sin arrastre), respetando ya-en-campo
    organic: dict[str, FaseDecision] = {}
    for c in clientes:
        if not getattr(c, "activo_en_cartera", True):
            continue
        codigo = c.codigo_cliente or str(c.id)
        fase_actual = getattr(c, "fase_gestion", "") or ""
        tramo = _tramo(c)
        seccion_terr = _territorial_key(c)

        if fase_actual == FASE_GESTION_CAMPO and not allow_return_to_call:
            organic[codigo] = FaseDecision(
                codigo_cliente=codigo,
                fase=FASE_GESTION_CAMPO,
                motivo=MOTIVO_YA_EN_CAMPO,
                tramo=tramo,
                seccion_territorial=seccion_terr,
            )
            continue

        fase, motivo = decide_fase_organic(c, umbral_campo=umbral_campo)
        if (
            not allow_return_to_call
            and fase_actual == FASE_GESTION_CAMPO
            and fase == FASE_GESTION_CALL
        ):
            organic[codigo] = FaseDecision(
                codigo_cliente=codigo,
                fase=FASE_GESTION_CAMPO,
                motivo=MOTIVO_YA_EN_CAMPO,
                tramo=tramo,
                seccion_territorial=seccion_terr,
            )
            continue

        pool = call_codigos_for_tramo(tramo) if fase == FASE_GESTION_CALL else ()
        organic[codigo] = FaseDecision(
            codigo_cliente=codigo,
            fase=fase,
            motivo=motivo,
            tramo=tramo,
            seccion_territorial=seccion_terr,
            call_pool=pool,
        )

    # Índice DNI de quienes quedan (o ya están) en campo tras pasada 1
    by_codigo = {
        (c.codigo_cliente or str(c.id)): c
        for c in clientes
        if getattr(c, "activo_en_cartera", True)
    }
    dni_campo: dict[str, list[Cliente]] = defaultdict(list)
    for codigo, dec in organic.items():
        if dec.fase != FASE_GESTION_CAMPO:
            continue
        c = by_codigo.get(codigo)
        if not c:
            continue
        dni = _dni_key(c)
        if dni:
            dni_campo[dni].append(c)

    # Pasada 2: arrastre — cuentas call con hermano en campo
    final: dict[str, FaseDecision] = dict(organic)
    for codigo, dec in list(organic.items()):
        if dec.fase != FASE_GESTION_CALL:
            continue
        c = by_codigo.get(codigo)
        if not c:
            continue
        dni = _dni_key(c)
        if not dni:
            continue
        hermanos = [
            h for h in dni_campo.get(dni, [])
            if (h.codigo_cliente or str(h.id)) != codigo
        ]
        if not hermanos:
            continue
        uid, nombre, seccion_ancla = _pick_ancla_from_campo_rows(
            hermanos, assignment_index=assignment_index,
        )
        final[codigo] = FaseDecision(
            codigo_cliente=codigo,
            fase=FASE_GESTION_CAMPO,
            motivo=MOTIVO_SEGUNDA_CUENTA_CAMPO,
            tramo=_tramo(c),
            arrastre_dni=True,
            gestor_ancla_uid=uid,
            gestor_ancla_nombre=nombre,
            seccion_ancla=seccion_ancla or _territorial_key(c),
            seccion_territorial=_territorial_key(c),
            call_pool=(),
        )
        dni_campo[dni].append(c)

    # Unificar ancla cuando varias del mismo DNI entran a campo en el lote
    dni_groups: dict[str, list[str]] = defaultdict(list)
    for codigo, dec in final.items():
        if dec.fase != FASE_GESTION_CAMPO:
            continue
        c = by_codigo.get(codigo)
        if not c:
            continue
        dni = _dni_key(c)
        if dni:
            dni_groups[dni].append(codigo)

    for dni, codigos in dni_groups.items():
        if len(codigos) < 2:
            continue
        rows = [by_codigo[c] for c in codigos if c in by_codigo]
        uid, nombre, seccion_ancla = _pick_ancla_from_campo_rows(
            rows, assignment_index=assignment_index,
        )
        if not seccion_ancla and not uid:
            continue
        for codigo in codigos:
            dec = final[codigo]
            # Solo forzar ancla en arrastres o cuando el motivo es segunda cuenta;
            # para orgánicos territoriales, si ya hay ancla de hermanos, alinear.
            if dec.motivo in (MOTIVO_SEGUNDA_CUENTA_CAMPO, MOTIVO_PASA_CAMPO_MONTO):
                final[codigo] = FaseDecision(
                    codigo_cliente=codigo,
                    fase=FASE_GESTION_CAMPO,
                    motivo=(
                        MOTIVO_SEGUNDA_CUENTA_CAMPO
                        if dec.motivo == MOTIVO_SEGUNDA_CUENTA_CAMPO
                        or any(
                            final[o].motivo == MOTIVO_SEGUNDA_CUENTA_CAMPO
                            for o in codigos if o != codigo
                        )
                        else dec.motivo
                    ),
                    tramo=dec.tramo,
                    arrastre_dni=dec.arrastre_dni or dec.motivo == MOTIVO_SEGUNDA_CUENTA_CAMPO,
                    gestor_ancla_uid=uid or dec.gestor_ancla_uid,
                    gestor_ancla_nombre=nombre or dec.gestor_ancla_nombre,
                    seccion_ancla=seccion_ancla or dec.seccion_ancla,
                    seccion_territorial=dec.seccion_territorial,
                    call_pool=(),
                )

    result.decisiones = list(final.values())

    for codigo, dec in final.items():
        c = by_codigo.get(codigo)
        if not c:
            continue
        fase_prev = getattr(c, "fase_gestion", "") or ""
        if fase_prev == FASE_GESTION_CALL and dec.fase == FASE_GESTION_CAMPO:
            seccion_dest = dec.seccion_ancla or dec.seccion_territorial
            result.pasos_a_campo.append({
                "cliente_id": getattr(c, "id", None),
                "codigo_cliente": codigo,
                "seccion_call": (
                    make_call_section_key(c.call_gestor_uid)
                    if c.call_gestor_uid else ""
                ),
                "seccion_territorial": seccion_dest,
                "call_gestor_uid_anterior": c.call_gestor_uid or "",
                "motivo": dec.motivo,
                "gestor_ancla_uid": dec.gestor_ancla_uid,
                "gestor_ancla_nombre": dec.gestor_ancla_nombre,
            })
        elif (
            allow_return_to_call
            and fase_prev == FASE_GESTION_CAMPO
            and dec.fase == FASE_GESTION_CALL
        ):
            result.pasos_a_call.append({
                "cliente_id": getattr(c, "id", None),
                "codigo_cliente": codigo,
                "motivo": dec.motivo,
                "tramo": dec.tramo,
            })
        elif (
            dec.fase == FASE_GESTION_CALL
            and c.call_gestor_uid
            and dec.call_pool
        ):
            # Detectar cambio de slot de etapa (requiere call_codigo del gestor
            # en capas superiores; aquí solo marcamos tramo vs pool esperado)
            result.cambios_slot.append({
                "codigo_cliente": codigo,
                "tramo": dec.tramo,
                "call_pool": list(dec.call_pool),
                "call_gestor_uid": c.call_gestor_uid or "",
            })

    return result


def apply_fase_decision_to_cliente(
    cliente: Cliente,
    decision: FaseDecision,
) -> bool:
    """Aplica fase (y limpia call_gestor si pasa a campo). Retorna True si cambió."""
    changed = False
    prev = getattr(cliente, "fase_gestion", "") or ""
    if decision.fase != prev:
        cliente.fase_gestion = decision.fase
        changed = True
    if decision.fase == FASE_GESTION_CAMPO:
        if cliente.call_gestor_uid or cliente.call_gestor_nombre:
            cliente.call_gestor_uid = None
            cliente.call_gestor_nombre = None
            changed = True
    return changed


def initial_fase_for_new_cliente(cliente: Cliente) -> None:
    """Asigna fase inicial al crear desde Excel (sin arrastre DNI aún)."""
    fase, _motivo = decide_fase_organic(cliente)
    cliente.fase_gestion = fase
    if fase == FASE_GESTION_CAMPO:
        cliente.call_gestor_uid = None
        cliente.call_gestor_nombre = None


def is_call_eligible_for_lpt(cliente: Cliente) -> bool:
    """Elegible para LPT call: fase call, tramo 1–3, saldo >= umbral mínimo."""
    load_config()
    if getattr(cliente, "fase_gestion", "") != FASE_GESTION_CALL:
        return False
    if not getattr(cliente, "activo_en_cartera", True):
        return False
    tramo = _tramo(cliente)
    if tramo not in (
        TramoEnum.TRAMO_1.value,
        TramoEnum.TRAMO_2.value,
        TramoEnum.TRAMO_3.value,
    ):
        return False
    return _saldo(cliente) >= UMBRAL_MINIMO_GESTION


def resolve_campo_seccion_for_decision(
    decision: FaseDecision,
) -> str:
    """Sección Firestore destino en campo (ancla o territorial)."""
    if decision.arrastre_dni and decision.seccion_ancla:
        return decision.seccion_ancla
    return decision.seccion_territorial or decision.seccion_ancla or ""
