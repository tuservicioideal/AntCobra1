"""
Genera archivos Excel de prueba con el layout del banco (columnas 0-indexed en config.EXCEL_COLUMNS).

Uso (desde admin-app/):
    python test-data/generate_test_excels.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import Any

import openpyxl
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EXCEL_COLUMNS  # noqa: E402
from services.excel_parser import parse_excel  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "excels")
NUM_COLS = max(EXCEL_COLUMNS.values()) + 1  # 79 columnas (A..CA)

HEADERS = [
    "Segmentación", "Segmento Cartera", "Etapa Deuda", "Cobrador", "Campaña",
    "Región", "Zona", "Seccion", "Terr", "Código Cliente", "Dígito Control",
    "Nombres", "Apellido Paterno", "Apellido Materno", "Género", "Edad",
    "", "", "", "", "", "", "",  # Q-W vacías
    "Número Documento", "",  # Y vacía
    "Telefono Fijo", "Telefono Trabajo", "Telefono Móvil", "Correo Electrónico",
    "Departamento", "Provincia", "Distrito", "",
    "Direccion", "Referencia", "Coordenada X", "Coordenada Y", "",
    "Fecha Documento", "Fecha Vencimiento", "Fecha Asignacion", "Fecha Cierre",
    "Dias de Atraso", "Importe Deuda Original", "Importe Abonos Anteriores",
    "Importe Deuda Asignada", "", "", "", "",
    "Importe Deuda Pendiente",
]
# Rellenar hasta NUM_COLS
while len(HEADERS) < NUM_COLS:
    HEADERS.append("")
HEADERS[NUM_COLS - 1] = "Perfil Score"


def _blank_row() -> list[Any]:
    return [""] * NUM_COLS


def _set(row: list[Any], field: str, value: Any) -> None:
    row[EXCEL_COLUMNS[field]] = value


def _auto_dni(codigo: str) -> str:
    digits = "".join(c for c in codigo if c.isdigit())
    if digits:
        return f"7{int(digits[-8:]) % 10000000:07d}"
    return f"7{abs(hash(codigo)) % 10000000:07d}"


def _client(
    *,
    codigo: str,
    nombres: str,
    ap_paterno: str,
    ap_materno: str = "PRUEBA",
    dni: str = "",
    region: str = "01",
    zona: str = "1211",
    seccion: str = "H",
    campana: str = "CAMP-TEST-2026",
    deuda_asignada: float = 150.0,
    deuda_pendiente: float | None = None,
    dias_atraso: int = 30,
    fecha_asignacion: date | None = None,
    telefono_movil: str = "999888777",
    direccion: str = "Av. Prueba 123",
    departamento: str = "LIMA",
    provincia: str = "LIMA",
    distrito: str = "MIRAFLORES",
    coord_x: float = -77.0282,
    coord_y: float = -12.1219,
    perfil_score: str = "B",
    digito: str = "0",
) -> list[Any]:
    row = _blank_row()
    hoy = date.today()
    fa = fecha_asignacion or (hoy - timedelta(days=5))
    fp = deuda_pendiente if deuda_pendiente is not None else deuda_asignada

    _set(row, "segmentacion", "COBRANZA")
    _set(row, "segmento_cartera", "CONSUMO")
    _set(row, "etapa_deuda", "TEMPRANA")
    _set(row, "cobrador", "EXT-ANT")
    _set(row, "campana", campana)
    _set(row, "region", region)
    _set(row, "zona", zona)
    _set(row, "seccion", seccion)
    _set(row, "territorio", "T01")
    _set(row, "codigo_cliente", codigo)
    _set(row, "digito_control", digito)
    _set(row, "nombres", nombres)
    _set(row, "apellido_paterno", ap_paterno)
    _set(row, "apellido_materno", ap_materno)
    _set(row, "genero", "M")
    _set(row, "edad", 35)
    _set(row, "numero_documento", dni or _auto_dni(codigo))
    _set(row, "telefono_fijo", "014445555")
    _set(row, "telefono_trabajo", "")
    _set(row, "telefono_movil", telefono_movil)
    _set(row, "correo", f"{codigo.lower()}@test.antcobranzas.local")
    _set(row, "departamento", departamento)
    _set(row, "provincia", provincia)
    _set(row, "distrito", distrito)
    _set(row, "direccion", direccion)
    _set(row, "referencia", "Frente al parque")
    _set(row, "coordenada_x", coord_x)
    _set(row, "coordenada_y", coord_y)
    _set(row, "fecha_documento", (hoy - timedelta(days=90)).strftime("%d/%m/%Y"))
    _set(row, "fecha_vencimiento", (hoy - timedelta(days=60)).strftime("%d/%m/%Y"))
    _set(row, "fecha_asignacion", fa.strftime("%d/%m/%Y"))
    _set(row, "fecha_cierre", (fa + timedelta(days=59)).strftime("%d/%m/%Y"))
    _set(row, "dias_atraso", dias_atraso)
    _set(row, "importe_deuda_original", deuda_asignada + 50)
    _set(row, "importe_abonos_anteriores", 50.0)
    _set(row, "importe_deuda_asignada", deuda_asignada)
    _set(row, "importe_deuda_pendiente", fp)
    _set(row, "perfil_score", perfil_score)
    return row


def _write_excel(filename: str, rows: list[list[Any]]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    wb = Workbook()
    ws = wb.active
    ws.title = "Cartera"
    ws.append(HEADERS[:NUM_COLS])
    for row in rows:
        ws.append(row)
    wb.save(path)
    wb.close()
    return path


def _clients_carga_inicial() -> list[list[Any]]:
    hoy = date.today()
    return [
        _client(codigo="CTEST001", nombres="MARIA", ap_paterno="LOPEZ",
                seccion="H", deuda_asignada=320.0, dias_atraso=25),
        _client(codigo="CTEST002", nombres="JUAN", ap_paterno="GARCIA",
                seccion="H", deuda_asignada=180.0, telefono_movil="911222333"),
        _client(codigo="CLI-H-003", nombres="ANA", ap_paterno="TORRES",
                seccion="H", deuda_asignada=95.0),
        _client(codigo="CLI-H-004", nombres="PEDRO", ap_paterno="RUIZ",
                seccion="H", deuda_asignada=45.0),
        _client(codigo="CLI-A-001", nombres="LUIS", ap_paterno="MENDOZA",
                seccion="A", deuda_asignada=210.0, region="01", zona="1211"),
        _client(codigo="CLI-A-002", nombres="ROSA", ap_paterno="VARGAS",
                seccion="A", deuda_asignada=75.0),
        _client(codigo="CLI-A-003", nombres="CARLOS", ap_paterno="DIAZ",
                seccion="A", deuda_asignada=8.0, deuda_pendiente=8.0),
        _client(codigo="CLI-C-001", nombres="ELENA", ap_paterno="CASTRO",
                seccion="C", region="02", zona="1305", deuda_asignada=500.0),
        _client(codigo="CLI-C-002", nombres="MIGUEL", ap_paterno="FLORES",
                seccion="C", region="02", zona="1305", deuda_asignada=120.0),
        _client(codigo="CLI-C-003", nombres="SOFIA", ap_paterno="RAMOS",
                seccion="C", region="02", zona="1305", deuda_asignada=35.0),
        # Misma letra H, distinta región → clave compuesta distinta
        _client(codigo="CLI-H-R2-01", nombres="DIEGO", ap_paterno="SOTO",
                seccion="H", region="02", zona="1211", deuda_asignada=260.0),
        _client(codigo="CLI-H-R2-02", nombres="PATRICIA", ap_paterno="NAVARRO",
                seccion="H", region="02", zona="1211", deuda_asignada=140.0),
    ]


def _clients_sin_ctest001() -> list[list[Any]]:
    return [r for r in _clients_carga_inicial()
            if r[EXCEL_COLUMNS["codigo_cliente"]] != "CTEST001"]


def _clients_con_cambios() -> list[list[Any]]:
    rows = _clients_sin_ctest001()
    out: list[list[Any]] = []
    for row in rows:
        code = row[EXCEL_COLUMNS["codigo_cliente"]]
        new_row = list(row)
        if code == "CTEST002":
            _set(new_row, "importe_deuda_pendiente", 95.50)
            _set(new_row, "importe_deuda_asignada", 95.50)
            _set(new_row, "telefono_movil", "988777666")
            _set(new_row, "direccion", "Jr. Actualizado 456 - Nuevo domicilio")
            _set(new_row, "dias_atraso", 32)
        out.append(new_row)
    out.append(
        _client(codigo="CTEST003", nombres="NUEVO", ap_paterno="CLIENTE",
                seccion="H", deuda_asignada=275.0, dias_atraso=10)
    )
    return out


def _clients_tramos() -> list[list[Any]]:
    hoy = date.today()
    return [
        _client(codigo="TRAMO-SALDO-BAJO", nombres="SALDO", ap_paterno="MENOR10",
                deuda_asignada=8.0, deuda_pendiente=5.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=3)),
        _client(codigo="TRAMO-SALDO-MEDIO", nombres="SALDO", ap_paterno="ENTRE10Y40",
                deuda_asignada=25.0, deuda_pendiente=25.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=3)),
        _client(codigo="TRAMO-SALDO-ALTO", nombres="SALDO", ap_paterno="MAYOR40",
                deuda_asignada=450.0, deuda_pendiente=450.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=3)),
        _client(codigo="TRAMO-DIA-01", nombres="CICLO", ap_paterno="DIA1",
                deuda_asignada=200.0, seccion="T",
                fecha_asignacion=hoy),
        _client(codigo="TRAMO-DIA-15", nombres="CICLO", ap_paterno="DIA15",
                deuda_asignada=200.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=14)),
        _client(codigo="TRAMO-DIA-45", nombres="CICLO", ap_paterno="DIA45",
                deuda_asignada=200.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=44)),
        _client(codigo="TRAMO-CALL-01", nombres="CALL", ap_paterno="REPARTO1",
                deuda_asignada=800.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=2)),
        _client(codigo="TRAMO-CALL-02", nombres="CALL", ap_paterno="REPARTO2",
                deuda_asignada=600.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=2)),
        _client(codigo="TRAMO-CALL-03", nombres="CALL", ap_paterno="REPARTO3",
                deuda_asignada=400.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=2)),
        _client(codigo="TRAMO-CALL-04", nombres="CALL", ap_paterno="REPARTO4",
                deuda_asignada=300.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=2)),
        _client(codigo="TRAMO-CALL-05", nombres="CALL", ap_paterno="REPARTO5",
                deuda_asignada=150.0, seccion="T",
                fecha_asignacion=hoy - timedelta(days=2)),
    ]


def _clients_minimo() -> list[list[Any]]:
    return [
        _client(codigo="SMOKE-001", nombres="PRUEBA", ap_paterno="RAPIDA",
                seccion="X", deuda_asignada=100.0),
        _client(codigo="SMOKE-002", nombres="SEGUNDA", ap_paterno="CUENTA",
                seccion="X", deuda_asignada=50.0),
    ]


def _clients_errores_borde() -> list[list[Any]]:
    """Filas para validar tolerancia del parser (no deben romper la carga)."""
    rows = [
        _client(codigo="EDGE-001", nombres="SIN", ap_paterno="GPS",
                coord_x=0.0, coord_y=0.0, seccion="E"),
        _client(codigo="EDGE-002", nombres="TELEFONO", ap_paterno="VACIO",
                telefono_movil="", seccion="E"),
    ]
    # Fila vacía (sin código) — el parser la ignora
    empty = _blank_row()
    rows.append(empty)
    # Deuda con coma decimal (el parser normaliza)
    r = _client(codigo="EDGE-003", nombres="MONTO", ap_paterno="COMA",
                seccion="E", deuda_asignada=1234.56)
    r[EXCEL_COLUMNS["importe_deuda_pendiente"]] = "1.234,56"
    rows.append(r)
    return rows


def _clients_multi_campana_banco() -> list[list[Any]]:
    """Varias campañas banco en la misma cartera — prueba filtro Monitor/Call Center/Stats."""
    return [
        _client(codigo="MCB-001", nombres="CAMPA", ap_paterno="UNO",
                campana="BANCO-2026-01", seccion="H", deuda_asignada=220.0),
        _client(codigo="MCB-002", nombres="CAMPA", ap_paterno="UNO-B",
                campana="BANCO-2026-01", seccion="H", deuda_asignada=180.0),
        _client(codigo="MCB-003", nombres="CAMPA", ap_paterno="DOS",
                campana="BANCO-2026-02", seccion="A", deuda_asignada=310.0),
        _client(codigo="MCB-004", nombres="CAMPA", ap_paterno="DOS-B",
                campana="BANCO-2026-02", seccion="A", deuda_asignada=95.0),
        _client(codigo="MCB-005", nombres="CAMPA", ap_paterno="TRES",
                campana="BANCO-2026-03", seccion="C", region="02", zona="1305",
                deuda_asignada=540.0),
        _client(codigo="MCB-006", nombres="CAMPA", ap_paterno="TRES-B",
                campana="BANCO-2026-03", seccion="C", region="02", zona="1305",
                deuda_asignada=120.0),
    ]


def _clients_devoluciones() -> list[list[Any]]:
    """Cartera para probar devoluciones, pool y gestión especial (secciones dispersas)."""
    return [
        _client(codigo="DEV-H-001", nombres="ZONA", ap_paterno="INACCESIBLE",
                seccion="H", deuda_asignada=350.0,
                direccion="Carretera sin acceso km 45", distrito="HUAROCHIRI"),
        _client(codigo="DEV-H-002", nombres="RUTA", ap_paterno="BLOQUEADA",
                seccion="H", deuda_asignada=210.0, direccion="Altura del puente colapsado"),
        _client(codigo="DEV-A-001", nombres="RIESGO", ap_paterno="SEGURIDAD",
                seccion="A", deuda_asignada=420.0, distrito="SAN JUAN DE LURIGANCHO"),
        _client(codigo="DEV-A-002", nombres="REASIGNAR", ap_paterno="POOL",
                seccion="A", deuda_asignada=165.0),
        _client(codigo="DEV-C-001", nombres="GESTION", ap_paterno="ESPECIAL",
                seccion="C", region="02", zona="1305", deuda_asignada=890.0),
        _client(codigo="DEV-C-002", nombres="OTRA", ap_paterno="SECCION",
                seccion="C", region="02", zona="1305", deuda_asignada=75.0),
        _client(codigo="DEV-G-001", nombres="SECCION", ap_paterno="G",
                seccion="G", region="01", zona="1211", deuda_asignada=130.0),
    ]


def _clients_call_center_volumen() -> list[list[Any]]:
    """20 cuentas call tramo 1 — reparto LPT y balances entre operadores."""
    hoy = date.today()
    fa = hoy - timedelta(days=2)
    montos = [1200, 980, 750, 620, 510, 440, 380, 320, 280, 240,
              200, 175, 150, 130, 110, 95, 85, 70, 55, 45]
    rows: list[list[Any]] = []
    for i, monto in enumerate(montos, start=1):
        rows.append(
            _client(
                codigo=f"CALL-VOL-{i:02d}",
                nombres="OPERADOR",
                ap_paterno=f"TEST{i:02d}",
                seccion="T",
                deuda_asignada=monto,
                deuda_pendiente=monto,
                fecha_asignacion=fa,
                dias_atraso=5 + (i % 10),
            )
        )
    return rows


def _clients_actualizacion_mixta() -> list[list[Any]]:
    """Escenario combinado: baja + cambios + altas en un solo Excel de actualización."""
    rows = _clients_sin_ctest001()
    out: list[list[Any]] = []
    for row in rows:
        code = row[EXCEL_COLUMNS["codigo_cliente"]]
        new_row = list(row)
        if code == "CLI-A-001":
            _set(new_row, "importe_deuda_pendiente", 150.0)
            _set(new_row, "telefono_movil", "955111222")
        if code == "CLI-C-001":
            _set(new_row, "direccion", "Av. Industrial 1200 - local 3")
            _set(new_row, "importe_deuda_pendiente", 480.0)
        out.append(new_row)
    out.append(
        _client(codigo="ACT-NEW-001", nombres="ALTA", ap_paterno="RECiente",
                seccion="H", deuda_asignada=190.0, dias_atraso=8)
    )
    out.append(
        _client(codigo="ACT-NEW-002", nombres="SEGUNDA", ap_paterno="ALTA",
                seccion="A", deuda_asignada=55.0, dias_atraso=12)
    )
    return out


DATASETS: list[tuple[str, str, list[list[Any]]]] = [
    (
        "01_carga_inicial.xlsx",
        "Carga inicial de campaña — 12 clientes, 4 secciones compuestas",
        _clients_carga_inicial(),
    ),
    (
        "02_actualizacion_sin_cliente.xlsx",
        "Actualización banco — igual que 01 pero sin CTEST001 (baja/pago)",
        _clients_sin_ctest001(),
    ),
    (
        "03_actualizacion_con_cambios.xlsx",
        "Actualización banco — cambios en CTEST002 + cliente nuevo CTEST003",
        _clients_con_cambios(),
    ),
    (
        "04_tramos_umbrales.xlsx",
        "Tramos, cartas y reparto call — saldos y fechas de asignación variadas",
        _clients_tramos(),
    ),
    (
        "05_minimo_smoke.xlsx",
        "Smoke test rápido — 2 clientes en sección X",
        _clients_minimo(),
    ),
    (
        "06_bordes_parser.xlsx",
        "Casos borde — GPS cero, teléfono vacío, fila vacía, monto con coma",
        _clients_errores_borde(),
    ),
    (
        "07_multi_campana_banco.xlsx",
        "Tres campañas banco distintas — filtro Nº campaña en Monitor/Call/Stats",
        _clients_multi_campana_banco(),
    ),
    (
        "08_devoluciones_gestion.xlsx",
        "Secciones H/A/C/G para devoluciones, pool y gestión especial",
        _clients_devoluciones(),
    ),
    (
        "09_call_center_volumen.xlsx",
        "20 cuentas call tramo 1 — reparto LPT entre operadores telefónicos",
        _clients_call_center_volumen(),
    ),
    (
        "10_actualizacion_mixta.xlsx",
        "Actualización banco — cambios en 2 clientes + 2 altas (sin CTEST001)",
        _clients_actualizacion_mixta(),
    ),
]


def main() -> int:
    print(f"Generando Excels en: {OUTPUT_DIR}\n")
    ok = 0
    for filename, desc, rows in DATASETS:
        path = _write_excel(filename, rows)
        data = parse_excel(path)
        n = data["summary"]["total_clientes"]
        secs = data["summary"]["total_secciones"]
        print(f"  OK  {filename}")
        print(f"      {desc}")
        print(f"      -> {n} clientes, {secs} secciones, S/ {data['summary']['total_deuda_pendiente']:,.2f} pendiente\n")
        ok += 1
    print(f"Listo: {ok} archivos generados y validados con excel_parser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
