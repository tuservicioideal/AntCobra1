"""Regresión: arrastre DNI saca de _CALL_ y agrupa en sección ancla."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta

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


def test_payload_arrastre_misma_seccion_ancla():
    from services.database import (
        Campana, Cliente, EstadoCampana, TramoEnum,
        FASE_GESTION_CALL, FASE_GESTION_CAMPO, make_call_section_key,
    )
    from services.campaign_manager import CampaignManager
    from services.call_center_service import get_effective_firestore_section

    svc, tmp = fresh_db()
    mgr = CampaignManager(svc)
    with svc.session() as session:
        today = date.today()
        session.add(Campana(
            id="camp1", nombre="Test", estado=EstadoCampana.ACTIVA.value,
            fecha_inicio=today, fecha_fin=today + timedelta(days=60),
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="ANCLA",
            numero_documento="55556666",
            nombre_completo="Ancla Campo",
            tramo_actual=TramoEnum.TRAMO_2.value,
            fase_gestion=FASE_GESTION_CAMPO,
            activo_en_cartera=True,
            importe_deuda_pendiente=250.0,
            region="01", zona="1211", seccion="H",
        ))
        session.add(Cliente(
            campana_id="camp1", codigo_cliente="HERMANA",
            numero_documento="55556666",
            nombre_completo="Hermana Call",
            tramo_actual=TramoEnum.TRAMO_1.value,
            fase_gestion=FASE_GESTION_CALL,
            call_gestor_uid="call_uid_1",
            call_gestor_nombre="Operador",
            activo_en_cartera=True,
            importe_deuda_pendiente=20.0,
            region="02", zona="9999", seccion="Z",
        ))
        session.commit()

    # Antes del arrastre: hermana vive en _CALL_
    with svc.session() as session:
        hermana = session.query(Cliente).filter_by(codigo_cliente="HERMANA").one()
        assert get_effective_firestore_section(hermana) == make_call_section_key("call_uid_1")

    out = mgr.apply_fases_reparto("camp1")
    assert out["cambios"] >= 1
    assert any(p.codigo_cliente == "HERMANA" for p in out["pasos_a_campo"])

    with svc.session() as session:
        hermana = session.query(Cliente).filter_by(codigo_cliente="HERMANA").one()
        assert hermana.fase_gestion == FASE_GESTION_CAMPO
        assert not hermana.call_gestor_uid
        # Ya no es sección call
        assert not get_effective_firestore_section(hermana).startswith("_CALL_")

    payload = mgr.get_firebase_payload("camp1")
    by_sec = payload["by_seccion"]
    # Ambas deben estar bajo 01_1211_H (ancla), no bajo 02_9999_Z
    assert "01_1211_H" in by_sec
    codes_in_ancla = {c["codigo_cliente"] for c in by_sec["01_1211_H"]}
    assert "ANCLA" in codes_in_ancla
    assert "HERMANA" in codes_in_ancla
    # No debe quedar en call ni en su territorio propio
    assert make_call_section_key("call_uid_1") not in by_sec or not any(
        c["codigo_cliente"] == "HERMANA"
        for c in by_sec.get(make_call_section_key("call_uid_1"), [])
    )
    if "02_9999_Z" in by_sec:
        assert "HERMANA" not in {c["codigo_cliente"] for c in by_sec["02_9999_Z"]}

    hermana_dict = next(
        c for c in by_sec["01_1211_H"] if c["codigo_cliente"] == "HERMANA"
    )
    assert hermana_dict.get("arrastre_dni") is True
    assert hermana_dict.get("seccion_key_origen") == "02_9999_Z"
    cleanup_db(svc, tmp)


if __name__ == "__main__":
    test_payload_arrastre_misma_seccion_ancla()
    print("OK arrastre payload")
