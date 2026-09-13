"""Casos de problema — embudo del resolutor (vista tabular admin)."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import messagebox

from ..theme import *
from ..components import KPICard, SectionHeader

if TYPE_CHECKING:
    from ..app import App

_TIPO_LABELS = {
    "suplantacion": ("Suplantación", "#E11D48"),
    "pago_no_registrado": ("Pago no registrado", "#3B82F6"),
    "no_hizo_pedido": ("No hizo pedido", "#EA580C"),
    "completo_pedido_socia": ("Completó el pedido la socia", "#0D9488"),
}

_ETAPA_LABELS = {
    "nuevo": "Nuevo",
    "en_gestion": "En gestión",
    "esperando_respuesta": "Esperando respuesta",
    "resuelto": "Resuelto",
    "no_procede": "No procede",
}


class CasosPage:
    """Lista/KPI de casos Firestore para admin, supervisor y resolutor."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._casos: list[dict] = []
        self._filtered: list[dict] = []
        self._filter_etapa = "todas"
        self._filter_tipo = "todos"
        self._busy = False

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        if not self.app.firebase_connected:
            ctk.CTkLabel(
                container,
                text="Conecte Firebase para ver casos.",
                font=font(14),
                text_color=TEXT_SECONDARY,
            ).pack(pady=20)
            return

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))
        SectionHeader(
            header,
            "Casos de problema",
            "Embudo del resolutor: suplantación, pagos y pedidos",
        ).pack(side="left", anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        if self.app.auth_result and self.app.auth_result.rol in (
            "admin",
            "supervisor",
        ):
            ctk.CTkButton(
                actions,
                text="Migrar alertas → casos",
                font=font(11, "bold"),
                fg_color=WARNING,
                hover_color="#D97706",
                height=32,
                corner_radius=8,
                command=self._migrate_alerts,
            ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Actualizar",
            font=font(11, "bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            height=32,
            width=110,
            corner_radius=8,
            command=self._refresh,
        ).pack(side="left")

        self._kpi_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._kpi_frame.pack(fill="x", padx=8, pady=8)
        for i in range(6):
            self._kpi_frame.grid_columnconfigure(i, weight=1)

        filters = ctk.CTkFrame(container, fg_color="transparent")
        filters.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(filters, text="Etapa:", font=font(11), text_color=TEXT_SECONDARY).pack(
            side="left", padx=(0, 4)
        )
        self._etapa_var = ctk.StringVar(value="todas")
        ctk.CTkOptionMenu(
            filters,
            variable=self._etapa_var,
            values=["todas", *list(_ETAPA_LABELS.keys())],
            command=lambda _: self._apply_filters(),
            width=160,
            height=28,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(filters, text="Tipo:", font=font(11), text_color=TEXT_SECONDARY).pack(
            side="left", padx=(0, 4)
        )
        self._tipo_var = ctk.StringVar(value="todos")
        ctk.CTkOptionMenu(
            filters,
            variable=self._tipo_var,
            values=["todos", *list(_TIPO_LABELS.keys())],
            command=lambda _: self._apply_filters(),
            width=180,
            height=28,
        ).pack(side="left")

        self._list = ctk.CTkScrollableFrame(
            container, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER, height=480,
        )
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._status_lbl = ctk.CTkLabel(
            container, text="Cargando…", font=font(12), text_color=TEXT_SECONDARY
        )
        self._status_lbl.pack(pady=4)

        self._refresh()

    def stop(self):
        pass

    def _refresh(self):
        if self._busy:
            return
        self._busy = True
        self._status_lbl.configure(text="Cargando casos…")

        def work():
            try:
                casos = self.app.firebase.list_casos(limit=400)
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._on_loaded(casos, None))
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._on_loaded([], str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, casos: list, err: str | None):
        self._busy = False
        if err:
            self._status_lbl.configure(text=f"Error: {err}", text_color=DANGER)
            return
        self._casos = casos
        self._apply_filters()
        self._status_lbl.configure(
            text=f"{len(self._filtered)} de {len(self._casos)} casos",
            text_color=TEXT_SECONDARY,
        )

    def _apply_filters(self):
        etapa = self._etapa_var.get() if hasattr(self, "_etapa_var") else "todas"
        tipo = self._tipo_var.get() if hasattr(self, "_tipo_var") else "todos"
        rows = self._casos
        if etapa != "todas":
            rows = [c for c in rows if c.get("etapa") == etapa]
        if tipo != "todos":
            rows = [c for c in rows if c.get("tipo") == tipo]
        self._filtered = rows
        self._render_kpis()
        self._render_list()

    def _render_kpis(self):
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        by_etapa = {k: 0 for k in _ETAPA_LABELS}
        abiertos = 0
        for c in self._casos:
            et = c.get("etapa", "nuevo")
            if et in by_etapa:
                by_etapa[et] += 1
            if c.get("abierto"):
                abiertos += 1
        cards = [
            ("Abiertos", str(abiertos), ACCENT),
            ("Nuevo", str(by_etapa["nuevo"]), WARNING),
            ("En gestión", str(by_etapa["en_gestion"]), INFO),
            ("Esperando", str(by_etapa["esperando_respuesta"]), "#7C3AED"),
            ("Resuelto", str(by_etapa["resuelto"]), SUCCESS),
            ("No procede", str(by_etapa["no_procede"]), TEXT_MUTED),
        ]
        for i, (title, val, color) in enumerate(cards):
            KPICard(self._kpi_frame, label=title, value=val, accent=color).grid(
                row=0, column=i, sticky="nsew", padx=4
            )

    def _render_list(self):
        for w in self._list.winfo_children():
            w.destroy()
        if not self._filtered:
            ctk.CTkLabel(
                self._list,
                text="Sin casos con estos filtros.",
                font=font(13),
                text_color=TEXT_MUTED,
            ).pack(pady=20)
            return
        for c in self._filtered:
            self._render_row(c)

    def _render_row(self, c: dict):
        tipo = c.get("tipo", "")
        label, color = _TIPO_LABELS.get(tipo, (tipo, TEXT_SECONDARY))
        etapa = _ETAPA_LABELS.get(c.get("etapa", ""), c.get("etapa", ""))
        card = ctk.CTkFrame(
            self._list, fg_color="#F8FAFC", corner_radius=8,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill="x", pady=3, padx=4)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left,
            text=c.get("cliente_nombre") or "Sin nombre",
            font=font(13, "bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=(
                f"DNI {c.get('cliente_dni') or '—'} · {label} · {etapa}"
                f" · Gestor: {c.get('gestor_nombre') or '—'}"
            ),
            font=font(11),
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w")
        nota = (c.get("nota_origen") or "").strip()
        if nota:
            ctk.CTkLabel(
                left,
                text=nota[:120] + ("…" if len(nota) > 120 else ""),
                font=font(11),
                text_color=TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

        badge = ctk.CTkLabel(
            row,
            text=label,
            font=font(10, "bold"),
            text_color=color,
            fg_color="#FFFFFF",
            corner_radius=6,
            padx=8,
            pady=4,
        )
        badge.pack(side="right")

    def _migrate_alerts(self):
        if not messagebox.askyesno(
            "Migrar alertas",
            "¿Crear casos desde alertas pendientes de "
            "suplantación y pago no registrado?\n"
            "Las alertas migradas se marcarán como revisadas.",
        ):
            return

        def work():
            try:
                result = self.app.firebase.migrate_pending_alerts_to_casos()
                msg = (
                    f"Creados: {result.get('created', 0)}\n"
                    f"Omitidos: {result.get('skipped', 0)}\n"
                    f"Alertas marcadas: {result.get('marked', 0)}"
                )
                errs = result.get("errors") or []
                if errs:
                    msg += f"\nErrores: {len(errs)}"
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0,
                        lambda: (
                            messagebox.showinfo("Migración", msg),
                            self._refresh(),
                        ),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: messagebox.showerror("Error", str(e))
                    )

        threading.Thread(target=work, daemon=True).start()
