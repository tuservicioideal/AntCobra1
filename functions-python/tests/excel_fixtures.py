"""Excels sintéticos con el layout del banco."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any

from openpyxl import Workbook

from cartera.config import EXCEL_COLUMNS

NUM_COLS = max(EXCEL_COLUMNS.values()) + 1

HEADERS = [""] * NUM_COLS
HEADERS[0] = "Segmentación"
HEADERS[1] = "Segmento Cartera"
HEADERS[2] = "Etapa Deuda"
HEADERS[3] = "Cobrador"
HEADERS[4] = "Campaña"
HEADERS[5] = "Región"
HEADERS[6] = "Zona"
HEADERS[7] = "Seccion"
HEADERS[8] = "Terr"
HEADERS[9] = "Código Cliente"
HEADERS[10] = "Dígito Control"
HEADERS[11] = "Nombres"
HEADERS[12] = "Apellido Paterno"
HEADERS[13] = "Apellido Materno"
HEADERS[23] = "Número Documento"
HEADERS[27] = "Telefono Móvil"
HEADERS[29] = "Departamento"
HEADERS[33] = "Direccion"
HEADERS[35] = "Coordenada X"
HEADERS[36] = "Coordenada Y"
HEADERS[40] = "Fecha Asignacion"
HEADERS[42] = "Dias de Atraso"
HEADERS[45] = "Importe Deuda Asignada"
HEADERS[50] = "Importe Deuda Pendiente"
HEADERS[78] = "Perfil Score"


def _blank() -> list[Any]:
    return [""] * NUM_COLS


def _set(row: list[Any], field: str, value: Any) -> None:
    row[EXCEL_COLUMNS[field]] = value


def client_row(
    *,
    codigo: str,
    nombres: str = "MARIA",
    ap_paterno: str = "LOPEZ",
    ap_materno: str = "PRUEBA",
    region: str = "01",
    zona: str = "1211",
    seccion: str = "H",
    campana: str = "BANCO-2026-01",
    deuda: float = 150.0,
    pendiente: float | None = None,
    dias: int = 20,
    telefono: str = "999888777",
    direccion: str = "Av. Prueba 123",
    coord_x: float = -77.02,
    coord_y: float = -12.12,
) -> list[Any]:
    row = _blank()
    fa = date.today() - timedelta(days=5)
    _set(row, "segmentacion", "COBRANZA")
    _set(row, "campana", campana)
    _set(row, "region", region)
    _set(row, "zona", zona)
    _set(row, "seccion", seccion)
    _set(row, "codigo_cliente", codigo)
    _set(row, "nombres", nombres)
    _set(row, "apellido_paterno", ap_paterno)
    _set(row, "apellido_materno", ap_materno)
    _set(row, "numero_documento", "70123456")
    _set(row, "telefono_movil", telefono)
    _set(row, "departamento", "LIMA")
    _set(row, "direccion", direccion)
    _set(row, "coordenada_x", coord_x)
    _set(row, "coordenada_y", coord_y)
    _set(row, "fecha_asignacion", fa.strftime("%d/%m/%Y"))
    _set(row, "dias_atraso", dias)
    _set(row, "importe_deuda_asignada", deuda)
    _set(row, "importe_deuda_pendiente", pendiente if pendiente is not None else deuda)
    return row


def workbook_bytes(rows: list[list[Any]], headers: list[str] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append((headers or HEADERS)[:NUM_COLS])
    for row in rows:
        padded = list(row) + [""] * (NUM_COLS - len(row))
        ws.append(padded[:NUM_COLS])
    buf = BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()
