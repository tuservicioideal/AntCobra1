"""Tests for new EstadoGestion values and campaign resumen keys."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.database import EstadoGestion  # noqa: E402
from services.campaign_manager import CampaignManager  # noqa: E402


def test_estado_gestion_nuevos_valores():
    assert EstadoGestion.NO_HIZO_PEDIDO.value == "no_hizo_pedido"
    assert EstadoGestion.COMPLETO_PEDIDO_SOCIA.value == "completo_pedido_socia"


def test_filter_firebase_status_counts_new_estados():
    mgr = CampaignManager.__new__(CampaignManager)
    data = {
        "secciones": {
            "01_A_H": {
                "info": {},
                "clientes": [
                    {
                        "estado_gestion": "no_hizo_pedido",
                        "importe_deuda_asignada": 10,
                        "campana_banco": "202516",
                    },
                    {
                        "estado_gestion": "completo_pedido_socia",
                        "importe_deuda_asignada": 20,
                        "campana_banco": "202516",
                    },
                    {
                        "estado_gestion": "suplantacion",
                        "importe_deuda_asignada": 5,
                        "campana_banco": "202516",
                    },
                ],
            }
        }
    }
    out = mgr.filter_firebase_status(data, "202516")
    res = out["resumen"]
    assert res["no_hizo_pedido"] == 1
    assert res["completo_pedido_socia"] == 1
    assert res["suplantacion"] == 1
    # Must NOT dump unknown into pendiente
    assert res["pendiente"] == 0
    assert res["total"] == 3
