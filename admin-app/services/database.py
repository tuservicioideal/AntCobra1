"""
Database Service — SQLAlchemy ORM Models & Engine
Central data persistence layer for AntCobranzas.
Uses SQLite as the local source of truth.

SQLAlchemy 2.0 style with Mapped[] type annotations.
"""

from __future__ import annotations

import os
import enum
import shutil
import sys
from datetime import datetime, date, timedelta
from typing import Any, Optional, List

from sqlalchemy import (
    create_engine, String, Text, Float, Integer, Boolean,
    ForeignKey, DateTime, Date, Enum, event, Index, inspect, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
    Session, sessionmaker,
)


# ── Enums ────────────────────────────────────────────────────────

class EstadoCampana(str, enum.Enum):
    ACTIVA = "activa"
    PAUSADA = "pausada"
    CERRADA = "cerrada"


class EstadoGestion(str, enum.Enum):
    PENDIENTE = "pendiente"
    VISITADO_HABIDO = "visitado_habido"
    VISITADO_NO_HABIDO = "visitado_no_habido"
    FALLECIDO_INUBICABLE = "fallecido_inubicable"
    SUPLANTACION = "suplantacion"
    PAGO_NO_REGISTRADO = "pago_no_registrado"
    DEVOLUCION_PENDIENTE = "devolucion_pendiente"


# Sección Firestore reservada para clientes sin gestor asignado (solo admin).
POOL_REASIGNACION_SECTION = "_POOL_REASIGNACION"

# Sección Firestore para cuentas en gestión especial (reasignables a gestor dedicado).
GESTION_ESPECIAL_SECTION = "_GESTION_ESPECIAL"

# Prefijo de sección virtual por gestor de call center (Firestore: _CALL_{uid}).
CALL_SECTION_PREFIX = "_CALL_"

# Fases operativas de gestión (tramo 1 telefónico vs campo territorial).
FASE_GESTION_CALL = "call"
FASE_GESTION_CAMPO = "campo"


def make_call_section_key(gestor_uid: str) -> str:
    """Clave Firestore para la cartera virtual de un gestor de call center."""
    return f"{CALL_SECTION_PREFIX}{gestor_uid.strip()}"


def is_call_section_key(seccion_key: str) -> bool:
    return str(seccion_key or "").startswith(CALL_SECTION_PREFIX)

# Cliente ausente en re-subida de Excel del banco (p. ej. pagó).
MOTIVO_BAJA_EXCEL_BANCO = "ausente_en_excel_banco"


class EstadoCiclo(str, enum.Enum):
    ACTIVA = "activa"
    CERRADA = "cerrada"
    RETORNADA_BANCO = "retornada_banco"


class TramoEnum(int, enum.Enum):
    NONE = 0       # Sin asignar
    TRAMO_1 = 1    # Etapa 1 — recuperación inicial (días 1-10)
    TRAMO_2 = 2    # Etapa 2 — seguimiento medio (días 11-43)
    TRAMO_3 = 3    # Etapa 3 — cierre de gestión (días 44-59)


# ── Base ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Schema Version (simple migration tracking) ───────────────────

class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    description: Mapped[Optional[str]] = mapped_column(String(200))


# ── Campana (Campaign) ──────────────────────────────────────────

class Campana(Base):
    __tablename__ = "campanas"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(
        String(20), default=EstadoCampana.ACTIVA.value
    )
    archivo_origen: Mapped[Optional[str]] = mapped_column(String(500))
    total_clientes: Mapped[int] = mapped_column(Integer, default=0)
    total_secciones: Mapped[int] = mapped_column(Integer, default=0)
    deuda_total_asignada: Mapped[float] = mapped_column(Float, default=0.0)
    deuda_total_pendiente: Mapped[float] = mapped_column(Float, default=0.0)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    notas: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    clientes: Mapped[List["Cliente"]] = relationship(
        back_populates="campana", cascade="all, delete-orphan"
    )
    historial_tramos: Mapped[List["HistorialTramo"]] = relationship(
        back_populates="campana", cascade="all, delete-orphan"
    )
    cartas: Mapped[List["CartaGenerada"]] = relationship(
        back_populates="campana", cascade="all, delete-orphan"
    )
    campana_banco_meta: Mapped[List["CampanaBancoMeta"]] = relationship(
        back_populates="campana", cascade="all, delete-orphan"
    )

    @property
    def dia_actual(self) -> int:
        """Días transcurridos desde la primera carga de la cartera (informativo)."""
        delta = date.today() - self.fecha_inicio
        return max(1, delta.days + 1)

    @property
    def dias_restantes(self) -> int:
        delta = self.fecha_fin - date.today()
        return max(0, delta.days)

    def __repr__(self) -> str:
        return f"Campana(id={self.id!r}, nombre={self.nombre!r}, estado={self.estado!r})"


# ── Cliente ──────────────────────────────────────────────────────

