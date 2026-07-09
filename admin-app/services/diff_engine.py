"""
Diff Engine — Cartera Change Detection
========================================

Compares old (current Firestore) vs new (parsed Excel) client data
and produces a structured ChangeReport that describes:
  - New clients (present in new, absent in old)
  - Removed clients (present in old, absent in new)
  - Updated clients (present in both, with field-level diffs)
  - Unchanged clients

Grouped by seccion_key for downstream notification routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Fields that should be compared for changes (bank-provided data only).
# Excludes management fields set by gestores (estado_gestion, nota_gestor, etc.)
COMPARE_FIELDS = [
    "nombre_completo", "nombres", "apellido_paterno", "apellido_materno",
    "genero", "edad",
    "telefono_fijo", "telefono_trabajo", "telefono_movil", "correo",
    "departamento", "provincia", "distrito", "direccion", "referencia",
    "coordenada_x", "coordenada_y",
    "segmentacion", "segmento_cartera", "etapa_deuda",
    "cobrador", "campana_banco", "territorio", "perfil_score",
    "fecha_documento", "fecha_vencimiento", "fecha_asignacion", "fecha_cierre",
    "dias_atraso",
    "importe_deuda_original", "importe_abonos_anteriores",
    "importe_deuda_asignada", "importe_deuda_pendiente",
]

# Fields considered "important" — changes here generate detailed notifications
IMPORTANT_FIELDS = {
    "importe_deuda_asignada", "importe_deuda_pendiente",
    "dias_atraso", "direccion", "telefono_movil",
    "nombre_completo",
}

# Human-readable labels for notification messages
FIELD_LABELS = {
    "importe_deuda_asignada": "Deuda asignada",
    "importe_deuda_pendiente": "Deuda pendiente",
    "dias_atraso": "Días de atraso",
    "direccion": "Dirección",
    "telefono_movil": "Teléfono móvil",
    "telefono_fijo": "Teléfono fijo",
    "telefono_trabajo": "Teléfono trabajo",
    "correo": "Correo",
    "nombre_completo": "Nombre",
    "departamento": "Departamento",
    "provincia": "Provincia",
    "distrito": "Distrito",
    "coordenada_x": "Coordenada X",
    "coordenada_y": "Coordenada Y",
}


@dataclass
class FieldChange:
    """A single field-level change for a client."""
    field: str
    old_value: Any
    new_value: Any
    is_important: bool = False

    @property
    def label(self) -> str:
        return FIELD_LABELS.get(self.field, self.field)

    def format_values(self) -> str:
        """Human-readable representation."""
        if self.field.startswith("importe_"):
            old = f"S/ {float(self.old_value or 0):,.2f}"
            new = f"S/ {float(self.new_value or 0):,.2f}"
            return f"{old} → {new}"
        return f"{self.old_value} → {self.new_value}"


@dataclass
class ClientChange:
    """All changes detected for a single client."""
    codigo_cliente: str
    nombre_completo: str
    seccion_key: str
    changes: list[FieldChange] = field(default_factory=list)

    @property
    def has_important_changes(self) -> bool:
        return any(c.is_important for c in self.changes)

    @property
    def important_changes(self) -> list[FieldChange]:
        return [c for c in self.changes if c.is_important]

    @property
    def debt_changed(self) -> bool:
        return any(
            c.field in ("importe_deuda_asignada", "importe_deuda_pendiente")
            for c in self.changes
        )


@dataclass
class SectionChanges:
    """Changes for a single section (maps to one gestor)."""
    seccion_key: str
    new_clients: list[dict] = field(default_factory=list)
    removed_clients: list[dict] = field(default_factory=list)
    updated_clients: list[ClientChange] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new_clients or self.removed_clients or self.updated_clients)

    @property
    def total_affected(self) -> int:
        return len(self.new_clients) + len(self.removed_clients) + len(self.updated_clients)

    @property
    def summary_text(self) -> str:
        parts = []
        if self.removed_clients:
            parts.append(f"{len(self.removed_clients)} removidos")
        if self.new_clients:
            parts.append(f"{len(self.new_clients)} nuevos")
        if self.updated_clients:
            parts.append(f"{len(self.updated_clients)} actualizados")
        if self.unchanged_count:
            parts.append(f"{self.unchanged_count} sin cambios")
        return ", ".join(parts) if parts else "Sin cambios"


@dataclass
class ChangeReport:
    """Complete diff report across all sections."""
    sections: dict[str, SectionChanges] = field(default_factory=dict)

    @property
    def total_new(self) -> int:
        return sum(len(s.new_clients) for s in self.sections.values())

    @property
    def total_removed(self) -> int:
        return sum(len(s.removed_clients) for s in self.sections.values())

    @property
    def total_updated(self) -> int:
        return sum(len(s.updated_clients) for s in self.sections.values())

    @property
    def total_unchanged(self) -> int:
        return sum(s.unchanged_count for s in self.sections.values())

    @property
    def has_changes(self) -> bool:
        return any(s.has_changes for s in self.sections.values())

    @property
    def affected_sections(self) -> list[str]:
        return [k for k, s in self.sections.items() if s.has_changes]

    @property
    def summary_text(self) -> str:
        return (
            f"{self.total_new} nuevos, {self.total_updated} actualizados, "
            f"{self.total_removed} removidos, {self.total_unchanged} sin cambios"
        )

    def get_section(self, seccion_key: str) -> SectionChanges:
        if seccion_key not in self.sections:
            self.sections[seccion_key] = SectionChanges(seccion_key=seccion_key)
        return self.sections[seccion_key]


def _normalize(value: Any) -> str:
    """Normalize a value for comparison, handling None, floats, etc."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).strip()


