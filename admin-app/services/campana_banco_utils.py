"""
Utilidades puras para filtrar y agrupar por número de campaña del banco (Excel col. E).

Alineado con flutter-app/lib/utils/campana_banco_utils.dart.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

# Clave interna para clientes sin campana_banco en el Excel.
SIN_CAMPANA_KEY = "_sin_campana_"
SIN_CAMPANA_LABEL = "Sin campaña"


def normalize_campana_banco(value: Any) -> str:
    """Normaliza el valor de campaña banco (trim, None → '')."""
    if value is None:
        return ""
    return str(value).strip()


def campana_banco_key_from_client(client: Mapping[str, Any]) -> str:
    """Clave de agrupación: valor normalizado o SIN_CAMPANA_KEY si vacío."""
    raw = client.get("campana_banco")
    normalized = normalize_campana_banco(raw)
    return normalized if normalized else SIN_CAMPANA_KEY


def campana_banco_key_from_value(value: Any) -> str:
    """Clave de agrupación desde un valor escalar."""
    normalized = normalize_campana_banco(value)
    return normalized if normalized else SIN_CAMPANA_KEY


def distinct_campana_banco_values(clientes: list[dict]) -> list[str]:
    """
    Valores distintos de campana_banco entre clientes.
    Incluye SIN_CAMPANA_KEY al final si hay filas sin número.
    """
    values: set[str] = set()
    has_empty = False
    for c in clientes:
        key = campana_banco_key_from_client(c)
        if key == SIN_CAMPANA_KEY:
            has_empty = True
        else:
            values.add(key)
    sorted_vals = sorted(values)
    if has_empty:
        sorted_vals.append(SIN_CAMPANA_KEY)
    return sorted_vals


def matches_campana_banco(client: Mapping[str, Any], filtro: str | None) -> bool:
    """True si el cliente coincide con el filtro (None = todas)."""
    if filtro is None:
        return True
    key = campana_banco_key_from_client(client)
    return key == filtro


def apply_campana_banco_filter(
    clientes: list[dict],
    filtro: str | None,
) -> list[dict]:
    """Devuelve subset filtrado; None en filtro = sin filtrar."""
    if filtro is None:
        return clientes
    return [c for c in clientes if matches_campana_banco(c, filtro)]


def filter_bar_visible(values: list[str]) -> bool:
    """Oculta la barra si solo hay una campaña banco (sin ruido UI)."""
    if not values:
        return False
    if len(values) == 1 and values[0] != SIN_CAMPANA_KEY:
        return False
    return len(values) > 1 or (
        len(values) == 1 and values[0] == SIN_CAMPANA_KEY
    )


def filter_label(filtro: str | None) -> str:
    """Etiqueta legible para el filtro activo."""
    if filtro is None:
        return "Todas las campañas"
    if filtro == SIN_CAMPANA_KEY:
        return SIN_CAMPANA_LABEL
    return filtro


def display_label_for_key(key: str) -> str:
    """Etiqueta visible para una clave de agrupación."""
    if key == SIN_CAMPANA_KEY:
        return SIN_CAMPANA_LABEL
    return key


def empty_etapa_recuperacion() -> dict[int, dict]:
    """Plantilla de recuperación por etapa E1/E2/E3."""
    return {
        1: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
        2: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
        3: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
    }


def aggregate_campana_banco_stats(clientes: list[dict]) -> dict[str, dict]:
    """
    Agrega cuentas, deuda asignada/recuperada y por_etapa por campana_banco.
    clientes: listas de dicts con campana_banco, tramo_actual, importes.
    """
    result: dict[str, dict] = {}

    for c in clientes:
        key = campana_banco_key_from_client(c)
        if key not in result:
            result[key] = {
                "label": display_label_for_key(key),
                "cuentas": 0,
                "asignada": 0.0,
                "recuperada": 0.0,
                "por_etapa_recuperacion": empty_etapa_recuperacion(),
            }

        bucket = result[key]
        asignada = float(c.get("importe_deuda_asignada") or 0.0)
        pendiente = float(c.get("importe_deuda_pendiente") or 0.0)
        recuperada = max(0.0, asignada - pendiente)

        bucket["cuentas"] += 1
        bucket["asignada"] += asignada
        bucket["recuperada"] += recuperada

        tramo = c.get("tramo_actual", 0)
        if tramo in (1, 2, 3):
            etapa = bucket["por_etapa_recuperacion"][tramo]
            etapa["asignada"] += asignada
            etapa["recuperada"] += recuperada
            etapa["cuentas"] += 1

    for bucket in result.values():
        bucket["asignada"] = round(bucket["asignada"], 2)
        bucket["recuperada"] = round(bucket["recuperada"], 2)
        for etapa in bucket["por_etapa_recuperacion"].values():
            etapa["asignada"] = round(etapa["asignada"], 2)
            etapa["recuperada"] = round(etapa["recuperada"], 2)

    return result


def compute_detected_dates_for_group(
    fechas_asignacion: list[date | None],
    fechas_cierre: list[date | None],
    duracion_dias: int,
) -> tuple[date | None, date | None]:
    """MIN fecha asignación y MAX fecha cierre de un grupo campana_banco."""
    valid_start = [d for d in fechas_asignacion if d]
    if not valid_start:
        return None, None
    inicio = min(valid_start)
    valid_end = [d for d in fechas_cierre if d]
    if valid_end:
        fin = max(valid_end)
    else:
        fin = inicio + timedelta(days=max(1, duracion_dias) - 1)
    return inicio, fin


def effective_campana_banco_dates(
    *,
    fecha_inicio_manual: date | None,
    fecha_fin_manual: date | None,
    fecha_inicio_detectada: date | None,
    fecha_fin_detectada: date | None,
    duracion_dias: int,
    today: date | None = None,
) -> dict[str, Any]:
    """Fechas efectivas, día del ciclo y días restantes para timeline."""
    today = today or date.today()
    inicio = fecha_inicio_manual or fecha_inicio_detectada or today
    fin = (
        fecha_fin_manual
        or fecha_fin_detectada
        or (inicio + timedelta(days=max(1, duracion_dias) - 1))
    )
    if fin < inicio:
        fin = inicio
    duracion = (fin - inicio).days + 1
    dia = max(1, min(duracion, (today - inicio).days + 1))
    dias_restantes = max(0, (fin - today).days)
    es_manual = fecha_inicio_manual is not None or fecha_fin_manual is not None
    return {
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "duracion": duracion,
        "dia_actual": dia,
        "dias_restantes": dias_restantes,
        "es_manual": es_manual,
    }
