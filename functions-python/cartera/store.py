"""Store en memoria para tests del publisher (sin Firestore)."""

from __future__ import annotations

from typing import Any


def join_path(*parts: str) -> str:
    return "/".join(str(p) for p in parts)


class InMemoryStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def get(self, *parts: str) -> dict[str, Any] | None:
        return self.docs.get(join_path(*parts))

    def set(self, *parts: str, data: dict[str, Any], merge: bool = False) -> None:
        key = join_path(*parts)
        if merge and key in self.docs:
            merged = dict(self.docs[key])
            merged.update(data)
            self.docs[key] = merged
        else:
            self.docs[key] = dict(data)

    def list_children(self, *parts: str) -> list[tuple[str, dict[str, Any]]]:
        prefix = join_path(*parts) + "/"
        children: dict[str, dict[str, Any]] = {}
        for key, value in self.docs.items():
            if not key.startswith(prefix):
                continue
            child_id = key[len(prefix) :].split("/")[0]
            child_path = join_path(*parts, child_id)
            if child_path == key:
                children[child_id] = value
            elif child_id not in children:
                children[child_id] = self.docs.get(child_path) or {}
        return list(children.items())

    def commit(self) -> None:
        return None

    def list_clientes(self, campaign_id: str, seccion: str) -> dict[str, dict[str, Any]]:
        prefix = join_path("campañas", campaign_id, "gestores", seccion, "clientes") + "/"
        result: dict[str, dict[str, Any]] = {}
        for key, value in self.docs.items():
            if key.startswith(prefix) and key.count("/") == prefix.count("/"):
                code = key.rsplit("/", 1)[-1]
                result[code] = value
        return result
