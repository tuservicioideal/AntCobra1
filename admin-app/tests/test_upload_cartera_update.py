"""Tests for upload_cartera_update — new gestor sections must use set(merge=True)."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.diff_engine import ChangeReport, SectionChanges
from services.firebase_service import FirebaseService


def _make_client(code: str = "C001") -> dict:
    return {
        "codigo_cliente": code,
        "nombre_completo": "Cliente Prueba",
        "region": "10",
        "zona": "2200",
        "seccion": "Z",
        "seccion_key": "10_2200_Z",
        "importe_deuda_asignada": 100.0,
        "importe_deuda_pendiente": 50.0,
        "coordenada_x": 0.0,
        "coordenada_y": 0.0,
    }


class UploadCarteraUpdateTests(unittest.TestCase):
    def test_uses_set_merge_for_new_gestor_section(self):
        """New section 10_2200_Z must not call gestor_ref.update (404 if doc missing)."""
        svc = FirebaseService()
        svc._initialized = True

        gestor_ref = MagicMock()
        gestor_ref.collection.return_value.document.return_value = MagicMock()
        campaign_ref = MagicMock()
        campaign_ref.collection.return_value.document.return_value = gestor_ref

        mock_db = MagicMock()
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_db.collection.return_value.document.return_value = campaign_ref
        svc.db = mock_db

        seccion_key = "10_2200_Z"
        client = _make_client()
        by_seccion = {seccion_key: [client]}
        report = ChangeReport(
            sections={
                seccion_key: SectionChanges(
                    seccion_key=seccion_key,
                    new_clients=[client],
                )
            }
        )

        with patch.object(svc, "_read_existing_visit_data", return_value={}), \
             patch.object(svc, "_claim_publisher_lock"), \
             patch.object(svc, "_release_publisher_lock"):
            result = svc.upload_cartera_update(
                by_seccion=by_seccion,
                change_report=report,
                campaign_id="cartera_activa",
                excel_by_seccion=by_seccion,
                ultimo_excel="nuevo.xlsx",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["errors"], [])
        gestor_ref.update.assert_not_called()
        gestor_ref.set.assert_called_once()
        args, kwargs = gestor_ref.set.call_args
        payload = args[0]
        self.assertTrue(kwargs.get("merge"))
        self.assertEqual(payload["seccion_key"], seccion_key)
        self.assertEqual(payload["seccion"], "Z")
        self.assertEqual(payload["region"], "10")
        self.assertEqual(payload["zona"], "2200")
        self.assertEqual(payload["num_clientes"], 1)
        self.assertEqual(payload["estado"], "pendiente")

        campaign_ref.update.assert_not_called()
        campaign_ref.set.assert_called_once()
        _, camp_kwargs = campaign_ref.set.call_args
        self.assertTrue(camp_kwargs.get("merge"))


class VisitSectionCacheTests(unittest.TestCase):
    def test_cross_section_lookup_reads_each_section_once(self):
        svc = FirebaseService()
        svc._initialized = True
        svc._clear_visit_section_cache()
        calls = []

        def fake_read(_campaign_ref, seccion):
            calls.append(seccion)
            return {
                "C001": {"estado_gestion": "visitado_habido", "fecha_gestion": "2026-09-01"},
                "C002": {"estado_gestion": "visitado_habido", "fecha_gestion": "2026-09-01"},
            }

        campaign_ref = MagicMock()
        with patch.object(svc, "_read_existing_visit_data", side_effect=fake_read):
            first = svc._read_visit_for_client_cross_sections(
                campaign_ref, "C001", ["10_2200_Z", "_CALL_u1"],
            )
            second = svc._read_visit_for_client_cross_sections(
                campaign_ref, "C002", ["10_2200_Z", "_CALL_u1"],
            )

        self.assertEqual(calls, ["10_2200_Z", "_CALL_u1"])
        self.assertEqual(first.get("estado_gestion"), "visitado_habido")
        self.assertEqual(second.get("estado_gestion"), "visitado_habido")

    def test_stale_lock_is_not_busy(self):
        now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        stale = {
            "estado": "publicando",
            "activo": "web",
            "since": now - timedelta(hours=2),
        }
        self.assertFalse(FirebaseService._publisher_lock_is_busy(stale, now=now))
        fresh = {
            "estado": "publicando",
            "activo": "web",
            "since": now - timedelta(minutes=5),
        }
        self.assertTrue(FirebaseService._publisher_lock_is_busy(fresh, now=now))


if __name__ == "__main__":
    unittest.main()