class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campana_id: Mapped[str] = mapped_column(
        ForeignKey("campanas.id", ondelete="CASCADE")
    )

    # Identificación
    codigo_cliente: Mapped[str] = mapped_column(String(50), index=True)
    digito_control: Mapped[Optional[str]] = mapped_column(String(10))
    numero_documento: Mapped[Optional[str]] = mapped_column(String(20))  # DNI — SOLO local
    nombres: Mapped[Optional[str]] = mapped_column(String(100))
    apellido_paterno: Mapped[Optional[str]] = mapped_column(String(100))
    apellido_materno: Mapped[Optional[str]] = mapped_column(String(100))
    nombre_completo: Mapped[Optional[str]] = mapped_column(String(300))
    genero: Mapped[Optional[str]] = mapped_column(String(10))
    edad: Mapped[Optional[int]] = mapped_column(Integer)

    # Contacto
    telefono_fijo: Mapped[Optional[str]] = mapped_column(String(30))
    telefono_trabajo: Mapped[Optional[str]] = mapped_column(String(30))
    telefono_movil: Mapped[Optional[str]] = mapped_column(String(30))
    correo: Mapped[Optional[str]] = mapped_column(String(100))

    # Ubicación
    departamento: Mapped[Optional[str]] = mapped_column(String(60))
    provincia: Mapped[Optional[str]] = mapped_column(String(60))
    distrito: Mapped[Optional[str]] = mapped_column(String(60))
    direccion: Mapped[Optional[str]] = mapped_column(Text)
    referencia: Mapped[Optional[str]] = mapped_column(Text)
    coordenada_x: Mapped[Optional[float]] = mapped_column(Float)  # Longitud
    coordenada_y: Mapped[Optional[float]] = mapped_column(Float)  # Latitud

    # Clasificación bancaria
    segmentacion: Mapped[Optional[str]] = mapped_column(String(50))
    segmento_cartera: Mapped[Optional[str]] = mapped_column(String(50))
    etapa_deuda: Mapped[Optional[str]] = mapped_column(String(50))
    cobrador: Mapped[Optional[str]] = mapped_column(String(100))
    campana_banco: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    zona: Mapped[Optional[str]] = mapped_column(String(50))
    seccion: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    seccion_key: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    territorio: Mapped[Optional[str]] = mapped_column(String(50))
    perfil_score: Mapped[Optional[str]] = mapped_column(String(50))

    # Fechas
    fecha_documento: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_vencimiento: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_asignacion: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_cierre: Mapped[Optional[str]] = mapped_column(String(20))

    # Montos
    dias_atraso: Mapped[int] = mapped_column(Integer, default=0)
    importe_deuda_original: Mapped[float] = mapped_column(Float, default=0.0)
    importe_abonos_anteriores: Mapped[float] = mapped_column(Float, default=0.0)
    importe_deuda_asignada: Mapped[float] = mapped_column(Float, default=0.0)
    importe_deuda_pendiente: Mapped[float] = mapped_column(Float, default=0.0)

    # Estado de gestión de cobranza
    tramo_actual: Mapped[int] = mapped_column(
        Integer, default=TramoEnum.NONE.value
    )
    estado_gestion: Mapped[str] = mapped_column(
        String(30), default=EstadoGestion.PENDIENTE.value
    )
    nota_gestor: Mapped[Optional[str]] = mapped_column(Text)
    fecha_gestion: Mapped[Optional[datetime]] = mapped_column(DateTime)
    gps_latitud: Mapped[Optional[float]] = mapped_column(Float)
    gps_longitud: Mapped[Optional[float]] = mapped_column(Float)
    gps_timestamp: Mapped[Optional[str]] = mapped_column(String(30))

    # ── Clasificación jerárquica de gestión (Niveles 1-4) ────
    nivel_1: Mapped[Optional[str]] = mapped_column(String(100))  # Contacto efectivo, No contacto, etc.
    nivel_2: Mapped[Optional[str]] = mapped_column(String(100))  # Promesa de pago, Renuente, etc.
    nivel_3: Mapped[Optional[str]] = mapped_column(String(100))  # Promesa parcial, Cliente fallecido, etc.
    nivel_4: Mapped[Optional[str]] = mapped_column(String(100))  # CAM Promesa parcial, TEL Llamada fallida, etc.
    canal_gestion: Mapped[Optional[str]] = mapped_column(String(10))  # CAM o TEL
    fecha_promesa_pago: Mapped[Optional[str]] = mapped_column(String(20))
    monto_promesa_pago: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    ultima_nota_contacto: Mapped[Optional[str]] = mapped_column(Text)
    fecha_actualizacion_contacto_iso: Mapped[Optional[str]] = mapped_column(String(40))
    actualizado_por_uid: Mapped[Optional[str]] = mapped_column(String(100))
    actualizado_por_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    actualizado_por_email: Mapped[Optional[str]] = mapped_column(String(120))
    origen_actualizacion: Mapped[Optional[str]] = mapped_column(String(20))

    # Ubicación verificada en campo (sync desde Firebase ubicacion_verificada)
    ubicacion_verificada_lat: Mapped[Optional[float]] = mapped_column(Float)
    ubicacion_verificada_lng: Mapped[Optional[float]] = mapped_column(Float)
    ubicacion_verificada_fecha: Mapped[Optional[str]] = mapped_column(String(40))
    ubicacion_verificada_gestor: Mapped[Optional[str]] = mapped_column(String(200))

    # Devolución por zona inaccesible (solicitud gestor → reasignación admin)
    motivo_devolucion: Mapped[Optional[str]] = mapped_column(String(50))
    nota_devolucion: Mapped[Optional[str]] = mapped_column(Text)
    fecha_devolucion_solicitud: Mapped[Optional[str]] = mapped_column(String(40))
    gestor_devolucion_uid: Mapped[Optional[str]] = mapped_column(String(100))
    gestor_devolucion_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    gestor_devolucion_seccion: Mapped[Optional[str]] = mapped_column(String(80))

    # Cartera activa (archivado cuando el banco deja de enviar el cliente en Excel)
    activo_en_cartera: Mapped[bool] = mapped_column(Boolean, default=True)
    motivo_baja: Mapped[Optional[str]] = mapped_column(String(80))
    fecha_baja: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ultimo_excel: Mapped[Optional[str]] = mapped_column(String(300))

    # Ciclo individual por cuenta (59 días desde fecha_asignacion)
    fecha_asignacion_dt: Mapped[Optional[date]] = mapped_column(Date)
    fecha_cierre_dt: Mapped[Optional[date]] = mapped_column(Date)
    estado_ciclo: Mapped[str] = mapped_column(
        String(30), default=EstadoCiclo.ACTIVA.value
    )
    fecha_cierre_real: Mapped[Optional[date]] = mapped_column(Date)

    # Gestión especial (derivación fuera del gestor principal)
    gestion_especial: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_gestion_especial: Mapped[Optional[str]] = mapped_column(String(100))
    fecha_gestion_especial: Mapped[Optional[datetime]] = mapped_column(DateTime)
    seccion_origen: Mapped[Optional[str]] = mapped_column(String(80))

    # Call center (tramo 1 telefónico) → pase a campo en tramo 2 si aplica
    fase_gestion: Mapped[str] = mapped_column(
        String(10), default=FASE_GESTION_CAMPO, index=True
    )
    call_gestor_uid: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    call_gestor_nombre: Mapped[Optional[str]] = mapped_column(String(200))

    # Etiquetas de seguimiento (IDs del catálogo global, JSON array)
    etiquetas: Mapped[Optional[str]] = mapped_column(Text, default="[]")

    # Metadatos
    sincronizado_firebase: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    campana: Mapped["Campana"] = relationship(back_populates="clientes")
    historial_tramos: Mapped[List["HistorialTramo"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )
    cartas: Mapped[List["CartaGenerada"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )

    @property
    def es_alto_valor(self) -> bool:
        """Deuda mayor a S/ 500 se marca como alto valor."""
        return self.importe_deuda_pendiente > 500.0

    @property
    def requiere_carta_fisica(self) -> bool:
        """Solo se generan cartas físicas si saldo > S/ 40."""
        return self.importe_deuda_pendiente > 40.0

    @property
    def sigue_en_gestion(self) -> bool:
        """El cliente sigue en gestión si saldo >= S/ 10."""
        return self.importe_deuda_pendiente >= 10.0

    def get_fecha_asignacion_date(self, fallback: Optional[date] = None) -> Optional[date]:
        """Fecha de inicio del ciclo individual de la cuenta."""
        if self.fecha_asignacion_dt:
            return self.fecha_asignacion_dt
        from .date_utils import parse_excel_fecha
        return parse_excel_fecha(self.fecha_asignacion, fallback)

    @property
    def dia_ciclo(self) -> int:
        """Día del ciclo de cobranza de esta cuenta (1 = fecha de asignación)."""
        fa = self.get_fecha_asignacion_date()
        if fa is None:
            return 1
        return max(1, (date.today() - fa).days + 1)

    @property
    def ciclo_activo(self) -> bool:
        """True si la cuenta sigue en cartera de trabajo del gestor."""
        return (
            self.activo_en_cartera
            and self.estado_ciclo == EstadoCiclo.ACTIVA.value
        )

    def __repr__(self) -> str:
        return (
            f"Cliente(id={self.id!r}, codigo={self.codigo_cliente!r}, "
            f"nombre={self.nombre_completo!r}, tramo={self.tramo_actual})"
        )


# ── Indexes on Cliente ───────────────────────────────────────────

Index("ix_clientes_campana_seccion", Cliente.campana_id, Cliente.seccion)
Index("ix_clientes_campana_tramo", Cliente.campana_id, Cliente.tramo_actual)


# ── Historial de Tramos ─────────────────────────────────────────

class HistorialTramo(Base):
    __tablename__ = "historial_tramos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE")
    )
    campana_id: Mapped[str] = mapped_column(
        ForeignKey("campanas.id", ondelete="CASCADE")
    )
    tramo_anterior: Mapped[int] = mapped_column(Integer, default=0)
    tramo_nuevo: Mapped[int] = mapped_column(Integer)
    fecha_transicion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    motivo: Mapped[str] = mapped_column(
        String(200), default="Evaluación automática"
    )
    saldo_al_momento: Mapped[float] = mapped_column(Float, default=0.0)
    dia_campana: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    cliente: Mapped["Cliente"] = relationship(back_populates="historial_tramos")
    campana: Mapped["Campana"] = relationship(back_populates="historial_tramos")

    def __repr__(self) -> str:
        return (
            f"HistorialTramo(cliente_id={self.cliente_id}, "
            f"{self.tramo_anterior}→{self.tramo_nuevo}, día={self.dia_campana})"
        )


# ── Cartas Generadas ────────────────────────────────────────────

