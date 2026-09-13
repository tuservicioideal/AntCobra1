"""Autorización admin/supervisor para carga de cartera."""

from __future__ import annotations

from typing import Any


class CarteraAuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def assert_can_manage_cartera(auth: dict[str, Any] | None, user_doc: dict[str, Any] | None) -> str:
    if not auth or not auth.get("uid"):
        raise CarteraAuthError("unauthenticated", "Debes iniciar sesión.")
    if not user_doc:
        raise CarteraAuthError("permission-denied", "Perfil no encontrado.")
    if user_doc.get("activo") is False:
        raise CarteraAuthError("permission-denied", "Usuario inactivo.")
    rol = str(user_doc.get("rol") or "")
    if rol not in ("admin", "supervisor"):
        raise CarteraAuthError(
            "permission-denied",
            "Solo administradores o supervisores pueden cargar cartera.",
        )
    return str(auth["uid"])
