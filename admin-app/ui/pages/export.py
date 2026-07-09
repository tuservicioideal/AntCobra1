"""Export page — Export management results to Excel."""
from __future__ import annotations

import os
import threading
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from services.campana_banco_utils import (
    apply_campana_banco_filter,
    display_label_for_key,
)
from ..theme import *
from ..components import KPICard, SectionHeader

if TYPE_CHECKING:
    from ..app import App


class ExportPage:
    """Page for exporting management results to Excel."""

    def __init__(self, app: App):
        self.app = app
        self._campana_banco_filter: str | None = None
        self._campana_options: list[str] = []
        self._campana_label_to_key: dict[str, str] = {}

    def render(self, container: ctk.CTkScrollableFrame):
        self._container = container
        for w in container.winfo_children():
            w.destroy()

        if not self.app.active_campaign:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            ctk.CTkLabel(container,
                         text="No hay campaña activa. Cargue un Excel o restaure desde la nube.",
                         font=font(14), text_color=TEXT_SECONDARY).pack(pady=20)
            return

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 12))
        SectionHeader(hdr, "Exportar Gestión",
                      "Genera un Excel con los resultados de gestión de campo"
                      ).pack(side="left")

        card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=8, pady=8)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text="Nombre proveedor:",
                     font=font(12), text_color=TEXT_PRIMARY
                     ).grid(row=0, column=0, sticky="w", pady=4)
        self._proveedor_var = ctk.StringVar(value="PERECAUDOL")
        ctk.CTkEntry(inner, textvariable=self._proveedor_var,
                     width=220, font=font(12)
                     ).grid(row=0, column=1, padx=(8, 0), pady=4, sticky="w")

        self._solo_gestionados = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(inner, text="Solo clientes gestionados (excluir pendientes)",
                        variable=self._solo_gestionados, font=font(11),
                        text_color=TEXT_PRIMARY
                        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=8)

        self._campana_options = (
            self.app.campaign_mgr.distinct_campana_banco_for_campaign(
                self.app.active_campaign.id
            )
        )
        campana_labels = ["(Todas las campañas)"]
        self._campana_label_to_key = {}
        for key in self._campana_options:
            label = display_label_for_key(key)
            campana_labels.append(label)
            self._campana_label_to_key[label] = key

        ctk.CTkLabel(inner, text="Nº campaña banco:",
                     font=font(12), text_color=TEXT_PRIMARY
                     ).grid(row=2, column=0, sticky="w", pady=4)
        self._campana_var = ctk.StringVar(value="(Todas las campañas)")
        ctk.CTkOptionMenu(
            inner,
            values=campana_labels,
            variable=self._campana_var,
            width=220,
            height=32,
            command=self._on_campana_menu_change,
        ).grid(row=2, column=1, padx=(8, 0), pady=4, sticky="w")

        kpi_frame = ctk.CTkFrame(container, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=8, pady=(8, 4))
        kpi_frame.grid_columnconfigure(tuple(range(4)), weight=1)

        clients = self._filtered_clients()
        total = len(clients)
        gestionados = sum(
            1 for c in clients if c.get("estado_gestion", "pendiente") != "pendiente"
        )
        con_niveles = sum(1 for c in clients if c.get("nivel_1"))
        con_promesa = sum(
            1 for c in clients
            if c.get("monto_promesa_pago") and float(c.get("monto_promesa_pago", 0)) > 0
        )

        kpi_defs = [
            ("Total clientes", str(total), ACCENT),
            ("Gestionados", str(gestionados), SUCCESS),
            ("Con niveles", str(con_niveles), INFO),
            ("Con promesa $", str(con_promesa), "#059669"),
        ]
        for i, (lbl, val, clr) in enumerate(kpi_defs):
            KPICard(kpi_frame, lbl, val, clr).grid(
                row=0, column=i, padx=3, pady=4, sticky="nsew")

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=16)

        self._export_btn = ctk.CTkButton(
            btn_frame, text="  Exportar a Excel  ",
            font=font(13, "bold"), height=42, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._on_export)
        self._export_btn.pack(anchor="center")

        self._status_lbl = ctk.CTkLabel(
            btn_frame, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._status_lbl.pack(anchor="center", pady=(8, 0))

        last = self.app.campaign_mgr.get_last_sync()
        if last:
            sync_text = (
                f"Última sincronización: {last['tipo']} — {last['fecha']} — "
                f"{last['registros_afectados']} registros ({last['resultado']})"
            )
        else:
            sync_text = "Sin sincronizaciones registradas. Sincronice visitas antes de exportar."
        ctk.CTkLabel(container, text=sync_text, font=font(10),
                     text_color=TEXT_MUTED).pack(padx=12, pady=(4, 8))

    def _on_campana_menu_change(self, _label: str):
        label = self._campana_var.get()
        if label == "(Todas las campañas)":
            self._campana_banco_filter = None
        else:
            self._campana_banco_filter = self._campana_label_to_key.get(label, label)
        self.render(self._container)

    def _filtered_clients(self) -> list[dict]:
        try:
            clients = self.app.campaign_mgr.get_all_clients(
                self.app.active_campaign.id)
        except Exception:
            return []
        return apply_campana_banco_filter(clients, self._campana_banco_filter)

    def _on_export(self):
        camp = self.app.active_campaign
        if not camp:
            messagebox.showwarning("Exportar", "No hay campaña activa.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Gestion_{camp.nombre.replace(' ', '_')}_{timestamp}.xlsx"

        path = filedialog.asksaveasfilename(
            title="Guardar Excel de Gestión",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        self._export_btn.configure(state="disabled", text="Exportando…")
        self._status_lbl.configure(text="Generando archivo…")
        campana_filter = self._campana_banco_filter

        def work():
            try:
                from services.excel_exporter import export_gestion_excel
                clients = self.app.campaign_mgr.get_all_clients(camp.id)
                clients = apply_campana_banco_filter(clients, campana_filter)

                result_path = export_gestion_excel(
                    clientes=clients,
                    output_path=path,
                    nombre_proveedor=self._proveedor_var.get().strip(),
                    solo_gestionados=self._solo_gestionados.get(),
                )
                exported = sum(
                    1 for c in clients
                    if not self._solo_gestionados.get()
                    or c.get("estado_gestion", "pendiente") != "pendiente"
                )
                self.app.after(0, lambda: self._export_done(result_path, exported))
            except Exception as e:
                self.app.after(0, lambda: self._export_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _export_done(self, path: str, count: int):
        self._export_btn.configure(state="normal", text="  Exportar a Excel  ")
        self._status_lbl.configure(
            text=f"Exportado: {count} registros → {os.path.basename(path)}")
        messagebox.showinfo(
            "Exportación Completa",
            f"Se exportaron {count} registros de gestión.\n\n"
            f"Archivo: {path}")

    def _export_error(self, msg: str):
        self._export_btn.configure(state="normal", text="  Exportar a Excel  ")
        self._status_lbl.configure(text=f"Error: {msg}")
        messagebox.showerror("Error de Exportación", msg)

    def stop(self):
        pass
