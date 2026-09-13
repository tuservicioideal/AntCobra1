"""Diff de cartera Excel vs Firestore. Origen: admin-app/services/diff_engine.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


COMPARE_FIELDS = [
    "nombre_completo",
    "nombres",
    "apellido_paterno",
    "apellido_materno",
    "genero",
    "edad",
    "telefono_fijo",
    "telefono_trabajo",
    "telefono_movil",
    "correo",
    "departamento",
    "provincia",
    "distrito",
    "direccion",
    "referencia",
    "coordenada_x",
    "coordenada_y",
    "segmentacion",
    "segmento_cartera",
    "etapa_deuda",
    "cobrador",
    "campana_banco",
    "territorio",
    "perfil_score",
    "fecha_documento",
    "fecha_vencimiento",
    "fecha_asignacion",
    "fecha_cierre",
    "dias_atraso",
    "importe_deuda_original",
    "importe_abonos_anteriores",
    "importe_deuda_asignada",
    "importe_deuda_pendiente",
]

IMPORTANT_FIELDS = {
    "importe_deuda_asignada",
    "importe_deuda_pendiente",
    "dias_atraso",
    "direccion",
    "telefono_movil",
    "nombre_completo",
}


@dataclass
class FieldChange:
    field: str
    old_value: Any
    new_value: Any
    is_important: bool = False


@dataclass
class ClientChange:
    codigo_cliente: str
    nombre_completo: str
    seccion_key: str
    changes: list[FieldChange] = field(default_factory=list)

    def to_sample(self) -> dict[str, Any]:
        return {
            "codigo_cliente": self.codigo_cliente,
            "nombre_completo": self.nombre_completo,
            "seccion_key": self.seccion_key,
        }


@dataclass
class SectionChanges:
    seccion_key: str
    new_clients: list[dict] = field(default_factory=list)
    removed_clients: list[dict] = field(default_factory=list)
    updated_clients: list[ClientChange] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new_clients or self.removed_clients or self.updated_clients)


@dataclass
class ChangeReport:
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

    def get_section(self, seccion_key: str) -> SectionChanges:
        if seccion_key not in self.sections:
            self.sections[seccion_key] = SectionChanges(seccion_key=seccion_key)
        return self.sections[seccion_key]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "nuevos": self.total_new,
            "actualizados": self.total_updated,
            "removidos": self.total_removed,
            "sin_cambios": self.total_unchanged,
            "secciones_afectadas": self.affected_sections,
        }


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).strip()


def _compare_client(old_data: dict, new_data: dict, seccion_key: str) -> ClientChange | None:
    changes = []
    for fld in COMPARE_FIELDS:
        old_val = old_data.get(fld)
        new_val = new_data.get(fld)
        if _normalize(old_val) != _normalize(new_val):
            changes.append(
                FieldChange(
                    field=fld,
                    old_value=old_val,
                    new_value=new_val,
                    is_important=fld in IMPORTANT_FIELDS,
                )
            )
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
    report = ChangeReport()
    all_sections = set(old_by_seccion.keys()) | set(new_by_seccion.keys())

    for seccion_key in all_sections:
        section = report.get_section(seccion_key)
        old_clients = old_by_seccion.get(seccion_key, {})
        new_clients_list = new_by_seccion.get(seccion_key, [])
        new_clients = {
            c.get("codigo_cliente", ""): c
            for c in new_clients_list
            if c.get("codigo_cliente")
        }

        old_codes = set(old_clients.keys())
        new_codes = set(new_clients.keys())

        for code in sorted(new_codes - old_codes):
            section.new_clients.append(new_clients[code])

        for code in sorted(old_codes - new_codes):
            old_data = old_clients[code]
            if old_data.get("activo_en_cartera", True) is False:
                continue
            section.removed_clients.append(old_data)

        for code in sorted(old_codes & new_codes):
            change = _compare_client(old_clients[code], new_clients[code], seccion_key)
            if change:
                section.updated_clients.append(change)
            else:
                section.unchanged_count += 1

    return report
