"""Tests: purge inactive campaigns while keeping visit/contact history."""

from __future__ import annotations

from datetime import date, datetime

import pytest


@pytest.fixture()
def mgr(tmp_path, monkeypatch):
    """Isolated CampaignManager backed by a temp SQLite DB."""
    db_path = tmp_path / "purge_test.db"
    monkeypatch.setenv("ANTCOBRANZAS_DB_PATH", str(db_path))

    from services.database import DatabaseService
    from services.campaign_manager import CampaignManager

    db = DatabaseService(db_path=str(db_path))
    db.initialize()
    return CampaignManager(db=db)


def _seed_campaign(mgr, campana_id: str, nombre: str, estado: str, codigo: str):
    from services.database import (
        Campana, Cliente, HistorialVisita, HistorialContacto, EstadoGestion,
    )

    with mgr.db.session() as session:
        camp = Campana(
            id=campana_id,
            nombre=nombre,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 3, 1),
            estado=estado,
            total_clientes=1,
        )
        session.add(camp)
        cliente = Cliente(
            campana_id=campana_id,
            codigo_cliente=codigo,
            nombre_completo=f"Cliente {codigo}",
            estado_gestion=EstadoGestion.PENDIENTE.value,
            importe_deuda_asignada=100.0,
            importe_deuda_pendiente=100.0,
        )
        session.add(cliente)
        session.flush()

        session.add(HistorialVisita(
            cliente_id=cliente.id,
            campana_id=campana_id,
            codigo_cliente=codigo,
            event_id=f"visit-{campana_id}-{codigo}",
            fecha_evento=datetime(2026, 1, 15, 10, 0, 0),
            estado_gestion="visitado_habido",
            nota_gestor="Promesa de pago",
            nivel_1="Contacto efectivo",
            gestor_nombre="Gestor Test",
        ))
        session.add(HistorialContacto(
            campana_id=campana_id,
            codigo_cliente=codigo,
            event_id=f"contact-{campana_id}-{codigo}",
            fecha_evento="2026-01-15T10:00:00",
            direccion_nueva="Av. Nueva 123",
            telefono_nuevo="999888777",
            usuario_nombre="Gestor Test",
        ))
        session.commit()
        return cliente.id


def test_purge_inactive_keeps_visit_and_contact_history(mgr):
    from services.database import (
        Campana, Cliente, HistorialVisita, HistorialContacto, EstadoCampana,
    )

    old_client_id = _seed_campaign(
        mgr, "camp_old", "Campaña Vieja", EstadoCampana.CERRADA.value, "C001",
    )
    active_client_id = _seed_campaign(
        mgr, "camp_active", "Campaña Activa", EstadoCampana.ACTIVA.value, "C002",
    )

    result = mgr.purge_inactive_campaigns()

    assert result["deleted_campaigns"] == 1
    assert "camp_old" in result["deleted_campaign_ids"]
    assert result["deleted_clients"] == 1

    with mgr.db.session() as session:
        assert session.get(Campana, "camp_old") is None
        assert session.get(Campana, "camp_active") is not None

        assert (
            session.query(Cliente).filter(Cliente.campana_id == "camp_old").count()
            == 0
        )
        assert session.get(Cliente, active_client_id) is not None

        # Visit history of purged campaign survives with cliente_id detached.
        old_visits = (
            session.query(HistorialVisita)
            .filter(HistorialVisita.campana_id == "camp_old")
            .all()
        )
        assert len(old_visits) == 1
        assert old_visits[0].cliente_id is None
        assert old_visits[0].codigo_cliente == "C001"
        assert old_visits[0].estado_gestion == "visitado_habido"
        assert old_visits[0].nota_gestor == "Promesa de pago"

        # Contact history preserved.
        old_contacts = (
            session.query(HistorialContacto)
            .filter(HistorialContacto.campana_id == "camp_old")
            .all()
        )
        assert len(old_contacts) == 1
        assert old_contacts[0].direccion_nueva == "Av. Nueva 123"

        # Active campaign history untouched.
        active_visits = (
            session.query(HistorialVisita)
            .filter(HistorialVisita.campana_id == "camp_active")
            .all()
        )
        assert len(active_visits) == 1
        assert active_visits[0].cliente_id == active_client_id


def test_delete_campaign_local_keeps_history(mgr):
    from services.database import HistorialVisita, HistorialContacto, EstadoCampana

    _seed_campaign(
        mgr, "camp_del", "A borrar", EstadoCampana.CERRADA.value, "C010",
    )
    mgr.delete_campaign_local("camp_del")

    with mgr.db.session() as session:
        visits = (
            session.query(HistorialVisita)
            .filter(HistorialVisita.campana_id == "camp_del")
            .all()
        )
        contacts = (
            session.query(HistorialContacto)
            .filter(HistorialContacto.campana_id == "camp_del")
            .all()
        )
        assert len(visits) == 1
        assert visits[0].cliente_id is None
        assert len(contacts) == 1


def test_delete_all_local_removes_history(mgr):
    from services.database import (
        HistorialVisita, HistorialContacto, Campana, EstadoCampana,
    )

    _seed_campaign(
        mgr, "camp_nuke", "Nuclear", EstadoCampana.ACTIVA.value, "C099",
    )
    mgr.delete_all_local_data()

    with mgr.db.session() as session:
        assert session.query(Campana).count() == 0
        assert session.query(HistorialVisita).count() == 0
        assert session.query(HistorialContacto).count() == 0


def test_schema_v20_cliente_id_nullable(mgr):
    """Fresh DB should be at schema v20 with nullable cliente_id."""
    from services.database import SchemaVersion, CURRENT_SCHEMA_VERSION

    with mgr.db.session() as session:
        sv = session.query(SchemaVersion).first()
        assert sv is not None
        assert sv.version == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION >= 20

        cols = {
            row[1]
            for row in session.connection()
            .exec_driver_sql("PRAGMA table_info(historial_visita)")
            .fetchall()
        }
        assert "cliente_id" in cols
        # notnull flag is index 3 in PRAGMA table_info
        info = {
            row[1]: row[3]
            for row in session.connection()
            .exec_driver_sql("PRAGMA table_info(historial_visita)")
            .fetchall()
        }
        assert info["cliente_id"] == 0  # nullable
