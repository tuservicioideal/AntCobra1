"""Flujo de actualización visible y a prueba de clics repetidos."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk

from config import APP_VERSION
from services import update_service
from .theme import *

BusyCb = Callable[[bool, str], None]
StatusCb = Callable[[str, float | None], None]


def _center_on_parent(dialog: ctk.CTkToplevel, parent, width: int, height: int) -> None:
    try:
        parent.update_idletasks()
        px = int(parent.winfo_rootx())
        py = int(parent.winfo_rooty())
        pw = int(parent.winfo_width())
        ph = int(parent.winfo_height())
        x = px + max(12, (pw - width) // 2)
        y = py + max(12, (ph - height) // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        dialog.geometry(f"{width}x{height}")


def _prepare_modal(dialog: ctk.CTkToplevel, parent) -> None:
    dialog.transient(parent)
    dialog.resizable(False, False)
    try:
        dialog.lift()
        dialog.focus_force()
        dialog.attributes("-topmost", True)
        dialog.after(250, lambda: dialog.attributes("-topmost", False))
        dialog.after(40, dialog.grab_set)
    except Exception:
        pass


def ask_yes_no(parent, title: str, message: str, *, ok_text: str = "Sí, actualizar") -> bool:
    """Diálogo CTk delante de la ventana (messagebox de Tk suele quedar detrás)."""
    result = {"ok": False}
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    _center_on_parent(dialog, parent, 480, 320)
    _prepare_modal(dialog, parent)

    body = ctk.CTkFrame(dialog, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=20, pady=18)

    ctk.CTkLabel(
        body,
        text=title,
        font=font(FONT_SCALE["lg"], "bold"),
        text_color=TEXT_PRIMARY,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        body,
        text=message,
        font=font(FONT_SCALE["sm"]),
        text_color=TEXT_SECONDARY,
        wraplength=430,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(10, 16))

    def _yes() -> None:
        result["ok"] = True
        dialog.destroy()

    def _no() -> None:
        dialog.destroy()

    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(fill="x", side="bottom")
    ctk.CTkButton(
        row,
        text=ok_text,
        font=font(FONT_SCALE["sm"], "bold"),
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        height=36,
        width=150,
        command=_yes,
    ).pack(side="right")
    ctk.CTkButton(
        row,
        text="Ahora no",
        font=font(FONT_SCALE["sm"]),
        fg_color="transparent",
        hover_color=BORDER,
        text_color=TEXT_SECONDARY,
        border_width=1,
        border_color=BORDER,
        height=36,
        width=110,
        command=_no,
    ).pack(side="right", padx=(0, 8))

    dialog.bind("<Return>", lambda _e: _yes())
    dialog.bind("<Escape>", lambda _e: _no())
    parent.wait_window(dialog)
    return bool(result["ok"])


def show_message(parent, title: str, message: str, *, kind: str = "info") -> None:
    color = {"error": DANGER, "warning": WARNING}.get(kind, ACCENT)
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    _center_on_parent(dialog, parent, 440, 240)
    _prepare_modal(dialog, parent)

    body = ctk.CTkFrame(dialog, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=20, pady=18)
    ctk.CTkLabel(
        body,
        text=title,
        font=font(FONT_SCALE["lg"], "bold"),
        text_color=color,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        body,
        text=message,
        font=font(FONT_SCALE["sm"]),
        text_color=TEXT_SECONDARY,
        wraplength=390,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(10, 16))

    def _close() -> None:
        dialog.destroy()

    ctk.CTkButton(
        body,
        text="Aceptar",
        font=font(FONT_SCALE["sm"], "bold"),
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        height=36,
        width=120,
        command=_close,
    ).pack(anchor="e", side="bottom")
    dialog.bind("<Return>", lambda _e: _close())
    dialog.bind("<Escape>", lambda _e: _close())
    parent.wait_window(dialog)


def offer_and_install(
    window,
    info,
    *,
    from_startup: bool = False,
    busy_cb: BusyCb | None = None,
    status_cb: StatusCb | None = None,
) -> bool:
    """Muestra un único diálogo visible y, si aceptan, descarga y aplica.

    Returns True when a download thread was started.
    """
    if not info.version:
        if not from_startup:
            show_message(window, "Actualizaciones", "Manifiesto de versión inválido.", kind="warning")
        return False
    if not info.is_newer:
        if not from_startup:
            show_message(
                window,
                "Actualizaciones",
                f"Ya tienes la última versión ({APP_VERSION}).\n"
                f"Publicada en servidor: {info.version}",
            )
        return False

    notes = info.notes or "(Sin notas)"
    if not ask_yes_no(
        window,
        "Actualización disponible",
        f"Hay una nueva versión: {info.version}\n"
        f"Tu versión: {APP_VERSION}\n\n"
        f"{notes}\n\n"
        "Se descargará e instalará ahora. La aplicación se cerrará y volverá a abrir.",
    ):
        return False

    if busy_cb:
        busy_cb(True, "Descargando…")
    if status_cb:
        status_cb("Descargando actualización…", 0.1)

    def progress(msg: str, frac: float) -> None:
        window.after(0, lambda m=msg, f=frac: _on_progress(m, f))

    def _on_progress(msg: str, frac: float) -> None:
        try:
            if not window.winfo_exists():
                return
        except Exception:
            return
        if busy_cb:
            busy_cb(True, (msg or "Descargando…")[:28])
        if status_cb:
            status_cb(msg, frac)

    def work() -> None:
        result = update_service.download_update(info, progress=progress)

        def done() -> None:
            try:
                if not window.winfo_exists():
                    return
            except Exception:
                return
            _apply_downloaded(window, result, info.version, busy_cb, status_cb)

        window.after(0, done)

    threading.Thread(target=work, daemon=True).start()
    return True


def _apply_downloaded(
    window,
    result,
    version: str,
    busy_cb: BusyCb | None,
    status_cb: StatusCb | None,
) -> None:
    if not result.success:
        if busy_cb:
            busy_cb(False, "")
        if status_cb:
            status_cb("Error al descargar actualización", 0)
        show_message(window, "Actualizaciones", result.message, kind="error")
        return

    if status_cb:
        status_cb(result.message, 1.0)
    if not result.exe_path:
        if busy_cb:
            busy_cb(False, "")
        update_service.open_folder(result.folder or result.zip_path)
        show_message(
            window,
            "Actualizaciones",
            "Se descargó el paquete pero no se encontró el ejecutable.",
            kind="warning",
        )
        return

    try:
        applied = update_service.apply_update_inplace(result.exe_path, relaunch=True)
    except Exception as e:
        if busy_cb:
            busy_cb(False, "")
        show_message(
            window,
            "Actualizaciones",
            f"No se pudo aplicar la actualización:\n{e}",
            kind="error",
        )
        update_service.open_folder(result.folder or result.exe_path)
        return

    if not applied.success:
        if busy_cb:
            busy_cb(False, "")
        show_message(window, "Actualizaciones", applied.message, kind="error")
        update_service.open_folder(result.folder or result.exe_path)
        return

    if applied.will_relaunch:
        window.destroy()
        return

    extra = applied.message or f"Versión {version} lista."
    show_message(window, "Actualizaciones", extra)
    if busy_cb:
        busy_cb(False, "")
