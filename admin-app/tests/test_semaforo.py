"""Tests del semáforo de voluntad de pago."""
from __future__ import annotations

from services.semaforo import (
    IDS_ORDEN,
    NIVELES,
    SIN_CLASIFICAR,
    filter_options,
    label_for,
    normalize_semaforo,
)


def test_normalize_semaforo():
    assert normalize_semaforo("rojo") == "rojo"
    assert normalize_semaforo("VERDE") == "verde"
    assert normalize_semaforo("") == ""
    assert normalize_semaforo(None) == ""
    assert normalize_semaforo("azul") == ""


def test_label_for():
    assert label_for("rojo") == "Renuente"
    assert label_for("verde") == "Cooperativo"
    assert label_for("") == "Sin clasificar"


def test_filter_options_include_sin_clasificar():
    opts = filter_options()
    assert opts[0] == (SIN_CLASIFICAR, "Sin clasificar")
    assert [o[0] for o in opts[1:]] == list(IDS_ORDEN)
    assert set(NIVELES.keys()) == set(IDS_ORDEN)
