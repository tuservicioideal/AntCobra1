from cartera.diff_engine import compare_cartera
from cartera.visit_merge import apply_visit_fields, extract_visit_fields, reindex_cartera_for_diff


def _cli(code: str, **extra):
    base = {
        "codigo_cliente": code,
        "nombre_completo": code,
        "telefono_movil": "999",
        "importe_deuda_pendiente": 100.0,
        "activo_en_cartera": True,
        "seccion_key": "01_1211_H",
    }
    base.update(extra)
    return base


def test_diff_new_updated_removed():
    old = {
        "01_1211_H": {
            "A": _cli("A", importe_deuda_pendiente=100.0),
            "B": _cli("B"),
        }
    }
    new = {
        "01_1211_H": [
            _cli("A", importe_deuda_pendiente=80.0),
            _cli("C"),
        ]
    }
    report = compare_cartera(old, new)
    assert report.total_removed == 1
    assert report.sections["01_1211_H"].removed_clients[0]["codigo_cliente"] == "B"
    assert report.total_new == 1
    assert report.sections["01_1211_H"].new_clients[0]["codigo_cliente"] == "C"
    assert report.total_updated == 1
    assert report.sections["01_1211_H"].updated_clients[0].codigo_cliente == "A"


def test_diff_ignores_already_archived():
    old = {
        "01_1211_H": {
            "Z": _cli("Z", activo_en_cartera=False),
        }
    }
    report = compare_cartera(old, {"01_1211_H": []})
    assert report.total_removed == 0


def test_visit_fields_preserved_on_merge():
    excel = {
        "codigo_cliente": "A",
        "importe_deuda_pendiente": 50,
        "estado_gestion": "pendiente",
        "telefono_movil": "111",
    }
    prev = extract_visit_fields(
        {
            "estado_gestion": "visitado_habido",
            "gps_latitud": -12.1,
            "nota_gestor": "Casa azul",
            "fecha_gestion": "2026-08-01",
        }
    )
    merged = apply_visit_fields(excel, prev)
    assert merged["estado_gestion"] == "visitado_habido"
    assert merged["gps_latitud"] == -12.1
    assert merged["importe_deuda_pendiente"] == 50


def test_semaforo_and_etiquetas_preserved_without_visit():
    """Semáforo/etiquetas se guardan en campo aunque el cliente siga pendiente."""
    excel = {
        "codigo_cliente": "A",
        "importe_deuda_pendiente": 50,
        "estado_gestion": "pendiente",
        "telefono_movil": "111",
    }
    prev = extract_visit_fields(
        {
            "estado_gestion": "pendiente",
            "semaforo": "rojo",
            "etiquetas": ["etq_abc"],
        }
    )
    assert prev.get("semaforo") == "rojo"
    assert prev.get("etiquetas") == ["etq_abc"]
    assert "estado_gestion" not in prev  # sin visita no se arrastra el resto
    merged = apply_visit_fields(excel, prev)
    assert merged["semaforo"] == "rojo"
    assert merged["etiquetas"] == ["etq_abc"]
    assert merged["estado_gestion"] == "pendiente"
    assert merged["importe_deuda_pendiente"] == 50


def test_reindex_call_section_uses_territorial_key():
    raw = {
        "_CALL_uid1": {
            "A": {
                "codigo_cliente": "A",
                "seccion_key": "_CALL_uid1",
                "seccion_key_origen": "01_1211_H",
                "estado_gestion": "pendiente",
            }
        }
    }
    indexed = reindex_cartera_for_diff(raw)
    assert "A" in indexed["01_1211_H"]
    assert indexed["01_1211_H"]["A"]["_firestore_seccion"] == "_CALL_uid1"
