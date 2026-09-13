from datetime import datetime, timezone, timedelta

from cartera.authz import CarteraAuthError, assert_can_manage_cartera
from cartera.client_lookup import campaign_section_keys
from cartera.config import MOTIVO_BAJA_EXCEL_BANCO
from cartera.diff_engine import compare_cartera
from cartera.preview import build_preview, index_section_gestores
from cartera.publisher import plan_and_apply, read_current_cartera
from cartera.publisher_lock import lock_is_busy
from cartera.store import InMemoryStore
from cartera.parsed_blob import dumps_parsed, loads_parsed
from cartera.excel_parser import parse_excel
from cartera.notifications import build_notifications
from cartera.visit_merge import reindex_cartera_for_diff

from excel_fixtures import client_row, workbook_bytes


class CountingStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.gets = 0
        self.list_children_calls = 0

    def get(self, *parts):
        self.gets += 1
        return super().get(*parts)

    def list_children(self, *parts):
        self.list_children_calls += 1
        return super().list_children(*parts)



def test_authz_rejects_gestor():
    try:
        assert_can_manage_cartera({"uid": "u1"}, {"rol": "gestor", "activo": True})
        assert False
    except CarteraAuthError as exc:
        assert exc.code == "permission-denied"


def test_authz_allows_supervisor():
    uid = assert_can_manage_cartera(
        {"uid": "u1"}, {"rol": "supervisor", "activo": True}
    )
    assert uid == "u1"


def test_publish_preserves_visit_and_archives_removed():
    store = InMemoryStore()
    first = parse_excel(
        workbook_bytes(
            [
                client_row(codigo="CTEST001", seccion="H", deuda=320),
                client_row(codigo="CTEST002", seccion="H", deuda=180),
            ]
        )
    )
    empty_old = {}
    report1 = compare_cartera(empty_old, first["by_seccion"])
    plan_and_apply(store, by_seccion=first["by_seccion"], change_report=report1)

    store.set(
        "campañas",
        "cartera_activa",
        "gestores",
        "01_1211_H",
        "clientes",
        "CTEST001",
        data={
            **store.get(
                "campañas",
                "cartera_activa",
                "gestores",
                "01_1211_H",
                "clientes",
                "CTEST001",
            ),
            "estado_gestion": "visitado_habido",
            "gps_latitud": -12.05,
            "nota_gestor": "Puerta negra",
        },
        merge=True,
    )

    second = parse_excel(
        workbook_bytes(
            [
                client_row(codigo="CTEST002", seccion="H", deuda=95.5, pendiente=95.5),
            ]
        )
    )
    old = reindex_cartera_for_diff(read_current_cartera(store))
    report2 = compare_cartera(old, second["by_seccion"])
    assert report2.total_removed == 1
    result = plan_and_apply(
        store,
        by_seccion=second["by_seccion"],
        change_report=report2,
        ultimo_excel="02.xlsx",
    )
    archived = store.get(
        "campañas",
        "cartera_activa",
        "gestores",
        "01_1211_H",
        "clientes",
        "CTEST001",
    )
    assert archived["activo_en_cartera"] is False
    assert archived["motivo_baja"] == MOTIVO_BAJA_EXCEL_BANCO
    assert archived["estado_gestion"] == "visitado_habido"
    assert archived["gps_latitud"] == -12.05
    assert result["archived_clients"] == 1

    updated = store.get(
        "campañas",
        "cartera_activa",
        "gestores",
        "01_1211_H",
        "clientes",
        "CTEST002",
    )
    assert updated["importe_deuda_pendiente"] == 95.5
    assert updated["activo_en_cartera"] is True

    catalog = store.get("estructura_territorial", "catalogo")
    assert "01" in catalog["regiones"]


def test_new_section_uses_merge_on_gestor_doc():
    store = InMemoryStore()
    parsed = parse_excel(
        workbook_bytes([client_row(codigo="N1", region="10", zona="2200", seccion="Z")])
    )
    report = compare_cartera({}, parsed["by_seccion"])
    plan_and_apply(store, by_seccion=parsed["by_seccion"], change_report=report)
    gestor = store.get("campañas", "cartera_activa", "gestores", "10_2200_Z")
    assert gestor["seccion"] == "Z"
    assert gestor["num_clientes"] == 1
    campaign = store.get("campañas", "cartera_activa")
    assert campaign["estado"] == "distribuida"
    assert "10_2200_Z" in campaign["secciones"]


