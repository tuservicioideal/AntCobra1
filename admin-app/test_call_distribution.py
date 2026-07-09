"""Tests for call center distribution and history."""
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fresh_db():
    from services.database import DatabaseService
    tmp = tempfile.mktemp(suffix=".db")
    svc = DatabaseService(db_path=tmp)
    svc.initialize()
    return svc, tmp


def cleanup_db(svc, tmp):
    try:
        if svc.engine:
            svc.engine.dispose()
    except Exception:
        pass
    for path in (tmp, tmp + "-wal", tmp + "-shm"):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass


def test_historial_reparto_call_table():
    from sqlalchemy import inspect
    svc, tmp = fresh_db()
    insp = inspect(svc.engine)
    assert "historial_reparto_call" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("historial_reparto_call")}
    for col in ("tipo", "motivo", "detalle_json", "firebase_ok"):
        assert col in cols
    from services.database import SchemaVersion
    with svc.session() as session:
        sv = session.query(SchemaVersion).first()
        assert sv is not None
        assert sv.version >= 16
    cleanup_db(svc, tmp)


def test_distribute_tramo1_records_changes():
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.call_center_service import distribute_tramo1, filter_call_gestores

    svc, tmp = fresh_db()
    gestores = [
        {"uid": "call_a", "nombre": "Operador A", "rol": "gestor", "canal": "call", "activo": True},
        {"uid": "call_b", "nombre": "Operador B", "rol": "gestor", "canal": "call", "activo": True},
    ]
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
            total_clientes=2, total_secciones=1,
        ))
        for i, cod in enumerate(("C001", "C002"), start=1):
            session.add(Cliente(
                campana_id="camp1",
                codigo_cliente=cod,
                nombre_completo=f"Cliente {i}",
                tramo_actual=TramoEnum.TRAMO_1.value,
                fase_gestion=FASE_GESTION_CALL,
                activo_en_cartera=True,
                importe_deuda_pendiente=100.0 * i,
                region="01", zona="1211", seccion="H",
            ))
        session.commit()

    with svc.session() as session:
        result = distribute_tramo1(
            session, "camp1", filter_call_gestores(gestores), only_unassigned=True,
        )
    assert result.cuentas_asignadas == 2
    assert len(result.cambios) == 2
    assert result.tipo == "reparto_inicial"
    assert all(c.razon for c in result.cambios)
    cleanup_db(svc, tmp)


def test_build_call_sections_payload():
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.campaign_manager import CampaignManager
    from services.database import make_call_section_key

    svc, tmp = fresh_db()
    mgr = CampaignManager(svc)
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        session.add(Cliente(
            campana_id="camp1",
            codigo_cliente="C001",
            nombre_completo="Cliente",
            tramo_actual=TramoEnum.TRAMO_1.value,
            fase_gestion=FASE_GESTION_CALL,
            call_gestor_uid="uid_x",
            call_gestor_nombre="Op X",
            activo_en_cartera=True,
            importe_deuda_pendiente=500.0,
            region="01", zona="1211", seccion="H",
        ))
        session.commit()

    sec = make_call_section_key("uid_x")
    payload = mgr.build_call_sections_payload("camp1", {sec})
    assert sec in payload
    assert len(payload[sec]) == 1
    assert payload[sec][0].get("numero_documento") is not None or "codigo_cliente" in payload[sec][0]
    cleanup_db(svc, tmp)


if __name__ == "__main__":
    test_historial_reparto_call_table()
    print("OK historial table")
    test_distribute_tramo1_records_changes()
    print("OK distribute changes")
    test_build_call_sections_payload()
    print("OK payload sections")
    print("All call distribution tests passed.")
