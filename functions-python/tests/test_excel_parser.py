from cartera.excel_parser import ExcelParseError, parse_excel, make_seccion_key

from excel_fixtures import client_row, workbook_bytes, HEADERS, NUM_COLS


def test_make_seccion_key_compuesta():
    assert make_seccion_key("01", "1211", "h") == "01_1211_H"
    assert make_seccion_key("", "", "") == "SR_SZ_SS"


def test_parse_smoke_two_clients_same_section():
    raw = workbook_bytes(
        [
            client_row(codigo="SMOKE-001", seccion="X", deuda=100),
            client_row(codigo="SMOKE-002", seccion="X", deuda=50),
        ]
    )
    data = parse_excel(raw)
    assert data["summary"]["total_clientes"] == 2
    assert data["summary"]["total_secciones"] == 1
    assert "01_1211_X" in data["by_seccion"]
    first = data["all_clients"][0]
    assert first["campana_banco"] == "BANCO-2026-01"
    assert first["numero_documento"] == "70123456"
    assert first["nombre_completo"].startswith("MARIA")


def test_parse_same_letter_different_region_are_distinct_keys():
    raw = workbook_bytes(
        [
            client_row(codigo="H1", seccion="H", region="01", zona="1211"),
            client_row(codigo="H2", seccion="H", region="02", zona="1211"),
        ]
    )
    data = parse_excel(raw)
    assert set(data["by_seccion"]) == {"01_1211_H", "02_1211_H"}


def test_parse_skips_row_without_codigo():
    rows = [
        client_row(codigo="EDGE-001", coord_x=0, coord_y=0),
        [""] * NUM_COLS,
        client_row(codigo="EDGE-002", telefono=""),
    ]
    data = parse_excel(workbook_bytes(rows))
    assert data["summary"]["total_clientes"] == 2


def test_parse_european_decimal_amount():
    row = client_row(codigo="EDGE-003", deuda=0)
    row_list = list(row)
    from cartera.config import EXCEL_COLUMNS

    row_list[EXCEL_COLUMNS["importe_deuda_pendiente"]] = "1.234,56"
    data = parse_excel(workbook_bytes([row_list]))
    assert data["all_clients"][0]["importe_deuda_pendiente"] == 1234.56


def test_parse_rejects_wrong_headers():
    bad = list(HEADERS)
    bad[9] = "Otra cosa"
    try:
        parse_excel(workbook_bytes([client_row(codigo="X")], headers=bad))
        assert False, "expected ExcelParseError"
    except ExcelParseError as exc:
        assert "Código Cliente" in str(exc) or "codigo" in str(exc).lower()


def test_parse_rejects_empty_workbook():
    try:
        parse_excel(workbook_bytes([]))
        assert False, "expected ExcelParseError"
    except ExcelParseError as exc:
        assert "válidos" in str(exc)
