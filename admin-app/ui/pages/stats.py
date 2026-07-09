"""Statistics page — charts and campaign progress."""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
from typing import TYPE_CHECKING
from services.campana_banco_utils import (
    apply_campana_banco_filter,
    filter_bar_visible,
    filter_label,
)
from services.database import db_service
from ..theme import *
from ..components import CampanaBancoFilterBar, SectionHeader

if TYPE_CHECKING:
    from ..app import App

_TREE_BATCH = 80


class StatsPage:
    """Campaign statistics with pie chart, bar chart and tables."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._campana_banco_filter: str | None = None
        self._campana_options: list[str] = []

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        if not self.app.firebase_connected and not self.app.active_campaign:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            ctk.CTkLabel(container, text="Conecte Firebase o cargue campaña local para ver estadísticas.",
                         font=font(14), text_color=TEXT_SECONDARY).pack(pady=20)
            return

        ctk.CTkLabel(container, text="Cargando estadísticas…",
                     font=font(14), text_color=TEXT_SECONDARY).pack(pady=40)
        self._load()

    def _on_campana_filter_change(self, filtro: str | None):
        self._campana_banco_filter = filtro
        self._load()

    def _load(self):
        def work():
            try:
                campana_id = (
                    self.app.active_campaign.id
                    if self.app.active_campaign else None
                )
                if campana_id:
                    self._campana_options = (
                        self.app.campaign_mgr.distinct_campana_banco_for_campaign(
                            campana_id
                        )
                    )

                if self.app.firebase_connected:
                    data = self.app.firebase.get_campaign_status()
                    data = self.app.campaign_mgr.filter_firebase_status(
                        data, self._campana_banco_filter
                    )
                else:
                    data = self._build_local_status(self._campana_banco_filter)

                etapa_stats: dict = {}
                campana_rows: list[dict] = []
                if campana_id:
                    etapa_stats = db_service.get_stats(
                        campana_id,
                        campana_banco=self._campana_banco_filter,
                    )
                    campana_rows = self.app.campaign_mgr.get_stats_by_campana_banco(
                        campana_id
                    )

                sec_stats = self._compute_section_stats(data["secciones"])
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0,
                        lambda: self._render_data(
                            data, sec_stats, etapa_stats, campana_rows
                        ),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._on_error(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _build_local_status(self, campana_banco: str | None = None) -> dict:
        """Build stats-compatible payload from local SQLite data."""
        empty_resumen = {
            "total": 0, "pendiente": 0, "visitado_habido": 0,
            "visitado_no_habido": 0, "fallecido_inubicable": 0,
            "suplantacion": 0, "pago_no_registrado": 0,
            "deuda_total": 0.0, "deuda_visitada": 0.0,
        }
        if not self.app.active_campaign:
            return {"resumen": empty_resumen, "secciones": {}}

        clients = self.app.campaign_mgr.get_all_clients(self.app.active_campaign.id)
        clients = apply_campana_banco_filter(clients, campana_banco)

        secciones: dict = {}
        resumen = dict(empty_resumen)
        resumen["deuda_total"] = 0.0
        resumen["deuda_visitada"] = 0.0

        for c in clients:
            sec = c.get("seccion") or "SIN_SECCION"
            secciones.setdefault(sec, {"clientes": []})["clientes"].append(c)
            estado = c.get("estado_gestion", "pendiente")
            if estado in resumen:
                resumen[estado] += 1
            else:
                resumen["pendiente"] += 1
            deuda = float(c.get("importe_deuda_asignada", 0) or 0)
            resumen["deuda_total"] += deuda
            if estado != "pendiente":
                resumen["deuda_visitada"] += deuda
        resumen["total"] = len(clients)
        return {"resumen": resumen, "secciones": secciones}

    @staticmethod
    def _compute_section_stats(secciones: dict) -> list[dict]:
        """Pre-compute per-section aggregates on the worker thread."""
        result = []
        for sec_id in sorted(secciones):
            sec = secciones[sec_id]
            clients = sec["clientes"]
            total_sec = len(clients)
            done_sec = sum(
                1 for c in clients
                if c.get("estado_gestion", "pendiente") != "pendiente")
            deuda_sec = sum(
                float(c.get("importe_deuda_asignada", 0) or 0)
                for c in clients)
            pct = done_sec / total_sec if total_sec else 0
            result.append({
                "id": sec_id, "total": total_sec, "done": done_sec,
                "deuda": deuda_sec, "pct": pct,
            })
        return result

    def _render_data(
        self,
        data,
        sec_stats: list[dict],
        etapa_stats: dict | None = None,
        campana_rows: list[dict] | None = None,
    ):
        container = self._container
        for w in container.winfo_children():
            w.destroy()

        res = data["resumen"]

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(hdr, text="📊 Estadísticas de Campaña",
                     font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        subtitle = "Resumen completo del estado de la cartera"
        if self._campana_banco_filter is not None:
            subtitle += f"  ·  Filtrando: {filter_label(self._campana_banco_filter)}"
        ctk.CTkLabel(hdr, text=subtitle,
                     font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        if filter_bar_visible(self._campana_options):
            filter_row = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                        border_width=1, border_color=BORDER)
            filter_row.pack(fill="x", padx=16, pady=(0, 12))
            inner_filter = ctk.CTkFrame(filter_row, fg_color="transparent")
            inner_filter.pack(fill="x", padx=16, pady=10)
            CampanaBancoFilterBar(
                inner_filter,
                available=self._campana_options,
                selected=self._campana_banco_filter,
                on_change=self._on_campana_filter_change,
            ).pack(fill="x")

        kpi_outer = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        kpi_outer.pack(fill="x", padx=16, pady=(0, 16))

        kpi_frame = ctk.CTkFrame(kpi_outer, fg_color="transparent")
        kpi_frame.pack(fill="x", padx=16, pady=14)
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        avance = res["total"] - res["pendiente"]
        pct = round(avance / res["total"] * 100) if res["total"] else 0
        kpis = [
            ("👥 Total Clientes", str(res["total"]), ACCENT),
            ("✅ Avance", f"{avance} ({pct}%)", SUCCESS),
            ("💰 Deuda Total", f"S/ {res['deuda_total']:,.0f}", WARNING),
            ("📊 Deuda Gestionada", f"S/ {res['deuda_visitada']:,.0f}", INFO),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            cell = ctk.CTkFrame(kpi_frame, fg_color="transparent")
            cell.grid(row=0, column=i, padx=12, sticky="w")
            ctk.CTkLabel(cell, text=lbl, font=font(FONT_SCALE['xs']),
                         text_color=TEXT_MUTED).pack(anchor="w")
            ctk.CTkLabel(cell, text=val, font=font(FONT_SCALE['2xl'], "bold"),
                         text_color=clr).pack(anchor="w", pady=(2, 0))

        prog_card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        prog_card.pack(fill="x", padx=16, pady=(0, 16))
        prog_inner = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_inner.pack(fill="x", padx=16, pady=14)

        prog_row = ctk.CTkFrame(prog_inner, fg_color="transparent")
        prog_row.pack(fill="x")
        ctk.CTkLabel(prog_row, text="Progreso General",
                     font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(prog_row, text=f"{pct}%",
                     font=font(FONT_SCALE['base'], "bold"), text_color=SUCCESS).pack(side="right")

        pb = ctk.CTkProgressBar(prog_inner, height=10, progress_color=SUCCESS,
                                fg_color=BORDER, corner_radius=5)
        pb.pack(fill="x", pady=(8, 0))
        pb.set(pct / 100)

        charts_row = ctk.CTkFrame(container, fg_color="transparent")
        charts_row.pack(fill="x", padx=16, pady=(0, 16))
        charts_row.grid_columnconfigure(0, weight=3)
        charts_row.grid_columnconfigure(1, weight=4)

        self._render_pie(charts_row, res)
        self._render_bar(charts_row, sec_stats)

        if etapa_stats and etapa_stats.get("por_etapa_recuperacion"):
            self._render_etapa_recovery(container, etapa_stats)

        if campana_rows and len(campana_rows) > 1:
            self._render_campana_banco_recovery(container, campana_rows)

        tbl_card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                border_width=1, border_color=BORDER)
        tbl_card.pack(fill="x", padx=16, pady=(0, 16))

        tbl_hdr = ctk.CTkFrame(tbl_card, fg_color=ACCENT_LIGHT, corner_radius=0, height=38)
        tbl_hdr.pack(fill="x")
        tbl_hdr.pack_propagate(False)
        ctk.CTkLabel(tbl_hdr, text="Deuda por Sección",
                     font=font(FONT_SCALE['base'], "bold"), text_color=ACCENT
                     ).pack(side="left", padx=16, pady=8)

        self._render_table(tbl_card, sec_stats)

    def _render_pie(self, parent, res):
        pie_card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                                border_width=1, border_color=BORDER)
        pie_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(pie_card, text="Distribución por Estado",
                     font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=16, pady=(14, 10), anchor="w")

        pie_body = ctk.CTkFrame(pie_card, fg_color="transparent")
        pie_body.pack(padx=16, pady=(0, 16), fill="x")

        canvas = tk.Canvas(pie_body, width=220, height=220, bg=WHITE,
                           highlightthickness=0)
        canvas.pack(side="left", padx=(0, 20))

        slices = [
            (res["pendiente"], "#94A3B8", "Pendiente"),
            (res["visitado_habido"], "#22C55E", "Habido"),
            (res["visitado_no_habido"], "#F59E0B", "No Habido"),
            (res["fallecido_inubicable"], "#EF4444", "Inubicable"),
            (res.get("suplantacion", 0), "#E11D48", "Suplantación"),
            (res.get("pago_no_registrado", 0), "#3B82F6", "Pago No Reg."),
        ]
        total_pie = sum(s[0] for s in slices) or 1
        start = -90
        cx, cy, r = 110, 110, 95
        for val, color, _ in slices:
            if val == 0:
                continue
            extent = val / total_pie * 360
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                              start=start, extent=extent,
                              fill=color, outline=WHITE, width=2)
            start += extent

        canvas.create_oval(cx - 40, cy - 40, cx + 40, cy + 40,
                           fill=WHITE, outline=WHITE)
        canvas.create_text(cx, cy, text=f"{round((total_pie - res['pendiente'])/total_pie*100) if total_pie else 0}%",
                           font=(FONT_FAMILY, 14, "bold"), fill=TEXT_PRIMARY)

        legend = ctk.CTkFrame(pie_body, fg_color="transparent")
        legend.pack(side="left", anchor="n")
        for val, color, label in slices:
            row = ctk.CTkFrame(legend, fg_color="transparent")
            row.pack(fill="x", pady=4)
            dot = ctk.CTkFrame(row, fg_color=color, corner_radius=4,
                               width=14, height=14)
            dot.pack(side="left", padx=(0, 8))
            dot.pack_propagate(False)
            pct_s = round(val / total_pie * 100, 1) if total_pie else 0
            ctk.CTkLabel(row, text=f"{label}: {val}",
                         font=font(FONT_SCALE['base']), text_color=TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(row, text=f"  ({pct_s}%)",
                         font=font(FONT_SCALE['sm']), text_color=TEXT_MUTED).pack(side="left")

    def _render_bar(self, parent, sec_stats: list[dict]):
        bar_card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                                border_width=1, border_color=BORDER)
        bar_card.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(bar_card, text="Avance por Sección",
                     font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=16, pady=(14, 10), anchor="w")

        if not sec_stats:
            ctk.CTkLabel(bar_card, text="Sin datos de secciones",
                         font=font(FONT_SCALE['sm']), text_color=TEXT_MUTED).pack(pady=40)
            return

        num_secs = len(sec_stats)
        bar_h = max(220, num_secs * 38 + 40)
        bar_canvas = tk.Canvas(bar_card, width=440, height=bar_h, bg=WHITE,
                               highlightthickness=0)
        bar_canvas.pack(padx=16, pady=(0, 16), fill="x")

        self._container.after(10, lambda: self._draw_bars(bar_canvas, sec_stats))

    def _draw_bars(self, canvas, sec_stats):
        if not canvas.winfo_exists():
            return
        left_margin = 70
        bar_width_max = 250
        y = 12
        for ss in sec_stats:
            canvas.create_text(left_margin - 10, y + 13, anchor="e",
                               text=ss["id"][:8],
                               font=(FONT_FAMILY, 11, "bold"),
                               fill=TEXT_PRIMARY)
            canvas.create_rectangle(left_margin, y,
                                    left_margin + bar_width_max, y + 24,
                                    fill=BORDER, outline="", width=0)
            if ss["pct"] > 0:
                fill_color = SUCCESS if ss["pct"] >= 0.7 else ACCENT if ss["pct"] >= 0.4 else WARNING
                canvas.create_rectangle(
                    left_margin, y,
                    left_margin + int(bar_width_max * ss["pct"]), y + 24,
                    fill=fill_color, outline="", width=0)
            canvas.create_rectangle(left_margin, y,
                                    left_margin + bar_width_max, y + 24,
                                    outline="#E2E8F0", width=1)
            pct_rounded = round(ss["pct"] * 100)
            canvas.create_text(
                left_margin + bar_width_max + 10, y + 13, anchor="w",
                text=f"{ss['done']}/{ss['total']} — {pct_rounded}%",
                font=(FONT_FAMILY, 11), fill=TEXT_PRIMARY)
            y += 36

    def _render_table(self, card_frame, sec_stats: list[dict]):
        cols = ("seccion", "clientes", "deuda", "gestionados", "avance")
        style_name = apply_treeview_style("Stats.Treeview")

        tree_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        tree_frame.pack(fill="both", padx=8, pady=(0, 8))

        num_secs = len(sec_stats)
        tbl_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                style=style_name,
                                height=min(max(num_secs, 3), 15))

        col_specs = [
            ("seccion",     "Sección",        120, "center"),
            ("clientes",    "Clientes",        90,  "center"),
            ("deuda",       "Deuda Asignada",  180, "center"),
            ("gestionados", "Gestionados",     130, "center"),
            ("avance",      "Avance",          100, "center"),
        ]
        for c, h, w, anchor in col_specs:
            tbl_tree.heading(c, text=h)
            tbl_tree.column(c, width=w, minwidth=60, anchor=anchor)

        tbl_tree.tag_configure("high",   background="#ECFDF5", foreground="#065F46")
        tbl_tree.tag_configure("medium", background="#EFF6FF", foreground="#1E40AF")
        tbl_tree.tag_configure("low",    background="#FFFBEB", foreground="#92400E")
        tbl_tree.tag_configure("zero",   background="#F8FAFC", foreground=TEXT_SECONDARY)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tbl_tree.yview)
        tbl_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tbl_tree.pack(fill="both", expand=True)

        total_clients = sum(ss["total"] for ss in sec_stats)
        total_deuda = sum(ss["deuda"] for ss in sec_stats)
        total_done = sum(ss["done"] for ss in sec_stats)
        total_pct = total_done / total_clients if total_clients else 0

        rows = []
        for ss in sec_stats:
            pct_v = round(ss["pct"] * 100)
            tag = "high" if pct_v >= 70 else "medium" if pct_v >= 40 else "low" if pct_v > 0 else "zero"
            rows.append((
                ss["id"],
                ss["total"],
                f"S/ {ss['deuda']:,.2f}",
                f"{ss['done']}/{ss['total']}",
                f"{pct_v}%",
                tag,
            ))

        self._insert_batch(tbl_tree, rows, 0)

        tbl_tree.insert("", "end", values=(
            "TOTAL",
            total_clients,
            f"S/ {total_deuda:,.2f}",
            f"{total_done}/{total_clients}",
            f"{round(total_pct * 100)}%",
        ), tags=("high",))

    def _insert_batch(self, tree, rows, start):
        if not tree.winfo_exists():
            return
        end = min(start + _TREE_BATCH, len(rows))
        for i in range(start, end):
            row = rows[i]
            tag = row[-1] if len(row) > 5 else ""
            values = row[:-1] if len(row) > 5 else row
            tree.insert("", "end", values=values, tags=(tag,))
        if end < len(rows):
            self._container.after(1, lambda: self._insert_batch(tree, rows, end))

    def _render_etapa_recovery(self, parent, etapa_stats: dict):
        """Recuperación por etapa (E1/E2/E3) según ciclo por cuenta."""
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(
            card, text="Recuperación por Etapa (ciclo por cuenta)",
            font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=(0, 14))
        inner.grid_columnconfigure((0, 1, 2), weight=1)

        labels = {1: "Etapa 1 (días 1-10)", 2: "Etapa 2 (días 11-43)", 3: "Etapa 3 (días 44-59)"}
        por_etapa = etapa_stats.get("por_etapa_recuperacion", {})
        for col, etapa in enumerate((1, 2, 3)):
            data = por_etapa.get(etapa, {})
            asignada = float(data.get("asignada", 0) or 0)
            recuperada = float(data.get("recuperada", 0) or 0)
            cuentas = int(data.get("cuentas", 0) or 0)
            pct = round(recuperada / asignada * 100) if asignada else 0
            cell = ctk.CTkFrame(inner, fg_color=ACCENT_LIGHT, corner_radius=8)
            cell.grid(row=0, column=col, padx=6, sticky="nsew")
            ctk.CTkLabel(cell, text=labels[etapa], font=font(FONT_SCALE['xs']),
                         text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(cell, text=f"{pct}%", font=font(FONT_SCALE['2xl'], "bold"),
                         text_color=SUCCESS if pct >= 30 else WARNING).pack(anchor="w", padx=12)
            ctk.CTkLabel(
                cell,
                text=f"{cuentas} cuentas  ·  S/ {recuperada:,.0f} / {asignada:,.0f}",
                font=font(FONT_SCALE['xs']), text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=12, pady=(0, 10))

    def _render_campana_banco_recovery(self, parent, campana_rows: list[dict]):
        """Tabla comparativa de recuperación por número de campaña del banco."""
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            card, text="Recuperación por Nº Campaña (banco)",
            font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        cols = ("campana", "cuentas", "asignada", "recuperada", "pct")
        style_name = apply_treeview_style("StatsCampBanco.Treeview")
        tree_frame = ctk.CTkFrame(card, fg_color="transparent")
        tree_frame.pack(fill="x", padx=8, pady=(0, 12))

        tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", style=style_name,
            height=min(max(len(campana_rows), 2), 12),
        )
        for c, h, w in [
            ("campana", "Nº Campaña", 160),
            ("cuentas", "Cuentas", 80),
            ("asignada", "Deuda Asignada", 140),
            ("recuperada", "Recuperado", 140),
            ("pct", "% Recup.", 90),
        ]:
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")

        for row in campana_rows:
            pct = row.get("pct_recuperacion", 0)
            tag = "high" if pct >= 30 else "low"
            tree.insert("", "end", values=(
                row.get("label", ""),
                row.get("cuentas", 0),
                f"S/ {row.get('asignada', 0):,.2f}",
                f"S/ {row.get('recuperada', 0):,.2f}",
                f"{pct}%",
            ), tags=(tag,))
        tree.tag_configure("high", background="#ECFDF5")
        tree.tag_configure("low", background="#FFFBEB")
        tree.pack(fill="x")

    def _on_error(self, msg):
        container = self._container
        for w in container.winfo_children():
            w.destroy()
        card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=DANGER_LIGHT)
        card.pack(fill="x", padx=40, pady=40)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=32)
        ctk.CTkLabel(inner, text="⚠️", font=font(32)).pack()
        ctk.CTkLabel(inner, text="Error al cargar estadísticas",
                     font=font(FONT_SCALE['xl'], "bold"), text_color=DANGER).pack(pady=(8, 4))
        ctk.CTkLabel(inner, text=str(msg), font=font(FONT_SCALE['base']),
                     text_color=TEXT_SECONDARY, wraplength=500).pack()
