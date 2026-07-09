"""
Campaign Manager — Orchestrator Service
========================================

Central orchestrator that coordinates:
  1. Excel file parsing → SQLite ingestion
  2. Tramo evaluation → Transition application
  3. Letter generation decisions
  4. SQLite → Firebase sync (includes DNI for gestores)
  5. Campaign lifecycle management

This replaces the direct Excel→Firebase pipeline with:
  Excel → SQLite (fuente de verdad) → Firebase (cloud sync)
"""

from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import (
    db_service, DatabaseService,
    Campana, Cliente, Gestor, CartaGenerada, HistorialTramo, HistorialContacto,
    HistorialZona, HistorialRepartoCall, CampanaBancoMeta, ContactoPersona,
    EtiquetaCatalogo, HistorialVisita,
    EstadoCampana, EstadoCiclo, TramoEnum, EstadoGestion, ConfigCampana,
    PlantillaCarta, MOTIVO_BAJA_EXCEL_BANCO, GESTION_ESPECIAL_SECTION,
    FASE_GESTION_CALL, FASE_GESTION_CAMPO, make_call_section_key,
    NIVEL_CONFIABLE, NIVEL_DUDOSA, NIVEL_DESCARTADA, NIVELES_CONFIANZA,
)
from .call_center_service import (
    distribute_tramo1,
    preview_distribution,
    get_call_center_summary,
    get_call_center_dashboard,
    get_clients_for_call_gestor,
    reassign_call_client,
    get_effective_firestore_section,
    get_territorial_seccion_key,
    filter_call_gestores,
    CallAssignmentChange,
    DistributionResult,
    MOTIVO_REASIGNACION_MANUAL,
)
from .excel_parser import parse_excel, get_seccion_summary, make_seccion_key, safe_str, safe_float, safe_int
from .campana_banco_utils import (
    SIN_CAMPANA_KEY,
    apply_campana_banco_filter,
    distinct_campana_banco_values,
    display_label_for_key,
    campana_banco_key_from_value,
    compute_detected_dates_for_group,
    effective_campana_banco_dates,
)
from .date_utils import parse_excel_fecha, format_fecha_iso
from .tramo_engine import TramoEngine, EvaluationResult, load_config

logger = logging.getLogger(__name__)


def _parse_etiquetas_json(raw: str | None) -> list[str]:
    """Parse etiquetas JSON array from SQLite/Firestore."""
    import json
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if x]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _serialize_etiquetas_json(ids: list[str] | None) -> str:
    import json
    clean = [str(x) for x in (ids or []) if x]
    return json.dumps(clean, ensure_ascii=False)


def _nivel_sort_rank(nivel: str) -> int:
    ranks = {NIVEL_CONFIABLE: 0, NIVEL_DUDOSA: 1, NIVEL_DESCARTADA: 2}
    return ranks.get((nivel or NIVEL_CONFIABLE).strip().lower(), 1)


def _infer_tipo_from_event(ev: Dict[str, Any]) -> str:
    tipo_raw = str(ev.get("tipo", "") or "").strip().lower()
    if tipo_raw == "gps_verificado":
        return "ubicacion"
    if tipo_raw in ("direccion", "telefono", "ubicacion"):
        return tipo_raw
    campo = str(ev.get("campo", "") or "").strip().lower()
    if campo == "ubicacion":
        return "ubicacion"
    addr = str(ev.get("direccion_nueva", "") or ev.get("direccion", "") or "").strip()
    phone = str(ev.get("telefono_nuevo", "") or ev.get("telefono", "") or "").strip()
    if addr and not phone:
        return "direccion"
    if phone and not addr:
        return "telefono"
    if addr:
        return "direccion"
    if phone:
        return "telefono"
    return "direccion"


def _contact_event_to_persona_fields(ev: Dict[str, Any]) -> Dict[str, Any]:
    gps = ev.get("gps") if isinstance(ev.get("gps"), dict) else {}
    direccion = str(ev.get("direccion_nueva", "") or ev.get("direccion", "") or "").strip()
    telefono = str(ev.get("telefono_nuevo", "") or ev.get("telefono", "") or "").strip()
    nivel = str(ev.get("nivel_confianza", NIVEL_CONFIABLE) or NIVEL_CONFIABLE).strip().lower()
    if nivel not in NIVELES_CONFIANZA:
        nivel = NIVEL_CONFIABLE
    return {
        "direccion": direccion or None,
        "telefono": telefono or None,
        "latitud": float(gps.get("latitude", gps.get("lat", 0)) or 0) or None,
        "longitud": float(gps.get("longitude", gps.get("lng", 0)) or 0) or None,
        "nivel_confianza": nivel,
        "orden": int(ev.get("orden", 0) or 0),
        "oculto": bool(ev.get("oculto", False)),
        "es_principal": bool(ev.get("es_principal", False)),
        "nota": str(ev.get("nota", "") or "").strip() or None,
        "tipo": _infer_tipo_from_event(ev),
        "usuario_uid": str(ev.get("usuario_uid", "") or "") or None,
        "usuario_nombre": str(ev.get("usuario_nombre", "") or "") or None,
        "usuario_email": str(ev.get("usuario_email", "") or "") or None,
        "fecha_evento": str(ev.get("fecha", "") or ev.get("fecha_evento", "") or "") or None,
    }


def upsert_contacto_persona(
    session: Session,
    numero_documento: str,
    event_id: str,
    ev: Dict[str, Any],
    campana_origen: str,
) -> None:
    """Persist or update durable contact agenda entry keyed by DNI."""
    dni = (numero_documento or "").strip()
    if not dni or not event_id:
        return
    fields = _contact_event_to_persona_fields(ev)
    if not fields["direccion"] and not fields["telefono"] and not fields["latitud"]:
        return
    existing = (
        session.query(ContactoPersona)
        .filter(ContactoPersona.event_id == event_id)
        .first()
    )
    if existing is None:
        session.add(ContactoPersona(
            numero_documento=dni,
            event_id=event_id,
            campana_origen=campana_origen,
            **fields,
        ))
    else:
        for key, val in fields.items():
            setattr(existing, key, val)
        if campana_origen and not existing.campana_origen:
            existing.campana_origen = campana_origen


def get_contactos_persona(
    session: Session,
    numero_documento: str,
    *,
    incluir_ocultos: bool = False,
) -> List[Dict[str, Any]]:
    """Return durable contact entries for a person (DNI), sorted for display."""
    dni = (numero_documento or "").strip()
    if not dni:
        return []
    q = session.query(ContactoPersona).filter(ContactoPersona.numero_documento == dni)
    if not incluir_ocultos:
        q = q.filter(ContactoPersona.oculto.is_(False))
    rows = q.all()
    rows.sort(
        key=lambda r: (
            0 if r.es_principal else 1,
            _nivel_sort_rank(r.nivel_confianza),
            r.orden,
            -(len(r.fecha_evento or "")),
        )
    )
    return [
        {
            "event_id": r.event_id,
            "numero_documento": r.numero_documento,
            "campana_origen": r.campana_origen or "",
            "direccion": r.direccion or "",
            "telefono": r.telefono or "",
            "latitud": r.latitud,
            "longitud": r.longitud,
            "nivel_confianza": r.nivel_confianza or NIVEL_CONFIABLE,
            "orden": r.orden or 0,
            "oculto": bool(r.oculto),
            "es_principal": bool(r.es_principal),
            "nota": r.nota or "",
            "tipo": r.tipo or "",
            "usuario_uid": r.usuario_uid or "",
            "usuario_nombre": r.usuario_nombre or "",
            "usuario_email": r.usuario_email or "",
            "fecha": r.fecha_evento or "",
            "fecha_evento": r.fecha_evento or "",
        }
        for r in rows
    ]


def contacto_seed_to_firestore_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Map local agenda entry to Firestore historial_contacto document."""
    tipo = entry.get("tipo") or "alternativa"
    firestore_tipo = "gps_verificado" if tipo == "ubicacion" else "alternativa"
    payload: Dict[str, Any] = {
        "fecha": entry.get("fecha") or entry.get("fecha_evento") or "",
        "campo": "ubicacion" if tipo == "ubicacion" else "contacto",
        "tipo": firestore_tipo,
        "direccion_nueva": entry.get("direccion") or "",
        "telefono_nuevo": entry.get("telefono") or "",
        "nota": entry.get("nota") or "",
        "usuario_uid": entry.get("usuario_uid") or "",
        "usuario_nombre": entry.get("usuario_nombre") or "",
        "usuario_email": entry.get("usuario_email") or "",
        "nivel_confianza": entry.get("nivel_confianza") or NIVEL_CONFIABLE,
        "orden": int(entry.get("orden", 0) or 0),
        "oculto": bool(entry.get("oculto", False)),
        "es_principal": bool(entry.get("es_principal", False)),
        "origen_actualizacion": "admin_seed",
        "usar_como_principal": bool(entry.get("es_principal", False)),
    }
    lat = entry.get("latitud")
    lng = entry.get("longitud")
    if lat and lng:
        payload["gps"] = {
            "latitude": float(lat),
            "longitude": float(lng),
            "timestamp": entry.get("fecha") or "",
        }
    return payload


def collect_direcciones_conocidas(
    cliente: Dict[str, Any],
    historial_contacto: List[Dict[str, Any]],
    *,
    incluir_ocultos: bool = False,
) -> List[Dict[str, Any]]:
    """Known addresses/phones: bank + reference + field updates, sorted by credibility."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def entry_key(direccion: str, telefono: str | None) -> str:
        return f"{(direccion or '').strip().lower()}|{(telefono or '').strip()}"

    def push_entry(
        direccion: str,
        telefono: str | None,
        fuente: str,
        fecha: str | None = None,
        *,
        event_id: str = "",
        nivel_confianza: str = NIVEL_CONFIABLE,
        orden: int = 0,
        oculto: bool = False,
        es_principal: bool = False,
        tipo: str = "direccion",
    ) -> None:
        d = (direccion or "").strip()
        t = (telefono or "").strip() or None
        if not d and not t:
            return
        if oculto and not incluir_ocultos:
            return
        key = entry_key(d or t or "", t)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "direccion": d,
            "telefono": t,
            "fuente": fuente,
            "fecha": fecha,
            "event_id": event_id,
            "nivel_confianza": nivel_confianza,
            "orden": orden,
            "oculto": oculto,
            "es_principal": es_principal,
            "tipo": tipo,
        })

    push_entry(
        str(cliente.get("direccion", "")),
        str(cliente.get("telefono_movil", "")),
        "Registro banco (principal)",
        es_principal=True,
        nivel_confianza=NIVEL_CONFIABLE,
        orden=-1,
    )
    push_entry(str(cliente.get("referencia", "")), None, "Referencia de ubicación")

    historial_sorted = sorted(
        historial_contacto,
        key=lambda h: (
            0 if h.get("es_principal") else 1,
            _nivel_sort_rank(str(h.get("nivel_confianza", NIVEL_CONFIABLE))),
            int(h.get("orden", 0) or 0),
            str(h.get("fecha_evento", h.get("fecha", ""))),
        ),
    )
    for h in historial_sorted:
        if h.get("oculto") and not incluir_ocultos:
            continue
        d = str(h.get("direccion_nueva", h.get("direccion", ""))).strip()
        t = str(h.get("telefono_nuevo", h.get("telefono", ""))).strip() or None
        if not d and not t:
            continue
        nota = str(h.get("nota", "")).strip()
        quien = str(h.get("usuario_nombre", "") or h.get("usuario_email", "")).strip()
        tipo_raw = str(h.get("tipo", ""))
        tipo_label = (
            "Ubicación GPS verificada" if tipo_raw == "gps_verificado"
            else "Actualización principal" if tipo_raw == "principal"
            else "Nota de campo"
        )
        fuente = " · ".join(
            x for x in [nota or tipo_label, f"Por: {quien}" if quien else ""] if x
        )
        fecha = str(h.get("fecha_evento", h.get("fecha", "")))[:16].replace("T", " ")
        push_entry(
            d, t, fuente, fecha or None,
            event_id=str(h.get("event_id", h.get("id", ""))),
            nivel_confianza=str(h.get("nivel_confianza", NIVEL_CONFIABLE)),
            orden=int(h.get("orden", 0) or 0),
            oculto=bool(h.get("oculto", False)),
            es_principal=bool(h.get("es_principal", False)),
            tipo=_infer_tipo_from_event(h),
        )

    out.sort(
        key=lambda e: (
            0 if e.get("es_principal") else 1,
            _nivel_sort_rank(str(e.get("nivel_confianza", NIVEL_CONFIABLE))),
            int(e.get("orden", 0) or 0),
        )
    )
    return out


