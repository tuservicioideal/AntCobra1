# Firebase Configuration
# Project: clase-001

import os as _os
import sys as _sys

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg",
    "authDomain": "clase-001.firebaseapp.com",
    "projectId": "clase-001",
    "storageBucket": "clase-001.firebasestorage.app",
    "messagingSenderId": "445584901998",
    "appId": "1:445584901998:web:5c3087ceb65418619ee37f",
    "measurementId": "G-LV7V8QBRKM"
}

# Path to Firebase service account key JSON (needed for admin SDK)
# Download from: Firebase Console > Project Settings > Service Accounts > Generate New Private Key
SERVICE_ACCOUNT_KEY_PATH = "clase-001-firebase-adminsdk-fbsvc-ee190f0bcc.json"

# Desktop app version (must match landing/updates/latest.json on release)
APP_VERSION = "1.0.24"
UPDATE_MANIFEST_URL = "https://clase-001.web.app/updates/latest.json"

# ── Database Configuration ──────────────────────────────────────
_APP_DIR = _os.path.dirname(_os.path.abspath(__file__))
DATABASE_DIR = _os.path.join(_APP_DIR, "data")
DATABASE_PATH = _os.path.join(DATABASE_DIR, "antcobranzas.db")


def resource_path(relative: str) -> str:
    """Resolve a path bundled with the app (PyInstaller _MEIPASS or source tree)."""
    if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
        return _os.path.join(_sys._MEIPASS, relative)
    return _os.path.join(_APP_DIR, relative)


def service_account_key_path() -> str:
    """Absolute path to the Firebase service-account JSON."""
    if _os.path.isabs(SERVICE_ACCOUNT_KEY_PATH):
        return SERVICE_ACCOUNT_KEY_PATH
    return resource_path(SERVICE_ACCOUNT_KEY_PATH)

# ── Tramo / Campaign Thresholds ─────────────────────────────────
UMBRAL_MINIMO_GESTION = 10.0    # S/ — Saldo mínimo para seguir en cobranza
UMBRAL_CARTA_FISICA = 40.0      # S/ — Saldo mínimo para carta física (cartas 2-4)
CAMPANA_DURACION_DIAS = 59      # Días de gestión por cuenta (ciclo individual)

# Columns to extract from Excel (0-indexed)
# These map to the actual Excel column positions
EXCEL_COLUMNS = {
    "segmentacion": 0,        # A: Segmentación
    "segmento_cartera": 1,    # B: Segmento Cartera
    "etapa_deuda": 2,         # C: Etapa Deuda
    "cobrador": 3,            # D: Cobrador
    "campana": 4,             # E: Campaña
    "region": 5,              # F: Región
    "zona": 6,                # G: Zona
    "seccion": 7,             # H: Seccion (CLAVE - asignación de gestor)
    "territorio": 8,          # I: Terr
    "codigo_cliente": 9,      # J: Código Cliente
    "digito_control": 10,     # K: Dígito Control
    "nombres": 11,            # L: Nombres
    "apellido_paterno": 12,   # M: Apellido Paterno
    "apellido_materno": 13,   # N: Apellido Materno
    "genero": 14,             # O: Género
    "edad": 15,               # P: Edad
    "numero_documento": 23,   # X: Número Documento (DNI)
    "telefono_fijo": 25,      # Z: Telefono Fijo
    "telefono_trabajo": 26,   # AA: Telefono Trabajo
    "telefono_movil": 27,     # AB: Telefono Móvil
    "correo": 28,             # AC: Correo Electrónico
    "departamento": 29,       # AD: Departamento
    "provincia": 30,          # AE: Provincia
    "distrito": 31,           # AF: Distrito
    "direccion": 33,          # AH: Direccion
    "referencia": 34,         # AI: Referencia
    "coordenada_x": 35,      # AJ: Coordenada X (longitud)
    "coordenada_y": 36,       # AK: Coordenada Y (latitud)
    "fecha_documento": 38,    # AM: Fecha Documento
    "fecha_vencimiento": 39,  # AN: Fecha Vencimiento
    "fecha_asignacion": 40,   # AO: Fecha Asignacion
    "fecha_cierre": 41,       # AP: Fecha Cierre
    "dias_atraso": 42,        # AQ: Dias de Atraso
    "importe_deuda_original": 43,   # AR: Importe Deuda Original
    "importe_abonos_anteriores": 44, # AS: Importe Abonos Anteriores
    "importe_deuda_asignada": 45,    # AT: Importe Deuda Asignada
    "importe_deuda_pendiente": 50,   # AY: Importe Deuda Pendiente
    "perfil_score": 78,       # CA: Perfil Score
}

# Key fields to display in the UI summary
DISPLAY_FIELDS = [
    "seccion", "codigo_cliente", "nombres", "apellido_paterno",
    "apellido_materno", "numero_documento", "telefono_movil",
    "departamento", "distrito", "dias_atraso",
    "importe_deuda_asignada", "importe_deuda_pendiente"
]
