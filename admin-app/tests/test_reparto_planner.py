"""Tests for reparto_planner — afinidad cliente-asesor."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def _gestores_campo_call():
    return [
        {
            "uid": "campo_1",
            "nombre": "Gestor Campo",
            "rol": "gestor",
            "activo": True,
            "secciones": ["01_1211_H"],
        },
        {
            "uid": "call_a",
            "nombre": "Operador A",
            "rol": "gestor",
            "canal": "call",
            "activo": True,
        },
        {
            "uid": "call_b",
            "nombre": "Operador B",
            "rol": "gestor",
            "canal": "call",
            "activo": True,
        },
        {
            "uid": "call_inactivo",
            "nombre": "Operador Inactivo",
            "rol": "gestor",
            "canal": "call",
            "activo": False,
        },
    ]


class RepartoPlannerTests(unittest.TestCase):
    def _seed_campaign(self, svc, clientes_extra=None):
        from services.database import Campana, Cliente, EstadoCampana, TramoEnum, FASE_GESTION_CALL

        today = date.today()
        with svc.session() as session:
            session.add(Campana(
                id="camp1",
                nombre="Test",
                estado=EstadoCampana.ACTIVA.value,
                fecha_inicio=today,
                fecha_fin=today + timedelta(days=60),
                total_clientes=1,
                total_secciones=1,
            ))
            base = dict(
                campana_id="camp1",
                tramo_actual=TramoEnum.TRAMO_1.value,
                fase_gestion=FASE_GESTION_CALL,
                activo_en_cartera=True,
                importe_deuda_pendiente=100.0,
                region="01",
                zona="1211",
                seccion="H",
            )
            if clientes_extra:
                for kw in clientes_extra:
                    session.add(Cliente(**{**base, **kw}))
            else:
                session.add(Cliente(**base))
            session.commit()

    def test_mantiene_call_gestor(self):
        from services.reparto_planner import build_reparto_plan, MANTIENE

        svc, tmp = fresh_db()
        self._seed_campaign(svc, [{
            "codigo_cliente": "C001",
            "nombre_completo": "Cliente Mantiene",
            "call_gestor_uid": "call_a",
            "call_gestor_nombre": "Operador A",
        }])
        with svc.session() as session:
            plan = build_reparto_plan(session, "camp1", _gestores_campo_call())
        row = next(c for c in plan.clientes if c.codigo_cliente == "C001")
        self.assertEqual(row.estado_afinidad, MANTIENE)
        self.assertEqual(row.call_gestor_uid, "call_a")
        cleanup_db(svc, tmp)

    def test_nuevo_sin_uid(self):
        from services.reparto_planner import build_reparto_plan, NUEVO

        svc, tmp = fresh_db()
        self._seed_campaign(svc, [{
            "codigo_cliente": "C002",
            "nombre_completo": "Cliente Nuevo",
            "call_gestor_uid": None,
        }])
        with svc.session() as session:
            plan = build_reparto_plan(session, "camp1", _gestores_campo_call())
        row = next(c for c in plan.clientes if c.codigo_cliente == "C002")
        self.assertEqual(row.estado_afinidad, NUEVO)
        self.assertIn(row.call_gestor_uid, ("call_a", "call_b"))
        cleanup_db(svc, tmp)

    def test_reasignado_huerfano(self):
        from services.reparto_planner import build_reparto_plan, REASIGNADO_HUERFANO

        svc, tmp = fresh_db()
        self._seed_campaign(svc, [{
            "codigo_cliente": "C003",
            "nombre_completo": "Cliente Huérfano",
            "call_gestor_uid": "call_inactivo",
            "call_gestor_nombre": "Operador Inactivo",
        }])
        with svc.session() as session:
            plan = build_reparto_plan(session, "camp1", _gestores_campo_call())
        row = next(c for c in plan.clientes if c.codigo_cliente == "C003")
        self.assertEqual(row.estado_afinidad, REASIGNADO_HUERFANO)
        self.assertIn(row.call_gestor_uid, ("call_a", "call_b"))
        self.assertNotEqual(row.call_gestor_uid, "call_inactivo")
        cleanup_db(svc, tmp)

    def test_afinidad_rota_campo(self):
        from services.reparto_planner import build_reparto_plan, AFINIDAD_ROTA_CAMPO

        svc, tmp = fresh_db()
        self._seed_campaign(svc, [{
            "codigo_cliente": "C004",
            "nombre_completo": "Cliente Sección Nueva",
            "call_gestor_uid": "call_a",
            "region": "02",
            "zona": "2200",
            "seccion": "Z",
        }])
        prev = {"C004": "01_1211_H"}
        with svc.session() as session:
            plan = build_reparto_plan(
                session, "camp1", _gestores_campo_call(),
                seccion_keys_anteriores=prev,
            )
        row = next(c for c in plan.clientes if c.codigo_cliente == "C004")
        self.assertEqual(row.estado_afinidad, AFINIDAD_ROTA_CAMPO)
        self.assertEqual(row.seccion_key, "02_2200_Z")
        cleanup_db(svc, tmp)

    def test_sin_gestor_campo(self):
        from services.reparto_planner import build_reparto_plan, SIN_GESTOR_CAMPO

        svc, tmp = fresh_db()
        self._seed_campaign(svc, [{
            "codigo_cliente": "C005",
            "nombre_completo": "Sin Gestor",
            "region": "99",
            "zona": "9999",
            "seccion": "X",
        }])
        with svc.session() as session:
            plan = build_reparto_plan(session, "camp1", _gestores_campo_call())
        row = next(c for c in plan.clientes if c.codigo_cliente == "C005")
        self.assertEqual(row.estado_afinidad, SIN_GESTOR_CAMPO)
        self.assertIn("99_9999_X", plan.sin_gestor_campo)
        cleanup_db(svc, tmp)


if __name__ == "__main__":
    unittest.main()