class CartaGenerada(Base):
    __tablename__ = "cartas_generadas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE")
    )
    campana_id: Mapped[str] = mapped_column(
        ForeignKey("campanas.id", ondelete="CASCADE")
    )
    numero_carta: Mapped[int] = mapped_column(Integer)  # 1, 2, 3, o 4
    tramo: Mapped[int] = mapped_column(Integer)
    fecha_generacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    archivo_path: Mapped[Optional[str]] = mapped_column(String(500))
    seccion_key: Mapped[Optional[str]] = mapped_column(String(50))
    gestor_uid: Mapped[Optional[str]] = mapped_column(String(100))
    gestor_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(300))
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    formato: Mapped[Optional[str]] = mapped_column(String(20))
    estado_publicacion: Mapped[str] = mapped_column(String(30), default="pendiente")
    fecha_publicacion: Mapped[Optional[datetime]] = mapped_column(DateTime)
    publicado_por_uid: Mapped[Optional[str]] = mapped_column(String(100))
    publicado_por_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    fue_impresa: Mapped[bool] = mapped_column(Boolean, default=False)
    omitida_por_monto: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    cliente: Mapped["Cliente"] = relationship(back_populates="cartas")
    campana: Mapped["Campana"] = relationship(back_populates="cartas")

    def __repr__(self) -> str:
        status = "omitida" if self.omitida_por_monto else "generada"
        return (
            f"Carta(#{self.numero_carta}, tramo={self.tramo}, "
            f"cliente_id={self.cliente_id}, {status})"
        )


# ── Gestor (copia local) ────────────────────────────────────────

class Gestor(Base):
    __tablename__ = "gestores"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # UID Firebase
    nombre: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(100))
    seccion: Mapped[str] = mapped_column(String(10), index=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(30))
    zona: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    rol: Mapped[str] = mapped_column(String(20), default="gestor")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )

    def __repr__(self) -> str:
        return f"Gestor(id={self.id!r}, nombre={self.nombre!r}, seccion={self.seccion!r})"


# ── Configuración de Campaña ─────────────────────────────────────

