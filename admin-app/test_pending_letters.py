from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.campaign_manager import CampaignManager
from services.database import Campana, CartaGenerada, Cliente, DatabaseService, EstadoCampana


def create_temp_db() -> tuple[DatabaseService, str]:
    path = tempfile.mktemp(suffix=".db")
    db = DatabaseService(db_path=path)
    db.initialize()
    return db, path


def cleanup_temp_db(db: DatabaseService, path: str) -> None:
    try:
        if db.engine:
            db.engine.dispose()
    except Exception:
        pass
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


class PendingLettersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db, self.db_path = create_temp_db()
        self.manager = CampaignManager(self.db)

    def tearDown(self) -> None:
        cleanup_temp_db(self.db, self.db_path)

    def _create_campaign(self, campaign_id: str, start_date: date) -> Campana:
        with self.db.session() as session:
            camp = Campana(
                id=campaign_id,
                nombre="Campaña test",
                fecha_inicio=start_date,
                fecha_fin=start_date + timedelta(days=59),
                estado=EstadoCampana.ACTIVA.value,
                archivo_origen="test.xlsx",
                total_clientes=0,
                total_secciones=0,
            )
            session.add(camp)
            session.commit()
            session.refresh(camp)
            return camp

    def _create_client(
        self,
        campana_id: str,
        codigo_cliente: str,
        saldo: float,
        *,
        tramo_actual: int = 1,
        region: str = "01",
        zona: str = "1001",
        seccion: str = "A",
    ) -> Cliente:
        with self.db.session() as session:
            client = Cliente(
                campana_id=campana_id,
                codigo_cliente=codigo_cliente,
                nombre_completo=f"Cliente {codigo_cliente}",
                region=region,
                zona=zona,
                seccion=seccion,
                tramo_actual=tramo_actual,
                importe_deuda_asignada=saldo,
                importe_deuda_pendiente=saldo,
            )
            session.add(client)
            camp = session.get(Campana, campana_id)
            if camp is not None:
                camp.total_clientes += 1
                camp.total_secciones = 1
            session.commit()
            session.refresh(client)
            return client

    def test_evaluate_tramos_keeps_letters_pending_until_publication(self) -> None:
        camp = self._create_campaign("camp_eval", date.today())
        self._create_client(camp.id, "C001", 120.0, tramo_actual=1)

        result = self.manager.evaluate_tramos(campana_id=camp.id, auto_apply=True)
        visibles = [c.numero_carta for c in result.cartas_pendientes if not c.omitida_por_monto]

        self.assertEqual(visibles, [1])
        with self.db.session() as session:
            recorded = (
                session.query(CartaGenerada)
                .filter(CartaGenerada.campana_id == camp.id)
                .count()
            )
        self.assertEqual(recorded, 0)

    def test_pending_letters_ignore_legacy_placeholder_rows(self) -> None:
        camp = self._create_campaign("camp_pending", date.today() - timedelta(days=9))
        ready = self._create_client(camp.id, "C001", 120.0, region="01", zona="1001", seccion="A")
        published = self._create_client(
            camp.id, "C002", 180.0, region="01", zona="1002", seccion="B"
        )
        omitted = self._create_client(camp.id, "C003", 20.0, region="01", zona="1003", seccion="C")

        with self.db.session() as session:
            session.add_all(
                [
                    CartaGenerada(
                        cliente_id=ready.id,
                        campana_id=camp.id,
                        numero_carta=2,
                        tramo=2,
                        estado_publicacion="pendiente",
                        omitida_por_monto=False,
                    ),
                    CartaGenerada(
                        cliente_id=published.id,
                        campana_id=camp.id,
                        numero_carta=2,
                        tramo=2,
                        estado_publicacion="publicada",
                        omitida_por_monto=False,
                    ),
                    CartaGenerada(
                        cliente_id=omitted.id,
                        campana_id=camp.id,
                        numero_carta=2,
                        tramo=2,
                        estado_publicacion="pendiente",
                        omitida_por_monto=True,
                    ),
                ]
            )
            session.commit()

        pending = self.manager.get_pending_letters(
            camp.id,
            numero_carta=2,
            tramo=2,
            include_omitted=True,
        )
        pending_codes = {row["codigo_cliente"] for row in pending}

        self.assertEqual(pending_codes, {"C001"})

    def test_distribution_counts_unique_clients_and_total_letters(self) -> None:
        camp = self._create_campaign("camp_distribution", date.today() - timedelta(days=9))
        self._create_client(camp.id, "C001", 120.0, region="01", zona="1001", seccion="A")

        gestores = [
            {
                "uid": "gestor-1",
                "nombre": "Gestor Uno",
                "email": "gestor1@test.local",
                "rol": "gestor",
                "activo": True,
                "secciones": ["01_1001_A"],
            }
        ]

        distribution = self.manager.build_pending_letter_distribution(
            camp.id,
            gestores,
            numero_carta=None,
            tramo=None,
        )

        summary = distribution["summary"]
        self.assertEqual(summary["total_clientes"], 1)
        self.assertEqual(summary["total_cartas"], 2)
        self.assertEqual(summary["cartas"], [1, 2])
        self.assertEqual(summary["total_gestores"], 1)
        gestor = distribution["by_gestor"]["gestor-1"]
        self.assertEqual(gestor["total_clientes"], 1)
        self.assertEqual(gestor["total_cartas"], 2)

    def test_publish_pending_letters_all_cards_aggregates_results(self) -> None:
        class FakeFirebase:
            def __init__(self) -> None:
                self._initialized = True
                self.notifications: list[dict] = []

            def notify_letters_published(self, **kwargs):
                self.notifications.append(kwargs)
                return {"sent": 2, "errors": []}

        firebase = FakeFirebase()
        overall_distribution = {
            "pending": [
                {"cliente_id": 1, "numero_carta": 1, "seccion_key": "01_1001_A", "tramo": 1},
                {"cliente_id": 2, "numero_carta": 3, "seccion_key": "01_1001_A", "tramo": 2},
            ],
            "by_gestor": {
                "gestor-1": {
                    "gestor_uid": "gestor-1",
                    "items": [],
                    "secciones": {"01_1001_A": []},
                    "total_clientes": 2,
                    "total_cartas": 2,
                }
            },
            "summary": {
                "tramo": None,
                "numero_carta": None,
                "cartas": [1, 3],
                "tramos": [1, 2],
                "total_clientes": 2,
                "total_cartas": 2,
                "total_secciones": 1,
                "total_gestores": 1,
                "secciones_sin_gestor": 0,
                "secciones_en_conflicto": 0,
            },
        }

        partial_results = [
            {
                "distribution": {"summary": {"numero_carta": 1}},
                "output_dir": "out1",
                "zip_path": "zip1",
                "files": ["a.pdf"],
                "entries": [{"path": "a.pdf"}],
                "total_letters": 1,
                "total_files": 1,
                "published_count": 1,
                "uploaded_files_count": 1,
                "used_word_template": False,
                "errors": [],
            },
            {
                "distribution": {"summary": {"numero_carta": 3}},
                "output_dir": "out3",
                "zip_path": "zip3",
                "files": ["b.pdf"],
                "entries": [{"path": "b.pdf"}],
                "total_letters": 1,
                "total_files": 1,
                "published_count": 1,
                "uploaded_files_count": 1,
                "used_word_template": True,
                "errors": ["minor"],
            },
        ]

        with patch.object(
            self.manager,
            "build_pending_letter_distribution",
            return_value=overall_distribution,
        ), patch.object(
            self.manager,
            "_publish_pending_letters_single",
            side_effect=partial_results,
        ) as publish_single:
            result = self.manager.publish_pending_letters(
                firebase,
                "camp-test",
                [],
                numero_carta=None,
                tramo=None,
                published_by={"uid": "admin-1", "nombre": "Admin"},
            )

        self.assertEqual(publish_single.call_count, 2)
        self.assertEqual(result["published_cards"], [1, 3])
        self.assertEqual(result["total_letters"], 2)
        self.assertEqual(result["published_count"], 2)
        self.assertEqual(result["uploaded_files_count"], 2)
        self.assertEqual(result["output_dirs"], ["out1", "out3"])
        self.assertEqual(result["zip_paths"], ["zip1", "zip3"])
        self.assertEqual(result["notifications_sent"], 2)
        self.assertIn("minor", result["errors"])
        self.assertEqual(len(firebase.notifications), 1)


if __name__ == "__main__":
    unittest.main()
