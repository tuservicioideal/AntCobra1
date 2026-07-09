"""Tests for upload_cartera_update — new gestor sections must use set(merge=True)."""
from __future__ import annotations

import os
import sys
import unittest
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

        with patch.object(svc, "_read_existing_visit_data", return_value={}):
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


if __name__ == "__main__":
    unittest.main()