def test_preview_lists_sections_without_gestor():
    parsed = parse_excel(
        workbook_bytes(
            [
                client_row(codigo="A", seccion="H"),
                client_row(codigo="B", seccion="A"),
            ]
        )
    )
    report = compare_cartera({}, parsed["by_seccion"])
    preview = build_preview(
        parse_result=parsed,
        change_report=report,
        usuarios=[
            {
                "uid": "g1",
                "nombre": "Gestor H",
                "activo": True,
                "secciones": ["01_1211_H"],
            }
        ],
        modo="inicial",
        archivo_nombre="a.xlsx",
    )
    assert preview["secciones_sin_gestor"] == ["01_1211_A"]
    assert preview["diff"]["nuevos"] == 2


def test_index_conflict_when_two_gestores_claim_section():
    index = index_section_gestores(
        [
            {"uid": "a", "nombre": "A", "activo": True, "secciones": ["01_1211_H"]},
            {"uid": "b", "nombre": "B", "activo": True, "secciones": ["01_1211_H"]},
        ]
    )
    assert index["01_1211_H"]["conflict"] == "1"


def test_notifications_skip_empty_destinatario():
    parsed = parse_excel(workbook_bytes([client_row(codigo="A", seccion="H")]))
    report = compare_cartera({}, parsed["by_seccion"])
    payload = build_notifications(
        change_report=report,
        usuarios=[],
        campaign_id="cartera_activa",
    )
    assert payload["gestor"] == []
    assert payload["alertas"][0]["tipo"] == "seccion_sin_gestor"


def test_parsed_blob_roundtrip():
    parsed = parse_excel(workbook_bytes([client_row(codigo="A")]))
    raw = dumps_parsed(parsed)
    loaded = loads_parsed(raw)
    assert "A" == loaded["by_seccion"]["01_1211_H"][0]["codigo_cliente"]


def test_publish_does_not_get_per_section_when_cartera_is_in_memory():
    store = CountingStore()
    for i in range(40):
        store.set(
            "campañas",
            "cartera_activa",
            "gestores",
            f"99_9900_{i:02d}",
            data={"num_clientes": 0},
            merge=True,
        )
    call_sec = "_CALL_uidCall1"
    store.set(
        "campañas",
        "cartera_activa",
        "gestores",
        call_sec,
        "clientes",
        "CTEST001",
        data={
            "codigo_cliente": "CTEST001",
            "seccion_key": "01_1211_H",
            "estado_gestion": "visitado_habido",
            "nota_gestor": "Puerta negra",
            "activo_en_cartera": True,
        },
        merge=False,
    )
    parsed = parse_excel(
        workbook_bytes([client_row(codigo="CTEST001", seccion="H", deuda=99)])
    )
    old = read_current_cartera(store)
    report = compare_cartera(reindex_cartera_for_diff(old), parsed["by_seccion"])
    store.gets = 0
    store.list_children_calls = 0
    plan_and_apply(
        store,
        by_seccion=parsed["by_seccion"],
        change_report=report,
        existing_cartera=old,
    )
    assert store.gets == 0
    assert store.list_children_calls == 0
    campaign = store.get("campañas", "cartera_activa")
    assert call_sec in campaign["secciones"]
    written = store.get(
        "campañas", "cartera_activa", "gestores", call_sec, "clientes", "CTEST001"
    )
    assert written["nota_gestor"] == "Puerta negra"
    assert written["importe_deuda_asignada"] == 99


def test_lock_busy_only_for_other_job_within_ttl():
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    other = {
        "estado": "publicando",
        "job_id": "job-a",
        "since": now - timedelta(minutes=5),
    }
    assert lock_is_busy(other, "job-b", now=now) is True
    assert lock_is_busy(other, "job-a", now=now) is True
    stale = {
        "estado": "publicando",
        "job_id": "job-a",
        "since": now - timedelta(hours=2),
    }
    assert lock_is_busy(stale, "job-b", now=now) is False
    assert lock_is_busy({"estado": "listo", "job_id": "job-a"}, "job-b", now=now) is False


def test_campaign_section_keys_keeps_call():
    keys = campaign_section_keys(
        {"01_1211_H": []},
        ["01_1211_H", "_CALL_abc", "99_9900_00"],
    )
    assert keys == ["01_1211_H", "_CALL_abc"]


def test_owned_storage_path():
    from cartera.job_paths import is_owned_storage_path

    uid, jid = "u1", "job1"
    assert is_owned_storage_path(f"cartera_uploads/{uid}/{jid}/origen.xlsx", uid, jid)
    assert not is_owned_storage_path(f"cartera_uploads/other/{jid}/origen.xlsx", uid, jid)
    assert not is_owned_storage_path(f"cartera_uploads/{uid}/{jid}/../x.xlsx", uid, jid)
    assert not is_owned_storage_path("cartas_generadas/a/b", uid, jid)
