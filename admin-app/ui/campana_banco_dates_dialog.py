"""Diálogo para editar fechas de inicio/fin de una campaña banco."""
from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox
from datetime import date
from typing import TYPE_CHECKING, Callable

from services.date_utils import parse_excel_fecha
from .theme import *

if TYPE_CHECKING:
    from .app import App


def _fmt(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


class CampanaBancoDatesDialog(ctk.CTkToplevel):
    """Modal para override manual de fechas de campaña banco."""

    def __init__(
        self,
        app: "App",
        campana_id: str,
        timeline: dict,
        on_saved: Callable[[], None] | None = None,
    ):
        super().__init__(app)
        self.app = app
        self.campana_id = campana_id
        self.timeline = timeline
        self._on_saved = on_saved
        self.key = timeline.get("key", "")

        self.title(f"Fechas — campaña {timeline.get('label', '')}")
        self.geometry("440x360")
        self.minsize(400, 320)
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            body,
            text=f"Campaña banco: {timeline.get('label', '—')}",
            font=font(FONT_SCALE["lg"], "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        det = timeline.get("fecha_inicio_detectada")
        det_fin = timeline.get("fecha_fin_detectada")
        ctk.CTkLabel(
            body,
            text=(
                f"Detectadas del Excel: {_fmt(det)} → {_fmt(det_fin)}\n"
                "Formato: DD/MM/AAAA"
            ),
            font=font(FONT_SCALE["sm"]),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        eff_ini = timeline.get("fecha_inicio")
        eff_fin = timeline.get("fecha_fin")

        self._var_inicio = ctk.StringVar(
            value=_fmt(eff_ini) if eff_ini else ""
        )
        self._var_fin = ctk.StringVar(
            value=_fmt(eff_fin) if eff_fin else ""
        )

        for lbl, var in (
            ("Fecha inicio:", self._var_inicio),
            ("Fecha fin:", self._var_fin),
        ):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(
                row, text=lbl, width=110, anchor="w",
                font=font(FONT_SCALE["sm"]), text_color=TEXT_PRIMARY,
            ).pack(side="left")
            ctk.CTkEntry(
                row, textvariable=var, width=200, height=32,
                font=font(FONT_SCALE["sm"]),
            ).pack(side="left", padx=(8, 0))

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(24, 0))

        ctk.CTkButton(
            btn_row,
            text="Guardar",
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            height=36,
            width=120,
            command=self._save,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Restaurar detectadas",
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SECONDARY,
            height=36,
            width=160,
            command=self._restore,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            fg_color="transparent",
            text_color=TEXT_MUTED,
            height=36,
            width=100,
            command=self.destroy,
        ).pack(side="right")

    def _parse_field(self, text: str, label: str) -> date:
        parsed = parse_excel_fecha(text.strip())
        if parsed is None:
            raise ValueError(f"{label}: formato inválido (use DD/MM/AAAA).")
        return parsed

    def _save(self):
        try:
            inicio = self._parse_field(self._var_inicio.get(), "Fecha inicio")
            fin = self._parse_field(self._var_fin.get(), "Fecha fin")
            if fin < inicio:
                raise ValueError(
                    "La fecha de fin no puede ser anterior a la de inicio."
                )
            self.app.campaign_mgr.update_campana_banco_dates(
                self.campana_id,
                self.key,
                fecha_inicio=inicio,
                fecha_fin=fin,
            )
            if self._on_saved:
                self._on_saved()
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("Fechas inválidas", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _restore(self):
        try:
            self.app.campaign_mgr.update_campana_banco_dates(
                self.campana_id,
                self.key,
                restore_detected=True,
            )
            if self._on_saved:
                self._on_saved()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)


def open_campana_banco_dates_dialog(
    app: "App",
    campana_id: str,
    timeline: dict,
    on_saved: Callable[[], None] | None = None,
) -> None:
    CampanaBancoDatesDialog(app, campana_id, timeline, on_saved=on_saved)
