"""Tests para timelines de campaña banco."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.campana_banco_utils import (
    compute_detected_dates_for_group,
    effective_campana_banco_dates,
)
from services.database import (
    DatabaseService,
    Campana,
    Cliente,
    CampanaBancoMeta,
    EstadoCampana,
)
from services.campaign_manager import CampaignManager


class TestCampanaBancoTimelineUtils(unittest.TestCase):
    def test_compute_detected_dates_min_max(self):
        fa1 = date(2026, 1, 10)
        fa2 = date(2026, 1, 15)
        fc1 = date(2026, 3, 10)
        fc2 = date(2026, 3, 20)
        inicio, fin = compute_detected_dates_for_group(
            [fa1, fa2], [fc1, fc2], 59
        )
        self.assertEqual(inicio, fa1)
        self.assertEqual(fin, fc2)

    def test_compute_detected_dates_fallback_fin(self):
        fa = date(2026, 2, 1)
        inicio, fin = compute_detected_dates_for_group([fa], [], 59)
        self.assertEqual(inicio, fa)
        self.assertEqual(fin, fa + timedelta(days=58))

    def test_effective_dates_manual_override(self):
        today = date(2026, 2, 15)
        eff = effective_campana_banco_dates(
            fecha_inicio_manual=date(2026, 2, 1),
            fecha_fin_manual=date(2026, 3, 31),
            fecha_inicio_detectada=date(2026, 1, 1),
            fecha_fin_detectada=date(2026, 2, 28),
            duracion_dias=59,
            today=today,
        )
        self.assertTrue(eff["es_manual"])
        self.assertEqual(eff["fecha_inicio"], date(2026, 2, 1))
        self.assertEqual(eff["dia_actual"], 15)
        self.assertEqual(eff["duracion"], 59)

    def test_effective_dates_uses_detected_when_no_manual(self):
        today = date(2026, 1, 5)
        eff = effective_campana_banco_dates(
            fecha_inicio_manual=None,
            fecha_fin_manual=None,
            fecha_inicio_detectada=date(2026, 1, 1),
            fecha_fin_detectada=date(2026, 2, 28),
            duracion_dias=59,
            today=today,
        )
        self.assertFalse(eff["es_manual"])
        self.assertEqual(eff["dia_actual"], 5)


class TestCampanaBancoTimelineService(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test_timeline.db")
        self.db = DatabaseService(self.db_path)
        self.db.initialize()
        self.mgr = CampaignManager(self.db)
        self.campana_id = "test_camp_timeline"
        today = date.today()
        with self.db.session() as session:
            session.add(
                Campana(
                    id=self.campana_id,
                    nombre="Test",
                    fecha_inicio=today,
                    fecha_fin=today + timedelta(days=59),
                    estado=EstadoCampana.ACTIVA.value,
                )
            )
            session.add(
                Cliente(
                    campana_id=self.campana_id,
                    codigo_cliente="CB-001",
                    campana_banco="202516",
                    fecha_asignacion_dt=today - timedelta(days=4),
                    fecha_cierre_dt=today + timedelta(days=55),
                    activo_en_cartera=True,
                    importe_deuda_asignada=100.0,
                    seccion_key="01_1211_H",
                )
            )
            session.add(
                Cliente(
                    campana_id=self.campana_id,
                    codigo_cliente="CB-002",
                    campana_banco="202610",
                    fecha_asignacion_dt=today - timedelta(days=10),
                    fecha_cierre_dt=today + timedelta(days=49),
                    activo_en_cartera=True,
                    importe_deuda_asignada=200.0,
                    seccion_key="01_1211_A",
                )
            )
            session.commit()

    def tearDown(self):
        if self.db.engine:
            self.db.engine.dispose()

    def test_sync_creates_meta_rows(self):
        self.mgr.sync_campana_banco_meta(self.campana_id)
        with self.db.session() as session:
            rows = (
                session.query(CampanaBancoMeta)
                .filter(CampanaBancoMeta.campana_id == self.campana_id)
                .all()
            )
        self.assertEqual(len(rows), 2)
        keys = {r.campana_banco_key for r in rows}
        self.assertEqual(keys, {"202516", "202610"})

    def test_get_timelines_two_campaigns(self):
        self.mgr.sync_campana_banco_meta(self.campana_id)
        timelines = self.mgr.get_campana_banco_timelines(self.campana_id)
        self.assertEqual(len(timelines), 2)
        by_key = {t["key"]: t for t in timelines}
        self.assertEqual(by_key["202516"]["dia_actual"], 5)
        self.assertEqual(by_key["202610"]["dia_actual"], 11)

    def test_update_manual_dates(self):
        self.mgr.sync_campana_banco_meta(self.campana_id)
        inicio = date(2026, 1, 1)
        fin = date(2026, 2, 28)
        self.mgr.update_campana_banco_dates(
            self.campana_id, "202516",
            fecha_inicio=inicio, fecha_fin=fin,
        )
        timelines = self.mgr.get_campana_banco_timelines(self.campana_id)
        t = next(x for x in timelines if x["key"] == "202516")
        self.assertTrue(t["es_manual"])
        self.assertEqual(t["fecha_inicio"], inicio)
        self.assertEqual(t["fecha_fin"], fin)

    def test_restore_detected(self):
        self.mgr.sync_campana_banco_meta(self.campana_id)
        self.mgr.update_campana_banco_dates(
            self.campana_id, "202516",
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 12, 31),
        )
        self.mgr.update_campana_banco_dates(
            self.campana_id, "202516", restore_detected=True,
        )
        with self.db.session() as session:
            meta = (
                session.query(CampanaBancoMeta)
                .filter(
                    CampanaBancoMeta.campana_id == self.campana_id,
                    CampanaBancoMeta.campana_banco_key == "202516",
                )
                .first()
            )
        self.assertIsNone(meta.fecha_inicio)
        self.assertIsNone(meta.fecha_fin)


if __name__ == "__main__":
    unittest.main()
