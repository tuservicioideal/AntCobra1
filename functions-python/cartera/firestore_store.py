"""Adaptador Firestore con la misma interfaz que InMemoryStore."""

from __future__ import annotations

from typing import Any

from .config import BATCH_LIMIT

try:
    from google.cloud.firestore import SERVER_TIMESTAMP
except ImportError:  # pragma: no cover
    SERVER_TIMESTAMP = "SERVER_TIMESTAMP"


def _replace_timestamps(data: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in data.items():
        if value == "SERVER_TIMESTAMP":
            out[key] = SERVER_TIMESTAMP
        elif isinstance(value, dict):
            out[key] = _replace_timestamps(value)
        else:
            out[key] = value
    return out


class FirestoreStore:
    def __init__(self, db: Any) -> None:
        self.db = db
        self._batch = None
        self._count = 0

    def _doc_ref(self, *parts: str):
        if len(parts) < 2 or len(parts) % 2 != 0:
            raise ValueError(f"Ruta de documento inválida: {parts}")
        ref = self.db.collection(parts[0]).document(parts[1])
        i = 2
        while i < len(parts):
            ref = ref.collection(parts[i]).document(parts[i + 1])
            i += 2
        return ref

    def _col_ref(self, *parts: str):
        if len(parts) % 2 == 0:
            raise ValueError(f"Ruta de colección inválida: {parts}")
        ref = self.db.collection(parts[0])
        i = 1
        while i < len(parts):
            ref = ref.document(parts[i]).collection(parts[i + 1])
            i += 2
        return ref

    def get(self, *parts: str) -> dict[str, Any] | None:
        snap = self._doc_ref(*parts).get()
        return snap.to_dict() if snap.exists else None

    def set(self, *parts: str, data: dict[str, Any], merge: bool = False) -> None:
        if self._batch is None:
            self._batch = self.db.batch()
            self._count = 0
        payload = _replace_timestamps(data)
        self._batch.set(self._doc_ref(*parts), payload, merge=merge)
        self._count += 1
        if self._count >= BATCH_LIMIT:
            self.commit()

    def list_children(self, *parts: str) -> list[tuple[str, dict[str, Any]]]:
        out: list[tuple[str, dict[str, Any]]] = []
        for snap in self._col_ref(*parts).stream():
            out.append((snap.id, snap.to_dict() or {}))
        return out

    def list_clientes(self, campaign_id: str, seccion: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for snap in self._col_ref(
            "campañas", campaign_id, "gestores", seccion, "clientes"
        ).stream():
            result[snap.id] = snap.to_dict() or {}
        return result

    def commit(self) -> None:
        if self._batch is not None and self._count > 0:
            self._batch.commit()
        self._batch = None
        self._count = 0
