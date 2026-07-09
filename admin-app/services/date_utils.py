"""Utilidades de parseo de fechas del Excel bancario."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


_DATE_FORMATS = (
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%d/%m/%y",
    "%Y/%m/%d",
)


def parse_excel_fecha(
    value: Any,
    fallback: Optional[date] = None,
) -> Optional[date]:
    """Convierte un valor del Excel (str, date, datetime) a ``date``."""
    if value is None:
        return fallback

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "-"}:
        return fallback

    # Excel serial number (días desde 1899-12-30)
    try:
        serial = float(text.replace(",", "."))
        if 30000 < serial < 60000:
            base = date(1899, 12, 30)
            return base.fromordinal(base.toordinal() + int(serial))
    except (ValueError, OverflowError):
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return fallback


def format_fecha_iso(d: Optional[date]) -> str:
    """Serializa fecha a ISO (YYYY-MM-DD) para Firestore."""
    return d.isoformat() if d else ""