class ConfigCampana(Base):
    """Singleton — runtime-editable campaign parameters.

    There is always exactly ONE row (id=1).  The first call to
    ``get_or_create()`` seeds it with the historical defaults so the
    app behaves identically to the hardcoded constants when no admin
    has touched the settings page yet.
    """
    __tablename__ = "config_campana"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── Campaign duration ────────────────────────────────────
    duracion_dias: Mapped[int] = mapped_column(Integer, default=59)
    dias_cierre: Mapped[int] = mapped_column(Integer, default=60)
    dias_retorno_banco: Mapped[int] = mapped_column(Integer, default=70)
    ventana_ingreso_dias: Mapped[int] = mapped_column(Integer, default=21)

    # ── Tramo boundaries (días del ciclo por cuenta) ─────────
    tramo1_inicio: Mapped[int] = mapped_column(Integer, default=1)
    tramo1_fin: Mapped[int] = mapped_column(Integer, default=10)
    tramo2_inicio: Mapped[int] = mapped_column(Integer, default=11)
    tramo2_fin: Mapped[int] = mapped_column(Integer, default=43)
    tramo3_inicio: Mapped[int] = mapped_column(Integer, default=44)
    tramo3_fin: Mapped[int] = mapped_column(Integer, default=59)

    # ── Letter schedule (campaign day each letter is issued) ─
    # E1-1: first letter, friendly invitation (day 1 of E1)
    carta1_dia: Mapped[int] = mapped_column(Integer, default=1)
    # E1-2: second letter, motivational — don't lose status (day 9, still E1)
    carta2_dia: Mapped[int] = mapped_column(Integer, default=9)
    # E2-1: formal payment requirement (day 11, start of E2)
    carta3_dia: Mapped[int] = mapped_column(Integer, default=11)
    # E2-2: insistence letter (day 35, mid E2)
    carta4_dia: Mapped[int] = mapped_column(Integer, default=35)
    # E3-1: pre-judicial demand (day 44, start of E3)
    carta5_dia: Mapped[int] = mapped_column(Integer, default=44)

    # ── Scheduled generation date/time per letter ────────────
    carta1_programada: Mapped[Optional[datetime]] = mapped_column(DateTime)
    carta2_programada: Mapped[Optional[datetime]] = mapped_column(DateTime)
    carta3_programada: Mapped[Optional[datetime]] = mapped_column(DateTime)
    carta4_programada: Mapped[Optional[datetime]] = mapped_column(DateTime)
    carta5_programada: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # ── Gestor / Empresa (datos fijos para encabezados de cartas) ──
    nombre_empresa: Mapped[Optional[str]] = mapped_column(String(200))
    ruc_empresa: Mapped[Optional[str]] = mapped_column(String(20))
    nombre_gestor: Mapped[Optional[str]] = mapped_column(String(200))
    cargo_gestor: Mapped[Optional[str]] = mapped_column(String(100))
    telefono_gestor: Mapped[Optional[str]] = mapped_column(String(50))
    correo_gestor: Mapped[Optional[str]] = mapped_column(String(100))
    direccion_empresa: Mapped[Optional[str]] = mapped_column(Text)

    # ── Thresholds ───────────────────────────────────────────
    umbral_minimo_gestion: Mapped[float] = mapped_column(Float, default=10.0)
    umbral_carta_fisica: Mapped[float] = mapped_column(Float, default=40.0)

    # ── Executive commission (% of bank recovery shown in admin stats) ──
    porcentaje_comision_jefe: Mapped[float] = mapped_column(Float, default=15.0)

    # ── Automation flags ─────────────────────────────────────
    auto_evaluar_tramos: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Per-letter automation (auto-generate & make available) ──
    auto_envio_carta1: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_envio_carta2: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_envio_carta3: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_envio_carta4: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_envio_carta5: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Per-letter output format ("Word", "PDF", "Ambos") ────────
    formato_carta1: Mapped[str] = mapped_column(String(10), default="Word")
    formato_carta2: Mapped[str] = mapped_column(String(10), default="Word")
    formato_carta3: Mapped[str] = mapped_column(String(10), default="Word")
    formato_carta4: Mapped[str] = mapped_column(String(10), default="Word")
    formato_carta5: Mapped[str] = mapped_column(String(10), default="Word")

    # ── Metadata ─────────────────────────────────────────────
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # ── Convenience helpers ──────────────────────────────────

    @classmethod
    def get_or_create(cls, session: Session) -> "ConfigCampana":
        """Return the singleton row, creating it with defaults if needed."""
        cfg = session.get(cls, 1)
        if cfg is None:
            cfg = cls(id=1)
            session.add(cfg)
            session.commit()
        return cfg

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for Firestore sync / UI)."""
        return {
            "duracion_dias": self.duracion_dias,
            "dias_cierre": self.dias_cierre,
            "dias_retorno_banco": self.dias_retorno_banco,
            "ventana_ingreso_dias": self.ventana_ingreso_dias,
            "tramo1_inicio": self.tramo1_inicio,
            "tramo1_fin": self.tramo1_fin,
            "tramo2_inicio": self.tramo2_inicio,
            "tramo2_fin": self.tramo2_fin,
            "tramo3_inicio": self.tramo3_inicio,
            "tramo3_fin": self.tramo3_fin,
            "carta1_dia": self.carta1_dia,
            "carta2_dia": self.carta2_dia,
            "carta3_dia": self.carta3_dia,
            "carta4_dia": self.carta4_dia,
            "carta5_dia": self.carta5_dia,
            "carta1_programada": self.carta1_programada.isoformat() if self.carta1_programada else None,
            "carta2_programada": self.carta2_programada.isoformat() if self.carta2_programada else None,
            "carta3_programada": self.carta3_programada.isoformat() if self.carta3_programada else None,
            "carta4_programada": self.carta4_programada.isoformat() if self.carta4_programada else None,
            "carta5_programada": self.carta5_programada.isoformat() if self.carta5_programada else None,
            "umbral_minimo_gestion": self.umbral_minimo_gestion,
            "umbral_carta_fisica": self.umbral_carta_fisica,
            "porcentaje_comision_jefe": self.porcentaje_comision_jefe,
            "auto_evaluar_tramos": self.auto_evaluar_tramos,
            "nombre_empresa": self.nombre_empresa or "",
            "ruc_empresa": self.ruc_empresa or "",
            "nombre_gestor": self.nombre_gestor or "",
            "cargo_gestor": self.cargo_gestor or "",
            "telefono_gestor": self.telefono_gestor or "",
            "correo_gestor": self.correo_gestor or "",
            "direccion_empresa": self.direccion_empresa or "",
            "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
            "auto_envio_carta1": self.auto_envio_carta1,
            "auto_envio_carta2": self.auto_envio_carta2,
            "auto_envio_carta3": self.auto_envio_carta3,
            "auto_envio_carta4": self.auto_envio_carta4,
            "auto_envio_carta5": self.auto_envio_carta5,
            "formato_carta1": self.formato_carta1 or "Word",
            "formato_carta2": self.formato_carta2 or "Word",
            "formato_carta3": self.formato_carta3 or "Word",
            "formato_carta4": self.formato_carta4 or "Word",
            "formato_carta5": self.formato_carta5 or "Word",
        }


# ── Sync Log ─────────────────────────────────────────────────────

class SyncLog(Base):
    """Tracks every synchronisation event (upload / download / visits)."""
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(30))  # full_download, visits_only, upload
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    registros_afectados: Mapped[int] = mapped_column(Integer, default=0)
    resultado: Mapped[str] = mapped_column(String(20), default="ok")  # ok, error, parcial
    detalle: Mapped[Optional[str]] = mapped_column(Text)


# Niveles de credibilidad para agenda de contactos
NIVEL_CONFIABLE = "confiable"
NIVEL_DUDOSA = "dudosa"
NIVEL_DESCARTADA = "descartada"
NIVELES_CONFIANZA = (NIVEL_CONFIABLE, NIVEL_DUDOSA, NIVEL_DESCARTADA)


class HistorialContacto(Base):
    """Audit trail of contact updates captured in field apps."""
    __tablename__ = "historial_contacto"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campana_id: Mapped[str] = mapped_column(String(100), index=True)
    codigo_cliente: Mapped[str] = mapped_column(String(50), index=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    fecha_evento: Mapped[Optional[str]] = mapped_column(String(40))
    direccion_anterior: Mapped[Optional[str]] = mapped_column(Text)
    direccion_nueva: Mapped[Optional[str]] = mapped_column(Text)
    telefono_anterior: Mapped[Optional[str]] = mapped_column(String(50))
    telefono_nuevo: Mapped[Optional[str]] = mapped_column(String(50))
    nota: Mapped[Optional[str]] = mapped_column(Text)
    usuario_uid: Mapped[Optional[str]] = mapped_column(String(100))
    usuario_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    usuario_email: Mapped[Optional[str]] = mapped_column(String(120))
    rol_editor: Mapped[Optional[str]] = mapped_column(String(30))
    seccion_key: Mapped[Optional[str]] = mapped_column(String(40))
    origen_actualizacion: Mapped[Optional[str]] = mapped_column(String(20))
    latitud: Mapped[Optional[float]] = mapped_column(Float)
    longitud: Mapped[Optional[float]] = mapped_column(Float)
    nivel_confianza: Mapped[str] = mapped_column(String(20), default=NIVEL_CONFIABLE)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    oculto: Mapped[bool] = mapped_column(Boolean, default=False)
    es_principal: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(20))
    fecha_registro_local: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EtiquetaCatalogo(Base):
    """Catálogo global de etiquetas de seguimiento (admin → Firebase → APK)."""
    __tablename__ = "etiquetas_catalogo"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(20), default="#3B82F6")
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class HistorialVisita(Base):
    """Historial append-only de visitas/gestiones sincronizado desde Firestore."""
    __tablename__ = "historial_visita"
    __table_args__ = (
        Index("ix_historial_visita_cliente", "cliente_id"),
        Index("ix_historial_visita_event", "event_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE")
    )
    campana_id: Mapped[str] = mapped_column(String(100), index=True)
    codigo_cliente: Mapped[str] = mapped_column(String(50), index=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    fecha_evento: Mapped[Optional[datetime]] = mapped_column(DateTime)
    estado_gestion: Mapped[Optional[str]] = mapped_column(String(30))
    nota_gestor: Mapped[Optional[str]] = mapped_column(Text)
    nivel_1: Mapped[Optional[str]] = mapped_column(String(100))
    nivel_2: Mapped[Optional[str]] = mapped_column(String(100))
    nivel_3: Mapped[Optional[str]] = mapped_column(String(100))
    nivel_4: Mapped[Optional[str]] = mapped_column(String(100))
    canal_gestion: Mapped[Optional[str]] = mapped_column(String(10))
    fecha_promesa_pago: Mapped[Optional[str]] = mapped_column(String(20))
    monto_promesa_pago: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    gps_latitud: Mapped[Optional[float]] = mapped_column(Float)
    gps_longitud: Mapped[Optional[float]] = mapped_column(Float)
    gestor_uid: Mapped[Optional[str]] = mapped_column(String(100))
    gestor_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    fecha_registro_local: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ContactoPersona(Base):
    """Agenda durable de contactos por persona (DNI), persiste entre campañas."""
    __tablename__ = "contacto_persona"
    __table_args__ = (
        Index("ix_contacto_persona_dni", "numero_documento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    numero_documento: Mapped[str] = mapped_column(String(20), index=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    campana_origen: Mapped[Optional[str]] = mapped_column(String(100))
    direccion: Mapped[Optional[str]] = mapped_column(Text)
    telefono: Mapped[Optional[str]] = mapped_column(String(50))
    latitud: Mapped[Optional[float]] = mapped_column(Float)
    longitud: Mapped[Optional[float]] = mapped_column(Float)
    nivel_confianza: Mapped[str] = mapped_column(String(20), default=NIVEL_CONFIABLE)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    oculto: Mapped[bool] = mapped_column(Boolean, default=False)
    es_principal: Mapped[bool] = mapped_column(Boolean, default=False)
    nota: Mapped[Optional[str]] = mapped_column(Text)
    tipo: Mapped[Optional[str]] = mapped_column(String(20))
    usuario_uid: Mapped[Optional[str]] = mapped_column(String(100))
    usuario_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    usuario_email: Mapped[Optional[str]] = mapped_column(String(120))
    fecha_evento: Mapped[Optional[str]] = mapped_column(String(40))
    fecha_registro_local: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class CampanaBancoMeta(Base):
    """Fechas de inicio/fin por número de campaña banco (Excel col. E)."""
    __tablename__ = "campana_banco_meta"
    __table_args__ = (
        Index(
            "ix_campana_banco_meta_campana_key",
            "campana_id",
            "campana_banco_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campana_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("campanas.id", ondelete="CASCADE"), index=True
    )
    campana_banco_key: Mapped[str] = mapped_column(String(100))
    fecha_inicio_detectada: Mapped[Optional[date]] = mapped_column(Date)
    fecha_fin_detectada: Mapped[Optional[date]] = mapped_column(Date)
    fecha_inicio: Mapped[Optional[date]] = mapped_column(Date)
    fecha_fin: Mapped[Optional[date]] = mapped_column(Date)
    fecha_primera_deteccion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now
    )
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime)

    campana: Mapped["Campana"] = relationship(back_populates="campana_banco_meta")


class HistorialRepartoCall(Base):
    """Audit trail of call-center portfolio distributions."""
    __tablename__ = "historial_reparto_call"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campana_id: Mapped[str] = mapped_column(String(100), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    tipo: Mapped[str] = mapped_column(String(30))  # reparto_inicial | reequilibrio | reasignacion_manual
    motivo: Mapped[str] = mapped_column(Text, default="")
    algoritmo: Mapped[str] = mapped_column(String(20), default="LPT")
    admin_uid: Mapped[Optional[str]] = mapped_column(String(100))
    admin_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    cuentas_afectadas: Mapped[int] = mapped_column(Integer, default=0)
    monto_afectado: Mapped[float] = mapped_column(Float, default=0.0)
    detalle_json: Mapped[Optional[str]] = mapped_column(Text)
    firebase_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    firebase_error: Mapped[Optional[str]] = mapped_column(Text)


class HistorialZona(Base):
    """Audit trail of section/zone changes for a client."""
    __tablename__ = "historial_zona"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campana_id: Mapped[str] = mapped_column(String(100), index=True)
    codigo_cliente: Mapped[str] = mapped_column(String(50), index=True)
    event_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    seccion_anterior: Mapped[Optional[str]] = mapped_column(String(40))
    seccion_nueva: Mapped[Optional[str]] = mapped_column(String(40))
    zona_anterior: Mapped[Optional[str]] = mapped_column(String(50))
    zona_nueva: Mapped[Optional[str]] = mapped_column(String(50))
    region_anterior: Mapped[Optional[str]] = mapped_column(String(50))
    region_nueva: Mapped[Optional[str]] = mapped_column(String(50))
    usuario_nombre: Mapped[Optional[str]] = mapped_column(String(200))
    usuario_email: Mapped[Optional[str]] = mapped_column(String(120))
    fecha_evento: Mapped[Optional[str]] = mapped_column(String(40))
    fecha_registro_local: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ── Plantilla Carta ───────────────────────────────────────────────

class PlantillaCarta(Base):
    """
    Stores the editable template text for each collection letter (1-5).
    Templates use {{TAG}} placeholders and simple markup:
      **bold**, *italic*, [ROJO]red[/ROJO], [CENTRO]centered[/CENTRO],
      [FIRMA]signature[/FIRMA], [NOTA]footnote[/NOTA]

    When word_template_path is set, generation uses the Word file instead of
    the text template (typically DOCX editable + PDF final, with JPG optional).
    """
    __tablename__ = "plantillas_carta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    numero_carta: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(100), default="")
    contenido: Mapped[str] = mapped_column(Text, default="")
    word_template_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default=None)
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    @classmethod
    def get_or_create(cls, session: Session, numero_carta: int) -> "PlantillaCarta":
        """Return the stored template for this carta, or create a default."""
        from .template_engine import DEFAULT_TEMPLATES, CARTA_NOMBRES
        obj = session.query(cls).filter_by(numero_carta=numero_carta).first()
        if obj is None:
            obj = cls(
                numero_carta=numero_carta,
                nombre=CARTA_NOMBRES.get(numero_carta, f"Carta {numero_carta}"),
                contenido=DEFAULT_TEMPLATES.get(numero_carta, ""),
            )
            session.add(obj)
            session.flush()
        return obj

    @classmethod
    def get_all(cls, session: Session) -> list["PlantillaCarta"]:
        return session.query(cls).order_by(cls.numero_carta).all()


# ══════════════════════════════════════════════════════════════════
#  DATABASE ENGINE & SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════════

CURRENT_SCHEMA_VERSION = 19

DB_FILENAME = "antcobranzas.db"


def _project_db_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", DB_FILENAME)


def _user_db_path() -> str:
    """Stable per-user SQLite path (AppData). Independent of EXE folder."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "AntCobranzas", "data", DB_FILENAME)
    return os.path.join(os.path.expanduser("~"), ".antcobranzas", DB_FILENAME)


