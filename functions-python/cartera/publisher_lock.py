"""Decisión de lock de publicación (sin I/O). El caller hace la transacción."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

STALE_AFTER = timedelta(minutes=45)


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def lock_is_busy(
    lock: dict[str, Any] | None,
    job_id: str,
    *,
    now: datetime | None = None,
    stale_after: timedelta = STALE_AFTER,
) -> bool:
    """True si hay una publicación en curso y el lock no está vencido.

    Cualquier job (incluido el mismo) queda bloqueado: evita doble tap / retry
    mientras la Function sigue viva. Tras STALE_AFTER se puede robar el lock.
    """
    data = lock or {}
    _ = job_id
    if data.get("estado") != "publicando":
        return False
    since = _as_utc(data.get("since"))
    if since is None:
        return True
    current = now or datetime.now(timezone.utc)
    return (current - since) < stale_after
