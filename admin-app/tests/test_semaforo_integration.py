"""Integración: set_client_semaforo + filtro en get_clients_page."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture()
def mgr(tmp_path, monkeypatch):
    db_path = tmp_path / "data" / "semaforo_int.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Archivo vacío: evita que _migrate_legacy_db_if_needed copie la BD real.
    db_path.touch()
    monkeypatch.setenv("ANTCOBRANZAS_DB_PATH", str(db_path))

    from services.database import DatabaseService
    from services.campaign_manager import CampaignManager

    db = DatabaseService(db_path=str(db_path))
    db.initialize()
    return CampaignManager(db=db)


def _seed(mgr, codigo: str, *, semaforo: str = ""):
    from services.database import Campana, Cliente, EstadoGestion

    with mgr.db.session() as session:
        if session.get(Campana, "camp_semaforo") is None:
            session.add(
                Campana(
                    id="camp_semaforo",
                    nombre="Test Semaforo",
                    fecha_inicio=date(2026, 1, 1),
                    fecha_fin=date(2026, 3, 1),
                    estado="activa",
                    total_clientes=2,
                )
            )
        session.add(
            Cliente(
                campana_id="camp_semaforo",
                codigo_cliente=codigo,
                nombre_completo=f"Cliente {codigo}",
                estado_gestion=EstadoGestion.PENDIENTE.value,
                importe_deuda_asignada=100.0,
                importe_deuda_pendiente=100.0,
                semaforo=semaforo,
                region="01",
                zona="1211",
                seccion="H",
            )
        )
        session.commit()


def test_set_client_semaforo_and_filter(mgr):
    from services.semaforo import SIN_CLASIFICAR
    from services.database import Cliente

    _seed(mgr, "SA", semaforo="")
    _seed(mgr, "SB", semaforo="rojo")

    with mgr.db.session() as session:
        n = (
            session.query(Cliente)
            .filter(Cliente.campana_id == "camp_semaforo")
            .count()
        )
        assert n == 2, f"expected 2 seeded clients, got {n} in {mgr.db.db_path}"

    assert mgr.set_client_semaforo("camp_semaforo", "SA", "verde") is True

    page_all = mgr.get_clients_page("camp_semaforo", page_size=50)
    assert page_all["total"] == 2

    page_verde = mgr.get_clients_page("camp_semaforo", semaforo="verde", page_size=50)
    assert page_verde["total"] == 1
    assert page_verde["items"][0]["codigo_cliente"] == "SA"
    assert page_verde["items"][0]["semaforo"] == "verde"

    page_sin = mgr.get_clients_page(
        "camp_semaforo", semaforo=SIN_CLASIFICAR, page_size=50
    )
    assert page_sin["total"] == 0

    assert mgr.set_client_semaforo("camp_semaforo", "SB", "") is True
    page_sin2 = mgr.get_clients_page(
        "camp_semaforo", semaforo=SIN_CLASIFICAR, page_size=50
    )
    assert page_sin2["total"] == 1
    assert page_sin2["items"][0]["codigo_cliente"] == "SB"

    payload = mgr.get_firebase_payload("camp_semaforo")
    codes = {
        c["codigo_cliente"]: c.get("semaforo")
        for sec in payload["by_seccion"].values()
        for c in sec
    }
    assert codes["SA"] == "verde"
    assert codes["SB"] == ""