def _compare_client(
    old_data: dict,
    new_data: dict,
    seccion_key: str,
) -> ClientChange | None:
    """
    Compare two client dicts field by field.
    Returns a ClientChange if any fields differ, None if identical.
    """
    changes = []
    for fld in COMPARE_FIELDS:
        old_val = old_data.get(fld)
        new_val = new_data.get(fld)

        if _normalize(old_val) != _normalize(new_val):
            changes.append(FieldChange(
                field=fld,
                old_value=old_val,
                new_value=new_val,
                is_important=fld in IMPORTANT_FIELDS,
            ))

    if not changes:
        return None

    return ClientChange(
        codigo_cliente=new_data.get("codigo_cliente", ""),
        nombre_completo=new_data.get("nombre_completo", ""),
        seccion_key=seccion_key,
        changes=changes,
    )


def compare_cartera(
    old_by_seccion: dict[str, dict[str, dict]],
    new_by_seccion: dict[str, list[dict]],
) -> ChangeReport:
    """
    Compare old cartera data (from Firestore) with new data (from Excel).

    Args:
        old_by_seccion: Dict of seccion_key → dict of codigo_cliente → client_data.
                        This is the current state in Firestore.
        new_by_seccion: Dict of seccion_key → list of client dicts.
                        This is the freshly parsed Excel data.

    Returns:
        ChangeReport with all detected changes.
    """
    report = ChangeReport()

    # All section keys from both old and new
    all_sections = set(old_by_seccion.keys()) | set(new_by_seccion.keys())

    for seccion_key in all_sections:
        section = report.get_section(seccion_key)

        old_clients = old_by_seccion.get(seccion_key, {})
        new_clients_list = new_by_seccion.get(seccion_key, [])

        # Index new clients by codigo_cliente
        new_clients = {
            c.get("codigo_cliente", ""): c
            for c in new_clients_list
            if c.get("codigo_cliente")
        }

        old_codes = set(old_clients.keys())
        new_codes = set(new_clients.keys())

        # New clients (in new but not in old)
        for code in sorted(new_codes - old_codes):
            section.new_clients.append(new_clients[code])

        # Removed clients (in old but not in new; skip already archived)
        for code in sorted(old_codes - new_codes):
            old_data = old_clients[code]
            if old_data.get("activo_en_cartera", True) is False:
                continue
            section.removed_clients.append(old_data)

        # Existing clients: compare field by field
        for code in sorted(old_codes & new_codes):
            change = _compare_client(
                old_clients[code], new_clients[code], seccion_key
            )
            if change:
                section.updated_clients.append(change)
            else:
                section.unchanged_count += 1

    return report
