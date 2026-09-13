"""Tests del motor fase_reparto (call/campo + arrastre DNI + slots)."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


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


def _cli(**kwargs):
    defaults = dict(
        codigo_cliente="X",
        numero_documento="",
        tramo_actual=1,
        fase_gestion="call",
        estado_gestion="pendiente",
        importe_deuda_pendiente=100.0,
        activo_en_cartera=True,
        region="01",
        zona="1211",
        seccion="H",
        call_gestor_uid="",
        call_gestor_nombre="",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_etapa1_unico_va_call():
    from services.fase_reparto import decide_fase_for_cliente, FASE_GESTION_CALL, MOTIVO_ETAPA1_CALL
    d = decide_fase_for_cliente(_cli(tramo_actual=1, importe_deuda_pendiente=50))
    assert d.fase == FASE_GESTION_CALL
    assert d.motivo == MOTIVO_ETAPA1_CALL
    assert d.call_pool == ("E1-1", "E1-2", "E1-3")


def test_etapa2_sobre_40_sin_habido_va_campo():
    from services.fase_reparto import (
        decide_fase_for_cliente, FASE_GESTION_CAMPO, MOTIVO_PASA_CAMPO_MONTO,
    )
    d = decide_fase_for_cliente(
        _cli(tramo_actual=2, importe_deuda_pendiente=41, estado_gestion="pendiente")
    )
    assert d.fase == FASE_GESTION_CAMPO
    assert d.motivo == MOTIVO_PASA_CAMPO_MONTO


def test_etapa2_igual_40_queda_call():
    from services.fase_reparto import (
        decide_fase_for_cliente, FASE_GESTION_CALL, MOTIVO_QUEDA_CALL_BAJO_MONTO,
    )
    d = decide_fase_for_cliente(
        _cli(tramo_actual=2, importe_deuda_pendiente=40, estado_gestion="pendiente")
    )
    assert d.fase == FASE_GESTION_CALL
    assert d.motivo == MOTIVO_QUEDA_CALL_BAJO_MONTO
    assert d.call_pool == ("E2-1", "E2-2")


def test_etapa2_habido_queda_call_aunque_saldo_alto():
    from services.fase_reparto import (
        decide_fase_for_cliente, FASE_GESTION_CALL, MOTIVO_QUEDA_CALL_HABIDO,
    )
    d = decide_fase_for_cliente(
        _cli(
            tramo_actual=2,
            importe_deuda_pendiente=100,
            estado_gestion="visitado_habido",
        )
    )
    assert d.fase == FASE_GESTION_CALL
    assert d.motivo == MOTIVO_QUEDA_CALL_HABIDO


def test_segunda_cuenta_sigue_ancla_campo():
    from services.fase_reparto import (
        decide_fase_for_cliente, FASE_GESTION_CAMPO, MOTIVO_SEGUNDA_CUENTA_CAMPO,
    )
    hermano = _cli(
        codigo_cliente="A1",
        numero_documento="12345678",
        tramo_actual=2,
        fase_gestion="campo",
        importe_deuda_pendiente=200,
        region="01", zona="1211", seccion="H",
    )
    nueva = _cli(
        codigo_cliente="A2",
        numero_documento="12345678",
        tramo_actual=1,
        fase_gestion="call",
        importe_deuda_pendiente=30,
    )
    d = decide_fase_for_cliente(
        nueva,
        dni_campo_index={"12345678": [hermano]},
        assignment_index={
            "01_1211_H": {
                "status": "assigned",
                "gestor_uid": "campo_uid",
                "gestor_nombre": "Gestor Campo",
            }
        },
    )
    assert d.fase == FASE_GESTION_CAMPO
    assert d.motivo == MOTIVO_SEGUNDA_CUENTA_CAMPO
    assert d.arrastre_dni is True
    assert d.gestor_ancla_uid == "campo_uid"


def test_batch_dos_cuentas_mismo_dni_mismo_ancla():
    from services.fase_reparto import (
        evaluate_fases_batch, FASE_GESTION_CAMPO, MOTIVO_PASA_CAMPO_MONTO,
    )
    a = _cli(
        codigo_cliente="B1", numero_documento="999",
        tramo_actual=2, fase_gestion="call",
        importe_deuda_pendiente=100, region="01", zona="1", seccion="A",
    )
    b = _cli(
        codigo_cliente="B2", numero_documento="999",
        tramo_actual=2, fase_gestion="call",
        importe_deuda_pendiente=80, region="02", zona="2", seccion="B",
    )
    idx = {
        "01_1_A": {"status": "assigned", "gestor_uid": "gA", "gestor_nombre": "A"},
        "02_2_B": {"status": "assigned", "gestor_uid": "gB", "gestor_nombre": "B"},
    }
    batch = evaluate_fases_batch([a, b], assignment_index=idx)
    decs = {d.codigo_cliente: d for d in batch.decisiones}
    assert decs["B1"].fase == FASE_GESTION_CAMPO
    assert decs["B2"].fase == FASE_GESTION_CAMPO
    # Unificados al ancla (mayor saldo → B1 → gA)
    assert decs["B1"].gestor_ancla_uid == decs["B2"].gestor_ancla_uid
    assert decs["B1"].gestor_ancla_uid == "gA"


def test_no_retorno_automatico_campo_a_call():
    from services.fase_reparto import (
        decide_fase_for_cliente, FASE_GESTION_CAMPO, MOTIVO_YA_EN_CAMPO,
    )
    d = decide_fase_for_cliente(
        _cli(
            tramo_actual=2,
            fase_gestion="campo",
            importe_deuda_pendiente=20,  # bajo umbral
            estado_gestion="pendiente",
        ),
        allow_return_to_call=False,
    )
    assert d.fase == FASE_GESTION_CAMPO
    assert d.motivo == MOTIVO_YA_EN_CAMPO


def test_dni_vacio_no_arrastre():
    from services.fase_reparto import decide_fase_for_cliente, FASE_GESTION_CALL
    d = decide_fase_for_cliente(
        _cli(numero_documento="", tramo_actual=1),
        dni_campo_index={"": [_cli(codigo_cliente="Z", fase_gestion="campo")]},
    )
    assert d.fase == FASE_GESTION_CALL


def test_saldo_bajo_no_lpt():
    from services.fase_reparto import is_call_eligible_for_lpt
    c = _cli(importe_deuda_pendiente=9.99, fase_gestion="call", tramo_actual=1)
    assert is_call_eligible_for_lpt(c) is False
    c2 = _cli(importe_deuda_pendiente=10.0, fase_gestion="call", tramo_actual=1)
    assert is_call_eligible_for_lpt(c2) is True


def test_call_codigos_por_tramo():
    from services.fase_reparto import call_codigos_for_tramo, validate_call_slots
    assert call_codigos_for_tramo(1) == ("E1-1", "E1-2", "E1-3")
    assert call_codigos_for_tramo(2) == ("E2-1", "E2-2")
    assert call_codigos_for_tramo(3) == ("E3-1",)
    errs = validate_call_slots([])
    assert any("Falta" in e for e in errs)


def test_slot_lpt_por_etapa_db():
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.call_center_service import distribute_tramo1, filter_call_gestores

    svc, tmp = fresh_db()
    gestores = [
        {
            "uid": "e1a", "nombre": "Op E1-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-1",
        },
        {
            "uid": "e1b", "nombre": "Op E1-2", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-2",
        },
        {
            "uid": "e2a", "nombre": "Op E2-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E2-1",
        },
    ]
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="T1",
            nombre_completo="Etapa1", tramo_actual=TramoEnum.TRAMO_1.value,
            fase_gestion=FASE_GESTION_CALL, activo_en_cartera=True,
            importe_deuda_pendiente=200.0, region="01", zona="1", seccion="A",
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="T2",
            nombre_completo="Etapa2", tramo_actual=TramoEnum.TRAMO_2.value,
            fase_gestion=FASE_GESTION_CALL, activo_en_cartera=True,
            importe_deuda_pendiente=30.0, region="01", zona="1", seccion="A",
        ))
        session.commit()

    with svc.session() as session:
        result = distribute_tramo1(
            session, "camp1", filter_call_gestores(gestores), only_unassigned=True,
        )
    assert result.cuentas_asignadas == 2
    with svc.session() as session:
        t1 = session.query(Cliente).filter_by(codigo_cliente="T1").one()
        t2 = session.query(Cliente).filter_by(codigo_cliente="T2").one()
        assert t1.call_gestor_uid in ("e1a", "e1b")
        assert t2.call_gestor_uid == "e2a"
    cleanup_db(svc, tmp)


def test_cambio_slot_al_avanzar_etapa():
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.call_center_service import distribute_tramo1, filter_call_gestores

    svc, tmp = fresh_db()
    gestores = [
        {
            "uid": "e1a", "nombre": "Op E1-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E1-1",
        },
        {
            "uid": "e2a", "nombre": "Op E2-1", "rol": "gestor",
            "canal": "call", "activo": True, "call_codigo": "E2-1",
        },
    ]
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        # Ya en etapa 2 pero aún con operador E1 (simula avance)
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="Cambio",
            nombre_completo="Cambio Slot",
            tramo_actual=TramoEnum.TRAMO_2.value,
            fase_gestion=FASE_GESTION_CALL,
            call_gestor_uid="e1a",
            call_gestor_nombre="Op E1-1",
            activo_en_cartera=True,
            importe_deuda_pendiente=25.0,
            region="01", zona="1", seccion="A",
        ))
        session.commit()

    with svc.session() as session:
        result = distribute_tramo1(
            session, "camp1", filter_call_gestores(gestores), only_unassigned=True,
        )
    assert result.cuentas_asignadas >= 1
    with svc.session() as session:
        c = session.query(Cliente).filter_by(codigo_cliente="Cambio").one()
        assert c.call_gestor_uid == "e2a"
    cleanup_db(svc, tmp)


def test_apply_fases_arrastre_en_campana():
    from services.database import (
        Campana, Cliente, EstadoCampana, TramoEnum,
        FASE_GESTION_CALL, FASE_GESTION_CAMPO,
    )
    from services.campaign_manager import CampaignManager

    svc, tmp = fresh_db()
    mgr = CampaignManager(svc)
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="PRIM",
            numero_documento="11112222",
            nombre_completo="Primera",
            tramo_actual=TramoEnum.TRAMO_2.value,
            fase_gestion=FASE_GESTION_CAMPO,
            activo_en_cartera=True,
            importe_deuda_pendiente=200.0,
            region="01", zona="1211", seccion="H",
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="SEG",
            numero_documento="11112222",
            nombre_completo="Segunda",
            tramo_actual=TramoEnum.TRAMO_1.value,
            fase_gestion=FASE_GESTION_CALL,
            call_gestor_uid="call_x",
            call_gestor_nombre="Call X",
            activo_en_cartera=True,
            importe_deuda_pendiente=15.0,
            region="01", zona="9999", seccion="Z",
        ))
        session.commit()

    out = mgr.apply_fases_reparto("camp1")
    assert out["cambios"] >= 1
    with svc.session() as session:
        seg = session.query(Cliente).filter_by(codigo_cliente="SEG").one()
        assert seg.fase_gestion == FASE_GESTION_CAMPO
        assert not seg.call_gestor_uid
    cleanup_db(svc, tmp)


def test_equidad_pool_etapa1_tres_operadoras():
    """9 cuentas E1 → 3/3/3 entre E1-1/E1-2/E1-3, sin fugas a E2/E3."""
    from collections import Counter
    from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL
    from services.call_center_service import distribute_tramo1, filter_call_gestores

    svc, tmp = fresh_db()
    gestores = [
        {"uid": f"e{i}", "nombre": f"Op {c}", "rol": "gestor",
         "canal": "call", "activo": True, "call_codigo": c}
        for i, c in enumerate(["E1-1", "E1-2", "E1-3", "E2-1", "E2-2", "E3-1"])
    ]
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        for i, m in enumerate([900, 800, 700, 600, 500, 400, 300, 200, 100]):
            session.add(Cliente(
                campana_id="camp1", codigo_cliente=f"E1-{i}",
                nombre_completo=f"C{i}", tramo_actual=TramoEnum.TRAMO_1.value,
                fase_gestion=FASE_GESTION_CALL, activo_en_cartera=True,
                importe_deuda_pendiente=float(m),
                region="01", zona="1", seccion="A",
            ))
        session.commit()

    with svc.session() as session:
        result = distribute_tramo1(
            session, "camp1", filter_call_gestores(gestores), only_unassigned=True,
        )
    assert result.cuentas_asignadas == 9
    with svc.session() as session:
        rows = session.query(Cliente).filter_by(campana_id="camp1").all()
        counts = Counter(c.call_gestor_uid for c in rows)
        assert counts["e0"] == 3 and counts["e1"] == 3 and counts["e2"] == 3
        assert not counts.get("e3") and not counts.get("e4") and not counts.get("e5")
        # LPT equilibra por monto: diferencia máxima entre operadoras < cuenta mayor
        montos = {}
        for c in rows:
            montos[c.call_gestor_uid] = montos.get(c.call_gestor_uid, 0) + float(
                c.importe_deuda_pendiente or 0
            )
        assert max(montos.values()) - min(montos.values()) < 900
    cleanup_db(svc, tmp)


def test_etapa_for_call_codigo_mapea_1_2_3():
    from services.fase_reparto import etapa_for_call_codigo
    assert [etapa_for_call_codigo(c) for c in ("E1-1", "E1-2", "E1-3")] == [1, 1, 1]
    assert [etapa_for_call_codigo(c) for c in ("E2-1", "E2-2")] == [2, 2]
    assert etapa_for_call_codigo("E3-1") == 3


if __name__ == "__main__":
    tests = [n for n, f in globals().items() if n.startswith("test_") and callable(f)]
    for name in tests:
        print(f"RUN {name}…")
        globals()[name]()
        print(f"OK  {name}")
    print(f"\n{len(tests)} tests passed")
