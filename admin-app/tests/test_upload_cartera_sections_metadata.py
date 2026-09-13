"""Partial CALL uploads must not overwrite campaign-wide metadata."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firebase_service import FirebaseService


def _make_client(code: str = "C001") -> dict:
    return {
        "codigo_cliente": code,
        "nombre_completo": "Cliente Call",
        "region": "01",
        "zona": "1211",
        "seccion": "A",
        "seccion_key": "_CALL_uid1",
        "importe_deuda_asignada": 100.0,
        "importe_deuda_pendiente": 50.0,
        "coordenada_x": 0.0,
        "coordenada_y": 0.0,
        "tramo_actual": 1,
        "fase_gestion": "call",
    }


class UploadCarteraSectionsMetadataTests(unittest.TestCase):
    def test_partial_upload_does_not_replace_campaign_index(self):
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

        with patch.object(svc, "_read_existing_visit_data", return_value={}), \
             patch.object(svc, "refresh_campaign_section_index") as refresh:
            result = svc.upload_cartera_sections(
                by_seccion={"_CALL_uid1": [_make_client()], "01_1211_H": [_make_client("X")]},
                campaign_id="cartera_activa",
                section_keys={"_CALL_uid1"},
            )

        self.assertTrue(result["success"])
        refresh.assert_called_once_with("cartera_activa")
        overwrite_sets = [
            c for c in campaign_ref.set.call_args_list if not c.kwargs.get("merge")
        ]
        self.assertEqual(
            overwrite_sets,
            [],
            "Partial CALL upload must not campaign_ref.set() without merge",
        )

    def test_call_seccion_guard_replaces_territorial_keys(self):
        svc = FirebaseService()
        svc._initialized = True
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = {
            "rol": "gestor",
            "canal": "call",
            "secciones": ["01_1211_A", "01_1211_B"],
        }
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = snap
        svc.db = mock_db

        out = svc._apply_call_seccion_guard("flor-uid", {"nombre": "Flor"})
        self.assertEqual(out["secciones"], ["_CALL_flor-uid"])
        self.assertEqual(out["region"], "")
        self.assertEqual(out["zona"], "")
        self.assertEqual(out["seccion"], "")

    def test_call_seccion_guard_skips_field_gestor(self):
        svc = FirebaseService()
        svc._initialized = True
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = {
            "rol": "gestor",
            "canal": "campo",
            "secciones": ["01_1211_H"],
        }
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = snap
        svc.db = mock_db

        out = svc._apply_call_seccion_guard("campo-uid", {"nombre": "José"})
        self.assertNotIn("secciones", out)


if __name__ == "__main__":
    unittest.main()
