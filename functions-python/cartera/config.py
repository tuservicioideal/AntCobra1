"""Columnas del Excel del banco (0-indexed). Origen: admin-app/config.py."""

EXCEL_COLUMNS = {
    "segmentacion": 0,
    "segmento_cartera": 1,
    "etapa_deuda": 2,
    "cobrador": 3,
    "campana": 4,
    "region": 5,
    "zona": 6,
    "seccion": 7,
    "territorio": 8,
    "codigo_cliente": 9,
    "digito_control": 10,
    "nombres": 11,
    "apellido_paterno": 12,
    "apellido_materno": 13,
    "genero": 14,
    "edad": 15,
    "numero_documento": 23,
    "telefono_fijo": 25,
    "telefono_trabajo": 26,
    "telefono_movil": 27,
    "correo": 28,
    "departamento": 29,
    "provincia": 30,
    "distrito": 31,
    "direccion": 33,
    "referencia": 34,
    "coordenada_x": 35,
    "coordenada_y": 36,
    "fecha_documento": 38,
    "fecha_vencimiento": 39,
    "fecha_asignacion": 40,
    "fecha_cierre": 41,
    "dias_atraso": 42,
    "importe_deuda_original": 43,
    "importe_abonos_anteriores": 44,
    "importe_deuda_asignada": 45,
    "importe_deuda_pendiente": 50,
    "perfil_score": 78,
}

CAMPAIGN_ID_DEFAULT = "cartera_activa"
MOTIVO_BAJA_EXCEL_BANCO = "ausente_en_excel_banco"
MAX_EXCEL_BYTES = 50 * 1024 * 1024
SAMPLE_LIMIT = 40
BATCH_LIMIT = 400
CALL_SECTION_PREFIX = "_CALL_"