def _exe_adjacent_db_path() -> str | None:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), DB_FILENAME)
    return None


def _resolve_default_db_path() -> str:
    """
    Resolve a persistent default path.

    Priority:
    1) ANTCOBRANZAS_DB_PATH env var (explicit override).
    2) %APPDATA%\\AntCobranzas\\data when frozen (stable across updates).
    3) Project data folder when running from source.
    """
    env_path = os.environ.get("ANTCOBRANZAS_DB_PATH")
    if env_path:
        return os.path.abspath(env_path)

    if getattr(sys, "frozen", False):
        return _user_db_path()

    return _project_db_path()


def _migrate_legacy_db_if_needed(target_db_path: str) -> None:
    """
    One-time migration into the persistent target path.
    Only runs when target does not exist yet.

    Prefers the portable DB next to the EXE (older installs), then the
    historical project data folder.
    """
    if os.path.exists(target_db_path):
        return

    candidates: list[str] = []
    exe_db = _exe_adjacent_db_path()
    if exe_db:
        candidates.append(exe_db)
    candidates.append(_project_db_path())

    for legacy_path in candidates:
        if not legacy_path or os.path.abspath(legacy_path) == os.path.abspath(target_db_path):
            continue
        if not os.path.exists(legacy_path):
            continue
        os.makedirs(os.path.dirname(target_db_path), exist_ok=True)
        try:
            shutil.copy2(legacy_path, target_db_path)
            return
        except Exception:
            # Try next candidate; if all fail we create a fresh DB later.
            continue


_DEFAULT_DB_PATH = _resolve_default_db_path()