def _coerce_firebase_datetime(value: Any) -> datetime | None:
    """Parse Firestore/ISO datetime values for SQLAlchemy DateTime columns."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        if hasattr(value, "isoformat"):
            return value  # type: ignore[return-value]
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ── Campos sensibles que NO se sincronizan a Firebase ────────────
CAMPOS_SENSIBLES = {"numero_documento"}

# Campos que se envían a Firebase por cada cliente
FIREBASE_CLIENT_FIELDS = [
    "codigo_cliente", "digito_control", "nombres",
    "apellido_paterno", "apellido_materno", "nombre_completo",
    "genero", "edad", "telefono_fijo", "telefono_trabajo",
    "telefono_movil", "correo", "departamento", "provincia",
    "distrito", "direccion", "referencia",
    "coordenada_x", "coordenada_y",
    "segmentacion", "segmento_cartera", "etapa_deuda",
    "cobrador", "campana_banco", "region", "zona", "seccion", "territorio",
    "perfil_score", "fecha_documento", "fecha_vencimiento",
    "fecha_asignacion", "fecha_cierre",
    "dias_atraso", "importe_deuda_original",
    "importe_abonos_anteriores", "importe_deuda_asignada",
    "importe_deuda_pendiente",
    # Campos de gestión
    "tramo_actual", "estado_gestion", "nota_gestor",
    "fecha_gestion", "gps_latitud", "gps_longitud",
    "dia_ciclo", "estado_ciclo", "fecha_asignacion_dt",
    "gestion_especial", "motivo_gestion_especial", "seccion_origen",
    # Clasificación jerárquica de gestión
    "nivel_1", "nivel_2", "nivel_3", "nivel_4",
    "canal_gestion", "fecha_promesa_pago", "monto_promesa_pago",
]


def generate_campaign_id(nombre: str = "") -> str:
    """Generate a unique campaign ID: YYYYMMDD_nombre_short-uuid."""
    today = date.today().strftime("%Y%m%d")
    slug = nombre.replace(" ", "_")[:20] if nombre else "camp"
    short_id = uuid.uuid4().hex[:6]
    return f"{today}_{slug}_{short_id}"


class CampaignManager:
    """
    High-level orchestrator for campaign operations.
    All public methods handle their own sessions.
    """

    def __init__(self, db: DatabaseService | None = None):
        self.db = db or db_service
        self.tramo_engine = TramoEngine()

    # ─────────────────────────────────────────────────────────────
    #  1. CAMPAIGN CREATION (Excel → SQLite)
    # ─────────────────────────────────────────────────────────────

    def create_campaign_from_excel(
        self,
        file_path: str,
        nombre: str = "",
        duracion_dias: int = 60,
    ) -> tuple[Campana, dict]:
        """
        Parse an Excel file and create a new campaign + clients in SQLite.

        Args:
            file_path: Path to the bank's Excel file.
            nombre: Human-readable campaign name.
            duracion_dias: Campaign duration (default 60 days).

        Returns:
            Tuple of (Campana object, summary dict).
        
        Raises:
            FileNotFoundError: If Excel file doesn't exist.
            ValueError: If another campaign is already active.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        # Ensure DB is initialized
        if not self.db.is_initialized:
            self.db.initialize()

        # Check for existing active campaign
        with self.db.session() as session:
            active = (
                session.query(Campana)
                .filter(Campana.estado == EstadoCampana.ACTIVA.value)
                .first()
            )
            if active:
                raise ValueError(
                    f"Ya existe una campaña activa: {active.nombre} ({active.id}). "
                    "Ciérrela antes de crear una nueva."
                )

        # Parse Excel
        logger.info("Parsing Excel file: %s", file_path)
        data = parse_excel(file_path)
        all_clients = data["all_clients"]
        summary = data["summary"]

        if not all_clients:
            raise ValueError("El archivo Excel no contiene clientes válidos.")

        # Generate IDs and dates (duración desde config si está disponible)
        if not self.db.is_initialized:
            self.db.initialize()
        with self.db.session() as session:
            cfg = ConfigCampana.get_or_create(session)
            duracion_dias = cfg.duracion_dias or duracion_dias

        campaign_id = generate_campaign_id(nombre)
        fecha_inicio = date.today()
        fecha_fin = fecha_inicio + timedelta(days=duracion_dias - 1)

        if not nombre:
            nombre = f"Campaña {fecha_inicio.strftime('%d/%m/%Y')}"

        # Create campaign + clients in a single transaction
        with self.db.session() as session:
            campana = Campana(
                id=campaign_id,
                nombre=nombre,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=EstadoCampana.ACTIVA.value,
                archivo_origen=os.path.basename(file_path),
                total_clientes=len(all_clients),
                total_secciones=summary.get("total_secciones", 0),
                deuda_total_asignada=summary.get("total_deuda_asignada", 0.0),
                deuda_total_pendiente=summary.get("total_deuda_pendiente", 0.0),
            )
            session.add(campana)

            # Bulk insert clients
            for client_data in all_clients:
                cliente = self._dict_to_cliente(client_data, campaign_id)
                session.add(cliente)

            session.commit()

            # Refresh to get IDs
            session.refresh(campana)
            result_summary = {
                "campaign_id": campaign_id,
                "nombre": nombre,
                "fecha_inicio": str(fecha_inicio),
                "fecha_fin": str(fecha_fin),
                "total_clientes": len(all_clients),
                "total_secciones": summary.get("total_secciones", 0),
                "deuda_asignada": summary.get("total_deuda_asignada", 0.0),
                "deuda_pendiente": summary.get("total_deuda_pendiente", 0.0),
                "secciones": summary.get("secciones", {}),
            }

        logger.info(
            "Campaign created: %s with %d clients",
            campaign_id, len(all_clients)
        )
        self.sync_campana_banco_meta(campaign_id)
        return campana, result_summary

    def _init_cliente_ciclo(
        self,
        cliente: Cliente,
        d: dict,
        *,
        fallback_fecha: date | None = None,
    ) -> None:
        """Inicializa fechas y tramo según fecha de asignación del Excel."""
        fb = fallback_fecha or date.today()
        fa = parse_excel_fecha(d.get("fecha_asignacion"), fb)
        fc = parse_excel_fecha(d.get("fecha_cierre"))
        cliente.fecha_asignacion_dt = fa
        cliente.fecha_cierre_dt = fc
        if not cliente.estado_ciclo:
            cliente.estado_ciclo = EstadoCiclo.ACTIVA.value
        load_config()
        dia = max(1, (date.today() - fa).days + 1) if fa else 1
        tramo = TramoEngine.get_tramo_for_day(dia)
        cliente.tramo_actual = tramo.value
        if tramo == TramoEnum.TRAMO_1:
            cliente.fase_gestion = FASE_GESTION_CALL
        else:
            cliente.fase_gestion = FASE_GESTION_CAMPO
            cliente.call_gestor_uid = None
            cliente.call_gestor_nombre = None

    def _dict_to_cliente(self, d: dict, campana_id: str) -> Cliente:
        """Convert a parsed Excel client dict to a Cliente ORM object."""
        cliente = Cliente(
            campana_id=campana_id,
            codigo_cliente=safe_str(d.get("codigo_cliente")),
            digito_control=safe_str(d.get("digito_control")),
            numero_documento=safe_str(d.get("numero_documento")),
            nombres=safe_str(d.get("nombres")),
            apellido_paterno=safe_str(d.get("apellido_paterno")),
            apellido_materno=safe_str(d.get("apellido_materno")),
            nombre_completo=safe_str(d.get("nombre_completo")),
            genero=safe_str(d.get("genero")),
            edad=safe_int(d.get("edad")),
            telefono_fijo=safe_str(d.get("telefono_fijo")),
            telefono_trabajo=safe_str(d.get("telefono_trabajo")),
            telefono_movil=safe_str(d.get("telefono_movil")),
            correo=safe_str(d.get("correo")),
            departamento=safe_str(d.get("departamento")),
            provincia=safe_str(d.get("provincia")),
            distrito=safe_str(d.get("distrito")),
            direccion=safe_str(d.get("direccion")),
            referencia=safe_str(d.get("referencia")),
            coordenada_x=safe_float(d.get("coordenada_x")),
            coordenada_y=safe_float(d.get("coordenada_y")),
            segmentacion=safe_str(d.get("segmentacion")),
            segmento_cartera=safe_str(d.get("segmento_cartera")),
            etapa_deuda=safe_str(d.get("etapa_deuda")),
            cobrador=safe_str(d.get("cobrador")),
            campana_banco=safe_str(d.get("campana")),
            region=safe_str(d.get("region")),
            zona=safe_str(d.get("zona")),
            seccion=safe_str(d.get("seccion")),
            territorio=safe_str(d.get("territorio")),
            perfil_score=safe_str(d.get("perfil_score")),
            fecha_documento=safe_str(d.get("fecha_documento")),
            fecha_vencimiento=safe_str(d.get("fecha_vencimiento")),
            fecha_asignacion=safe_str(d.get("fecha_asignacion")),
            fecha_cierre=safe_str(d.get("fecha_cierre")),
            dias_atraso=safe_int(d.get("dias_atraso")),
            importe_deuda_original=safe_float(d.get("importe_deuda_original")),
            importe_abonos_anteriores=safe_float(d.get("importe_abonos_anteriores")),
            importe_deuda_asignada=safe_float(d.get("importe_deuda_asignada")),
            importe_deuda_pendiente=safe_float(d.get("importe_deuda_pendiente")),
            ultima_nota_contacto=safe_str(d.get("ultima_nota_contacto")),
            fecha_actualizacion_contacto_iso=safe_str(d.get("fecha_actualizacion_contacto_iso")),
            actualizado_por_uid=safe_str(d.get("actualizado_por_uid")),
            actualizado_por_nombre=safe_str(d.get("actualizado_por_nombre")),
            actualizado_por_email=safe_str(d.get("actualizado_por_email")),
            origen_actualizacion=safe_str(d.get("origen_actualizacion")),
            tramo_actual=TramoEnum.NONE.value,
            estado_gestion=EstadoGestion.PENDIENTE.value,
            estado_ciclo=EstadoCiclo.ACTIVA.value,
            activo_en_cartera=True,
        )
        self._init_cliente_ciclo(cliente, d)
        return cliente

    # ─────────────────────────────────────────────────────────────
    #  1b. CAMPAIGN UPDATE (New Excel → Diff → SQLite + Firebase)
    # ─────────────────────────────────────────────────────────────

    def update_campaign_from_excel(
        self,
        file_path: str,
        campana_id: str | None = None,
        firebase_service=None,
        old_by_seccion: dict | None = None,
    ) -> tuple[Any, Any]:
        """
        Parse a new Excel file, compare with current Firestore data,
        update SQLite, and return the change report for upload/notification.

        Args:
            file_path: Path to the updated Excel file.
            campana_id: Campaign to update (defaults to active).
            firebase_service: FirebaseService instance for reading current data.
            old_by_seccion: Pre-loaded Firestore cartera (avoids duplicate read).

        Returns:
            Tuple of (new_parsed_data dict, ChangeReport).

        Raises:
            FileNotFoundError: If Excel file doesn't exist.
            ValueError: If no active campaign exists.
        """
        from .diff_engine import compare_cartera

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        if not self.db.is_initialized:
            self.db.initialize()

        # Get the active campaign
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                raise ValueError("No hay campaña activa para actualizar.")
            campana_id = campana.id

        # Parse new Excel
        logger.info("Parsing updated Excel: %s", file_path)
        new_data = parse_excel(file_path)
        new_by_seccion = new_data["by_seccion"]

        if not new_data["all_clients"]:
            raise ValueError("El archivo Excel no contiene clientes válidos.")

        # Read current data from Firestore (or use pre-loaded snapshot)
        if old_by_seccion is None:
            old_by_seccion = {}
            if firebase_service and firebase_service.is_initialized():
                logger.info("Reading current cartera from Firestore...")
                old_by_seccion = firebase_service.read_current_cartera("cartera_activa")

        # Compare
        change_report = compare_cartera(old_by_seccion, new_by_seccion)

        logger.info(
            "Update analysis complete: %s", change_report.summary_text
        )
        return new_data, change_report

    def apply_excel_update_to_sqlite(
        self,
        campana_id: str,
        new_data: dict,
        change_report,
        *,
        ultimo_excel: str = "",
    ) -> dict[str, str]:
        """Persist Excel changes to SQLite (call only after user confirms).

        Returns:
            Snapshot seccion_key por codigo_cliente antes del update (afinidad campo).
        """
        from .reparto_planner import snapshot_seccion_keys

        with self.db.session() as session:
            prev_sections = snapshot_seccion_keys(session, campana_id)
        self._update_sqlite_clients(
            campana_id,
            new_data["all_clients"],
            new_data["summary"],
            change_report=change_report,
            ultimo_excel=ultimo_excel,
        )
        return prev_sections

    def _update_sqlite_clients(
        self,
        campana_id: str,
        all_clients: list[dict],
        summary: dict,
        *,
        change_report=None,
        ultimo_excel: str = "",
    ) -> None:
        """
        Update SQLite with new client data from Excel.
        Updates existing clients by codigo_cliente, inserts new ones.
        Archives clients absent from the new Excel (soft delete).
        Preserves management fields (estado_gestion, nota_gestor, etc.).
        """
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                return

            # Index existing clients by codigo_cliente
            existing = {
                c.codigo_cliente: c
                for c in session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
                .all()
            }

            excel_codes = {
                safe_str(c.get("codigo_cliente"))
                for c in all_clients
                if safe_str(c.get("codigo_cliente"))
            }

            for client_data in all_clients:
                code = safe_str(client_data.get("codigo_cliente"))
                if not code:
                    continue

                if code in existing:
                    cliente = existing[code]
                    self._update_cliente_from_dict(cliente, client_data)
                    cliente.activo_en_cartera = True
                    cliente.motivo_baja = None
                    cliente.fecha_baja = None
                    cliente.fecha_actualizacion = datetime.now()
                else:
                    cliente = self._dict_to_cliente(client_data, campana_id)
                    cliente.activo_en_cartera = True
                    session.add(cliente)
                    existing[code] = cliente

            def _archive_cliente(cliente: Cliente) -> None:
                cliente.activo_en_cartera = False
                cliente.motivo_baja = MOTIVO_BAJA_EXCEL_BANCO
                cliente.fecha_baja = datetime.now()
                if ultimo_excel:
                    cliente.ultimo_excel = ultimo_excel
                cliente.fecha_actualizacion = datetime.now()

            # Archive via Firestore diff (primary path when cartera was distributed)
            if change_report is not None:
                for section in change_report.sections.values():
                    for removed in section.removed_clients:
                        code = safe_str(removed.get("codigo_cliente"))
                        if not code or code in excel_codes:
                            continue
                        cliente = existing.get(code)
                        if cliente is None:
                            continue
                        _archive_cliente(cliente)

            # Archive any local row absent from Excel (e.g. never uploaded to Firestore)
            for code, cliente in existing.items():
                if code in excel_codes:
                    continue
                if not getattr(cliente, "activo_en_cartera", True):
                    continue
                _archive_cliente(cliente)

            # Campaign totals: active clients only (matches bank Excel)
            activos = [
                c for c in existing.values()
                if getattr(c, "activo_en_cartera", True)
            ]
            campana.total_clientes = len(activos)
            campana.total_secciones = summary.get("total_secciones", 0)
            campana.deuda_total_asignada = sum(
                c.importe_deuda_asignada or 0.0 for c in activos
            )
            campana.deuda_total_pendiente = sum(
                c.importe_deuda_pendiente or 0.0 for c in activos
            )
            if ultimo_excel:
                campana.archivo_origen = f"(actualizado) {ultimo_excel}"
            else:
                campana.archivo_origen = f"(actualizado) {campana.archivo_origen}"

            session.commit()

        self.sync_campana_banco_meta(campana_id)

    def _update_cliente_from_dict(self, cliente: Cliente, d: dict) -> None:
        """Update a Cliente ORM object from a parsed Excel dict.
        Only updates bank-provided fields, preserving management fields."""
        cliente.digito_control = safe_str(d.get("digito_control"))
        cliente.numero_documento = safe_str(d.get("numero_documento"))
        cliente.nombres = safe_str(d.get("nombres"))
        cliente.apellido_paterno = safe_str(d.get("apellido_paterno"))
        cliente.apellido_materno = safe_str(d.get("apellido_materno"))
        cliente.nombre_completo = safe_str(d.get("nombre_completo"))
        cliente.genero = safe_str(d.get("genero"))
        cliente.edad = safe_int(d.get("edad"))
        cliente.telefono_fijo = safe_str(d.get("telefono_fijo"))
        cliente.telefono_trabajo = safe_str(d.get("telefono_trabajo"))
        if not (cliente.fecha_actualizacion_contacto_iso or "").strip():
            cliente.telefono_movil = safe_str(d.get("telefono_movil"))
        cliente.correo = safe_str(d.get("correo"))
        cliente.departamento = safe_str(d.get("departamento"))
        cliente.provincia = safe_str(d.get("provincia"))
        cliente.distrito = safe_str(d.get("distrito"))
        if not (cliente.fecha_actualizacion_contacto_iso or "").strip():
            cliente.direccion = safe_str(d.get("direccion"))
        cliente.referencia = safe_str(d.get("referencia"))
        cliente.coordenada_x = safe_float(d.get("coordenada_x"))
        cliente.coordenada_y = safe_float(d.get("coordenada_y"))
        cliente.segmentacion = safe_str(d.get("segmentacion"))
        cliente.segmento_cartera = safe_str(d.get("segmento_cartera"))
        cliente.etapa_deuda = safe_str(d.get("etapa_deuda"))
        cliente.cobrador = safe_str(d.get("cobrador"))
        cliente.campana_banco = safe_str(d.get("campana"))
        cliente.region = safe_str(d.get("region"))
        cliente.zona = safe_str(d.get("zona"))
        cliente.seccion = safe_str(d.get("seccion"))
        cliente.territorio = safe_str(d.get("territorio"))
        cliente.perfil_score = safe_str(d.get("perfil_score"))
        cliente.fecha_documento = safe_str(d.get("fecha_documento"))
        cliente.fecha_vencimiento = safe_str(d.get("fecha_vencimiento"))
        cliente.fecha_asignacion = safe_str(d.get("fecha_asignacion"))
        cliente.fecha_cierre = safe_str(d.get("fecha_cierre"))
        fa = parse_excel_fecha(d.get("fecha_asignacion"))
        if fa:
            cliente.fecha_asignacion_dt = fa
        fc = parse_excel_fecha(d.get("fecha_cierre"))
        if fc:
            cliente.fecha_cierre_dt = fc
        cliente.dias_atraso = safe_int(d.get("dias_atraso"))
        cliente.importe_deuda_original = safe_float(d.get("importe_deuda_original"))
        cliente.importe_abonos_anteriores = safe_float(d.get("importe_abonos_anteriores"))
        cliente.importe_deuda_asignada = safe_float(d.get("importe_deuda_asignada"))
        cliente.importe_deuda_pendiente = safe_float(d.get("importe_deuda_pendiente"))
        # estado_gestion, nota_gestor, tramo_actual are NOT overwritten

    # ─────────────────────────────────────────────────────────────
    #  2. TRAMO EVALUATION
    # ─────────────────────────────────────────────────────────────

    def evaluate_tramos(
        self,
        campana_id: str | None = None,
        dia_override: int | None = None,
        auto_apply: bool = True,
        firebase_service=None,
        admin_email: str = "",
        admin_name: str = "",
    ) -> EvaluationResult:
        """
        Evaluate all clients in the campaign and advance tramos.

        Args:
            campana_id: Specific campaign or None for active one.
            dia_override: Force day number (for simulation).
            auto_apply: Apply tramo transitions immediately.

        Returns:
            EvaluationResult with all actions taken/pending.
        """
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                result = EvaluationResult(
                    campana_id=campana_id or "N/A", dia_campana=0
                )
                result.errores.append("No se encontró campaña activa.")
                return result

            result = self.tramo_engine.evaluate_campaign(
                session, campana, dia_override=dia_override
            )

            if auto_apply and (
                result.transiciones
                or result.cartas_pendientes
                or result.cambios_ciclo
                or result.pasos_a_campo
            ):
                self.tramo_engine.apply_transitions(session, result)
                self.tramo_engine.apply_cycle_changes(session, result)
                # Do not pre-register due letters here. A pending carta must remain
                # eligible for the publication workflow until it is actually
                # published (or explicitly recorded as omitted).

            if auto_apply and result.pasos_a_campo and firebase_service:
                self.sync_call_to_campo_firestore(
                    campana.id,
                    result.pasos_a_campo,
                    firebase_service,
                    admin_email=admin_email,
                    admin_name=admin_name,
                )

        logger.info("Tramo evaluation complete:\n%s", result.resumen)
        return result

    def distribute_call_center(
        self,
        campana_id: str | None = None,
        gestores_firestore: list | None = None,
        *,
        rebalance_all: bool = False,
        firebase_service=None,
        auto_publish: bool = True,
        admin_uid: str = "",
        admin_nombre: str = "",
    ) -> DistributionResult:
        """Reparte cuentas tramo 1 entre gestores de call center (LPT por monto)."""
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                r = DistributionResult(campana_id=campana_id or "N/A")
                r.errores.append("No se encontró campaña activa.")
                return r
            gestores = filter_call_gestores(gestores_firestore or [])
            result = distribute_tramo1(
                session,
                campana.id,
                gestores,
                only_unassigned=not rebalance_all,
            )

        if (
            auto_publish
            and firebase_service
            and not result.errores
            and result.cambios
        ):
            result.firebase_publish = self.publish_call_distribution(
                result.campana_id,
                cambios=result.cambios,
                tipo=result.tipo or "reparto_inicial",
                motivo=result.motivo,
                algoritmo="LPT",
                firebase_service=firebase_service,
                admin_uid=admin_uid,
                admin_nombre=admin_nombre,
            )
        return result

    def preview_call_center_distribution(
        self,
        campana_id: str | None = None,
        gestores_firestore: list | None = None,
        *,
        rebalance_all: bool = False,
    ):
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                from .call_center_service import DistributionResult
                r = DistributionResult(campana_id=campana_id or "N/A")
                r.errores.append("No se encontró campaña activa.")
                return r
            gestores = filter_call_gestores(gestores_firestore or [])
            return preview_distribution(
                session,
                campana.id,
                gestores,
                only_unassigned=not rebalance_all,
            )

    def build_reparto_plan_for_campaign(
        self,
        campana_id: str | None = None,
        gestores_firestore: list | None = None,
        *,
        overrides: dict[str, str] | None = None,
        seccion_keys_anteriores: dict[str, str] | None = None,
    ):
        from .reparto_planner import build_reparto_plan

        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                from .reparto_planner import RepartoPlan
                p = RepartoPlan(campana_id=campana_id or "N/A")
                p.errores.append("No se encontró campaña activa.")
                return p
            return build_reparto_plan(
                session,
                campana.id,
                gestores_firestore or [],
                overrides=overrides,
                seccion_keys_anteriores=seccion_keys_anteriores,
            )

    def apply_reparto_plan(
        self,
        campana_id: str,
        plan,
        *,
        admin_uid: str = "",
        admin_nombre: str = "",
    ) -> list:
        """
        Persiste asignaciones call del plan en SQLite (nuevos, huérfanos, overrides).
        """
        from .reparto_planner import NUEVO, REASIGNADO_HUERFANO, OVERRIDE_MANUAL
        from .call_center_service import CallAssignmentChange, RAZON_LPT_NUEVAS, RAZON_REASIGNACION_MANUAL

        cambios: list[CallAssignmentChange] = []
        override_codes = set(plan.overrides or {})

        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.activo_en_cartera.is_(True),
                )
                .all()
            )
            by_codigo = {c.codigo_cliente: c for c in rows if c.codigo_cliente}

            for row in plan.clientes:
                needs_write = (
                    row.estado_afinidad in (NUEVO, REASIGNADO_HUERFANO, OVERRIDE_MANUAL)
                    or row.codigo_cliente in override_codes
                )
                if not needs_write or not row.call_gestor_uid:
                    continue
                cliente = by_codigo.get(row.codigo_cliente)
                if cliente is None:
                    continue
                prev_uid = cliente.call_gestor_uid or ""
                prev_nombre = cliente.call_gestor_nombre or ""
                if prev_uid == row.call_gestor_uid:
                    continue

                cliente.call_gestor_uid = row.call_gestor_uid
                cliente.call_gestor_nombre = row.call_gestor_nombre
                cliente.fecha_actualizacion = datetime.now()

                razon = RAZON_LPT_NUEVAS
                if row.codigo_cliente in override_codes:
                    razon = RAZON_REASIGNACION_MANUAL.format(
                        nombre_destino=row.call_gestor_nombre,
                    )

                cambios.append(CallAssignmentChange(
                    codigo_cliente=row.codigo_cliente,
                    nombre=row.nombre,
                    importe=row.importe,
                    gestor_anterior_uid=prev_uid,
                    gestor_anterior_nombre=prev_nombre,
                    gestor_nuevo_uid=row.call_gestor_uid,
                    gestor_nuevo_nombre=row.call_gestor_nombre,
                    razon=razon,
                ))

            session.commit()

        if cambios:
            self._save_call_distribution_history(
                campana_id,
                tipo="reparto_afinidad",
                motivo="Plan de reparto con afinidad (pre-publicación)",
                algoritmo="LPT+afinidad",
                cambios=cambios,
                admin_uid=admin_uid,
                admin_nombre=admin_nombre,
                firebase_ok=False,
            )
        return cambios

    def reconcile_call_sections_after_update(
        self,
        campana_id: str,
        plan,
        firebase_service,
        cambios: list | None = None,
    ) -> dict:
        """
        Re-publica secciones _CALL_* afectadas tras upload territorial.
        """
        from .database import make_call_section_key, FASE_GESTION_CALL

        result: dict[str, Any] = {
            "success": False,
            "uploaded": 0,
            "errors": [],
        }
        if not firebase_service or not getattr(firebase_service, "_initialized", False):
            result["errors"].append("Firebase no conectado.")
            return result

        affected_uids: set[str] = set()
        for ch in cambios or []:
            if ch.gestor_nuevo_uid:
                affected_uids.add(ch.gestor_nuevo_uid)
            if ch.gestor_anterior_uid:
                affected_uids.add(ch.gestor_anterior_uid)

        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.fase_gestion == FASE_GESTION_CALL,
                    Cliente.activo_en_cartera.is_(True),
                    Cliente.call_gestor_uid.isnot(None),
                    Cliente.call_gestor_uid != "",
                )
                .all()
            )
        for c in rows:
            if c.call_gestor_uid:
                affected_uids.add(c.call_gestor_uid)

        if not affected_uids:
            result["success"] = True
            result["detail"] = "Sin secciones call que reconciliar."
            return result

        section_keys = {make_call_section_key(uid) for uid in affected_uids}
        try:
            if cambios:
                pub = self.publish_call_distribution(
                    campana_id,
                    cambios=cambios,
                    tipo="reparto_afinidad",
                    motivo="Reconciliación call tras actualización Excel",
                    algoritmo="LPT+afinidad",
                    firebase_service=firebase_service,
                )
                result["uploaded"] = pub.get("uploaded", 0)
                result["errors"].extend(pub.get("errors") or [])
                result["success"] = pub.get("success", False)
            else:
                by_seccion = self.build_call_sections_payload(campana_id, section_keys)
                tramo_info = self.build_etapa_summary(campana_id)
                upload_res = firebase_service.upload_cartera_sections(
                    by_seccion,
                    campaign_id="cartera_activa",
                    section_keys=section_keys,
                    tramo_info=tramo_info,
                )
                result["uploaded"] = upload_res.get("total_uploaded", 0)
                result["errors"].extend(upload_res.get("errors") or [])
                result["success"] = not result["errors"]
        except Exception as e:
            result["errors"].append(str(e))

        return result

    def get_call_center_status(
        self,
        campana_id: str | None = None,
        gestores_firestore: list | None = None,
    ) -> dict:
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return {"gestores": [], "sin_asignar": 0, "total_tramo1_call": 0}
            gestores = filter_call_gestores(gestores_firestore or [])
            return get_call_center_summary(session, campana.id, gestores)

    def get_call_center_dashboard(
        self,
        campana_id: str | None = None,
        gestores_firestore: list | None = None,
    ) -> dict:
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return {
                    "gestores": [], "sin_asignar": 0, "total_tramo1_call": 0,
                    "monto_total_call": 0.0,
                }
            gestores = filter_call_gestores(gestores_firestore or [])
            return get_call_center_dashboard(session, campana.id, gestores)

    def get_call_gestor_clients(
        self,
        gestor_uid: str,
        campana_id: str | None = None,
    ) -> list[dict]:
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None or not gestor_uid:
                return []
            return get_clients_for_call_gestor(session, campana.id, gestor_uid)

    def reassign_call_client(
        self,
        cliente_id: int,
        new_uid: str,
        new_nombre: str,
        campana_id: str | None = None,
        *,
        firebase_service=None,
        auto_publish: bool = True,
        admin_uid: str = "",
        admin_nombre: str = "",
    ) -> tuple[bool, str, CallAssignmentChange | None]:
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return False, "No hay campaña activa.", None
            ok, msg, change = reassign_call_client(
                session, campana.id, cliente_id, new_uid, new_nombre,
            )
            camp_id = campana.id

        if ok and auto_publish and firebase_service and change:
            self.publish_call_distribution(
                camp_id,
                cambios=[change],
                tipo="reasignacion_manual",
                motivo=MOTIVO_REASIGNACION_MANUAL,
                algoritmo="manual",
                firebase_service=firebase_service,
                admin_uid=admin_uid,
                admin_nombre=admin_nombre,
            )
        return ok, msg, change

    def build_call_sections_payload(
        self,
        campana_id: str,
        section_keys: set[str] | list[str],
    ) -> dict[str, list]:
        """Payload Firebase filtrado a secciones call virtuales."""
        keys = set(section_keys)
        payload = self.get_firebase_payload(campana_id)
        return {
            k: v for k, v in payload.get("by_seccion", {}).items() if k in keys
        }

    def publish_call_distribution(
        self,
        campana_id: str,
        *,
        cambios: list[CallAssignmentChange],
        tipo: str,
        motivo: str,
        algoritmo: str,
        firebase_service,
        admin_uid: str = "",
        admin_nombre: str = "",
    ) -> dict:
        """
        Publica reparto call en Firestore, registra historial y notifica gestores.
        """
        import json
        from .database import HistorialRepartoCall

        result: dict[str, Any] = {
            "success": False,
            "moved": 0,
            "uploaded": 0,
            "notifications": 0,
            "errors": [],
        }
        if not cambios:
            result["success"] = True
            result["detail"] = "Sin cambios que publicar."
            return result
        if not firebase_service or not getattr(firebase_service, "_initialized", False):
            result["errors"].append("Firebase no está conectado.")
            self._save_call_distribution_history(
                campana_id, tipo, motivo, algoritmo, cambios,
                admin_uid, admin_nombre, firebase_ok=False,
                firebase_error="Firebase no conectado",
            )
            return result

        campaign_fs_id = "cartera_activa"
        admin_email = admin_uid or "sistema@antcobranzas"

        affected_uids: set[str] = set()
        for ch in cambios:
            if ch.gestor_nuevo_uid:
                affected_uids.add(ch.gestor_nuevo_uid)
            if ch.gestor_anterior_uid:
                affected_uids.add(ch.gestor_anterior_uid)

        section_keys = {make_call_section_key(uid) for uid in affected_uids if uid}

        for ch in cambios:
            if (
                ch.gestor_anterior_uid
                and ch.gestor_nuevo_uid
                and ch.gestor_anterior_uid != ch.gestor_nuevo_uid
            ):
                from_sec = make_call_section_key(ch.gestor_anterior_uid)
                to_sec = make_call_section_key(ch.gestor_nuevo_uid)
                move_res = firebase_service.update_client_zone(
                    campaign_fs_id,
                    from_sec,
                    ch.codigo_cliente,
                    to_sec,
                    admin_email=admin_email,
                    admin_name=admin_nombre or "Sistema",
                    motivo="reparto_call_center",
                    extra_fields={
                        "call_gestor_uid": ch.gestor_nuevo_uid,
                        "call_gestor_nombre": ch.gestor_nuevo_nombre,
                        "fase_gestion": FASE_GESTION_CALL,
                    },
                )
                if move_res.get("success"):
                    result["moved"] += 1
                elif "no encontrado" not in str(move_res.get("error", "")).lower():
                    result["errors"].append(
                        f"{ch.codigo_cliente}: {move_res.get('error', 'error moviendo')}"
                    )

        try:
            by_seccion = self.build_call_sections_payload(campana_id, section_keys)
            tramo_info = self.build_etapa_summary(campana_id)
            upload_res = firebase_service.upload_cartera_sections(
                by_seccion,
                campaign_id=campaign_fs_id,
                section_keys=section_keys,
                tramo_info=tramo_info,
            )
            result["uploaded"] = upload_res.get("total_uploaded", 0)
            result["errors"].extend(upload_res.get("errors") or [])
        except Exception as e:
            result["errors"].append(str(e))

        by_gestor_notify = self._group_call_changes_for_notify(cambios)
        try:
            notif = firebase_service.notify_call_repartition(
                campaign_id=campaign_fs_id,
                motivo=motivo,
                tipo=tipo,
                by_gestor=by_gestor_notify,
            )
            result["notifications"] = notif.get("sent", 0)
            result["errors"].extend(notif.get("errors") or [])
        except Exception as e:
            result["errors"].append(f"Notificaciones: {e}")

        firebase_ok = not result["errors"]
        result["success"] = firebase_ok or result["uploaded"] > 0 or result["moved"] > 0
        err_text = "; ".join(result["errors"]) if result["errors"] else ""

        hist_id = self._save_call_distribution_history(
            campana_id, tipo, motivo, algoritmo, cambios,
            admin_uid, admin_nombre,
            firebase_ok=result["success"],
            firebase_error=err_text or None,
        )
        result["historial_id"] = hist_id

        monto = sum(ch.importe for ch in cambios)
        self._record_sync(
            "call_distribution_upload",
            len(cambios),
            "ok" if result["success"] else "parcial",
            f"{tipo}: {len(cambios)} cuentas, S/ {monto:,.2f}",
        )
        return result

    def _group_call_changes_for_notify(
        self, cambios: list[CallAssignmentChange],
    ) -> dict[str, dict]:
        grouped: dict[str, dict] = {}
        for ch in cambios:
            uid = ch.gestor_nuevo_uid
            if not uid:
                continue
            if uid not in grouped:
                grouped[uid] = {
                    "nombre": ch.gestor_nuevo_nombre,
                    "nuevas_cuentas": 0,
                    "monto_nuevo": 0.0,
                    "detalles": [],
                }
            g = grouped[uid]
            g["nuevas_cuentas"] += 1
            g["monto_nuevo"] += ch.importe
            g["detalles"].append({
                "codigo": ch.codigo_cliente,
                "nombre": ch.nombre,
                "importe": ch.importe,
                "razon": ch.razon,
            })
        return grouped

    def _save_call_distribution_history(
        self,
        campana_id: str,
        tipo: str,
        motivo: str,
        algoritmo: str,
        cambios: list[CallAssignmentChange],
        admin_uid: str,
        admin_nombre: str,
        *,
        firebase_ok: bool,
        firebase_error: str | None = None,
    ) -> int | None:
        import json
        from .database import HistorialRepartoCall

        balances_before: dict[str, dict] = {}
        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.fase_gestion == FASE_GESTION_CALL,
                    Cliente.call_gestor_uid.isnot(None),
                    Cliente.call_gestor_uid != "",
                    Cliente.activo_en_cartera.is_(True),
                )
                .all()
            )
        for c in rows:
            uid = c.call_gestor_uid or ""
            if uid not in balances_before:
                balances_before[uid] = {
                    "nombre": c.call_gestor_nombre or uid,
                    "cuentas": 0,
                    "monto": 0.0,
                }
            balances_before[uid]["cuentas"] += 1
            balances_before[uid]["monto"] += float(c.importe_deuda_pendiente or 0)

        resumen_gestores: list[dict] = []
        grouped_after: dict[str, dict] = self._group_call_changes_for_notify(cambios)
        all_uids = set(balances_before) | set(grouped_after)
        for uid in all_uids:
            antes = balances_before.get(uid, {"cuentas": 0, "monto": 0.0, "nombre": uid})
            nuevas = grouped_after.get(uid, {})
            resumen_gestores.append({
                "uid": uid,
                "nombre": nuevas.get("nombre") or antes.get("nombre") or uid,
                "cuentas_antes": antes.get("cuentas", 0),
                "cuentas_nuevas": nuevas.get("nuevas_cuentas", 0),
                "monto_nuevo": nuevas.get("monto_nuevo", 0.0),
            })

        detalle = {
            "cambios": [c.to_dict() for c in cambios],
            "resumen_gestores": resumen_gestores,
        }
        monto_afectado = sum(c.importe for c in cambios)
        try:
            with self.db.session() as session:
                row = HistorialRepartoCall(
                    campana_id=campana_id,
                    fecha=datetime.now(),
                    tipo=tipo,
                    motivo=motivo,
                    algoritmo=algoritmo,
                    admin_uid=admin_uid or None,
                    admin_nombre=admin_nombre or None,
                    cuentas_afectadas=len(cambios),
                    monto_afectado=monto_afectado,
                    detalle_json=json.dumps(detalle, ensure_ascii=False),
                    firebase_ok=firebase_ok,
                    firebase_error=firebase_error,
                )
                session.add(row)
                session.commit()
                return row.id
        except Exception as e:
            logger.warning("Could not save call distribution history: %s", e)
            return None

    def get_call_distribution_history(
        self,
        campana_id: str | None = None,
        *,
        limit: int = 20,
    ) -> list[dict]:
        import json
        from .database import HistorialRepartoCall

        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return []
            rows = (
                session.query(HistorialRepartoCall)
                .filter(HistorialRepartoCall.campana_id == campana.id)
                .order_by(HistorialRepartoCall.fecha.desc())
                .limit(limit)
                .all()
            )
            out = []
            for r in rows:
                detalle = {}
                try:
                    detalle = json.loads(r.detalle_json or "{}")
                except Exception:
                    pass
                out.append({
                    "id": r.id,
                    "fecha": r.fecha.isoformat() if r.fecha else "",
                    "tipo": r.tipo,
                    "motivo": r.motivo,
                    "algoritmo": r.algoritmo,
                    "admin_nombre": r.admin_nombre or "",
                    "cuentas_afectadas": r.cuentas_afectadas,
                    "monto_afectado": r.monto_afectado,
                    "firebase_ok": r.firebase_ok,
                    "firebase_error": r.firebase_error or "",
                    "detalle": detalle,
                })
            return out

    def get_operational_status(
        self,
        campana_id: str | None = None,
        *,
        gestores_firestore: list | None = None,
        firebase_connected: bool = False,
    ) -> dict:
        """Estado operativo para checklist en Inicio."""
        from .database import SyncLog, HistorialRepartoCall

        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return {"items": [], "all_ok": False}

            cid = campana.id
            gestores = filter_call_gestores(gestores_firestore or [])
            dash = get_call_center_dashboard(session, cid, gestores)

            last_upload = (
                session.query(SyncLog)
                .filter(SyncLog.tipo.in_(("upload", "call_distribution_upload")))
                .order_by(SyncLog.fecha.desc())
                .first()
            )
            last_visits = (
                session.query(SyncLog)
                .filter(SyncLog.tipo == "visits_only")
                .order_by(SyncLog.fecha.desc())
                .first()
            )
            last_call_pub = (
                session.query(HistorialRepartoCall)
                .filter(
                    HistorialRepartoCall.campana_id == cid,
                    HistorialRepartoCall.firebase_ok.is_(True),
                )
                .order_by(HistorialRepartoCall.fecha.desc())
                .first()
            )

        def _fmt_sync(entry) -> str:
            if not entry or not entry.fecha:
                return "Nunca"
            return entry.fecha.strftime("%d/%m/%Y %H:%M")

        sin_asignar = dash.get("sin_asignar", 0)
        total_call = dash.get("total_tramo1_call", 0)

        items = [
            {
                "id": "excel",
                "label": "Campaña activa",
                "status": "ok",
                "detail": campana.nombre,
            },
            {
                "id": "firebase",
                "label": "Firebase conectado",
                "status": "ok" if firebase_connected else "error",
                "detail": "Conectado" if firebase_connected else "Sin conexión",
            },
            {
                "id": "upload",
                "label": "Cartera publicada en Firebase",
                "status": "ok" if last_upload else "warn",
                "detail": _fmt_sync(last_upload),
            },
            {
                "id": "call_reparto",
                "label": "Call center repartido",
                "status": (
                    "ok" if total_call > 0 and sin_asignar == 0
                    else "warn" if total_call == 0
                    else "error"
                ),
                "detail": (
                    f"{sin_asignar} sin asignar de {total_call}"
                    if total_call else "Sin cuentas call en tramo 1"
                ),
            },
            {
                "id": "call_firebase",
                "label": "Call publicado en Firebase",
                "status": "ok" if last_call_pub else "warn",
                "detail": _fmt_sync(last_call_pub),
            },
            {
                "id": "sync_visits",
                "label": "Última sync visitas",
                "status": "ok" if last_visits else "warn",
                "detail": _fmt_sync(last_visits),
            },
        ]

        all_ok = all(i["status"] == "ok" for i in items)
        return {"items": items, "all_ok": all_ok, "call_dashboard": dash}

    def get_campaign_readiness(
        self,
        campana_id: str | None = None,
        *,
        gestores_firestore: list | None = None,
        firebase_connected: bool = False,
    ) -> dict:
        """Pasos del asistente de publicación de campaña."""
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return {
                    "steps": [],
                    "blockers": ["No hay campaña activa. Cargue un Excel primero."],
                    "can_publish": False,
                }
            cid = campana.id
            stats = self.get_campaign_stats(cid)

        gestores = gestores_firestore or []
        call_gestores = filter_call_gestores(gestores)
        field_gestores = [
            g for g in gestores
            if g.get("rol") == "gestor" and g.get("activo", True) and g.get("canal") != "call"
        ]
        field_with_sections = [
            g for g in field_gestores if g.get("secciones")
        ]

        op = self.get_operational_status(
            cid, gestores_firestore=gestores, firebase_connected=firebase_connected,
        )
        dash = op.get("call_dashboard", {})
        sin_asignar = dash.get("sin_asignar", 0)
        last_call_pub = any(
            i["id"] == "call_firebase" and i["status"] == "ok"
            for i in op.get("items", [])
        )

        steps = [
            {
                "id": "data",
                "label": "1. Verificar datos de campaña",
                "status": "ok",
                "detail": f"{stats.get('total_clientes', 0)} clientes · "
                          f"{stats.get('total_secciones', 0)} secciones",
                "action_key": None,
            },
            {
                "id": "tramos",
                "label": "2. Evaluar tramos",
                "status": "warn",
                "detail": "Ejecute evaluación de tramos en Campaña o desde este asistente",
                "action_key": "evaluate_tramos",
            },
            {
                "id": "team",
                "label": "3. Equipo listo",
                "status": (
                    "ok" if call_gestores and field_with_sections
                    else "error"
                ),
                "detail": (
                    f"{len(call_gestores)} operadores call · "
                    f"{len(field_with_sections)} gestores campo con sección"
                ),
                "action_key": "open_team",
            },
            {
                "id": "call_distribute",
                "label": "4. Reparto call center",
                "status": (
                    "ok" if sin_asignar == 0 and last_call_pub
                    else "warn" if sin_asignar > 0
                    else "ok" if last_call_pub
                    else "warn"
                ),
                "detail": (
                    f"{sin_asignar} cuentas sin asignar"
                    if sin_asignar else "Reparto publicado en Firebase"
                ),
                "action_key": "call_distribute",
            },
            {
                "id": "upload",
                "label": "5. Subir cartera completa",
                "status": "ok" if firebase_connected else "error",
                "detail": "Publicar toda la cartera a Firebase" if firebase_connected
                          else "Conecte Firebase primero",
                "action_key": "upload_full",
            },
        ]

        blockers = []
        if not firebase_connected:
            blockers.append("Firebase no conectado.")
        if not call_gestores:
            blockers.append("Cree al menos un gestor con canal «call».")
        if sin_asignar > 0:
            blockers.append(f"Quedan {sin_asignar} cuentas call sin asignar.")

        can_publish = firebase_connected and bool(call_gestores)
        return {
            "steps": steps,
            "blockers": blockers,
            "can_publish": can_publish,
            "campana_id": cid,
        }

    def sync_call_to_campo_firestore(
        self,
        campana_id: str,
        pasos: list,
        firebase_service,
        *,
        admin_email: str = "",
        admin_name: str = "",
    ) -> int:
        """Mueve clientes de sección call virtual a sección territorial en Firestore."""
        if not pasos or not firebase_service:
            return 0
        moved = 0
        campaign_fs_id = "cartera_activa"
        for paso in pasos:
            from_sec = paso.seccion_call or make_call_section_key(paso.call_gestor_uid_anterior or "")
            to_sec = paso.seccion_territorial
            if not from_sec or not to_sec or from_sec == to_sec:
                continue
            result = firebase_service.update_client_zone(
                campaign_fs_id,
                from_sec,
                paso.codigo_cliente,
                to_sec,
                admin_email=admin_email or "sistema@antcobranzas",
                admin_name=admin_name or "Sistema",
                motivo="pase_automatico_call_a_campo",
                extra_fields={
                    "fase_gestion": FASE_GESTION_CAMPO,
                    "call_gestor_uid": "",
                    "call_gestor_nombre": "",
                    "seccion_key_origen": to_sec,
                },
            )
            if result.get("success"):
                moved += 1
            else:
                logger.warning(
                    "Failed to move %s from %s to %s: %s",
                    paso.codigo_cliente, from_sec, to_sec, result.get("error"),
                )
        return moved

    def build_etapa_summary(self, campana_id: str) -> dict:
        """Conteos por etapa y ciclo para metadata de Firestore."""
        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                return {}
            clientes = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.activo_en_cartera.is_(True),
                )
                .all()
            )
            por_etapa = {1: 0, 2: 0, 3: 0}
            por_estado_ciclo = {
                EstadoCiclo.ACTIVA.value: 0,
                EstadoCiclo.CERRADA.value: 0,
                EstadoCiclo.RETORNADA_BANCO.value: 0,
            }
            gestion_especial = 0
            for c in clientes:
                t = c.tramo_actual
                if t in por_etapa:
                    por_etapa[t] += 1
                ec = c.estado_ciclo or EstadoCiclo.ACTIVA.value
                por_estado_ciclo[ec] = por_estado_ciclo.get(ec, 0) + 1
                if c.gestion_especial:
                    gestion_especial += 1
            cfg = ConfigCampana.get_or_create(session)
            return {
                "dia_actual": campana.dia_actual,
                "campana_sqlite_id": campana_id,
                "duracion_ciclo": cfg.duracion_dias,
                "por_etapa": por_etapa,
                "por_estado_ciclo": por_estado_ciclo,
                "gestion_especial": gestion_especial,
                "modo_ciclo": "por_cuenta",
            }

    # ─────────────────────────────────────────────────────────────
    #  3. DATA ACCESS  (for UI and sync)
    # ─────────────────────────────────────────────────────────────

    def get_active_campaign(self) -> Campana | None:
        """Return the active campaign or None."""
        return self.db.get_active_campana()

    def get_clients_by_section(
        self,
        campana_id: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return clients grouped by composite section key (region_zona_seccion).
        Maintains backward compatibility with existing UI code.
        """
        with self.db.session() as session:
            clientes = (
                session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
                .order_by(Cliente.seccion, Cliente.codigo_cliente)
                .all()
            )
            by_seccion: Dict[str, list] = {}
            for c in clientes:
                sec_key = make_seccion_key(
                    c.region or "", c.zona or "", c.seccion or "SIN_SECCION"
                )
                if sec_key not in by_seccion:
                    by_seccion[sec_key] = []
                by_seccion[sec_key].append(self._cliente_to_dict(c))
            return by_seccion

    def get_all_clients(
        self,
        campana_id: str,
    ) -> List[Dict[str, Any]]:
        """Return all clients as dicts for a campaign."""
        with self.db.session() as session:
            clientes = (
                session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
                .order_by(Cliente.seccion, Cliente.codigo_cliente)
                .all()
            )
            return [self._cliente_to_dict(c) for c in clientes]

    def get_campaign_stats(
        self,
        campana_id: str,
        *,
        campana_banco: str | None = None,
    ) -> dict:
        """Get summary statistics for a campaign."""
        return self.db.get_stats(campana_id, campana_banco=campana_banco)

    def get_stats_by_campana_banco(self, campana_id: str) -> list[dict]:
        """Lista comparativa de KPIs por número de campaña del banco."""
        stats = self.db.get_stats(campana_id)
        por_cb = stats.get("por_campana_banco") or {}
        rows = []
        for key in sorted(por_cb.keys(), key=lambda k: (k == SIN_CAMPANA_KEY, k)):
            bucket = por_cb[key]
            asignada = float(bucket.get("asignada") or 0)
            recuperada = float(bucket.get("recuperada") or 0)
            pct = round(recuperada / asignada * 100) if asignada else 0
            rows.append({
                "key": key,
                "label": bucket.get("label") or display_label_for_key(key),
                "cuentas": int(bucket.get("cuentas") or 0),
                "asignada": asignada,
                "recuperada": recuperada,
                "pct_recuperacion": pct,
                "por_etapa_recuperacion": bucket.get("por_etapa_recuperacion") or {},
            })
        return rows

    def filter_firebase_status(
        self,
        data: dict,
        campana_banco: str | None,
    ) -> dict:
        """
        Filtra clientes en payload get_campaign_status y recalcula resumen.
        """
        if campana_banco is None:
            return data

        secciones = data.get("secciones") or {}
        filtered_secciones: dict[str, dict] = {}
        resumen = {
            "total": 0,
            "pendiente": 0,
            "visitado_habido": 0,
            "visitado_no_habido": 0,
            "fallecido_inubicable": 0,
            "suplantacion": 0,
            "pago_no_registrado": 0,
            "deuda_total": 0.0,
            "deuda_visitada": 0.0,
        }

        for sec_id, sec in secciones.items():
            clients = sec.get("clientes") or []
            filtered = apply_campana_banco_filter(clients, campana_banco)
            if not filtered:
                continue
            filtered_secciones[sec_id] = {
                **sec,
                "clientes": filtered,
            }
            for c in filtered:
                estado = c.get("estado_gestion", "pendiente")
                deuda = float(c.get("importe_deuda_asignada", 0) or 0)
                resumen["deuda_total"] += deuda
                resumen["total"] += 1
                if estado in resumen:
                    resumen[estado] += 1
                else:
                    resumen["pendiente"] += 1
                if estado != "pendiente":
                    resumen["deuda_visitada"] += deuda

        return {
            **data,
            "secciones": filtered_secciones,
            "resumen": resumen,
            "campana_banco_filtro": campana_banco,
        }

    def distinct_campana_banco_for_campaign(self, campana_id: str) -> list[str]:
        """Valores distintos de campana_banco en una campaña SQLite."""
        clients = self.get_all_clients(campana_id)
        return distinct_campana_banco_values(clients)

    def sync_campana_banco_meta(self, campana_id: str) -> None:
        """Recalcula fechas detectadas por campaña banco desde clientes activos."""
        load_config()
        with self.db.session() as session:
            cfg = ConfigCampana.get_or_create(session)
            duracion = cfg.duracion_dias or 59
            clientes = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.activo_en_cartera.is_(True),
                )
                .all()
            )
            groups: dict[str, list[Cliente]] = {}
            for c in clientes:
                key = campana_banco_key_from_value(c.campana_banco)
                groups.setdefault(key, []).append(c)

            now = datetime.now()
            for key, rows in groups.items():
                fa_list = [c.get_fecha_asignacion_date() for c in rows]
                fc_list = [c.fecha_cierre_dt for c in rows]
                inicio_d, fin_d = compute_detected_dates_for_group(
                    fa_list, fc_list, duracion
                )
                meta = (
                    session.query(CampanaBancoMeta)
                    .filter(
                        CampanaBancoMeta.campana_id == campana_id,
                        CampanaBancoMeta.campana_banco_key == key,
                    )
                    .first()
                )
                if meta is None:
                    session.add(
                        CampanaBancoMeta(
                            campana_id=campana_id,
                            campana_banco_key=key,
                            fecha_inicio_detectada=inicio_d,
                            fecha_fin_detectada=fin_d,
                            fecha_primera_deteccion=now,
                        )
                    )
                else:
                    meta.fecha_inicio_detectada = inicio_d
                    meta.fecha_fin_detectada = fin_d
                    meta.fecha_actualizacion = now

            session.commit()

    def get_campana_banco_timelines(self, campana_id: str) -> list[dict]:
        """Metadatos + KPIs + día/tramo por campaña banco activa."""
        load_config()
        with self.db.session() as session:
            cfg = ConfigCampana.get_or_create(session)
            duracion_default = cfg.duracion_dias or 59
            carta_days = [
                cfg.carta1_dia, cfg.carta2_dia, cfg.carta3_dia,
                cfg.carta4_dia, cfg.carta5_dia,
            ]
            tramo_boundaries = {
                1: (cfg.tramo1_inicio, cfg.tramo1_fin),
                2: (cfg.tramo2_inicio, cfg.tramo2_fin),
                3: (cfg.tramo3_inicio, cfg.tramo3_fin),
            }

            clientes = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.activo_en_cartera.is_(True),
                )
                .all()
            )
            groups: dict[str, list[Cliente]] = {}
            for c in clientes:
                key = campana_banco_key_from_value(c.campana_banco)
                groups.setdefault(key, []).append(c)

            metas = {
                m.campana_banco_key: m
                for m in session.query(CampanaBancoMeta)
                .filter(CampanaBancoMeta.campana_id == campana_id)
                .all()
            }

            timelines: list[dict] = []
            for key in sorted(groups.keys()):
                rows = groups[key]
                meta = metas.get(key)
                eff = effective_campana_banco_dates(
                    fecha_inicio_manual=meta.fecha_inicio if meta else None,
                    fecha_fin_manual=meta.fecha_fin if meta else None,
                    fecha_inicio_detectada=meta.fecha_inicio_detectada if meta else None,
                    fecha_fin_detectada=meta.fecha_fin_detectada if meta else None,
                    duracion_dias=duracion_default,
                )
                dia = eff["dia_actual"]
                tramo = TramoEngine.get_tramo_for_day(dia)
                tramo_labels = {
                    TramoEnum.TRAMO_1: "Tramo 1",
                    TramoEnum.TRAMO_2: "Tramo 2",
                    TramoEnum.TRAMO_3: "Tramo 3",
                    TramoEnum.NONE: "N/A",
                }
                cuentas = len(rows)
                deuda = sum(c.importe_deuda_asignada or 0.0 for c in rows)
                timelines.append({
                    "key": key,
                    "label": display_label_for_key(key),
                    "fecha_inicio": eff["fecha_inicio"],
                    "fecha_fin": eff["fecha_fin"],
                    "fecha_inicio_detectada": (
                        meta.fecha_inicio_detectada if meta else None
                    ),
                    "fecha_fin_detectada": (
                        meta.fecha_fin_detectada if meta else None
                    ),
                    "es_manual": eff["es_manual"],
                    "dia_actual": dia,
                    "duracion": eff["duracion"],
                    "dias_restantes": eff["dias_restantes"],
                    "tramo": tramo,
                    "tramo_label": tramo_labels.get(tramo, "N/A"),
                    "cuentas": cuentas,
                    "deuda_asignada": deuda,
                    "carta_days": carta_days,
                    "tramo_boundaries": tramo_boundaries,
                })

            return timelines

    def update_campana_banco_dates(
        self,
        campana_id: str,
        campana_banco_key: str,
        *,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        restore_detected: bool = False,
    ) -> None:
        """Guarda override manual o restaura fechas detectadas del Excel."""
        with self.db.session() as session:
            meta = (
                session.query(CampanaBancoMeta)
                .filter(
                    CampanaBancoMeta.campana_id == campana_id,
                    CampanaBancoMeta.campana_banco_key == campana_banco_key,
                )
                .first()
            )
            if meta is None:
                self.sync_campana_banco_meta(campana_id)
                meta = (
                    session.query(CampanaBancoMeta)
                    .filter(
                        CampanaBancoMeta.campana_id == campana_id,
                        CampanaBancoMeta.campana_banco_key == campana_banco_key,
                    )
                    .first()
                )
            if meta is None:
                raise ValueError(
                    f"No hay metadatos para campaña banco {campana_banco_key!r}"
                )

            if restore_detected:
                meta.fecha_inicio = None
                meta.fecha_fin = None
            else:
                if fecha_inicio is not None:
                    meta.fecha_inicio = fecha_inicio
                if fecha_fin is not None:
                    meta.fecha_fin = fecha_fin
                if (
                    meta.fecha_inicio is not None
                    and meta.fecha_fin is not None
                    and meta.fecha_fin < meta.fecha_inicio
                ):
                    raise ValueError(
                        "La fecha de fin no puede ser anterior a la de inicio."
                    )

            meta.fecha_actualizacion = datetime.now()
            session.commit()

    def get_filtered_campaign_kpis(
        self,
        campana_id: str,
        campana_banco: str | None = None,
    ) -> dict:
        """KPIs del panel según filtro campana_banco (None = toda la campaña)."""
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                return {
                    "total": 0, "secciones": 0, "deuda": 0.0,
                    "dia": 1, "restantes": 0, "duracion": 59,
                }

            query = session.query(Cliente).filter(
                Cliente.campana_id == campana_id,
                Cliente.activo_en_cartera.is_(True),
            )
            if campana_banco is not None:
                if campana_banco == SIN_CAMPANA_KEY:
                    query = query.filter(
                        (Cliente.campana_banco.is_(None))
                        | (Cliente.campana_banco == "")
                    )
                else:
                    query = query.filter(Cliente.campana_banco == campana_banco)

            rows = query.all()
            total = len(rows)
            deuda = sum(c.importe_deuda_asignada or 0.0 for c in rows)
            secciones = len({c.seccion_key for c in rows if c.seccion_key})

            cfg = ConfigCampana.get_or_create(session)
            duracion_default = cfg.duracion_dias or 59

            if campana_banco is None:
                dia = campana.dia_actual
                restantes = campana.dias_restantes
                duracion = duracion_default
            else:
                meta = (
                    session.query(CampanaBancoMeta)
                    .filter(
                        CampanaBancoMeta.campana_id == campana_id,
                        CampanaBancoMeta.campana_banco_key == campana_banco,
                    )
                    .first()
                )
                eff = effective_campana_banco_dates(
                    fecha_inicio_manual=meta.fecha_inicio if meta else None,
                    fecha_fin_manual=meta.fecha_fin if meta else None,
                    fecha_inicio_detectada=(
                        meta.fecha_inicio_detectada if meta else None
                    ),
                    fecha_fin_detectada=meta.fecha_fin_detectada if meta else None,
                    duracion_dias=duracion_default,
                )
                dia = eff["dia_actual"]
                restantes = eff["dias_restantes"]
                duracion = eff["duracion"]

            return {
                "total": total,
                "secciones": secciones,
                "deuda": deuda,
                "dia": dia,
                "restantes": restantes,
                "duracion": duracion,
            }

    def distinct_seccion_keys_for_campaign(self, campana_id: str) -> list[str]:
        """Claves de sección distintas en SQLite (para reasignación)."""
        with self.db.session() as session:
            rows = (
                session.query(Cliente.seccion_key)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.seccion_key.isnot(None),
                    Cliente.seccion_key != "",
                )
                .distinct()
                .all()
            )
        return sorted({r[0] for r in rows if r[0]})

    def get_clients_page(
        self,
        campana_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
        search: str = "",
        estado: str = "",
        region: str = "",
        zona: str = "",
        seccion: str = "",
        campana_banco: str = "",
        carta_numero: int | None = None,
        formato_publicacion: str = "",
        estado_publicacion: str = "",
        gestor_publicacion: str = "",
    ) -> Dict[str, Any]:
        """
        Return one paginated page of clients for local desktop browsing.
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 1
        if page_size > 500:
            page_size = 500

        with self.db.session() as session:
            query = session.query(Cliente).filter(Cliente.campana_id == campana_id)
            query = self._apply_client_filters(
                query,
                search=search,
                estado=estado,
                region=region,
                zona=zona,
                seccion=seccion,
                campana_banco=campana_banco,
                carta_numero=carta_numero,
                formato_publicacion=formato_publicacion,
                estado_publicacion=estado_publicacion,
                gestor_publicacion=gestor_publicacion,
            )
            total = query.with_entities(func.count(Cliente.id)).scalar() or 0

            offset = (page - 1) * page_size
            rows = (
                query
                .order_by(Cliente.seccion, Cliente.codigo_cliente)
                .offset(offset)
                .limit(page_size)
                .all()
            )

            total_pages = (total + page_size - 1) // page_size if total else 1
            return {
                "items": [self._cliente_to_dict(c, include_sensitive=True) for c in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }

    def get_filter_options(
        self,
        campana_id: str,
        *,
        region: str = "",
        zona: str = "",
        seccion: str = "",
    ) -> Dict[str, List[str]]:
        """Return available local values for filter dropdowns."""
        with self.db.session() as session:
            regiones = (
                session.query(Cliente.region)
                .filter(Cliente.campana_id == campana_id, Cliente.region.isnot(None))
                .distinct()
                .order_by(Cliente.region)
                .all()
            )
            zonas_query = (
                session.query(Cliente.zona)
                .filter(Cliente.campana_id == campana_id, Cliente.zona.isnot(None))
            )
            if region:
                zonas_query = zonas_query.filter(Cliente.region == region)
            zonas = zonas_query.distinct().order_by(Cliente.zona).all()

            secciones_query = (
                session.query(Cliente.seccion)
                .filter(Cliente.campana_id == campana_id, Cliente.seccion.isnot(None))
            )
            if region:
                secciones_query = secciones_query.filter(Cliente.region == region)
            if zona:
                secciones_query = secciones_query.filter(Cliente.zona == zona)
            secciones = secciones_query.distinct().order_by(Cliente.seccion).all()
            estados = (
                session.query(Cliente.estado_gestion)
                .filter(Cliente.campana_id == campana_id, Cliente.estado_gestion.isnot(None))
                .distinct()
                .order_by(Cliente.estado_gestion)
                .all()
            )

            cartas_query = (
                session.query(CartaGenerada.numero_carta)
                .join(
                    Cliente,
                    (Cliente.id == CartaGenerada.cliente_id)
                    & (Cliente.campana_id == CartaGenerada.campana_id),
                )
                .filter(CartaGenerada.campana_id == campana_id)
            )
            formatos_query = (
                session.query(CartaGenerada.formato)
                .join(
                    Cliente,
                    (Cliente.id == CartaGenerada.cliente_id)
                    & (Cliente.campana_id == CartaGenerada.campana_id),
                )
                .filter(CartaGenerada.campana_id == campana_id)
            )
            estados_pub_query = (
                session.query(CartaGenerada.estado_publicacion)
                .join(
                    Cliente,
                    (Cliente.id == CartaGenerada.cliente_id)
                    & (Cliente.campana_id == CartaGenerada.campana_id),
                )
                .filter(CartaGenerada.campana_id == campana_id)
            )
            gestores_pub_query = (
                session.query(CartaGenerada.gestor_nombre)
                .join(
                    Cliente,
                    (Cliente.id == CartaGenerada.cliente_id)
                    & (Cliente.campana_id == CartaGenerada.campana_id),
                )
                .filter(CartaGenerada.campana_id == campana_id)
            )
            if region:
                cartas_query = cartas_query.filter(Cliente.region == region)
                formatos_query = formatos_query.filter(Cliente.region == region)
                estados_pub_query = estados_pub_query.filter(Cliente.region == region)
                gestores_pub_query = gestores_pub_query.filter(Cliente.region == region)
            if zona:
                cartas_query = cartas_query.filter(Cliente.zona == zona)
                formatos_query = formatos_query.filter(Cliente.zona == zona)
                estados_pub_query = estados_pub_query.filter(Cliente.zona == zona)
                gestores_pub_query = gestores_pub_query.filter(Cliente.zona == zona)
            if seccion:
                cartas_query = cartas_query.filter(Cliente.seccion == seccion)
                formatos_query = formatos_query.filter(Cliente.seccion == seccion)
                estados_pub_query = estados_pub_query.filter(Cliente.seccion == seccion)
                gestores_pub_query = gestores_pub_query.filter(Cliente.seccion == seccion)

            cartas = cartas_query.distinct().order_by(CartaGenerada.numero_carta).all()
            formatos = formatos_query.distinct().order_by(CartaGenerada.formato).all()
            estados_pub = estados_pub_query.distinct().order_by(CartaGenerada.estado_publicacion).all()
            gestores_pub = gestores_pub_query.distinct().order_by(CartaGenerada.gestor_nombre).all()

            campanas_banco_rows = (
                session.query(Cliente.campana_banco)
                .filter(Cliente.campana_id == campana_id)
                .distinct()
                .order_by(Cliente.campana_banco)
                .all()
            )
            campanas_banco: list[str] = []
            for row in campanas_banco_rows:
                raw = (row[0] or "").strip()
                key = raw if raw else SIN_CAMPANA_KEY
                if key not in campanas_banco:
                    campanas_banco.append(key)

            return {
                "regiones": [r[0] for r in regiones if r[0]],
                "zonas": [z[0] for z in zonas if z[0]],
                "secciones": [s[0] for s in secciones if s[0]],
                "estados": [e[0] for e in estados if e[0]],
                "campanas_banco": campanas_banco,
                "cartas_publicadas": [str(c[0]) for c in cartas if c[0] is not None],
                "formatos_publicacion": [f[0] for f in formatos if f[0]],
                "estados_publicacion": [e[0] for e in estados_pub if e[0]],
                "gestores_publicacion": [g[0] for g in gestores_pub if g[0]],
            }

    def save_client_contact_update(
        self,
        campana_id: str,
        codigo_cliente: str,
        *,
        telefono_nuevo: str = "",
        direccion_nueva: str = "",
        nota: str,
        usar_como_principal: bool = False,
        editor_nombre: str = "Escritorio",
        editor_email: str = "",
        editor_uid: str = "",
        editor_rol: str = "admin",
    ) -> Dict[str, Any]:
        """Record contact change locally; optionally update main address/phone."""
        nota = (nota or "").strip()
        if not nota:
            raise ValueError("La nota del cambio es obligatoria.")
        telefono_nuevo = (telefono_nuevo or "").strip()
        direccion_nueva = (direccion_nueva or "").strip()
        if not telefono_nuevo and not direccion_nueva:
            raise ValueError("Indique al menos un teléfono o una dirección nueva.")

        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if cliente is None:
                raise ValueError("Cliente no encontrado en la campaña activa.")

            telefono_anterior = str(cliente.telefono_movil or "")
            direccion_anterior = str(cliente.direccion or "")
            phone_changed = bool(telefono_nuevo) and telefono_nuevo != telefono_anterior
            addr_changed = bool(direccion_nueva) and direccion_nueva != direccion_anterior

            if (
                telefono_nuevo
                and telefono_nuevo == telefono_anterior
                and direccion_nueva
                and direccion_nueva == direccion_anterior
            ):
                raise ValueError(
                    "Los datos coinciden con la ficha principal. "
                    "Desmarque «Usar como principal» si registra una dirección alternativa distinta."
                )

            now_iso = datetime.now().isoformat()
            event_id = f"admin-{uuid.uuid4()}"

            session.add(HistorialContacto(
                campana_id=campana_id,
                codigo_cliente=str(codigo_cliente),
                event_id=event_id,
                fecha_evento=now_iso,
                direccion_anterior=direccion_anterior if addr_changed else None,
                direccion_nueva=direccion_nueva if addr_changed else None,
                telefono_anterior=telefono_anterior if phone_changed else None,
                telefono_nuevo=telefono_nuevo if phone_changed else None,
                nota=nota,
                usuario_uid=editor_uid or None,
                usuario_nombre=editor_nombre or "Escritorio",
                usuario_email=editor_email or None,
                rol_editor=editor_rol or "admin",
                seccion_key=str(cliente.seccion or ""),
                origen_actualizacion="admin",
                nivel_confianza=NIVEL_CONFIABLE,
                orden=0,
                oculto=False,
                es_principal=usar_como_principal,
                tipo=_infer_tipo_from_event({
                    "direccion_nueva": direccion_nueva,
                    "telefono_nuevo": telefono_nuevo,
                }),
            ))

            ev_dict = {
                "fecha": now_iso,
                "direccion_nueva": direccion_nueva if addr_changed else "",
                "telefono_nuevo": telefono_nuevo if phone_changed else "",
                "nota": nota,
                "usuario_uid": editor_uid,
                "usuario_nombre": editor_nombre,
                "usuario_email": editor_email,
                "nivel_confianza": NIVEL_CONFIABLE,
                "orden": 0,
                "oculto": False,
                "es_principal": usar_como_principal,
            }
            if cliente.numero_documento:
                upsert_contacto_persona(
                    session,
                    cliente.numero_documento,
                    event_id,
                    ev_dict,
                    campana_id,
                )

            cliente.ultima_nota_contacto = nota
            cliente.fecha_actualizacion_contacto_iso = now_iso
            cliente.actualizado_por_nombre = editor_nombre or "Escritorio"
            cliente.actualizado_por_email = editor_email or None
            cliente.actualizado_por_uid = editor_uid or None
            cliente.origen_actualizacion = "admin"
            cliente.fecha_actualizacion = datetime.now()

            if usar_como_principal:
                if phone_changed:
                    cliente.telefono_movil = telefono_nuevo
                if addr_changed:
                    cliente.direccion = direccion_nueva

            session.commit()

        return {"ok": True, "event_id": event_id}

    def update_contacto_persona_entry(
        self,
        event_id: str,
        *,
        nivel_confianza: str | None = None,
        orden: int | None = None,
        oculto: bool | None = None,
        es_principal: bool | None = None,
    ) -> bool:
        """Update durable contact agenda entry (admin desktop)."""
        with self.db.session() as session:
            row = (
                session.query(ContactoPersona)
                .filter(ContactoPersona.event_id == event_id)
                .first()
            )
            if row is None:
                return False
            if nivel_confianza is not None:
                nivel = nivel_confianza.strip().lower()
                row.nivel_confianza = nivel if nivel in NIVELES_CONFIANZA else NIVEL_CONFIABLE
            if orden is not None:
                row.orden = orden
            if oculto is not None:
                row.oculto = oculto
            if es_principal is not None:
                if es_principal:
                    session.query(ContactoPersona).filter(
                        ContactoPersona.numero_documento == row.numero_documento,
                        ContactoPersona.event_id != event_id,
                    ).update({"es_principal": False})
                row.es_principal = es_principal
            hist = (
                session.query(HistorialContacto)
                .filter(HistorialContacto.event_id == event_id)
                .first()
            )
            if hist is not None:
                if nivel_confianza is not None:
                    hist.nivel_confianza = row.nivel_confianza
                if orden is not None:
                    hist.orden = orden
                if oculto is not None:
                    hist.oculto = oculto
                if es_principal is not None:
                    hist.es_principal = es_principal
            session.commit()
        return True

    def get_client_timeline(self, campana_id: str, codigo_cliente: str) -> Dict[str, Any] | None:
        """Return full local client detail + visit history/events."""
        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if cliente is None:
                return None

            historial_tramos = (
                session.query(HistorialTramo)
                .filter(
                    HistorialTramo.campana_id == campana_id,
                    HistorialTramo.cliente_id == cliente.id,
                )
                .order_by(HistorialTramo.fecha_transicion.desc())
                .all()
            )
            cartas = (
                session.query(CartaGenerada)
                .filter(
                    CartaGenerada.campana_id == campana_id,
                    CartaGenerada.cliente_id == cliente.id,
                )
                .order_by(CartaGenerada.fecha_generacion.desc())
                .all()
            )
            eventos = []
            historial_visitas_rows = (
                session.query(HistorialVisita)
                .filter(
                    HistorialVisita.campana_id == campana_id,
                    HistorialVisita.cliente_id == cliente.id,
                )
                .order_by(HistorialVisita.fecha_evento.desc())
                .all()
            )
            for hv in historial_visitas_rows:
                fecha_hv = (
                    hv.fecha_evento.isoformat() if hv.fecha_evento else ""
                )
                detalle_parts = [f"Estado: {hv.estado_gestion or '—'}"]
                if hv.nivel_1:
                    detalle_parts.append(f"Nivel: {hv.nivel_1}")
                if hv.nota_gestor:
                    detalle_parts.append(f"Nota: {hv.nota_gestor}")
                if hv.gestor_nombre:
                    detalle_parts.append(f"Gestor: {hv.gestor_nombre}")
                eventos.append({
                    "tipo": "visita",
                    "fecha": fecha_hv,
                    "titulo": "Visita / gestión registrada",
                    "detalle": " · ".join(detalle_parts),
                })
            if not historial_visitas_rows and cliente.fecha_gestion:
                eventos.append({
                    "tipo": "gestion",
                    "fecha": cliente.fecha_gestion.isoformat(),
                    "titulo": "Visita / gestión registrada",
                    "detalle": f"Estado: {cliente.estado_gestion}",
                })
            for h in historial_tramos:
                eventos.append({
                    "tipo": "tramo",
                    "fecha": h.fecha_transicion.isoformat() if h.fecha_transicion else "",
                    "titulo": f"Tramo {h.tramo_anterior} → {h.tramo_nuevo}",
                    "detalle": f"Día {h.dia_campana} · Motivo: {h.motivo}",
                })
            for c in cartas:
                formato = c.formato or "—"
                estado_pub = c.estado_publicacion or ("impresa" if c.fue_impresa else "pendiente")
                gestor_destino = c.gestor_nombre or c.gestor_uid or ""
                eventos.append({
                    "tipo": "carta",
                    "fecha": (
                        c.fecha_publicacion.isoformat()
                        if c.fecha_publicacion else
                        (c.fecha_generacion.isoformat() if c.fecha_generacion else "")
                    ),
                    "titulo": f"Carta #{c.numero_carta} registrada",
                    "detalle": (
                        f"Estado: {estado_pub}"
                        f" · Formato: {formato}"
                        f"{f' · Gestor: {gestor_destino}' if gestor_destino else ''}"
                    ),
                })
            historial_contacto = (
                session.query(HistorialContacto)
                .filter(
                    HistorialContacto.campana_id == campana_id,
                    HistorialContacto.codigo_cliente == str(codigo_cliente),
                )
                .order_by(HistorialContacto.fecha_registro_local.desc())
                .all()
            )
            for h in historial_contacto:
                gps_part = ""
                if h.latitud and h.longitud:
                    gps_part = f" · GPS {h.latitud:.5f}, {h.longitud:.5f}"
                origen = h.origen_actualizacion or ""
                titulo = "Nota de campo" if origen == "mobile" else "Actualización de contacto"
                eventos.append({
                    "tipo": "contacto",
                    "fecha": h.fecha_evento or (h.fecha_registro_local.isoformat() if h.fecha_registro_local else ""),
                    "titulo": titulo,
                    "detalle": (
                        f"Tel: {h.telefono_anterior or '—'} → {h.telefono_nuevo or '—'} · "
                        f"Dir: {h.direccion_anterior or '—'} → {h.direccion_nueva or '—'} · "
                        f"{h.usuario_nombre or 'usuario'}"
                        f"{f' ({origen})' if origen else ''}{gps_part}"
                    ),
                    "latitud": h.latitud,
                    "longitud": h.longitud,
                    "origen": origen,
                })

            historial_zona_rows = (
                session.query(HistorialZona)
                .filter(
                    HistorialZona.campana_id == campana_id,
                    HistorialZona.codigo_cliente == str(codigo_cliente),
                )
                .order_by(HistorialZona.fecha_registro_local.desc())
                .all()
            )
            for z in historial_zona_rows:
                eventos.append({
                    "tipo": "zona",
                    "fecha": z.fecha_evento or (z.fecha_registro_local.isoformat() if z.fecha_registro_local else ""),
                    "titulo": "Cambio de zona/sección",
                    "detalle": (
                        f"Sección {z.seccion_anterior or '—'} → {z.seccion_nueva or '—'} · "
                        f"Zona {z.zona_anterior or '—'} → {z.zona_nueva or '—'} · "
                        f"{z.usuario_nombre or ''}"
                    ),
                })

            eventos.sort(key=lambda e: e.get("fecha", ""), reverse=True)

            cliente_dict = self._cliente_to_dict(cliente, include_sensitive=True)
            hist_contacto_dicts = [
                {
                    "event_id": h.event_id,
                    "fecha_evento": h.fecha_evento or "",
                    "direccion_anterior": h.direccion_anterior or "",
                    "direccion_nueva": h.direccion_nueva or "",
                    "telefono_anterior": h.telefono_anterior or "",
                    "telefono_nuevo": h.telefono_nuevo or "",
                    "nota": h.nota or "",
                    "usuario_uid": h.usuario_uid or "",
                    "usuario_nombre": h.usuario_nombre or "",
                    "usuario_email": h.usuario_email or "",
                    "rol_editor": h.rol_editor or "",
                    "seccion_key": h.seccion_key or "",
                    "origen_actualizacion": h.origen_actualizacion or "",
                    "latitud": h.latitud,
                    "longitud": h.longitud,
                    "nivel_confianza": h.nivel_confianza or NIVEL_CONFIABLE,
                    "orden": h.orden or 0,
                    "oculto": bool(h.oculto),
                    "es_principal": bool(h.es_principal),
                    "tipo": h.tipo or "",
                }
                for h in historial_contacto
            ]
            contacto_agenda = (
                get_contactos_persona(session, cliente.numero_documento or "", incluir_ocultos=True)
                if cliente.numero_documento
                else []
            )

            cuentas_relacionadas: list[dict] = []
            if cliente.numero_documento:
                hermanos = (
                    session.query(Cliente)
                    .filter(
                        Cliente.campana_id == campana_id,
                        Cliente.numero_documento == cliente.numero_documento,
                        Cliente.activo_en_cartera.is_(True),
                    )
                    .order_by(Cliente.codigo_cliente)
                    .all()
                )
                cuentas_relacionadas = [
                    self._cliente_to_dict(h, include_sensitive=True)
                    for h in hermanos
                ]

            return {
                "cliente": cliente_dict,
                "direcciones_conocidas": collect_direcciones_conocidas(cliente_dict, hist_contacto_dicts),
                "contacto_agenda": contacto_agenda,
                "historial_tramos": [
                    {
                        "tramo_anterior": h.tramo_anterior,
                        "tramo_nuevo": h.tramo_nuevo,
                        "fecha_transicion": h.fecha_transicion.isoformat() if h.fecha_transicion else "",
                        "motivo": h.motivo,
                        "saldo_al_momento": h.saldo_al_momento,
                        "dia_campana": h.dia_campana,
                    }
                    for h in historial_tramos
                ],
                "cartas": [
                    {
                        "numero_carta": c.numero_carta,
                        "tramo": c.tramo,
                        "fecha_generacion": c.fecha_generacion.isoformat() if c.fecha_generacion else "",
                        "fecha_publicacion": c.fecha_publicacion.isoformat() if c.fecha_publicacion else "",
                        "fue_impresa": c.fue_impresa,
                        "archivo_path": c.archivo_path or "",
                        "seccion_key": c.seccion_key or "",
                        "gestor_uid": c.gestor_uid or "",
                        "gestor_nombre": c.gestor_nombre or "",
                        "nombre_archivo": c.nombre_archivo or "",
                        "storage_path": c.storage_path or "",
                        "formato": c.formato or "",
                        "estado_publicacion": c.estado_publicacion or "",
                        "publicado_por_uid": c.publicado_por_uid or "",
                        "publicado_por_nombre": c.publicado_por_nombre or "",
                    }
                    for c in cartas
                ],
                "eventos": eventos,
                "historial_contacto": hist_contacto_dicts,
                "historial_zona": [
                    {
                        "event_id": z.event_id,
                        "seccion_anterior": z.seccion_anterior or "",
                        "seccion_nueva": z.seccion_nueva or "",
                        "zona_anterior": z.zona_anterior or "",
                        "zona_nueva": z.zona_nueva or "",
                        "region_anterior": z.region_anterior or "",
                        "region_nueva": z.region_nueva or "",
                        "usuario_nombre": z.usuario_nombre or "",
                        "usuario_email": z.usuario_email or "",
                        "fecha_evento": z.fecha_evento or "",
                    }
                    for z in historial_zona_rows
                ],
                "historial_visitas": [
                    {
                        "event_id": hv.event_id,
                        "fecha_evento": (
                            hv.fecha_evento.isoformat() if hv.fecha_evento else ""
                        ),
                        "estado_gestion": hv.estado_gestion or "",
                        "nota_gestor": hv.nota_gestor or "",
                        "nivel_1": hv.nivel_1 or "",
                        "nivel_2": hv.nivel_2 or "",
                        "nivel_3": hv.nivel_3 or "",
                        "nivel_4": hv.nivel_4 or "",
                        "canal_gestion": hv.canal_gestion or "",
                        "fecha_promesa_pago": hv.fecha_promesa_pago or "",
                        "monto_promesa_pago": hv.monto_promesa_pago or 0.0,
                        "gestor_uid": hv.gestor_uid or "",
                        "gestor_nombre": hv.gestor_nombre or "",
                        "gps_latitud": hv.gps_latitud,
                        "gps_longitud": hv.gps_longitud,
                    }
                    for hv in historial_visitas_rows
                ],
                "cuentas_relacionadas": cuentas_relacionadas,
            }

    def _apply_client_filters(
        self,
        query,
        *,
        search: str = "",
        estado: str = "",
        region: str = "",
        zona: str = "",
        seccion: str = "",
        campana_banco: str = "",
        carta_numero: int | None = None,
        formato_publicacion: str = "",
        estado_publicacion: str = "",
        gestor_publicacion: str = "",
    ):
        if region:
            query = query.filter(Cliente.region == region)
        if zona:
            query = query.filter(Cliente.zona == zona)
        if seccion:
            query = query.filter(Cliente.seccion == seccion)
        if campana_banco:
            if campana_banco == SIN_CAMPANA_KEY:
                query = query.filter(
                    (Cliente.campana_banco.is_(None)) | (Cliente.campana_banco == "")
                )
            else:
                query = query.filter(Cliente.campana_banco == campana_banco)
        if estado:
            query = query.filter(Cliente.estado_gestion == estado)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                (Cliente.codigo_cliente.ilike(term)) |
                (Cliente.nombre_completo.ilike(term)) |
                (Cliente.numero_documento.ilike(term))
            )
        if (
            carta_numero is not None
            or formato_publicacion
            or estado_publicacion
            or gestor_publicacion
        ):
            letters_query = (
                query.session.query(CartaGenerada.id)
                .filter(
                    CartaGenerada.campana_id == Cliente.campana_id,
                    CartaGenerada.cliente_id == Cliente.id,
                )
            )
            if carta_numero is not None:
                letters_query = letters_query.filter(
                    CartaGenerada.numero_carta == carta_numero
                )
            if formato_publicacion:
                letters_query = letters_query.filter(
                    CartaGenerada.formato == formato_publicacion
                )
            if estado_publicacion:
                letters_query = letters_query.filter(
                    CartaGenerada.estado_publicacion == estado_publicacion
                )
            if gestor_publicacion:
                letters_query = letters_query.filter(
                    CartaGenerada.gestor_nombre == gestor_publicacion
                )
            query = query.filter(letters_query.exists())
        return query

    def rebuild_parsed_data(self, campana_id: str) -> Dict[str, Any] | None:
        """
        Reconstruct the in-memory parsed_data dict from SQLite.

        Returns the same structure as excel_parser.parse_excel() so
        App.parsed_data can be restored on startup without re-reading
        the original Excel file.

        Returns None if the campaign has no clients yet.
        """
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                return None

            clientes = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.activo_en_cartera.is_(True),
                )
                .order_by(Cliente.seccion, Cliente.codigo_cliente)
                .all()
            )

            if not clientes:
                return None

            all_clients: list = []
            by_seccion: Dict[str, list] = {}

            for c in clientes:
                d = self._cliente_to_dict(c, include_sensitive=True)
                sec_key = make_seccion_key(
                    c.region or "", c.zona or "", c.seccion or "SIN_SECCION"
                )
                d["seccion_key"] = sec_key
                all_clients.append(d)
                if sec_key not in by_seccion:
                    by_seccion[sec_key] = []
                by_seccion[sec_key].append(d)

            total_deuda_asignada = sum(
                c.get("importe_deuda_asignada", 0) or 0 for c in all_clients
            )
            total_deuda_pendiente = sum(
                c.get("importe_deuda_pendiente", 0) or 0 for c in all_clients
            )
            departamentos = list({
                c.get("departamento", "") for c in all_clients
                if c.get("departamento")
            })

            summary = {
                "total_clientes": len(all_clients),
                "total_secciones": len(by_seccion),
                "secciones": {k: len(v) for k, v in sorted(by_seccion.items())},
                "total_deuda_asignada": round(total_deuda_asignada, 2),
                "total_deuda_pendiente": round(total_deuda_pendiente, 2),
                "departamentos": departamentos,
            }

        return {
            "all_clients": all_clients,
            "by_seccion": by_seccion,
            "summary": summary,
            "headers": [],  # headers not stored in DB; empty list is safe for all consumers
        }

    def _cliente_to_dict(
        self,
        c: Cliente,
        *,
        include_sensitive: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert a Cliente ORM object to a plain dict.
        
        Args:
            include_sensitive: If False, exclude DNI and other
                             sensitive fields (for Firebase sync).
        """
        d = {
            "codigo_cliente": c.codigo_cliente,
            "digito_control": c.digito_control or "",
            "nombres": c.nombres or "",
            "apellido_paterno": c.apellido_paterno or "",
            "apellido_materno": c.apellido_materno or "",
            "nombre_completo": c.nombre_completo or "",
            "genero": c.genero or "",
            "edad": c.edad or 0,
            "telefono_fijo": c.telefono_fijo or "",
            "telefono_trabajo": c.telefono_trabajo or "",
            "telefono_movil": c.telefono_movil or "",
            "correo": c.correo or "",
            "departamento": c.departamento or "",
            "provincia": c.provincia or "",
            "distrito": c.distrito or "",
            "direccion": c.direccion or "",
            "referencia": c.referencia or "",
            "coordenada_x": c.coordenada_x or 0.0,
            "coordenada_y": c.coordenada_y or 0.0,
            "segmentacion": c.segmentacion or "",
            "segmento_cartera": c.segmento_cartera or "",
            "etapa_deuda": c.etapa_deuda or "",
            "cobrador": c.cobrador or "",
            "campana_banco": c.campana_banco or "",
            "region": c.region or "",
            "zona": c.zona or "",
            "seccion": c.seccion or "",
            "seccion_key": make_seccion_key(
                c.region or "",
                c.zona or "",
                c.seccion or "",
            ),
            "territorio": c.territorio or "",
            "perfil_score": c.perfil_score or "",
            "fecha_documento": c.fecha_documento or "",
            "fecha_vencimiento": c.fecha_vencimiento or "",
            "fecha_asignacion": c.fecha_asignacion or "",
            "fecha_cierre": c.fecha_cierre or "",
            "dias_atraso": c.dias_atraso or 0,
            "importe_deuda_original": c.importe_deuda_original or 0.0,
            "importe_abonos_anteriores": c.importe_abonos_anteriores or 0.0,
            "importe_deuda_asignada": c.importe_deuda_asignada or 0.0,
            "importe_deuda_pendiente": c.importe_deuda_pendiente or 0.0,
            # Campos de gestión
            "tramo_actual": c.tramo_actual,
            "estado_gestion": c.estado_gestion,
            "nota_gestor": c.nota_gestor or "",
            "fecha_gestion": str(c.fecha_gestion) if c.fecha_gestion else "",
            "gps_latitud": c.gps_latitud or 0.0,
            "gps_longitud": c.gps_longitud or 0.0,
            "ubicacion_verificada_lat": c.ubicacion_verificada_lat or 0.0,
            "ubicacion_verificada_lng": c.ubicacion_verificada_lng or 0.0,
            "ubicacion_verificada_fecha": c.ubicacion_verificada_fecha or "",
            "ubicacion_verificada_gestor": c.ubicacion_verificada_gestor or "",
            # Clasificación jerárquica
            "nivel_1": c.nivel_1 or "",
            "nivel_2": c.nivel_2 or "",
            "nivel_3": c.nivel_3 or "",
            "nivel_4": c.nivel_4 or "",
            "canal_gestion": c.canal_gestion or "",
            "fecha_promesa_pago": c.fecha_promesa_pago or "",
            "monto_promesa_pago": c.monto_promesa_pago or 0.0,
            "ultima_nota_contacto": c.ultima_nota_contacto or "",
            "fecha_actualizacion_contacto_iso": c.fecha_actualizacion_contacto_iso or "",
            "actualizado_por_uid": c.actualizado_por_uid or "",
            "actualizado_por_nombre": c.actualizado_por_nombre or "",
            "actualizado_por_email": c.actualizado_por_email or "",
            "origen_actualizacion": c.origen_actualizacion or "",
            "activo_en_cartera": getattr(c, "activo_en_cartera", True),
            "motivo_baja": c.motivo_baja or "",
            "fecha_baja": (
                c.fecha_baja.isoformat() if getattr(c, "fecha_baja", None) else ""
            ),
            "ultimo_excel": getattr(c, "ultimo_excel", None) or "",
            "dia_ciclo": c.dia_ciclo,
            "estado_ciclo": c.estado_ciclo or EstadoCiclo.ACTIVA.value,
            "fecha_asignacion_dt": format_fecha_iso(c.fecha_asignacion_dt),
            "fecha_cierre_real": format_fecha_iso(c.fecha_cierre_real),
            "gestion_especial": bool(getattr(c, "gestion_especial", False)),
            "motivo_gestion_especial": c.motivo_gestion_especial or "",
            "seccion_origen": c.seccion_origen or "",
            "fase_gestion": getattr(c, "fase_gestion", FASE_GESTION_CAMPO) or FASE_GESTION_CAMPO,
            "call_gestor_uid": c.call_gestor_uid or "",
            "call_gestor_nombre": c.call_gestor_nombre or "",
            "seccion_key_origen": get_territorial_seccion_key(c),
            "etiquetas": _parse_etiquetas_json(getattr(c, "etiquetas", None)),
        }

        if include_sensitive:
            d["numero_documento"] = c.numero_documento or ""
        # Intentionally omit DNI when include_sensitive=False

        return d

    # ─────────────────────────────────────────────────────────────
    #  4. FIREBASE SYNC — Prepare payload (no sensitive data)
    # ─────────────────────────────────────────────────────────────

    def get_firebase_payload(
        self,
        campana_id: str,
        *,
        solo_activos: bool = True,
    ) -> Dict[str, Any]:
        """
        Build the payload structure for Firebase upload.
        Includes required operational fields for gestores, including DNI.
        Returns a dict structured like the original upload format
        for backward compatibility with firebase_service.upload_cartera().

        Args:
            solo_activos: If True, omit archived clients (activo_en_cartera=False).

        Structure:
            {
                "campaign_id": "...",
                "by_seccion": {
                    "A": [client_dict, ...],
                    "B": [client_dict, ...],
                },
                "summary": { ... },
            }
        """
        with self.db.session() as session:
            q = (
                session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
            )
            if solo_activos:
                q = q.filter(Cliente.activo_en_cartera.is_(True))
            clientes = q.order_by(Cliente.seccion, Cliente.codigo_cliente).all()

            by_seccion: Dict[str, list] = {}
            for c in clientes:
                sec_key = get_effective_firestore_section(c)
                if sec_key not in by_seccion:
                    by_seccion[sec_key] = []
                client_dict = self._cliente_to_dict(c, include_sensitive=True)
                # En call: el doc vive en _CALL_{uid} pero conserva sección territorial.
                if (
                    getattr(c, "fase_gestion", FASE_GESTION_CAMPO) == FASE_GESTION_CALL
                    and c.call_gestor_uid
                ):
                    client_dict["seccion_key"] = sec_key
                if c.numero_documento:
                    client_dict["contactos_seed"] = get_contactos_persona(
                        session, c.numero_documento
                    )
                by_seccion[sec_key].append(client_dict)

            # Summary
            campana = session.get(Campana, campana_id)
            summary = {
                "total_clientes": len(clientes),
                "total_secciones": len(by_seccion),
                "secciones": {k: len(v) for k, v in by_seccion.items()},
                "deuda_asignada": campana.deuda_total_asignada if campana else 0,
                "deuda_pendiente": campana.deuda_total_pendiente if campana else 0,
            }

        return {
            "campaign_id": campana_id,
            "by_seccion": by_seccion,
            "summary": summary,
        }

    # ─────────────────────────────────────────────────────────────
    #  5. SYNC BACK FROM FIREBASE (gestor visits → SQLite)
    # ─────────────────────────────────────────────────────────────

    def sync_visits_from_firebase(
        self,
        campana_id: str,
        firebase_data: Dict[str, Any],
    ) -> int:
        """
        Import gestor visit data from Firebase back into SQLite.
        Updates estado_gestion, niveles, promesa, nota_gestor, fecha_gestion, gps fields.

        Args:
            campana_id: Campaign to update.
            firebase_data: Dict keyed by seccion, each containing
                          a list of client dicts with visit fields.

        Returns:
            Number of clients updated.
        """
        updated = 0
        # direccion/telefono_movil excluded: bank record comes from Excel;
        # field alternatives are stored in historial_contacto only.
        visit_fields = [
            "estado_gestion", "nota_gestor", "fecha_gestion",
            "gps_latitud", "gps_longitud", "gps_timestamp",
            "nivel_1", "nivel_2", "nivel_3", "nivel_4",
            "canal_gestion", "fecha_promesa_pago", "monto_promesa_pago",
            "ultima_nota_contacto", "fecha_actualizacion_contacto_iso",
            "actualizado_por_uid", "actualizado_por_nombre", "actualizado_por_email",
            "origen_actualizacion",
            "ubicacion_verificada_lat", "ubicacion_verificada_lng",
            "ubicacion_verificada_fecha", "ubicacion_verificada_gestor",
            "motivo_devolucion", "nota_devolucion", "fecha_devolucion_solicitud",
            "gestor_devolucion_uid", "gestor_devolucion_nombre", "gestor_devolucion_seccion",
            "seccion_key", "region", "zona", "seccion",
            "etiquetas",
        ]

        with self.db.session() as session:
            for seccion, clients_data in firebase_data.items():
                for cd in clients_data:
                    codigo = cd.get("codigo_cliente")
                    if not codigo:
                        continue

                    cliente = (
                        session.query(Cliente)
                        .filter(
                            Cliente.campana_id == campana_id,
                            Cliente.codigo_cliente == str(codigo),
                        )
                        .first()
                    )
                    if cliente is None:
                        continue

                    uv = cd.get("ubicacion_verificada")
                    if isinstance(uv, dict) and float(uv.get("lat", 0) or 0):
                        cd = dict(cd)
                        cd["ubicacion_verificada_lat"] = float(uv.get("lat", 0) or 0)
                        cd["ubicacion_verificada_lng"] = float(uv.get("lng", 0) or 0)
                        cd["ubicacion_verificada_fecha"] = str(uv.get("timestamp", "") or "")
                        cd["ubicacion_verificada_gestor"] = str(
                            uv.get("gestor_nombre", "") or ""
                        )

                    changed = False
                    for field in visit_fields:
                        fb_val = cd.get(field)
                        if fb_val is not None and fb_val != "":
                            if field == "fecha_gestion":
                                parsed = _coerce_firebase_datetime(fb_val)
                                if parsed is None:
                                    continue
                                fb_val = parsed
                            elif field == "etiquetas":
                                if isinstance(fb_val, list):
                                    fb_val = _serialize_etiquetas_json(fb_val)
                                else:
                                    continue
                            current = getattr(cliente, field, None)
                            if str(fb_val) != str(current or ""):
                                setattr(cliente, field, fb_val)
                                changed = True

                    fb_sk = str(cd.get("seccion_key") or seccion or "")
                    if fb_sk and str(cliente.seccion_key or "") != fb_sk:
                        parts = fb_sk.split("_")
                        cliente.seccion_key = fb_sk
                        cliente.seccion = parts[2] if len(parts) >= 3 else fb_sk
                        if len(parts) >= 1 and parts[0]:
                            cliente.region = parts[0]
                        if len(parts) >= 2 and parts[1]:
                            cliente.zona = parts[1]
                        changed = True

                    if changed:
                        cliente.fecha_actualizacion = datetime.now()
                        cliente.sincronizado_firebase = True
                        updated += 1

                    for vev in (cd.get("historial_visitas") or []):
                        if not isinstance(vev, dict):
                            continue
                        v_event_id = str(vev.get("event_id") or vev.get("id") or "")
                        if not v_event_id:
                            base = (
                                f"{campana_id}:{codigo}:"
                                f"{vev.get('fecha_gestion', vev.get('fecha', ''))}:"
                                f"{vev.get('estado_gestion', '')}"
                            )
                            v_event_id = str(abs(hash(base)))
                        exists_v = (
                            session.query(HistorialVisita)
                            .filter(HistorialVisita.event_id == v_event_id)
                            .first()
                        )
                        if exists_v:
                            continue
                        fecha_v = _coerce_firebase_datetime(
                            vev.get("fecha_gestion")
                            or vev.get("fecha")
                            or vev.get("fecha_evento")
                        )
                        session.add(HistorialVisita(
                            cliente_id=cliente.id,
                            campana_id=campana_id,
                            codigo_cliente=str(codigo),
                            event_id=v_event_id,
                            fecha_evento=fecha_v,
                            estado_gestion=str(vev.get("estado_gestion", "")),
                            nota_gestor=str(vev.get("nota_gestor", "")),
                            nivel_1=str(vev.get("nivel_1", "")),
                            nivel_2=str(vev.get("nivel_2", "")),
                            nivel_3=str(vev.get("nivel_3", "")),
                            nivel_4=str(vev.get("nivel_4", "")),
                            canal_gestion=str(vev.get("canal_gestion", "")),
                            fecha_promesa_pago=str(vev.get("fecha_promesa_pago", "")),
                            monto_promesa_pago=float(vev.get("monto_promesa_pago", 0) or 0),
                            gps_latitud=float(vev.get("gps_latitud", 0) or 0) or None,
                            gps_longitud=float(vev.get("gps_longitud", 0) or 0) or None,
                            gestor_uid=str(vev.get("gestor_uid", "")),
                            gestor_nombre=str(vev.get("gestor_nombre", "")),
                        ))

                    # Persist contact history events into local audit table.
                    for ev in (cd.get("historial_contacto") or []):
                        event_id = str(ev.get("event_id") or ev.get("id") or "")
                        if not event_id:
                            base = f"{campana_id}:{codigo}:{ev.get('fecha','')}:{ev.get('nota','')}"
                            event_id = str(abs(hash(base)))
                        nivel = str(ev.get("nivel_confianza", NIVEL_CONFIABLE) or NIVEL_CONFIABLE)
                        if nivel not in NIVELES_CONFIANZA:
                            nivel = NIVEL_CONFIABLE
                        orden = int(ev.get("orden", 0) or 0)
                        oculto = bool(ev.get("oculto", False))
                        es_principal = bool(ev.get("es_principal", False))
                        tipo_ev = _infer_tipo_from_event(ev)
                        gps = ev.get("gps") if isinstance(ev.get("gps"), dict) else {}
                        exists = (
                            session.query(HistorialContacto)
                            .filter(HistorialContacto.event_id == event_id)
                            .first()
                        )
                        if exists:
                            exists.nivel_confianza = nivel
                            exists.orden = orden
                            exists.oculto = oculto
                            exists.es_principal = es_principal
                            exists.tipo = tipo_ev
                            if ev.get("nota"):
                                exists.nota = str(ev.get("nota", ""))
                        else:
                            session.add(HistorialContacto(
                                campana_id=campana_id,
                                codigo_cliente=str(codigo),
                                event_id=event_id,
                                fecha_evento=str(ev.get("fecha", ev.get("fecha_evento", ""))),
                                direccion_anterior=str(ev.get("direccion_anterior", "")),
                                direccion_nueva=str(ev.get("direccion_nueva", "")),
                                telefono_anterior=str(ev.get("telefono_anterior", "")),
                                telefono_nuevo=str(ev.get("telefono_nuevo", "")),
                                nota=str(ev.get("nota", "")),
                                usuario_uid=str(ev.get("usuario_uid", "")),
                                usuario_nombre=str(ev.get("usuario_nombre", "")),
                                usuario_email=str(ev.get("usuario_email", "")),
                                rol_editor=str(ev.get("rol_editor", "")),
                                seccion_key=str(ev.get("seccion_key", "")),
                                origen_actualizacion=str(ev.get("origen_actualizacion", "")),
                                latitud=float(gps.get("latitude", gps.get("lat", 0)) or 0) or None,
                                longitud=float(gps.get("longitude", gps.get("lng", 0)) or 0) or None,
                                nivel_confianza=nivel,
                                orden=orden,
                                oculto=oculto,
                                es_principal=es_principal,
                                tipo=tipo_ev,
                            ))
                        if cliente.numero_documento:
                            upsert_contacto_persona(
                                session,
                                cliente.numero_documento,
                                event_id,
                                {**ev, "event_id": event_id},
                                campana_id,
                            )

                    for zev in (cd.get("historial_zona") or []):
                        if not isinstance(zev, dict):
                            continue
                        z_event_id = str(
                            zev.get("event_id")
                            or zev.get("id")
                            or f"{campana_id}:{codigo}:{zev.get('fecha','')}:{zev.get('seccion_nueva','')}"
                        )
                        exists_z = (
                            session.query(HistorialZona)
                            .filter(HistorialZona.event_id == z_event_id)
                            .first()
                        )
                        if exists_z:
                            continue
                        session.add(HistorialZona(
                            campana_id=campana_id,
                            codigo_cliente=str(codigo),
                            event_id=z_event_id,
                            seccion_anterior=str(zev.get("seccion_anterior", zev.get("from_section", ""))),
                            seccion_nueva=str(zev.get("seccion_nueva", zev.get("to_section", ""))),
                            zona_anterior=str(zev.get("zona_anterior", "")),
                            zona_nueva=str(zev.get("zona_nueva", "")),
                            region_anterior=str(zev.get("region_anterior", "")),
                            region_nueva=str(zev.get("region_nueva", "")),
                            usuario_nombre=str(zev.get("usuario_nombre", zev.get("admin_name", ""))),
                            usuario_email=str(zev.get("usuario_email", zev.get("admin_email", ""))),
                            fecha_evento=str(zev.get("fecha", zev.get("fecha_evento", ""))),
                        ))
                        # Apply latest zone from pull when Firebase section differs from SQLite.
                        new_sk = str(zev.get("seccion_nueva", zev.get("to_section", "")) or "")
                        fb_sk = str(cd.get("seccion_key") or seccion or "")
                        target_sk = fb_sk or new_sk
                        if target_sk and cliente.seccion_key != target_sk:
                            parts = target_sk.split("_")
                            cliente.seccion_key = target_sk
                            cliente.seccion = parts[2] if len(parts) >= 3 else target_sk
                            cliente.region = parts[0] if len(parts) >= 1 else cliente.region
                            cliente.zona = parts[1] if len(parts) >= 2 else cliente.zona
                            changed = True

            session.commit()

        # Record sync event
        self._record_sync("visits_only", updated)

        logger.info(
            "Synced %d client visits from Firebase for campaign %s",
            updated, campana_id,
        )
        return updated

    def update_local_client_section(
        self,
        campana_id: str,
        codigo_cliente: str,
        new_seccion_key: str,
        reset_gestion: bool = True,
    ) -> bool:
        """Update SQLite section assignment after a Firestore zone move."""
        parts = new_seccion_key.split("_")
        new_seccion = parts[2] if len(parts) >= 3 else new_seccion_key
        new_region = parts[0] if len(parts) >= 1 else ""
        new_zona = parts[1] if len(parts) >= 2 else ""
        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if not cliente:
                return False
            cliente.seccion_key = new_seccion_key
            cliente.seccion = new_seccion
            cliente.region = new_region or cliente.region
            cliente.zona = new_zona or cliente.zona
            if reset_gestion:
                cliente.estado_gestion = EstadoGestion.PENDIENTE.value
                cliente.motivo_devolucion = None
                cliente.nota_devolucion = None
                cliente.fecha_devolucion_solicitud = None
                cliente.gestor_devolucion_uid = None
                cliente.gestor_devolucion_nombre = None
                cliente.gestor_devolucion_seccion = None
            cliente.fecha_actualizacion = datetime.now()
            session.commit()
        return True

    def mark_gestion_especial(
        self,
        campana_id: str,
        codigo_cliente: str,
        motivo: str,
        seccion_destino: str = GESTION_ESPECIAL_SECTION,
    ) -> dict:
        """Deriva una cuenta a gestión especial y la mueve de sección."""
        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if not cliente:
                return {"success": False, "error": "Cliente no encontrado en SQLite"}

            origen = cliente.seccion_key or make_seccion_key(
                cliente.region or "", cliente.zona or "", cliente.seccion or "",
            )
            if not cliente.seccion_origen:
                cliente.seccion_origen = origen

            cliente.gestion_especial = True
            cliente.motivo_gestion_especial = motivo
            cliente.fecha_gestion_especial = datetime.now()
            cliente.estado_gestion = EstadoGestion.PENDIENTE.value
            cliente.motivo_devolucion = None
            cliente.nota_devolucion = None
            cliente.fecha_devolucion_solicitud = None
            cliente.gestor_devolucion_uid = None
            cliente.gestor_devolucion_nombre = None
            cliente.gestor_devolucion_seccion = None

            parts = seccion_destino.split("_")
            cliente.seccion_key = seccion_destino
            cliente.seccion = parts[2] if len(parts) >= 3 else seccion_destino
            if len(parts) >= 2:
                cliente.region = parts[0] or cliente.region
                cliente.zona = parts[1] or cliente.zona
            cliente.fecha_actualizacion = datetime.now()
            session.commit()

        return {
            "success": True,
            "codigo_cliente": codigo_cliente,
            "seccion_origen": origen,
            "seccion_destino": seccion_destino,
        }

    def restore_from_gestion_especial(
        self,
        campana_id: str,
        codigo_cliente: str,
    ) -> dict:
        """Restituye una cuenta desde gestión especial a su sección original."""
        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if not cliente:
                return {"success": False, "error": "Cliente no encontrado"}
            if not cliente.gestion_especial:
                return {"success": False, "error": "La cuenta no está en gestión especial"}

            destino = cliente.seccion_origen
            if not destino:
                return {"success": False, "error": "Sin sección de origen registrada"}

            parts = destino.split("_")
            cliente.seccion_key = destino
            cliente.seccion = parts[2] if len(parts) >= 3 else destino
            if len(parts) >= 2:
                cliente.region = parts[0] or cliente.region
                cliente.zona = parts[1] or cliente.zona
            cliente.gestion_especial = False
            cliente.motivo_gestion_especial = None
            cliente.fecha_gestion_especial = None
            cliente.seccion_origen = None
            cliente.fecha_actualizacion = datetime.now()
            session.commit()

        return {"success": True, "codigo_cliente": codigo_cliente, "seccion_destino": destino}

    def get_gestion_especial_local(self, campana_id: str) -> list:
        """Cuentas marcadas como gestión especial en SQLite."""
        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.gestion_especial.is_(True),
                )
                .all()
            )
            return [
                {
                    "codigo_cliente": c.codigo_cliente,
                    "nombre_completo": c.nombre_completo or "",
                    "seccion_key": c.seccion_key or "",
                    "seccion_origen": c.seccion_origen or "",
                    "motivo_gestion_especial": c.motivo_gestion_especial or "",
                    "dia_ciclo": c.dia_ciclo,
                    "tramo_actual": c.tramo_actual,
                    "estado_ciclo": c.estado_ciclo or "",
                    "importe_deuda_pendiente": c.importe_deuda_pendiente,
                }
                for c in rows
            ]

    def get_pending_returns_local(self, campana_id: str) -> list:
        """Clients with devolucion_pendiente in local SQLite."""
        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.estado_gestion == EstadoGestion.DEVOLUCION_PENDIENTE.value,
                )
                .all()
            )
            return [
                {
                    "codigo_cliente": c.codigo_cliente,
                    "nombre_completo": c.nombre_completo or "",
                    "seccion_key": c.seccion_key or "",
                    "region": c.region or "",
                    "zona": c.zona or "",
                    "motivo_devolucion": c.motivo_devolucion or "",
                    "nota_devolucion": c.nota_devolucion or "",
                    "fecha_devolucion_solicitud": c.fecha_devolucion_solicitud or "",
                    "gestor_devolucion_nombre": c.gestor_devolucion_nombre or "",
                    "gestor_devolucion_seccion": c.gestor_devolucion_seccion or "",
                    "importe_deuda_pendiente": c.importe_deuda_pendiente,
                }
                for c in rows
            ]

    # ─────────────────────────────────────────────────────────────
    #  5b. FULL RESTORE FROM FIREBASE (new PC)
    # ─────────────────────────────────────────────────────────────

    def restore_campaign_from_firebase(
        self,
        firebase_data: dict,
        nombre: str = "",
        duracion_dias: int = 60,
    ) -> tuple[Campana, dict]:
        """
        Create a local campaign in SQLite from data downloaded from Firebase.
        Includes all visit/nivel data so the local DB is a full mirror.

        Args:
            firebase_data: Dict returned by FirebaseService.download_full_cartera().
            nombre: Campaign name override.
            duracion_dias: Campaign duration (days).

        Returns:
            Tuple of (Campana object, summary dict).
        """
        if not self.db.is_initialized:
            self.db.initialize()

        by_seccion = firebase_data.get("by_seccion", {})
        metadata = firebase_data.get("metadata", {})
        all_clients = []
        for clients in by_seccion.values():
            all_clients.extend(clients)

        if not all_clients:
            raise ValueError("No hay clientes en los datos descargados de Firebase.")

        # Check for existing active campaign
        with self.db.session() as session:
            active = (
                session.query(Campana)
                .filter(Campana.estado == EstadoCampana.ACTIVA.value)
                .first()
            )
            if active:
                raise ValueError(
                    f"Ya existe una campaña activa: {active.nombre} ({active.id}). "
                    "Ciérrela antes de restaurar desde la nube."
                )

        campaign_id = generate_campaign_id(nombre or "cloud_restore")
        fecha_inicio = date.today()
        fecha_fin = fecha_inicio + timedelta(days=duracion_dias - 1)

        if not nombre:
            nombre = f"Restaurada {fecha_inicio.strftime('%d/%m/%Y')}"

        deuda_total = sum(
            float(c.get("importe_deuda_asignada", 0) or 0) for c in all_clients
        )
        deuda_pendiente = sum(
            float(c.get("importe_deuda_pendiente", 0) or 0) for c in all_clients
        )

        with self.db.session() as session:
            campana = Campana(
                id=campaign_id,
                nombre=nombre,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                estado=EstadoCampana.ACTIVA.value,
                archivo_origen="(restaurada desde Firebase)",
                total_clientes=len(all_clients),
                total_secciones=len(by_seccion),
                deuda_total_asignada=deuda_total,
                deuda_total_pendiente=deuda_pendiente,
            )
            session.add(campana)

            for client_data in all_clients:
                cliente = self._dict_to_cliente(client_data, campaign_id)
                # Also restore visit / nivel fields from Firebase
                cliente.estado_gestion = client_data.get(
                    "estado_gestion", EstadoGestion.PENDIENTE.value
                )
                cliente.nota_gestor = client_data.get("nota_gestor") or None
                fg = _coerce_firebase_datetime(client_data.get("fecha_gestion"))
                if fg:
                    cliente.fecha_gestion = fg
                cliente.gps_latitud = float(client_data.get("gps_latitud", 0) or 0) or None
                cliente.gps_longitud = float(client_data.get("gps_longitud", 0) or 0) or None
                cliente.gps_timestamp = client_data.get("gps_timestamp") or None
                cliente.nivel_1 = client_data.get("nivel_1") or None
                cliente.nivel_2 = client_data.get("nivel_2") or None
                cliente.nivel_3 = client_data.get("nivel_3") or None
                cliente.nivel_4 = client_data.get("nivel_4") or None
                cliente.canal_gestion = client_data.get("canal_gestion") or None
                cliente.fecha_promesa_pago = client_data.get("fecha_promesa_pago") or None
                cliente.monto_promesa_pago = float(
                    client_data.get("monto_promesa_pago", 0) or 0
                ) or None
                uv = client_data.get("ubicacion_verificada")
                if isinstance(uv, dict) and float(uv.get("lat", 0) or 0):
                    cliente.ubicacion_verificada_lat = float(uv.get("lat", 0) or 0) or None
                    cliente.ubicacion_verificada_lng = float(uv.get("lng", 0) or 0) or None
                    cliente.ubicacion_verificada_fecha = str(uv.get("timestamp", "") or "") or None
                    cliente.ubicacion_verificada_gestor = str(
                        uv.get("gestor_nombre", "") or ""
                    ) or None
                cliente.sincronizado_firebase = True
                session.add(cliente)

            session.commit()
            session.refresh(campana)

        self._record_sync("full_download", len(all_clients))

        summary = {
            "campaign_id": campaign_id,
            "nombre": nombre,
            "total_clientes": len(all_clients),
            "total_secciones": len(by_seccion),
            "deuda_asignada": deuda_total,
            "deuda_pendiente": deuda_pendiente,
        }
        logger.info(
            "Restored campaign from Firebase: %s with %d clients",
            campaign_id, len(all_clients),
        )
        return campana, summary

    # ─────────────────────────────────────────────────────────────
    #  5c. CATALOG SYNC
    # ─────────────────────────────────────────────────────────────

    def upload_catalogo_niveles(self, firebase_service) -> bool:
        """Load the local catalog JSON and upload it to Firestore.

        Args:
            firebase_service: An initialised FirebaseService instance.

        Returns:
            True if the upload succeeded.
        """
        import json
        catalog_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "catalogo_niveles_PE.json",
        )
        if not os.path.exists(catalog_path):
            logger.warning("Catalog file not found: %s", catalog_path)
            return False

        with open(catalog_path, "r", encoding="utf-8") as f:
            catalogo = json.load(f)

        return firebase_service.upload_catalogo_niveles(catalogo)

    def get_client_accounts_by_documento(
        self,
        campana_id: str,
        numero_documento: str,
    ) -> list[dict]:
        """Return all active client accounts sharing the same DNI in a campaign."""
        if not numero_documento:
            return []
        with self.db.session() as session:
            rows = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.numero_documento == numero_documento,
                    Cliente.activo_en_cartera.is_(True),
                )
                .order_by(Cliente.codigo_cliente)
                .all()
            )
            return [self._cliente_to_dict(c, include_sensitive=True) for c in rows]

    # ── Etiquetas (catálogo global) ──────────────────────────────

    def list_etiquetas(self, *, solo_activas: bool = False) -> list[dict]:
        with self.db.session() as session:
            q = session.query(EtiquetaCatalogo).order_by(
                EtiquetaCatalogo.orden, EtiquetaCatalogo.nombre
            )
            if solo_activas:
                q = q.filter(EtiquetaCatalogo.activa.is_(True))
            return [
                {
                    "id": e.id,
                    "nombre": e.nombre,
                    "color": e.color,
                    "descripcion": e.descripcion or "",
                    "activa": e.activa,
                    "orden": e.orden,
                }
                for e in q.all()
            ]

    def create_etiqueta(
        self,
        nombre: str,
        color: str = "#3B82F6",
        descripcion: str = "",
        orden: int = 0,
    ) -> dict:
        tag_id = f"etq_{uuid.uuid4().hex[:10]}"
        with self.db.session() as session:
            session.add(EtiquetaCatalogo(
                id=tag_id,
                nombre=nombre.strip(),
                color=color.strip() or "#3B82F6",
                descripcion=descripcion.strip(),
                activa=True,
                orden=int(orden),
            ))
            session.commit()
        return {"id": tag_id, "nombre": nombre.strip(), "color": color, "activa": True}

    def update_etiqueta(self, tag_id: str, **fields) -> bool:
        with self.db.session() as session:
            row = session.get(EtiquetaCatalogo, tag_id)
            if row is None:
                return False
            if "nombre" in fields and fields["nombre"]:
                row.nombre = str(fields["nombre"]).strip()
            if "color" in fields and fields["color"]:
                row.color = str(fields["color"]).strip()
            if "descripcion" in fields:
                row.descripcion = str(fields["descripcion"] or "").strip()
            if "activa" in fields:
                row.activa = bool(fields["activa"])
            if "orden" in fields:
                row.orden = int(fields["orden"])
            session.commit()
        return True

    def delete_etiqueta(self, tag_id: str) -> bool:
        """Soft-delete: marca la etiqueta como inactiva."""
        return self.update_etiqueta(tag_id, activa=False)

    def build_catalogo_etiquetas_payload(self) -> dict:
        etiquetas = self.list_etiquetas()
        return {
            "version": 1,
            "etiquetas": etiquetas,
        }

    def upload_catalogo_etiquetas(self, firebase_service) -> bool:
        catalogo = self.build_catalogo_etiquetas_payload()
        return firebase_service.upload_catalogo_etiquetas(catalogo)

    def set_client_etiquetas(
        self,
        campana_id: str,
        codigo_cliente: str,
        etiqueta_ids: list[str],
        *,
        firebase_service=None,
        firestore_campaign_id: str = "cartera_activa",
    ) -> bool:
        """Assign etiquetas to a client locally and optionally push to Firestore."""
        clean = [str(x) for x in etiqueta_ids if x]
        with self.db.session() as session:
            cliente = (
                session.query(Cliente)
                .filter(
                    Cliente.campana_id == campana_id,
                    Cliente.codigo_cliente == str(codigo_cliente),
                )
                .first()
            )
            if cliente is None:
                return False
            cliente.etiquetas = _serialize_etiquetas_json(clean)
            cliente.fecha_actualizacion = datetime.now()
            session.commit()
            seccion_key = get_effective_firestore_section(cliente)
        if firebase_service and firebase_service.is_initialized:
            firebase_service.update_client_etiquetas_firestore(
                firestore_campaign_id,
                seccion_key,
                str(codigo_cliente),
                clean,
            )
        return True

    # ─────────────────────────────────────────────────────────────
    #  SYNC LOG HELPER
    # ─────────────────────────────────────────────────────────────

    def _record_sync(
        self, tipo: str, registros: int, resultado: str = "ok", detalle: str = ""
    ) -> None:
        """Record a synchronisation event in the local sync_log table."""
        from .database import SyncLog
        try:
            with self.db.session() as session:
                session.add(SyncLog(
                    tipo=tipo,
                    fecha=datetime.now(),
                    registros_afectados=registros,
                    resultado=resultado,
                    detalle=detalle,
                ))
                session.commit()
        except Exception as e:
            logger.warning("Could not write sync log: %s", e)

    def get_last_sync(self) -> dict | None:
        """Return the most recent sync log entry as a dict, or None."""
        from .database import SyncLog
        try:
            with self.db.session() as session:
                entry = (
                    session.query(SyncLog)
                    .order_by(SyncLog.fecha.desc())
                    .first()
                )
                if entry is None:
                    return None
                return {
                    "tipo": entry.tipo,
                    "fecha": entry.fecha.isoformat() if entry.fecha else "",
                    "registros_afectados": entry.registros_afectados,
                    "resultado": entry.resultado,
                    "detalle": entry.detalle or "",
                }
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    #  6. CAMPAIGN LIFECYCLE
    # ─────────────────────────────────────────────────────────────

    def close_campaign(self, campana_id: str) -> bool:
        """Mark a campaign as closed."""
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                return False
            campana.estado = EstadoCampana.CERRADA.value
            session.commit()
        logger.info("Campaign closed: %s", campana_id)
        return True

    def pause_campaign(self, campana_id: str) -> bool:
        """Pause a campaign."""
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                return False
            campana.estado = EstadoCampana.PAUSADA.value
            session.commit()
        logger.info("Campaign paused: %s", campana_id)
        return True

    def resume_campaign(self, campana_id: str) -> bool:
        """Resume a paused campaign."""
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None or campana.estado != EstadoCampana.PAUSADA.value:
                return False
            campana.estado = EstadoCampana.ACTIVA.value
            session.commit()
        logger.info("Campaign resumed: %s", campana_id)
        return True

    def list_campaigns(self) -> List[Dict[str, Any]]:
        """List all campaigns with basic info."""
        with self.db.session() as session:
            campanas = (
                session.query(Campana)
                .order_by(Campana.fecha_creacion.desc())
                .all()
            )
            return [
                {
                    "id": c.id,
                    "nombre": c.nombre,
                    "estado": c.estado,
                    "fecha_inicio": str(c.fecha_inicio),
                    "fecha_fin": str(c.fecha_fin),
                    "total_clientes": c.total_clientes,
                    "dia_actual": c.dia_actual,
                    "dias_restantes": c.dias_restantes,
                }
                for c in campanas
            ]

    def resolve_browse_campaign_id(self, preferred: str | None = None) -> str | None:
        """
        Pick a campaign id for read-only browsing in the database UI.

        Priority: explicit selection → active campaign → most recent stored.
        """
        campaigns = self.list_campaigns()
        if not campaigns:
            return None
        if preferred and any(c["id"] == preferred for c in campaigns):
            return preferred
        active = self.get_active_campaign()
        if active:
            return active.id
        return campaigns[0]["id"]

    @staticmethod
    def _purge_campaign_records(session: Session, campana_id: str | None = None) -> None:
        """
        Remove campaign-related rows in FK-safe order.

        SQLite has PRAGMA foreign_keys=ON; bulk ``DELETE FROM campanas`` fails if
        ``campana_banco_meta`` (and other dependents) still reference the row.
        """
        def _scoped(query, model):
            if campana_id is None:
                return query
            return query.filter(model.campana_id == campana_id)

        _scoped(session.query(CartaGenerada), CartaGenerada).delete(
            synchronize_session=False
        )
        _scoped(session.query(HistorialTramo), HistorialTramo).delete(
            synchronize_session=False
        )
        _scoped(session.query(Cliente), Cliente).delete(synchronize_session=False)
        _scoped(session.query(CampanaBancoMeta), CampanaBancoMeta).delete(
            synchronize_session=False
        )
        _scoped(session.query(HistorialContacto), HistorialContacto).delete(
            synchronize_session=False
        )
        _scoped(session.query(HistorialZona), HistorialZona).delete(
            synchronize_session=False
        )
        _scoped(session.query(HistorialRepartoCall), HistorialRepartoCall).delete(
            synchronize_session=False
        )

    def delete_campaign_local(self, campana_id: str) -> Dict[str, Any]:
        """Delete one stored campaign and its related local audit rows."""
        with self.db.session() as session:
            campana = session.get(Campana, campana_id)
            if campana is None:
                raise ValueError(f"Campaña no encontrada: {campana_id}")

            n_clients = (
                session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
                .count()
            )
            self._purge_campaign_records(session, campana_id)
            session.delete(campana)
            session.commit()

        self._record_sync(
            "delete_campaign",
            n_clients,
            "ok",
            f"campaign={campana_id}",
        )
        logger.info("Deleted local campaign %s (%d clients)", campana_id, n_clients)
        return {
            "campaign_id": campana_id,
            "clients_deleted": n_clients,
        }

    def delete_all_campaign_data(
        self,
        firebase_service=None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Delete ALL campaign data from SQLite and optionally Firebase.

        This is a nuclear reset: removes all campaigns, clients,
        historial_tramos, cartas_generadas, and sync_log from the
        local database.  If firebase_service is provided, also deletes
        the 'cartera_activa' campaign from Firestore.

        Args:
            firebase_service: Optional FirebaseService instance.
            progress_callback: Optional callable(step, total, msg).

        Returns:
            {
                "local_campaigns_deleted": int,
                "local_clients_deleted":   int,
                "local_sync_logs_deleted":  int,
                "firebase": { ... } | None,
            }
        """
        result: Dict[str, Any] = {
            "local_campaigns_deleted": 0,
            "local_clients_deleted": 0,
            "local_sync_logs_deleted": 0,
            "firebase": None,
        }

        total_steps = 3 if firebase_service else 2

        # Step 1: Delete Firebase data (if connected)
        if firebase_service:
            if progress_callback:
                progress_callback(0, total_steps, "Eliminando datos de Firebase…")
            try:
                fb_result = firebase_service.delete_cartera_activa(
                    progress_callback=None  # firebase has its own sub-progress
                )
                result["firebase"] = fb_result
            except Exception as e:
                logger.error("Firebase delete failed: %s", e)
                result["firebase"] = {"error": str(e)}

        # Step 2: Delete local campaign data (cascade deletes clients etc.)
        step = 2 if firebase_service else 1
        if progress_callback:
            progress_callback(step - 1, total_steps, "Eliminando campañas locales…")

        from .database import SyncLog
        with self.db.session() as session:
            # Count before delete
            n_clients = session.query(Cliente).count()
            n_campaigns = session.query(Campana).count()

            self._purge_campaign_records(session)
            session.query(Campana).delete(synchronize_session=False)
            session.commit()

            result["local_campaigns_deleted"] = n_campaigns
            result["local_clients_deleted"] = n_clients

        # Step 3: Clear sync log
        if progress_callback:
            progress_callback(step, total_steps, "Limpiando registro de sincronización…")

        with self.db.session() as session:
            n_logs = session.query(SyncLog).count()
            session.query(SyncLog).delete()
            session.commit()
            result["local_sync_logs_deleted"] = n_logs

        if progress_callback:
            progress_callback(total_steps, total_steps, "Limpieza completada")

        self._record_sync(
            "delete_all",
            result["local_clients_deleted"],
            "ok",
            f"Campaigns: {result['local_campaigns_deleted']}, "
            f"Firebase: {'sí' if firebase_service else 'no'}",
        )

        logger.info("All campaign data deleted: %s", result)
        return result

    def delete_all_local_data(
        self,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Delete ALL local campaign-related data without touching Firebase.
        """
        result: Dict[str, Any] = {
            "local_campaigns_deleted": 0,
            "local_clients_deleted": 0,
            "local_sync_logs_deleted": 0,
        }

        if progress_callback:
            progress_callback(0, 2, "Eliminando campañas locales…")

        from .database import SyncLog
        with self.db.session() as session:
            n_clients = session.query(Cliente).count()
            n_campaigns = session.query(Campana).count()
            self._purge_campaign_records(session)
            session.query(Campana).delete(synchronize_session=False)
            session.commit()
            result["local_campaigns_deleted"] = n_campaigns
            result["local_clients_deleted"] = n_clients

        if progress_callback:
            progress_callback(1, 2, "Limpiando registro de sincronización…")

        with self.db.session() as session:
            n_logs = session.query(SyncLog).count()
            session.query(SyncLog).delete()
            session.commit()
            result["local_sync_logs_deleted"] = n_logs

        if progress_callback:
            progress_callback(2, 2, "Limpieza local completada")

        self._record_sync(
            "delete_all_local",
            result["local_clients_deleted"],
            "ok",
            f"Campaigns: {result['local_campaigns_deleted']}, Firebase: no",
        )

        logger.info("All local data deleted: %s", result)
        return result

    def cleanup_old_local_data(
        self,
        days_to_keep: int = 90,
    ) -> Dict[str, Any]:
        """
        Smart local cleanup: remove non-active campaigns older than N days.

        Rules:
        - Never deletes the active campaign.
        - Deletes campaigns in estado != activa if fecha_fin/fecha_creacion are old.
        - Cleans old sync logs older than the same cutoff.
        """
        days = max(1, int(days_to_keep or 90))
        cutoff_date = date.today() - timedelta(days=days)
        cutoff_dt = datetime.now() - timedelta(days=days)

        result: Dict[str, Any] = {
            "days_to_keep": days,
            "deleted_campaign_ids": [],
            "deleted_campaigns": 0,
            "deleted_clients_estimate": 0,
            "deleted_sync_logs": 0,
        }

        from .database import SyncLog
        with self.db.session() as session:
            candidates = (
                session.query(Campana)
                .filter(Campana.estado != EstadoCampana.ACTIVA.value)
                .all()
            )

            for camp in candidates:
                fecha_ref = camp.fecha_fin or camp.fecha_inicio
                if fecha_ref and fecha_ref >= cutoff_date:
                    continue
                if (not fecha_ref) and camp.fecha_creacion and camp.fecha_creacion >= cutoff_dt:
                    continue

                result["deleted_clients_estimate"] += camp.total_clientes or 0
                result["deleted_campaign_ids"].append(camp.id)
                self._purge_campaign_records(session, camp.id)
                session.delete(camp)

            session.commit()
            result["deleted_campaigns"] = len(result["deleted_campaign_ids"])

        with self.db.session() as session:
            logs = session.query(SyncLog).filter(SyncLog.fecha < cutoff_dt).all()
            result["deleted_sync_logs"] = len(logs)
            for item in logs:
                session.delete(item)
            session.commit()

        self._record_sync(
            "cleanup_old",
            result["deleted_clients_estimate"],
            "ok",
            f"dias={days}, campañas={result['deleted_campaigns']}, logs={result['deleted_sync_logs']}",
        )
        logger.info("Old local data cleanup done: %s", result)
        return result

    # ─────────────────────────────────────────────────────────────
    #  7. LETTER TRACKING
    # ─────────────────────────────────────────────────────────────

    def get_pending_letters(
        self,
        campana_id: str,
        numero_carta: int | None = None,
        tramo: int | None = None,
        *,
        include_omitted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get clients that still need letters published.

        Args:
            campana_id: Campaign ID.
            numero_carta: Filter by specific carta number (1-5).
            tramo: Filter by tramo number (1-3).
            include_omitted: Include cartas omitted by balance threshold.

        Returns:
            List of dicts with client info + carta details.
        """
        with self.db.session() as session:
            # Run evaluation to get the latest pending cartas
            campana = session.get(Campana, campana_id)
            if campana is None:
                return []

            result = self.tramo_engine.evaluate_campaign(session, campana)

            pending = []
            for cp in result.cartas_pendientes:
                if cp.omitida_por_monto and not include_omitted:
                    continue
                if numero_carta is not None and cp.numero_carta != numero_carta:
                    continue
                if tramo is not None and cp.tramo != tramo:
                    continue
                pending.append(self._pending_letter_to_dict(cp))

            return pending

    def group_pending_letters_by_section(
        self,
        campana_id: str,
        numero_carta: int | None = None,
        tramo: int | None = None,
        *,
        include_omitted: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return pending letters grouped by composite section key."""
        pending = self.get_pending_letters(
            campana_id,
            numero_carta=numero_carta,
            tramo=tramo,
            include_omitted=include_omitted,
        )
        return self._group_pending_letters_by_section(pending)

    def build_pending_letter_distribution(
        self,
        campana_id: str,
        gestor_users: List[Dict[str, Any]],
        numero_carta: int | None = None,
        tramo: int | None = None,
        *,
        include_omitted: bool = False,
    ) -> Dict[str, Any]:
        """
        Build a publication-ready preview of pending letters grouped by gestor.

        This is the base for the future "publicar cartas" flow: it resolves
        the pending client list against the current gestor/section assignment
        without generating files yet.
        """
        pending = self.get_pending_letters(
            campana_id,
            numero_carta=numero_carta,
            tramo=tramo,
            include_omitted=include_omitted,
        )
        by_seccion = self._group_pending_letters_by_section(pending)
        assignment_index = self._build_section_assignment_index(gestor_users)

        by_gestor: Dict[str, Dict[str, Any]] = {}
        unassigned_sections: Dict[str, Dict[str, Any]] = {}
        conflicted_sections: Dict[str, Dict[str, Any]] = {}
        pending_client_ids: set[int] = set()
        pending_cartas: set[int] = set()
        pending_tramos: set[int] = set()

        for item in pending:
            cliente_id = item.get("cliente_id")
            if cliente_id is not None:
                pending_client_ids.add(int(cliente_id))
            numero = item.get("numero_carta")
            if numero is not None:
                pending_cartas.add(int(numero))
            tramo_item = item.get("tramo")
            if tramo_item is not None:
                pending_tramos.add(int(tramo_item))

        for seccion_key, items in by_seccion.items():
            assignment = assignment_index.get(seccion_key)
            if not assignment:
                unassigned_sections[seccion_key] = {
                    "seccion_key": seccion_key,
                    "seccion": items[0].get("seccion", ""),
                    "region": items[0].get("region", ""),
                    "zona": items[0].get("zona", ""),
                    "total_clientes": len(items),
                    "items": items,
                }
                continue

            if assignment["status"] == "conflict":
                conflicted_sections[seccion_key] = {
                    "seccion_key": seccion_key,
                    "seccion": items[0].get("seccion", ""),
                    "region": items[0].get("region", ""),
                    "zona": items[0].get("zona", ""),
                    "total_clientes": len(items),
                    "items": items,
                    "gestores": assignment["gestores"],
                }
                continue

            gestor_uid = assignment["gestor_uid"]
            gestor_bucket = by_gestor.setdefault(
                gestor_uid,
                {
                    "gestor_uid": gestor_uid,
                    "gestor_nombre": assignment["gestor_nombre"],
                    "gestor_email": assignment["gestor_email"],
                    "gestor_rol": assignment["gestor_rol"],
                    "gestor_telefono": assignment.get("gestor_telefono", ""),
                    "secciones": {},
                    "items": [],
                    "total_clientes": 0,
                    "total_cartas": 0,
                    "_cliente_ids": set(),
                },
            )
            gestor_bucket["secciones"][seccion_key] = items
            gestor_bucket["items"].extend(items)
            gestor_bucket["total_cartas"] += len(items)
            for item in items:
                cliente_id = item.get("cliente_id")
                if cliente_id is not None:
                    gestor_bucket["_cliente_ids"].add(int(cliente_id))
            gestor_bucket["total_clientes"] = len(gestor_bucket["_cliente_ids"])

        for gestor_bucket in by_gestor.values():
            gestor_bucket.pop("_cliente_ids", None)

        return {
            "pending": pending,
            "by_seccion": by_seccion,
            "by_gestor": by_gestor,
            "unassigned_sections": unassigned_sections,
            "conflicted_sections": conflicted_sections,
            "summary": {
                "tramo": tramo,
                "numero_carta": numero_carta,
                "cartas": sorted(pending_cartas),
                "tramos": sorted(t for t in pending_tramos if t),
                "total_clientes": len(pending_client_ids),
                "total_cartas": len(pending),
                "total_secciones": len(by_seccion),
                "total_gestores": len(by_gestor),
                "secciones_sin_gestor": len(unassigned_sections),
                "secciones_en_conflicto": len(conflicted_sections),
            },
        }

    def publish_pending_letters(
        self,
        firebase_service,
        campana_id: str,
        gestor_users: List[Dict[str, Any]],
        numero_carta: int | None,
        tramo: int | None = None,
        *,
        published_by: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Generate and publish pending letters for one carta or all cartas.
        """
        if firebase_service is None or not getattr(firebase_service, "_initialized", False):
            raise RuntimeError("Firebase no está inicializado.")
        published_by = published_by or {}

        if numero_carta is not None:
            return self._publish_pending_letters_single(
                firebase_service,
                campana_id,
                gestor_users,
                numero_carta=numero_carta,
                tramo=tramo,
                published_by=published_by,
                send_notifications=True,
            )

        distribution = self.build_pending_letter_distribution(
            campana_id,
            gestor_users,
            numero_carta=None,
            tramo=tramo,
        )
        if not distribution["pending"]:
            raise ValueError("No hay cartas pendientes para publicar con esos filtros.")
        if not distribution["by_gestor"]:
            raise ValueError(
                "No hay gestores listos para publicación. Revise secciones sin gestor o en conflicto."
            )

        cartas_publicadas = sorted(
            {
                int(item["numero_carta"])
                for item in distribution["pending"]
                if item.get("numero_carta") is not None
            }
        )
        if not cartas_publicadas:
            raise ValueError("No se encontró ninguna carta pendiente para publicar.")

        aggregate: Dict[str, Any] = {
            "distribution": distribution,
            "output_dir": "",
            "output_dirs": [],
            "zip_path": None,
            "zip_paths": [],
            "files": [],
            "entries": [],
            "total_letters": 0,
            "total_files": 0,
            "published_count": 0,
            "uploaded_files_count": 0,
            "uploaded_by_format": {"DOCX": 0, "PDF": 0, "JPG": 0},
            "used_word_template": False,
            "used_word_template_cards": {},
            "errors": [],
            "published_cards": cartas_publicadas,
            "notifications_sent": 0,
        }

        for carta_num in cartas_publicadas:
            result = self._publish_pending_letters_single(
                firebase_service,
                campana_id,
                gestor_users,
                numero_carta=carta_num,
                tramo=tramo,
                published_by=published_by,
                send_notifications=False,
            )
            output_dir = str(result.get("output_dir") or "")
            if output_dir:
                aggregate["output_dirs"].append(output_dir)
                if not aggregate["output_dir"]:
                    aggregate["output_dir"] = output_dir
            zip_path = result.get("zip_path")
            if zip_path:
                aggregate["zip_paths"].append(zip_path)
                if not aggregate["zip_path"]:
                    aggregate["zip_path"] = zip_path
            aggregate["files"].extend(result.get("files", []))
            aggregate["entries"].extend(result.get("entries", []))
            aggregate["total_letters"] += int(result.get("total_letters", 0))
            aggregate["total_files"] += int(result.get("total_files", 0))
            aggregate["published_count"] += int(result.get("published_count", 0))
            aggregate["uploaded_files_count"] += int(result.get("uploaded_files_count", 0))
            by_fmt = result.get("uploaded_by_format") or {}
            agg_fmt = aggregate["uploaded_by_format"]
            for key in ("DOCX", "PDF", "JPG"):
                agg_fmt[key] = int(agg_fmt.get(key, 0)) + int(by_fmt.get(key, 0))
            aggregate["used_word_template"] = (
                aggregate["used_word_template"] or bool(result.get("used_word_template"))
            )
            aggregate["used_word_template_cards"][carta_num] = bool(
                result.get("used_word_template")
            )
            aggregate["errors"].extend(result.get("errors", []))

        if aggregate["published_count"] > 0:
            notif = firebase_service.notify_letters_published(
                campaign_id=campana_id,
                distribution=distribution,
                published_cards=cartas_publicadas,
                tramo=tramo,
                total_letters=aggregate["published_count"],
            )
            aggregate["notifications_sent"] = int(notif.get("sent", 0))
            notif_errors = [f"notificación: {err}" for err in notif.get("errors", [])]
            aggregate["errors"].extend(notif_errors)

        return aggregate

    def _publish_pending_letters_single(
        self,
        firebase_service,
        campana_id: str,
        gestor_users: List[Dict[str, Any]],
        *,
        numero_carta: int,
        tramo: int | None = None,
        published_by: Dict[str, Any] | None = None,
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """Publish a single carta number for the selected tramo/all tramos."""
        if not numero_carta:
            raise ValueError("Debe seleccionar una carta específica para publicar.")

        distribution = self.build_pending_letter_distribution(
            campana_id,
            gestor_users,
            numero_carta=numero_carta,
            tramo=tramo,
        )
        if not distribution["pending"]:
            raise ValueError("No hay cartas pendientes para publicar con esos filtros.")
        if not distribution["by_gestor"]:
            raise ValueError(
                "No hay gestores listos para publicación. Revise secciones sin gestor o en conflicto."
            )

        published_by = published_by or {}

        with self.db.session() as session:
            campana = self._get_campana(session, campana_id)
            if campana is None:
                raise ValueError("No se encontró la campaña activa.")

            cfg = ConfigCampana.get_or_create(session)
            plantilla = PlantillaCarta.get_or_create(session, numero_carta)
            template_text = plantilla.contenido or ""
            word_template_path = str(plantilla.word_template_path or "").strip()
            campaign_info = {
                "id": str(campana.id),
                "nombre": getattr(campana, "nombre", ""),
            }
            gestor_config = {
                k: v for k, v in cfg.to_dict().items()
                if k in (
                    "nombre_empresa", "ruc_empresa", "nombre_gestor",
                    "cargo_gestor", "telefono_gestor", "correo_gestor",
                    "direccion_empresa",
                )
            }
            client_ids = [
                int(item["cliente_id"])
                for item in distribution["pending"]
                if item.get("cliente_id") is not None
            ]
            full_clients = self._get_client_dicts_by_ids(session, client_ids)

        by_seccion_full: Dict[str, List[Dict[str, Any]]] = {}
        gestores_info: Dict[str, str] = {}
        gestores_phones: Dict[str, str] = {}
        section_assignments: Dict[str, Dict[str, Any]] = {}
        pending_index: Dict[tuple[int, str], Dict[str, Any]] = {}

        for item in distribution["pending"]:
            pending_index[(int(item["cliente_id"]), str(item["seccion_key"]))] = item

        for gestor in distribution["by_gestor"].values():
            for seccion_key, items in (gestor.get("secciones") or {}).items():
                section_assignments[seccion_key] = gestor
                gestores_info[seccion_key] = gestor.get("gestor_nombre", "")
                gestores_phones[seccion_key] = gestor.get("gestor_telefono", "")
                full_list: List[Dict[str, Any]] = []
                for item in items:
                    full = dict(full_clients.get(int(item["cliente_id"])) or item)
                    full["cliente_id"] = item["cliente_id"]
                    full["seccion_key"] = item["seccion_key"]
                    full["seccion"] = full.get("seccion") or item.get("seccion", "")
                    full["region"] = full.get("region") or item.get("region", "")
                    full["zona"] = full.get("zona") or item.get("zona", "")
                    full_list.append(full)
                by_seccion_full[seccion_key] = full_list

        output_dir = self._build_publication_output_dir(
            campana_id=campana_id,
            numero_carta=numero_carta,
            tramo=tramo,
        )

        from .letter_exporter import (
            export_all_letters,
            export_all_letters_from_word,
            build_zip,
        )

        use_word_template = bool(word_template_path and os.path.isfile(word_template_path))
        if use_word_template:
            export_result = export_all_letters_from_word(
                by_seccion=by_seccion_full,
                numero_carta=numero_carta,
                template_path=word_template_path,
                output_dir=output_dir,
                gestores_info=gestores_info,
                gestores_phones=gestores_phones,
                campaign_id=campana_id,
                gestor_config=gestor_config,
                campaign_info=campaign_info,
                formats=["docx"],
            )
        else:
            export_result = export_all_letters(
                by_seccion=by_seccion_full,
                numero_carta=numero_carta,
                output_dir=output_dir,
                formats=["docx"],
                gestores_info=gestores_info,
                campaign_id=campana_id,
                gestor_config=gestor_config,
                template_text=template_text,
                campaign_info=campaign_info,
            )

        zip_path = None
        if export_result.get("files"):
            zip_name = f"cartas_publicadas_E{numero_carta}_{campana_id}.zip"
            zip_path = build_zip(
                export_result["files"],
                os.path.join(output_dir, zip_name),
            )

        uploaded_files_count = 0
        uploaded_by_format: Dict[str, int] = {"DOCX": 0, "PDF": 0, "JPG": 0}
        local_publication_records: Dict[tuple[int, str], Dict[str, Any]] = {}
        upload_errors: List[str] = []
        for entry in export_result.get("entries", []):
            seccion_key = str(entry.get("seccion_key") or "")
            gestor = section_assignments.get(seccion_key)
            if not gestor:
                upload_errors.append(
                    f"No se encontró gestor para la sección {seccion_key} al subir {entry.get('path', '')}"
                )
                continue

            cliente_id_int = int(entry.get("cliente_id") or 0)
            pending_item = pending_index.get((cliente_id_int, seccion_key), {})
            try:
                metadata = firebase_service.upload_generated_letter(
                    file_path=entry["path"],
                    campaign_id=campana_id,
                    numero_carta=numero_carta,
                    seccion_key=seccion_key,
                    gestor_uid=str(gestor.get("gestor_uid") or ""),
                    cliente_id=str(entry.get("codigo_cliente") or ""),
                    extra_metadata={
                        "formato": str(entry.get("format") or "pdf").upper(),
                        "estado_publicacion": "publicada",
                        "gestor_nombre": gestor.get("gestor_nombre", ""),
                        "seccion": pending_item.get("seccion", ""),
                        "region": pending_item.get("region", ""),
                        "zona": pending_item.get("zona", ""),
                        "publicado_por_uid": str(published_by.get("uid") or ""),
                        "publicado_por_nombre": str(published_by.get("nombre") or ""),
                        "fecha_publicacion": firebase_service.firestore_timestamp(),
                    },
                )
                key = (cliente_id_int, seccion_key)
                record = local_publication_records.setdefault(
                    key,
                    {
                        "cliente_id": cliente_id_int,
                        "campana_id": campana_id,
                        "numero_carta": numero_carta,
                        "tramo": int(pending_item.get("tramo") or 0),
                        "seccion_key": seccion_key,
                        "gestor_uid": str(gestor.get("gestor_uid") or ""),
                        "gestor_nombre": str(gestor.get("gestor_nombre") or ""),
                        "archivo_path": "",
                        "nombre_archivo": "",
                        "storage_path": "",
                        "formato_set": set(),
                        "publicado_por_uid": str(published_by.get("uid") or ""),
                        "publicado_por_nombre": str(published_by.get("nombre") or ""),
                        "estado_publicacion": "publicada",
                    },
                )
                fmt = str(entry.get("format") or "pdf").upper()
                record["formato_set"].add(fmt)
                record["estado_publicacion"] = "publicada"
                if fmt == "JPG" or (fmt != "DOCX" and not record["archivo_path"]):
                    record["archivo_path"] = str(entry.get("path") or "")
                    record["nombre_archivo"] = str(
                        metadata.get("nombre_archivo") or os.path.basename(entry["path"])
                    )
                    record["storage_path"] = str(metadata.get("storage_path") or "")
                elif fmt == "PDF" and not record["archivo_path"]:
                    record["archivo_path"] = str(entry.get("path") or "")
                    record["nombre_archivo"] = str(
                        metadata.get("nombre_archivo") or os.path.basename(entry["path"])
                    )
                    record["storage_path"] = str(metadata.get("storage_path") or "")
                uploaded_files_count += 1
                if fmt in uploaded_by_format:
                    uploaded_by_format[fmt] += 1
            except Exception as e:
                upload_errors.append(
                    f"{entry.get('codigo_cliente', '?')} — {e}"
                )
                key = (cliente_id_int, seccion_key)
                record = local_publication_records.setdefault(
                    key,
                    {
                        "cliente_id": cliente_id_int,
                        "campana_id": campana_id,
                        "numero_carta": numero_carta,
                        "tramo": int(pending_item.get("tramo") or 0),
                        "seccion_key": seccion_key,
                        "gestor_uid": str(gestor.get("gestor_uid") or ""),
                        "gestor_nombre": str(gestor.get("gestor_nombre") or ""),
                        "archivo_path": str(entry.get("path") or ""),
                        "nombre_archivo": os.path.basename(str(entry.get("path") or "")),
                        "storage_path": "",
                        "formato_set": set(),
                        "publicado_por_uid": str(published_by.get("uid") or ""),
                        "publicado_por_nombre": str(published_by.get("nombre") or ""),
                        "estado_publicacion": "error",
                    },
                )
                record["formato_set"].add(str(entry.get("format") or "pdf").upper())
                if record["estado_publicacion"] != "publicada":
                    record["estado_publicacion"] = "error"

        published_count = 0
        for record in local_publication_records.values():
            formato_set = record.pop("formato_set", set())
            record["formato"] = "+".join(sorted(formato_set)) if formato_set else "PDF"
            self.record_letter_publication(**record)
            if record.get("estado_publicacion") == "publicada":
                published_count += 1

        errors = list(export_result.get("errors", [])) + upload_errors
        notifications_sent = 0
        if send_notifications and published_count > 0:
            notif = firebase_service.notify_letters_published(
                campaign_id=campana_id,
                distribution=distribution,
                numero_carta=numero_carta,
                tramo=tramo,
                total_letters=published_count,
            )
            notifications_sent = int(notif.get("sent", 0))
            errors.extend(f"notificación: {err}" for err in notif.get("errors", []))

        return {
            "distribution": distribution,
            "output_dir": output_dir,
            "zip_path": zip_path,
            "files": export_result.get("files", []),
            "entries": export_result.get("entries", []),
            "total_letters": export_result.get("total_letters", 0),
            "total_files": export_result.get("total_files", 0),
            "published_count": published_count,
            "uploaded_files_count": uploaded_files_count,
            "uploaded_by_format": uploaded_by_format,
            "used_word_template": use_word_template,
            "published_cards": [numero_carta],
            "notifications_sent": notifications_sent,
            "errors": errors,
        }

    def mark_letter_generated(
        self,
        cliente_id: int,
        campana_id: str,
        numero_carta: int,
        archivo_path: str = "",
    ) -> None:
        """Record that a letter has been physically generated."""
        with self.db.session() as session:
            existing = (
                session.query(CartaGenerada)
                .filter(
                    CartaGenerada.cliente_id == cliente_id,
                    CartaGenerada.campana_id == campana_id,
                    CartaGenerada.numero_carta == numero_carta,
                )
                .first()
            )
            if existing:
                existing.archivo_path = archivo_path
                existing.fue_impresa = True
            else:
                carta = CartaGenerada(
                    cliente_id=cliente_id,
                    campana_id=campana_id,
                    numero_carta=numero_carta,
                    tramo=self.tramo_engine.get_tramo_for_day(
                        CARTA_SCHEDULE_DAYS.get(numero_carta, 1)
                    ).value if hasattr(self, '_carta_days') else numero_carta,
                    archivo_path=archivo_path,
                    fue_impresa=True,
                )
                session.add(carta)
            session.commit()

    def record_letter_publication(
        self,
        cliente_id: int,
        campana_id: str,
        numero_carta: int,
        *,
        tramo: int = 0,
        archivo_path: str = "",
        seccion_key: str = "",
        gestor_uid: str = "",
        gestor_nombre: str = "",
        nombre_archivo: str = "",
        storage_path: str = "",
        formato: str = "PDF",
        publicado_por_uid: str = "",
        publicado_por_nombre: str = "",
        estado_publicacion: str = "publicada",
    ) -> None:
        """Persist local publication metadata without marking the letter as printed."""
        with self.db.session() as session:
            existing = (
                session.query(CartaGenerada)
                .filter(
                    CartaGenerada.cliente_id == cliente_id,
                    CartaGenerada.campana_id == campana_id,
                    CartaGenerada.numero_carta == numero_carta,
                )
                .first()
            )
            if existing is None:
                existing = CartaGenerada(
                    cliente_id=cliente_id,
                    campana_id=campana_id,
                    numero_carta=numero_carta,
                    tramo=tramo or numero_carta,
                )
                session.add(existing)

            existing.tramo = tramo or existing.tramo
            existing.archivo_path = archivo_path or existing.archivo_path
            existing.seccion_key = seccion_key or existing.seccion_key
            existing.gestor_uid = gestor_uid or existing.gestor_uid
            existing.gestor_nombre = gestor_nombre or existing.gestor_nombre
            existing.nombre_archivo = nombre_archivo or existing.nombre_archivo
            existing.storage_path = storage_path or existing.storage_path
            existing.formato = formato or existing.formato
            existing.estado_publicacion = estado_publicacion or existing.estado_publicacion
            existing.fecha_publicacion = datetime.now()
            existing.publicado_por_uid = publicado_por_uid or existing.publicado_por_uid
            existing.publicado_por_nombre = (
                publicado_por_nombre or existing.publicado_por_nombre
            )
            session.commit()

    # ─────────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────────

    def _get_campana(
        self,
        session: Session,
        campana_id: str | None = None,
    ) -> Campana | None:
        """Helper to get a specific or the active campaign."""
        if campana_id:
            return session.get(Campana, campana_id)
        return (
            session.query(Campana)
            .filter(Campana.estado == EstadoCampana.ACTIVA.value)
            .order_by(Campana.fecha_creacion.desc())
            .first()
        )

    def _get_client_dicts_by_ids(
        self,
        session: Session,
        client_ids: List[int],
    ) -> Dict[int, Dict[str, Any]]:
        """Load a map of SQLite client id -> full client dict."""
        if not client_ids:
            return {}
        rows = (
            session.query(Cliente)
            .filter(Cliente.id.in_(sorted(set(client_ids))))
            .all()
        )
        result: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            data = self._cliente_to_dict(row, include_sensitive=True)
            data["cliente_id"] = row.id
            result[row.id] = data
        return result

    def _build_publication_output_dir(
        self,
        *,
        campana_id: str,
        numero_carta: int,
        tramo: int | None,
    ) -> str:
        """Build a persistent output folder for published letters."""
        base_dir = os.path.join(
            os.path.dirname(self.db.db_path),
            "publicaciones",
            str(campana_id),
        )
        tramo_label = f"T{tramo}" if tramo is not None else "Tall"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            base_dir,
            f"{stamp}_E{numero_carta}_{tramo_label}",
        )
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    # ─────────────────────────────────────────────────────────────
    #  AUTO-EVALUATION & SCHEDULED LETTERS
    # ─────────────────────────────────────────────────────────────

    def auto_evaluate_on_startup(self) -> EvaluationResult | None:
        """Run tramo evaluation if ``auto_evaluar_tramos`` is enabled.

        Called once when the admin-app starts.  Returns the result or
        *None* if auto-eval is disabled / no active campaign exists.
        """
        from .tramo_engine import load_config
        cfg = load_config()
        if cfg is None or not cfg.auto_evaluar_tramos:
            return None

        camp = self.get_active_campaign()
        if camp is None:
            return None

        logger.info("Auto-evaluating tramos on startup …")
        return self.evaluate_tramos(campana_id=camp.id)

    def check_scheduled_letters(self) -> list[dict]:
        """Check for letters whose scheduled datetime has passed.

        For every carta whose ``cartaN_programada <= now`` **and** that
        still has pending (un-generated) instances, return a list of
        ``{"numero_carta": int, "pending": [dict]}`` entries.

        The caller (typically the background thread) decides whether to
        actually generate the Word documents.
        """
        from .database import ConfigCampana
        from datetime import datetime as _dt

        now = _dt.now()
        results: list[dict] = []

        with self.db.session() as session:
            cfg = ConfigCampana.get_or_create(session)
            active_campaign = self._get_campana(session)
            schedule = {
                1: cfg.carta1_programada,
                2: cfg.carta2_programada,
                3: cfg.carta3_programada,
                4: cfg.carta4_programada,
                5: cfg.carta5_programada,
            }

        if active_campaign is None:
            return results

        for num, programada in schedule.items():
            if programada is None or programada > now:
                continue
            pending = self.get_pending_letters(active_campaign.id, numero_carta=num)
            if pending:
                results.append({"numero_carta": num, "pending": pending})

        return results

    def _pending_letter_to_dict(self, cp) -> Dict[str, Any]:
        """Normalize CartaPendiente DTOs for UI/service consumers."""
        return {
            "cliente_id": cp.cliente_id,
            "codigo_cliente": cp.codigo_cliente,
            "nombre_completo": cp.nombre_completo,
            "region": cp.region,
            "zona": cp.zona,
            "seccion": cp.seccion,
            "seccion_key": cp.seccion_key,
            "numero_carta": cp.numero_carta,
            "tramo": cp.tramo,
            "dia_campana": cp.dia_campana,
            "saldo": cp.saldo,
            "omitida_por_monto": cp.omitida_por_monto,
        }

    def _group_pending_letters_by_section(
        self,
        pending: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group pending letter dicts by composite section key."""
        by_seccion: Dict[str, List[Dict[str, Any]]] = {}
        for item in pending:
            sec_key = str(
                item.get("seccion_key")
                or make_seccion_key(
                    item.get("region", ""),
                    item.get("zona", ""),
                    item.get("seccion", ""),
                )
            )
            item["seccion_key"] = sec_key
            by_seccion.setdefault(sec_key, []).append(item)
        return by_seccion

    def _build_section_assignment_index(
        self,
        gestor_users: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a section -> gestor assignment index from Firebase user profiles.

        If more than one active user claims the same section, the section is
        marked as a conflict so the publication flow can stop before sending.
        """
        assignments: Dict[str, Dict[str, Any]] = {}

        for user in gestor_users or []:
            if user.get("activo", True) is False:
                continue

            gestor_uid = str(user.get("uid") or user.get("id") or "").strip()
            if not gestor_uid:
                continue

            gestor_nombre = str(
                user.get("nombre") or user.get("email") or gestor_uid
            ).strip()
            gestor_email = str(user.get("email") or "").strip()
            gestor_rol = str(user.get("rol") or "gestor").strip()
            gestor_telefono = str(
                user.get("telefono") or user.get("telefono_movil") or ""
            ).strip()

            raw_sections = user.get("secciones") or []
            normalized_sections: List[str] = []
            if isinstance(raw_sections, list):
                normalized_sections.extend(
                    str(sk).strip()
                    for sk in raw_sections
                    if str(sk).strip()
                )

            legacy_section = str(user.get("seccion") or "").strip()
            if legacy_section:
                if "_" in legacy_section:
                    normalized_sections.append(legacy_section)
                else:
                    region = str(user.get("region") or "").strip()
                    zona = str(user.get("zona") or "").strip()
                    if region or zona:
                        normalized_sections.append(
                            make_seccion_key(region, zona, legacy_section)
                        )

            for sec_key in sorted(set(normalized_sections)):
                info = {
                    "gestor_uid": gestor_uid,
                    "gestor_nombre": gestor_nombre,
                    "gestor_email": gestor_email,
                    "gestor_rol": gestor_rol,
                    "gestor_telefono": gestor_telefono,
                    "status": "assigned",
                }
                existing = assignments.get(sec_key)
                if existing is None:
                    assignments[sec_key] = info
                    continue
                if existing.get("status") == "conflict":
                    known = {g["gestor_uid"] for g in existing["gestores"]}
                    if gestor_uid not in known:
                        existing["gestores"].append(info)
                    continue
                if existing["gestor_uid"] == gestor_uid:
                    continue
                assignments[sec_key] = {
                    "status": "conflict",
                    "gestores": [existing, info],
                }

        return assignments


# ── Carta schedule helper for mark_letter_generated ──────────────
CARTA_SCHEDULE_DAYS = {1: 1, 2: 9, 3: 11, 4: 35, 5: 44}


# ── Singleton ────────────────────────────────────────────────────
campaign_manager = CampaignManager()
