"""Gestión del catálogo global de etiquetas de seguimiento (admin → Firebase → APK)."""
from __future__ import annotations

import threading
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from ..theme import *
from ..components import SectionHeader

if TYPE_CHECKING:
    from ..app import App

_PRESET_COLORS = [
    "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
    "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#6366F1",
]


class EtiquetasPage:
    """CRUD de etiquetas globales para organización de clientes en el APK."""

    def __init__(self, app: "App"):
        self.app = app
        self._container = None
        self._tree: ttk.Treeview | None = None
        self._rows: list[dict] = []

    def render(self, parent):
        self._container = ctk.CTkFrame(parent, fg_color="transparent")
        self._container.pack(fill="both", expand=True)

        SectionHeader(
            self._container,
            title="Etiquetas de seguimiento",
            subtitle="Catálogo global visible para todos los gestores en el APK",
        ).pack(fill="x", padx=24, pady=(16, 8))

        toolbar = ctk.CTkFrame(self._container, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkButton(
            toolbar, text="+ Nueva etiqueta", width=140, height=34,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._on_add,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="Editar", width=90, height=34,
            command=self._on_edit,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="Desactivar", width=100, height=34,
            fg_color="#6B7280", hover_color="#4B5563",
            command=self._on_deactivate,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="Publicar a Firebase", width=160, height=34,
            fg_color="#059669", hover_color="#047857",
            command=self._on_publish,
        ).pack(side="right")

        table_frame = ctk.CTkFrame(self._container, fg_color=CARD_BG, corner_radius=8)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        cols = ("orden", "nombre", "color", "activa", "descripcion")
        self._tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", height=16,
        )
        self._tree.heading("orden", text="#")
        self._tree.heading("nombre", text="Nombre")
        self._tree.heading("color", text="Color")
        self._tree.heading("activa", text="Activa")
        self._tree.heading("descripcion", text="Descripción")
        self._tree.column("orden", width=40, anchor="center")
        self._tree.column("nombre", width=200)
        self._tree.column("color", width=80, anchor="center")
        self._tree.column("activa", width=60, anchor="center")
        self._tree.column("descripcion", width=300)
        self._tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._tree.bind("<Double-1>", lambda _e: self._on_edit())

        self._refresh()

    def _refresh(self):
        if not self._tree or not self._tree.winfo_exists():
            return
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._rows = self.app.campaign_mgr.list_etiquetas()
        for row in self._rows:
            self._tree.insert("", "end", iid=row["id"], values=(
                row.get("orden", 0),
                row.get("nombre", ""),
                row.get("color", ""),
                "Sí" if row.get("activa") else "No",
                row.get("descripcion", ""),
            ))

    def _selected_id(self) -> str | None:
        if not self._tree:
            return None
        sel = self._tree.selection()
        return sel[0] if sel else None

    def _open_dialog(self, existing: dict | None = None):
        win = ctk.CTkToplevel(self._container)
        win.title("Editar etiqueta" if existing else "Nueva etiqueta")
        win.geometry("420x360")
        win.transient(self._container.winfo_toplevel())
        win.grab_set()

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(body, text="Nombre", font=font(12)).pack(anchor="w")
        name_entry = ctk.CTkEntry(body, width=360)
        name_entry.pack(fill="x", pady=(4, 12))
        if existing:
            name_entry.insert(0, existing.get("nombre", ""))

        ctk.CTkLabel(body, text="Color", font=font(12)).pack(anchor="w")
        color_var = ctk.StringVar(value=existing.get("color", "#3B82F6") if existing else "#3B82F6")
        color_row = ctk.CTkFrame(body, fg_color="transparent")
        color_row.pack(fill="x", pady=(4, 12))
        color_entry = ctk.CTkEntry(color_row, textvariable=color_var, width=120)
        color_entry.pack(side="left")
        for c in _PRESET_COLORS:
            ctk.CTkButton(
                color_row, text="", width=24, height=24,
                fg_color=c, hover_color=c,
                command=lambda col=c: color_var.set(col),
            ).pack(side="left", padx=2)

        ctk.CTkLabel(body, text="Orden", font=font(12)).pack(anchor="w")
        orden_entry = ctk.CTkEntry(body, width=80)
        orden_entry.pack(anchor="w", pady=(4, 12))
        orden_entry.insert(0, str(existing.get("orden", 0) if existing else len(self._rows)))

        ctk.CTkLabel(body, text="Descripción (opcional)", font=font(12)).pack(anchor="w")
        desc_entry = ctk.CTkTextbox(body, height=60)
        desc_entry.pack(fill="x", pady=(4, 12))
        if existing and existing.get("descripcion"):
            desc_entry.insert("1.0", existing["descripcion"])

        activa_var = ctk.BooleanVar(value=existing.get("activa", True) if existing else True)
        ctk.CTkCheckBox(body, text="Activa", variable=activa_var).pack(anchor="w", pady=(0, 12))

        def save():
            nombre = name_entry.get().strip()
            if not nombre:
                messagebox.showwarning("Validación", "El nombre es obligatorio.", parent=win)
                return
            color = color_var.get().strip() or "#3B82F6"
            try:
                orden = int(orden_entry.get().strip() or "0")
            except ValueError:
                orden = 0
            descripcion = desc_entry.get("1.0", "end").strip()
            if existing:
                self.app.campaign_mgr.update_etiqueta(
                    existing["id"],
                    nombre=nombre,
                    color=color,
                    descripcion=descripcion,
                    activa=activa_var.get(),
                    orden=orden,
                )
            else:
                self.app.campaign_mgr.create_etiqueta(
                    nombre=nombre,
                    color=color,
                    descripcion=descripcion,
                    orden=orden,
                )
            win.destroy()
            self._refresh()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(
            btn_row, text="Guardar", width=100, fg_color=ACCENT,
            hover_color=ACCENT_HOVER, command=save,
        ).pack(side="right")
        ctk.CTkButton(btn_row, text="Cancelar", width=100, command=win.destroy).pack(side="right", padx=8)

    def _on_add(self):
        self._open_dialog()

    def _on_edit(self):
        tag_id = self._selected_id()
        if not tag_id:
            messagebox.showinfo("Etiquetas", "Seleccione una etiqueta.")
            return
        existing = next((r for r in self._rows if r["id"] == tag_id), None)
        if existing:
            self._open_dialog(existing)

    def _on_deactivate(self):
        tag_id = self._selected_id()
        if not tag_id:
            messagebox.showinfo("Etiquetas", "Seleccione una etiqueta.")
            return
        if messagebox.askyesno("Desactivar", "¿Desactivar esta etiqueta?"):
            self.app.campaign_mgr.delete_etiqueta(tag_id)
            self._refresh()

    def _on_publish(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return

        def work():
            try:
                ok = self.app.campaign_mgr.upload_catalogo_etiquetas(self.app.firebase)
                self.app.after(0, lambda: self._publish_done(ok))
            except Exception as e:
                self.app.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _publish_done(self, ok: bool):
        if ok:
            messagebox.showinfo("Etiquetas", "Catálogo publicado en Firebase correctamente.")
            self.app.set_status("Catálogo de etiquetas publicado", 1)
        else:
            messagebox.showerror("Error", "No se pudo publicar el catálogo.")