class DatabaseService:
    """Manages the SQLite database connection and session lifecycle."""

    def __init__(self, db_path: str | None = None):
        self.db_path = os.path.abspath(db_path or _DEFAULT_DB_PATH)
        self.engine: Any = None
        self._SessionFactory: Any = None
        self._initialized = False

    def initialize(self) -> None:
        """Create the database engine, tables, and apply migrations."""
        _migrate_legacy_db_if_needed(self.db_path)
        # Ensure data directory exists
        db_dir = os.path.dirname(self.db_path)
        os.makedirs(db_dir, exist_ok=True)

        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,  # Set True for SQL debugging
            pool_pre_ping=True,
        )

        # Enable WAL mode for better concurrent read performance
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables
        Base.metadata.create_all(self.engine)

        self._SessionFactory = sessionmaker(bind=self.engine)
        self._initialized = True

        # Apply schema versioning
        self._ensure_schema_version()

    def _sqlite_table_columns(self, conn, table: str) -> set[str]:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {row[1] for row in rows}

    def _add_sqlite_column(self, conn, table: str, col_name: str, col_type: str) -> None:
        existing = self._sqlite_table_columns(conn, table)
        if col_name in existing:
            return
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))

    def _ensure_cliente_columns_for_orm(self, session: Session) -> None:
        """
        Garantiza columnas del modelo Cliente antes de consultas ORM en migraciones.

        El modelo SQLAlchemy siempre refleja el esquema actual; si la BD está en
        una versión anterior, SELECT sobre Cliente falla hasta aplicar ALTER TABLE.
        """
        conn = session.connection()
        pending_cols = [
            ("fecha_asignacion_dt", "DATE"),
            ("fecha_cierre_dt", "DATE"),
            ("estado_ciclo", "VARCHAR(30) DEFAULT 'activa'"),
            ("fecha_cierre_real", "DATE"),
            ("gestion_especial", "BOOLEAN DEFAULT 0"),
            ("motivo_gestion_especial", "VARCHAR(100)"),
            ("fecha_gestion_especial", "DATETIME"),
            ("seccion_origen", "VARCHAR(80)"),
            ("fase_gestion", "VARCHAR(10) DEFAULT 'campo'"),
            ("call_gestor_uid", "VARCHAR(100)"),
            ("call_gestor_nombre", "VARCHAR(200)"),
        ]
        for col_name, col_type in pending_cols:
            try:
                self._add_sqlite_column(conn, "clientes", col_name, col_type)
            except Exception:
                pass

    def _ensure_schema_version(self) -> None:
        """Track and apply incremental schema changes."""
        with self.session() as session:
            sv = session.query(SchemaVersion).first()
            if sv is None:
                insp = inspect(self.engine)
                is_legacy = "clientes" in insp.get_table_names()
                if is_legacy:
                    sv = SchemaVersion(
                        version=1,
                        description="Base de datos heredada sin registro de versión",
                    )
                else:
                    sv = SchemaVersion(
                        version=CURRENT_SCHEMA_VERSION,
                        description=f"Initial schema v{CURRENT_SCHEMA_VERSION}",
                    )
                session.add(sv)
                session.commit()
                if not is_legacy:
                    return

            self._ensure_cliente_columns_for_orm(session)
            session.commit()

            if sv.version < 2:
                self._migrate_v2(session)
                sv.version = 2
                sv.applied_at = datetime.now()
                sv.description = "v2: niveles gestión + sync_log"
                session.commit()

            if sv.version < 3:
                self._migrate_v3(session)
                sv.version = 3
                sv.applied_at = datetime.now()
                sv.description = "v3: carta5 + gestor/empresa config"
                session.commit()

            if sv.version < 4:
                self._migrate_v4(session)
                sv.version = 4
                sv.applied_at = datetime.now()
                sv.description = "v4: plantillas_carta table"
                session.commit()

            if sv.version < 5:
                self._migrate_v5(session)
                sv.version = 5
                sv.applied_at = datetime.now()
                sv.description = "v5: per-letter auto-send and format fields"
                session.commit()

            if sv.version < 6:
                self._migrate_v6(session)
                sv.version = 6
                sv.applied_at = datetime.now()
                sv.description = "v6: word_template_path in plantillas_carta"
                session.commit()

            if sv.version < 7:
                self._migrate_v7(session)
                sv.version = 7
                sv.applied_at = datetime.now()
                sv.description = "v7: historial_contacto audit table"
                session.commit()

            if sv.version < 8:
                self._migrate_v8(session)
                sv.version = 8
                sv.applied_at = datetime.now()
                sv.description = "v8: historial_zona audit table"
                session.commit()

            if sv.version < 9:
                self._migrate_v9(session)
                sv.version = 9
                sv.applied_at = datetime.now()
                sv.description = "v9: publication metadata for cartas_generadas"
                session.commit()

            if sv.version < 10:
                self._migrate_v10(session)
                sv.version = 10
                sv.applied_at = datetime.now()
                sv.description = "v10: ubicacion verificada en clientes"
                session.commit()

            if sv.version < 11:
                self._migrate_v11(session)
                sv.version = 11
                sv.applied_at = datetime.now()
                sv.description = "v11: porcentaje comision jefe en config_campana"
                session.commit()

            if sv.version < 12:
                self._migrate_v12(session)
                sv.version = 12
                sv.applied_at = datetime.now()
                sv.description = "v12: devoluciones zona inaccesible + seccion_key en clientes"
                session.commit()

            if sv.version < 13:
                self._migrate_v13(session)
                sv.version = 13
                sv.applied_at = datetime.now()
                sv.description = "v13: archivado cartera activo_en_cartera / motivo_baja"
                session.commit()

            if sv.version < 14:
                self._migrate_v14(session)
                sv.version = 14
                sv.applied_at = datetime.now()
                sv.description = "v14: ciclo por cuenta 59d, estado_ciclo, gestión especial"
                session.commit()

            if sv.version < 15:
                self._migrate_v15(session)
                sv.version = 15
                sv.applied_at = datetime.now()
                sv.description = "v15: call center fase_gestion y asignación call"
                session.commit()

            if sv.version < 16:
                self._migrate_v16(session)
                sv.version = 16
                sv.applied_at = datetime.now()
                sv.description = "v16: historial reparto call center"
                session.commit()

            if sv.version < 17:
                self._migrate_v17(session)
                sv.version = 17
                sv.applied_at = datetime.now()
                sv.description = "v17: campana_banco_meta fechas por campaña banco"
                session.commit()

            if sv.version < 18:
                self._migrate_v18(session)
                sv.version = 18
                sv.applied_at = datetime.now()
                sv.description = "v18: contacto_persona agenda + credibilidad historial"
                session.commit()

            if sv.version < 19:
                self._migrate_v19(session)
                sv.version = 19
                sv.applied_at = datetime.now()
                sv.description = "v19: etiquetas_catalogo + historial_visita + clientes.etiquetas"
                session.commit()

    def _migrate_v19(self, session: Session) -> None:
        """Etiquetas de seguimiento + historial de visitas."""
        conn = session.connection()
        text_mod = __import__("sqlalchemy").text
        try:
            conn.execute(text_mod(
                "ALTER TABLE clientes ADD COLUMN etiquetas TEXT DEFAULT '[]'"
            ))
        except Exception:
            pass
        Base.metadata.create_all(
            bind=session.connection(),
            tables=[EtiquetaCatalogo.__table__, HistorialVisita.__table__],
            checkfirst=True,
        )
        session.commit()

    def _migrate_v18(self, session: Session) -> None:
        """Agenda cross-campaña por DNI + campos de credibilidad en historial."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        hist_cols = [
            ("nivel_confianza", "VARCHAR(20) DEFAULT 'confiable'"),
            ("orden", "INTEGER DEFAULT 0"),
            ("oculto", "BOOLEAN DEFAULT 0"),
            ("es_principal", "BOOLEAN DEFAULT 0"),
            ("tipo", "VARCHAR(20)"),
        ]
        for col_name, col_type in hist_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE historial_contacto ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        Base.metadata.create_all(
            bind=session.connection(),
            tables=[ContactoPersona.__table__],
            checkfirst=True,
        )
        session.commit()

    def _migrate_v17(self, session: Session) -> None:
        """Tabla campana_banco_meta + backfill desde clientes activos."""
        from .campana_banco_utils import (
            campana_banco_key_from_value,
            compute_detected_dates_for_group,
        )

        Base.metadata.create_all(
            bind=session.connection(),
            tables=[CampanaBancoMeta.__table__],
            checkfirst=True,
        )

        cfg = ConfigCampana.get_or_create(session)
        duracion = cfg.duracion_dias or 59

        campanas = session.query(Campana.id).all()
        for (campana_id,) in campanas:
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
                existing = (
                    session.query(CampanaBancoMeta)
                    .filter(
                        CampanaBancoMeta.campana_id == campana_id,
                        CampanaBancoMeta.campana_banco_key == key,
                    )
                    .first()
                )
                if existing is None:
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
                    existing.fecha_inicio_detectada = inicio_d
                    existing.fecha_fin_detectada = fin_d
                    existing.fecha_actualizacion = now

        session.commit()

    def _migrate_v16(self, session: Session) -> None:
        """Tabla historial_reparto_call."""
        Base.metadata.create_all(
            bind=session.connection(),
            tables=[HistorialRepartoCall.__table__],
            checkfirst=True,
        )

    def _migrate_v15(self, session: Session) -> None:
        """Call center: fase_gestion, call_gestor_uid/nombre."""
        conn = session.connection()
        text = __import__("sqlalchemy").text

        cliente_cols = [
            ("fase_gestion", "VARCHAR(10) DEFAULT 'campo'"),
            ("call_gestor_uid", "VARCHAR(100)"),
            ("call_gestor_nombre", "VARCHAR(200)"),
        ]
        for col_name, col_type in cliente_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass

        try:
            conn.execute(text(
                "UPDATE clientes SET fase_gestion = 'call' "
                "WHERE tramo_actual = 1 AND activo_en_cartera = 1 "
                "AND (fase_gestion IS NULL OR fase_gestion = '' OR fase_gestion = 'campo')"
            ))
        except Exception:
            pass

    def _migrate_v14(self, session: Session) -> None:
        """Ciclo individual por cuenta, cierre día 60, retorno día 70."""
        from .date_utils import parse_excel_fecha

        conn = session.connection()
        text = __import__("sqlalchemy").text

        cliente_cols = [
            ("fecha_asignacion_dt", "DATE"),
            ("fecha_cierre_dt", "DATE"),
            ("estado_ciclo", "VARCHAR(30) DEFAULT 'activa'"),
            ("fecha_cierre_real", "DATE"),
            ("gestion_especial", "BOOLEAN DEFAULT 0"),
            ("motivo_gestion_especial", "VARCHAR(100)"),
            ("fecha_gestion_especial", "DATETIME"),
            ("seccion_origen", "VARCHAR(80)"),
        ]
        for col_name, col_type in cliente_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass

        config_cols = [
            ("dias_cierre", "INTEGER DEFAULT 60"),
            ("dias_retorno_banco", "INTEGER DEFAULT 70"),
            ("ventana_ingreso_dias", "INTEGER DEFAULT 21"),
        ]
        for col_name, col_type in config_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE config_campana ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass

        # Actualizar defaults de tramos solo si aún usa el esquema antiguo (60 días)
        try:
            conn.execute(text(
                "UPDATE config_campana SET "
                "duracion_dias = 59, "
                "tramo1_fin = 10, tramo2_inicio = 11, tramo2_fin = 43, "
                "tramo3_inicio = 44, tramo3_fin = 59, "
                "dias_cierre = 60, dias_retorno_banco = 70, ventana_ingreso_dias = 21 "
                "WHERE id = 1 AND tramo3_fin = 60"
            ))
        except Exception:
            pass

        session.commit()

        # Backfill fechas parseadas y estado_ciclo (SQL directo: el ORM exige todas las columnas del modelo)
        rows = session.execute(text(
            "SELECT id, fecha_asignacion, fecha_cierre, "
            "fecha_asignacion_dt, fecha_cierre_dt, estado_ciclo FROM clientes"
        )).fetchall()
        for row in rows:
            cid, fa_str, fc_str, fa_dt, fc_dt, estado = row
            updates: dict[str, Any] = {}
            if not fa_dt:
                parsed = parse_excel_fecha(fa_str)
                if parsed:
                    updates["fecha_asignacion_dt"] = parsed
            if not fc_dt:
                parsed = parse_excel_fecha(fc_str)
                if parsed:
                    updates["fecha_cierre_dt"] = parsed
            if not estado:
                updates["estado_ciclo"] = EstadoCiclo.ACTIVA.value
            if not updates:
                continue
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            session.execute(
                text(f"UPDATE clientes SET {set_clause} WHERE id = :id"),
                {"id": cid, **updates},
            )
        session.commit()

    def _migrate_v13(self, session: Session) -> None:
        """Add soft-archive fields when client disappears from bank Excel."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_cols = [
            ("activo_en_cartera", "BOOLEAN DEFAULT 1"),
            ("motivo_baja", "VARCHAR(80)"),
            ("fecha_baja", "DATETIME"),
            ("ultimo_excel", "VARCHAR(300)"),
        ]
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        session.commit()

    def _migrate_v12(self, session: Session) -> None:
        """Add return-request fields and seccion_key on clientes."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_cols = [
            ("seccion_key", "VARCHAR(80)"),
            ("motivo_devolucion", "VARCHAR(50)"),
            ("nota_devolucion", "TEXT"),
            ("fecha_devolucion_solicitud", "VARCHAR(40)"),
            ("gestor_devolucion_uid", "VARCHAR(100)"),
            ("gestor_devolucion_nombre", "VARCHAR(200)"),
            ("gestor_devolucion_seccion", "VARCHAR(80)"),
        ]
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_clientes_seccion_key "
                "ON clientes (campana_id, seccion_key)"
            ))
        except Exception:
            pass
        session.commit()

    def _migrate_v11(self, session: Session) -> None:
        """Add executive commission percentage to config_campana."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        try:
            conn.execute(text(
                "ALTER TABLE config_campana ADD COLUMN porcentaje_comision_jefe FLOAT DEFAULT 15.0"
            ))
        except Exception:
            pass
        session.commit()

    def _migrate_v10(self, session: Session) -> None:
        """Add field-verified GPS coordinates to clientes."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_columns = [
            ("ubicacion_verificada_lat", "FLOAT"),
            ("ubicacion_verificada_lng", "FLOAT"),
            ("ubicacion_verificada_fecha", "VARCHAR(40)"),
            ("ubicacion_verificada_gestor", "VARCHAR(200)"),
        ]
        for col_name, col_type in new_columns:
            try:
                conn.execute(text(
                    f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        session.commit()

    def _migrate_v8(self, session: Session) -> None:
        """Create historial_zona table."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS historial_zona ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  campana_id VARCHAR(100),"
            "  codigo_cliente VARCHAR(50),"
            "  event_id VARCHAR(120) UNIQUE,"
            "  seccion_anterior VARCHAR(40),"
            "  seccion_nueva VARCHAR(40),"
            "  zona_anterior VARCHAR(50),"
            "  zona_nueva VARCHAR(50),"
            "  region_anterior VARCHAR(50),"
            "  region_nueva VARCHAR(50),"
            "  usuario_nombre VARCHAR(200),"
            "  usuario_email VARCHAR(120),"
            "  fecha_evento VARCHAR(40),"
            "  fecha_registro_local DATETIME"
            ")"
        ))
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hist_zona_campana ON historial_zona (campana_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hist_zona_codigo ON historial_zona (codigo_cliente)"))
        except Exception:
            pass
        session.commit()

    def _migrate_v9(self, session: Session) -> None:
        """Add publication metadata columns to cartas_generadas."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_cols = [
            ("seccion_key", "VARCHAR(50)"),
            ("gestor_uid", "VARCHAR(100)"),
            ("gestor_nombre", "VARCHAR(200)"),
            ("nombre_archivo", "VARCHAR(300)"),
            ("storage_path", "VARCHAR(500)"),
            ("formato", "VARCHAR(20)"),
            ("estado_publicacion", "VARCHAR(30) DEFAULT 'pendiente'"),
            ("fecha_publicacion", "DATETIME"),
            ("publicado_por_uid", "VARCHAR(100)"),
            ("publicado_por_nombre", "VARCHAR(200)"),
        ]
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE cartas_generadas ADD COLUMN {col_name} {col_type}"
                ))
            except Exception:
                pass
        session.commit()

    def _migrate_v7(self, session: Session) -> None:
        """Create historial_contacto table and contact metadata fields."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        # Add contact metadata columns on clientes
        new_cols = [
            ("ultima_nota_contacto", "TEXT"),
            ("fecha_actualizacion_contacto_iso", "VARCHAR(40)"),
            ("actualizado_por_uid", "VARCHAR(100)"),
            ("actualizado_por_nombre", "VARCHAR(200)"),
            ("actualizado_por_email", "VARCHAR(120)"),
            ("origen_actualizacion", "VARCHAR(20)"),
        ]
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS historial_contacto ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  campana_id VARCHAR(100),"
            "  codigo_cliente VARCHAR(50),"
            "  event_id VARCHAR(120) UNIQUE,"
            "  fecha_evento VARCHAR(40),"
            "  direccion_anterior TEXT,"
            "  direccion_nueva TEXT,"
            "  telefono_anterior VARCHAR(50),"
            "  telefono_nuevo VARCHAR(50),"
            "  nota TEXT,"
            "  usuario_uid VARCHAR(100),"
            "  usuario_nombre VARCHAR(200),"
            "  usuario_email VARCHAR(120),"
            "  rol_editor VARCHAR(30),"
            "  seccion_key VARCHAR(40),"
            "  origen_actualizacion VARCHAR(20),"
            "  latitud FLOAT,"
            "  longitud FLOAT,"
            "  fecha_registro_local DATETIME"
            ")"
        ))
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hist_contacto_campana ON historial_contacto (campana_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hist_contacto_codigo ON historial_contacto (codigo_cliente)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_hist_contacto_event ON historial_contacto (event_id)"))
        except Exception:
            pass
        session.commit()

    def _migrate_v6(self, session: Session) -> None:
        """Add word_template_path column to plantillas_carta."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        try:
            conn.execute(text(
                "ALTER TABLE plantillas_carta ADD COLUMN word_template_path VARCHAR(500)"
            ))
        except Exception:
            pass  # Column already exists
        session.commit()

    def _migrate_v5(self, session: Session) -> None:
        """Add per-letter auto-send and format fields to config_campana."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_cols = []
        for i in range(1, 6):
            new_cols.append((f"auto_envio_carta{i}", "BOOLEAN DEFAULT 0"))
            new_cols.append((f"formato_carta{i}", "VARCHAR(10) DEFAULT 'Word'"))
        for col_name, col_type in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE config_campana ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass  # Column already exists
        session.commit()

    def _migrate_v4(self, session: Session) -> None:
        """Create plantillas_carta table and seed with default templates."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS plantillas_carta ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  numero_carta INTEGER NOT NULL UNIQUE,"
            "  nombre VARCHAR(100) DEFAULT '',"
            "  contenido TEXT DEFAULT '',"
            "  fecha_actualizacion DATETIME"
            ")"
        ))
        session.commit()
        # Seed default templates
        from .template_engine import DEFAULT_TEMPLATES, CARTA_NOMBRES
        for nc, contenido in DEFAULT_TEMPLATES.items():
            existing = session.query(PlantillaCarta).filter_by(numero_carta=nc).first()
            if existing is None:
                session.add(PlantillaCarta(
                    numero_carta=nc,
                    nombre=CARTA_NOMBRES.get(nc, f"Carta {nc}"),
                    contenido=contenido,
                    fecha_actualizacion=datetime.now(),
                ))
        session.commit()

    def _migrate_v3(self, session: Session) -> None:
        """Add carta5 and gestor/empresa fields to config_campana."""
        conn = session.connection()
        text = __import__("sqlalchemy").text
        new_cols = [
            ("carta5_dia",         "INTEGER DEFAULT 44"),
            ("carta5_programada",  "DATETIME"),
            ("nombre_empresa",     "VARCHAR(200)"),
            ("ruc_empresa",        "VARCHAR(20)"),
            ("nombre_gestor",      "VARCHAR(200)"),
            ("cargo_gestor",       "VARCHAR(100)"),
            ("telefono_gestor",    "VARCHAR(50)"),
            ("correo_gestor",      "VARCHAR(100)"),
            ("direccion_empresa",  "TEXT"),
        ]
        for col_name, col_type in new_cols:
            try:
                conn.execute(
                    text(f"ALTER TABLE config_campana ADD COLUMN {col_name} {col_type}")
                )
            except Exception:
                pass  # Column already exists

        # Update existing carta3/carta4 defaults to new E-schedule if they
        # still hold the old default values (38 / 44 respectively).
        try:
            conn.execute(text(
                "UPDATE config_campana SET carta5_dia = carta4_dia "
                "WHERE carta5_dia IS NULL OR carta5_dia = 44"
            ))
            conn.execute(text(
                "UPDATE config_campana SET carta4_dia = carta3_dia "
                "WHERE carta3_dia = 38"
            ))
            conn.execute(text(
                "UPDATE config_campana SET carta3_dia = 11 "
                "WHERE carta3_dia = 38"
            ))
        except Exception:
            pass
        session.commit()

    def _migrate_v2(self, session: Session) -> None:
        """Add nivel 1-4, canal, promesa fields to clientes; create sync_log."""
        conn = session.connection()
        new_columns = [
            ("nivel_1", "VARCHAR(100)"),
            ("nivel_2", "VARCHAR(100)"),
            ("nivel_3", "VARCHAR(100)"),
            ("nivel_4", "VARCHAR(100)"),
            ("canal_gestion", "VARCHAR(10)"),
            ("fecha_promesa_pago", "VARCHAR(20)"),
            ("monto_promesa_pago", "FLOAT DEFAULT 0.0"),
        ]
        for col_name, col_type in new_columns:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE clientes ADD COLUMN {col_name} {col_type}"
                    )
                )
            except Exception:
                pass  # Column already exists

        # Create sync_log table if not exists
        conn.execute(__import__("sqlalchemy").text(
            "CREATE TABLE IF NOT EXISTS sync_log ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  tipo VARCHAR(30) NOT NULL,"
            "  fecha DATETIME,"
            "  registros_afectados INTEGER DEFAULT 0,"
            "  resultado VARCHAR(20) DEFAULT 'ok',"
            "  detalle TEXT"
            ")"
        ))

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def session(self) -> Session:
        """
        Get a new Session.
        Usage:
            with db.session() as session:
                session.add(obj)
                session.commit()
        """
        if not self._initialized:
            raise RuntimeError(
                "Database not initialized. Call initialize() first."
            )
        return self._SessionFactory()

    def get_active_campana(self) -> Campana | None:
        """Return the currently active campaign, if any."""
        with self.session() as session:
            return (
                session.query(Campana)
                .filter(Campana.estado == EstadoCampana.ACTIVA.value)
                .order_by(Campana.fecha_creacion.desc())
                .first()
            )

    def get_storage_info(self) -> dict:
        """Return local SQLite file metadata and row counts."""
        info = {
            "path": self.db_path,
            "exists": os.path.exists(self.db_path),
            "size_bytes": 0,
            "campaign_count": 0,
            "client_count": 0,
            "initialized": self._initialized,
        }
        if info["exists"]:
            try:
                info["size_bytes"] = os.path.getsize(self.db_path)
            except OSError:
                pass
        if not self._initialized:
            return info
        from sqlalchemy import func
        with self.session() as session:
            info["campaign_count"] = session.query(func.count(Campana.id)).scalar() or 0
            info["client_count"] = session.query(func.count(Cliente.id)).scalar() or 0
        return info

    def export_database_file(self, dest_path: str) -> str:
        """
        Copy the SQLite database to dest_path after WAL checkpoint.

        Returns the absolute path written.
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        dest = os.path.abspath(dest_path)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(FULL)")
            conn.commit()
        shutil.copy2(self.db_path, dest)
        return dest

    def get_stats(
        self,
        campana_id: str,
        *,
        campana_banco: str | None = None,
    ) -> dict:
        """
        Get summary statistics for a campaign.
        Returns dict with counts by tramo, estado, and financial totals.

        campana_banco: clave de filtro (valor Excel o SIN_CAMPANA_KEY); None = todas.
        Siempre incluye por_campana_banco agregado sobre el universo completo.
        """
        from services.campana_banco_utils import (
            aggregate_campana_banco_stats,
            matches_campana_banco,
        )

        with self.session() as session:
            clientes = (
                session.query(Cliente)
                .filter(Cliente.campana_id == campana_id)
                .all()
            )
            if not clientes:
                return {}

            all_dicts = [
                {
                    "campana_banco": c.campana_banco,
                    "tramo_actual": c.tramo_actual,
                    "importe_deuda_asignada": c.importe_deuda_asignada,
                    "importe_deuda_pendiente": c.importe_deuda_pendiente,
                }
                for c in clientes
            ]
            por_campana_banco = aggregate_campana_banco_stats(all_dicts)

            if campana_banco is not None:
                clientes = [
                    c for c in clientes
                    if matches_campana_banco(
                        {"campana_banco": c.campana_banco},
                        campana_banco,
                    )
                ]
                if not clientes:
                    return {
                        "total_clientes": 0,
                        "por_tramo": {0: 0, 1: 0, 2: 0, 3: 0},
                        "por_estado": {},
                        "por_etapa_recuperacion": {
                            1: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                            2: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                            3: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                        },
                        "por_seccion_etapa": {},
                        "por_campana_banco": por_campana_banco,
                        "deuda_total_asignada": 0.0,
                        "deuda_total_pendiente": 0.0,
                        "clientes_alto_valor": 0,
                        "secciones": [],
                        "campana_banco_filtro": campana_banco,
                    }

            total = len(clientes)
            by_tramo = {0: 0, 1: 0, 2: 0, 3: 0}
            by_estado = {}
            deuda_total = 0.0
            deuda_pendiente = 0.0
            alto_valor = 0

            por_etapa_recuperacion: dict[int, dict] = {
                1: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                2: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                3: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
            }
            por_seccion_etapa: dict[str, dict[int, dict]] = {}

            for c in clientes:
                by_tramo[c.tramo_actual] = by_tramo.get(c.tramo_actual, 0) + 1
                by_estado[c.estado_gestion] = by_estado.get(c.estado_gestion, 0) + 1
                deuda_total += c.importe_deuda_asignada
                deuda_pendiente += c.importe_deuda_pendiente
                if c.es_alto_valor:
                    alto_valor += 1

                tramo = c.tramo_actual if c.tramo_actual in (1, 2, 3) else 0
                if tramo:
                    asignada = c.importe_deuda_asignada or 0.0
                    recuperada = max(0.0, asignada - (c.importe_deuda_pendiente or 0.0))
                    por_etapa_recuperacion[tramo]["asignada"] += asignada
                    por_etapa_recuperacion[tramo]["recuperada"] += recuperada
                    por_etapa_recuperacion[tramo]["cuentas"] += 1

                    sec = c.seccion_key or c.seccion or "SIN_SECCION"
                    por_seccion_etapa.setdefault(sec, {
                        1: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                        2: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                        3: {"asignada": 0.0, "recuperada": 0.0, "cuentas": 0},
                    })
                    por_seccion_etapa[sec][tramo]["asignada"] += asignada
                    por_seccion_etapa[sec][tramo]["recuperada"] += recuperada
                    por_seccion_etapa[sec][tramo]["cuentas"] += 1

            result = {
                "total_clientes": total,
                "por_tramo": by_tramo,
                "por_estado": by_estado,
                "por_etapa_recuperacion": por_etapa_recuperacion,
                "por_seccion_etapa": por_seccion_etapa,
                "por_campana_banco": por_campana_banco,
                "deuda_total_asignada": round(deuda_total, 2),
                "deuda_total_pendiente": round(deuda_pendiente, 2),
                "clientes_alto_valor": alto_valor,
                "secciones": list(set(
                    c.seccion for c in clientes if c.seccion
                )),
            }
            if campana_banco is not None:
                result["campana_banco_filtro"] = campana_banco
            return result


# ── Singleton ────────────────────────────────────────────────────

db_service = DatabaseService()
