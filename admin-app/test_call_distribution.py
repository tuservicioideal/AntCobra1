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


def _call_gestores_r6():
    return [
        {
            "uid": "g_r6", "nombre": "Gestora R6", "rol": "gestor",
            "canal": "call", "activo": True, "call_reparto_rol": "r6",
        },
        {
            "uid": "g_e2", "nombre": "Gestora E2", "rol": "gestor",
            "canal": "call", "activo": True, "call_reparto_rol": "r6_etapa2",
        },
        {
            "uid": "g_a", "nombre": "Gestora A", "rol": "gestor",
            "canal": "call", "activo": True, "call_reparto_rol": "general",
        },
        {
            "uid": "g_b", "nombre": "Gestora B", "rol": "gestor",
            "canal": "call", "activo": True, "call_reparto_rol": "general",
        },
    ]


def test_region_and_etapa_classifiers():
    from types import SimpleNamespace
    from services.call_center_service import (
        is_region_6, is_etapa_2, classify_call_bucket,
        CALL_ROL_R6, CALL_ROL_R6_ETAPA2, CALL_ROL_GENERAL,
    )

    assert is_region_6("06")
    assert is_region_6("6")
    assert is_region_6("R6")
    assert is_region_6("Región 6")
    assert not is_region_6("01")
    assert not is_region_6("")

    c_e2 = SimpleNamespace(tramo_actual=2, etapa_deuda="")
    c_e2_label = SimpleNamespace(tramo_actual=1, etapa_deuda="ETAPA 2")
    c_e1 = SimpleNamespace(tramo_actual=1, etapa_deuda="TEMPRANA")
    assert is_etapa_2(c_e2)
    assert is_etapa_2(c_e2_label)
    assert not is_etapa_2(c_e1)

    r6 = SimpleNamespace(region="06", tramo_actual=1, etapa_deuda="")
    r6e2 = SimpleNamespace(region="R6", tramo_actual=2, etapa_deuda="")
    other = SimpleNamespace(region="01", tramo_actual=1, etapa_deuda="")
    assert classify_call_bucket(r6) == CALL_ROL_R6
    assert classify_call_bucket(r6e2) == CALL_ROL_R6_ETAPA2
    assert classify_call_bucket(other) == CALL_ROL_GENERAL


def _call_gestores_slots():
    return [
        {
            "uid": "e1_1", "nombre": "Op E1-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-1",
        },
        {
            "uid": "e1_2", "nombre": "Op E1-2", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-2",
        },
        {
            "uid": "e1_3", "nombre": "Op E1-3", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-3",
        },
        {
            "uid": "e2_1", "nombre": "Op E2-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E2-1",
        },
        {
            "uid": "e2_2", "nombre": "Op E2-2", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E2-2",
        },
        {
            "uid": "e3_1", "nombre": "Op E3-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E3-1",
        },
    ]


def test_distribute_by_stage_slots():
    """Con call_codigo, R6 ya no es bucket: todo etapa 1 va a E1-*."""
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.call_center_service import distribute_tramo1, filter_call_gestores

    svc, tmp = fresh_db()
    gestores = _call_gestores_slots()
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
            total_clientes=6, total_secciones=1,
        ))
        rows = [
            ("R6A", "06", 1, 150),
            ("R6B", "6", 1, 140),
            ("X1", "01", 1, 130),
            ("X2", "02", 1, 120),
            ("E2LOW", "01", 2, 30),
            ("E3LOW", "01", 3, 25),
        ]
        for i, (cod, region, tramo, monto) in enumerate(rows, start=1):
            session.add(Cliente(
                campana_id="camp1",
                codigo_cliente=cod,
                nombre_completo=f"Cliente {cod}",
                tramo_actual=tramo,
                fase_gestion=FASE_GESTION_CALL,
                activo_en_cartera=True,
                importe_deuda_pendiente=float(monto),
                region=region, zona="1211", seccion="H",
            ))
        session.commit()

    with svc.session() as session:
        result = distribute_tramo1(
            session, "camp1", filter_call_gestores(gestores), only_unassigned=True,
        )
    assert result.cuentas_asignadas == 6
    assert result.bucket_counts.get("E1") == 4
    assert result.bucket_counts.get("E2") == 1
    assert result.bucket_counts.get("E3") == 1

    e1_uids = {"e1_1", "e1_2", "e1_3"}
    with svc.session() as session:
        by_code = {
            c.codigo_cliente: c.call_gestor_uid
            for c in session.query(Cliente).filter(Cliente.campana_id == "camp1")
        }
    assert by_code["R6A"] in e1_uids
    assert by_code["R6B"] in e1_uids
    assert by_code["X1"] in e1_uids
    assert by_code["X2"] in e1_uids
    assert by_code["E2LOW"] in {"e2_1", "e2_2"}
    assert by_code["E3LOW"] == "e3_1"
    cleanup_db(svc, tmp)


if __name__ == "__main__":
    test_historial_reparto_call_table()
    print("OK historial table")
    test_distribute_tramo1_records_changes()
    print("OK distribute changes")
    test_build_call_sections_payload()
    print("OK payload sections")
    test_region_and_etapa_classifiers()
    print("OK classifiers")
    test_distribute_by_stage_slots()
    print("OK stage slots")
    print("All call distribution tests passed.")
