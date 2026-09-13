"""Semáforo de voluntad de pago (escala fija de 5 colores)."""

from __future__ import annotations

# id → (label, color hex)
NIVELES: dict[str, tuple[str, str]] = {
    "rojo": ("Renuente", "#DC2626"),
    "naranja": ("Resistente", "#EA580C"),
    "amarillo": ("Indefinido", "#EAB308"),
    "lima": ("Dispuesto", "#84CC16"),
    "verde": ("Cooperativo", "#16A34A"),
}

IDS_ORDEN = ("rojo", "naranja", "amarillo", "lima", "verde")

# Valor especial para filtros (no se persiste en el cliente)
SIN_CLASIFICAR = "__sin__"


def normalize_semaforo(value: str | None) -> str:
    """Return a valid level id or empty string."""
    if not value:
        return ""
    key = str(value).strip().lower()
    return key if key in NIVELES else ""


def label_for(value: str | None) -> str:
    key = normalize_semaforo(value)
    if not key:
        return "Sin clasificar"
    return NIVELES[key][0]


def color_for(value: str | None) -> str:
    key = normalize_semaforo(value)
    if not key:
        return "#94A3B8"
    return NIVELES[key][1]


def filter_options() -> list[tuple[str, str]]:
    """(value, label) for dropdowns including Sin clasificar."""
    opts = [(SIN_CLASIFICAR, "Sin clasificar")]
    for sid in IDS_ORDEN:
        opts.append((sid, NIVELES[sid][0]))
    return opts
