"""Call Center — panel visual de reparto y cartera por gestor telefónico."""
from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import TYPE_CHECKING, Any

from services.campana_banco_utils import apply_campana_banco_filter, filter_bar_visible
from ..theme import *
from ..components import SectionHeader, CampanaBancoFilterBar

if TYPE_CHECKING:
    from ..app import App

_STATUS_LABELS = {
    "pendiente": "Pendiente",
    "visitado_habido": "Habido",
    "visitado_no_habido": "No habido",
    "fallecido_inubicable": "Inubicable",
    "suplantacion": "Suplantación",
    "pago_no_registrado": "Pago N/R",
}


class CallCenterPage:
    """Dashboard de call center: reparto LPT, balance y cartera por gestor."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._gestores: list[dict] = []
        self._call_gestores: list[dict] = []
        self._dashboard: dict[str, Any] = {}
        self._selected_uid: str | None = None
        self._tree: ttk.Treeview | None = None
        self._client_rows: dict[str, dict] = {}
        self._preview_frame: ctk.CTkFrame | None = None
        self._gestor_cards_frame: ctk.CTkFrame | None = None
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._detail_title: ctk.CTkLabel | None = None
        self._campana_banco_filter: str | None = None
        self._campana_options: list[str] = []

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container
        self._selected_uid = None
        self._client_rows = {}

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="📞 Call Center",
            font=font(FONT_SCALE["xl"], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            hdr,
            text=(
                "Reparto equitativo tramo 1 (LPT por monto) · "
                "visualice la cartera de cada operador telefónico"
            ),
            font=font(FONT_SCALE["sm"]), text_color=TEXT_SECONDARY, wraplength=720, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        if not self.app.active_campaign:
            self._empty_card(
                "📂  Sin campaña activa",
                "Cargue un Excel y active una campaña para gestionar el call center.",
            )
            return

        self._campana_options = (
            self.app.campaign_mgr.distinct_campana_banco_for_campaign(
                self.app.active_campaign.id
            )
        )
        if filter_bar_visible(self._campana_options):
            filter_row = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=10,
                                      border_width=1, border_color=BORDER)
            filter_row.pack(fill="x", padx=16, pady=(0, 8))
            inner_f = ctk.CTkFrame(filter_row, fg_color="transparent")
            inner_f.pack(fill="x", padx=14, pady=8)
            CampanaBancoFilterBar(
                inner_f,
                available=self._campana_options,
                selected=self._campana_banco_filter,
                on_change=self._on_campana_filter_change,
            ).pack(fill="x")
            ctk.CTkLabel(
                inner_f,
                text="El reparto masivo incluye toda la campaña; el filtro solo afecta la visualización.",
                font=font(FONT_SCALE["xs"]),
                text_color=TEXT_MUTED,
            ).pack(anchor="w", pady=(6, 0))

        self._build_kpi_strip(container)
        self._build_actions(container)
        # Solo se empaqueta al mostrar vista previa (evita hueco vertical).
        self._preview_frame = ctk.CTkFrame(container, fg_color="transparent", height=0)

        charts = ctk.CTkFrame(container, fg_color="transparent", height=0)
        charts.pack(fill="x", padx=16, pady=(4, 12))
        charts.grid_columnconfigure((0, 1), weight=1)
        self._chart_cuentas = ctk.CTkFrame(
            charts, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER,
            height=0,
        )
        self._chart_cuentas.grid(row=0, column=0, sticky="new", padx=(0, 6))
        self._chart_monto = ctk.CTkFrame(
            charts, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER,
            height=0,
        )
        self._chart_monto.grid(row=0, column=1, sticky="new", padx=(6, 0))

        self._gestor_cards_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._gestor_cards_frame.pack(fill="x", padx=16, pady=(0, 12))

        self._build_client_table(container)
        self._build_history_panel(container)
        self._load_data()

    def _on_campana_filter_change(self, filtro: str | None):
        self._campana_banco_filter = filtro
        if self._dashboard:
            self._render_filtered_kpis()
            if self._selected_uid:
                self._load_gestor_clients(self._selected_uid)

    def _render_filtered_kpis(self):
        """Recalcula KPIs visibles cuando hay filtro campana_banco activo."""
        if self._campana_banco_filter is None:
            self._render_kpis(self._dashboard)
            self._render_charts(
                self._dashboard.get("gestores", []), self._dashboard
            )
            return
        camp_id = self.app.active_campaign.id
        clients = self.app.campaign_mgr.get_all_clients(camp_id)
        clients = apply_campana_banco_filter(clients, self._campana_banco_filter)
        call_clients = [
            c for c in clients
            if c.get("fase_gestion") == "call"
            and int(c.get("tramo_actual") or 0) == 1
            and c.get("activo_en_cartera", True)
        ]
        total = len(call_clients)
        pendientes = sum(
            1 for c in call_clients if c.get("estado_gestion", "pendiente") == "pendiente"
        )
        monto = sum(float(c.get("importe_deuda_pendiente") or 0) for c in call_clients)
        gestionados = total - pendientes
        filtered_d = {
            **self._dashboard,
            "total_tramo1_call": total,
            "sin_asignar": sum(1 for c in call_clients if not c.get("call_gestor_uid")),
            "monto_total_call": monto,
            "pendientes_global": pendientes,
            "pct_avance_global": round(gestionados / total * 100, 1) if total else 0.0,
        }
        self._render_kpis(filtered_d)
        gestores_filtered = []
        for g in self._dashboard.get("gestores", []):
            uid = g.get("uid", "")
            g_clients = [
                c for c in call_clients if c.get("call_gestor_uid") == uid
            ]
            gestores_filtered.append({
                **g,
                "num_cuentas": len(g_clients),
                "monto_total": sum(
                    float(c.get("importe_deuda_pendiente") or 0) for c in g_clients
                ),
            })
        self._render_charts(gestores_filtered, filtered_d)

    def _empty_card(self, title: str, message: str):
        card = ctk.CTkFrame(self._container, fg_color=CARD_BG, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=16, pady=20)
        ctk.CTkLabel(card, text=title, font=font(FONT_SCALE["base"], "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(20, 4))
        ctk.CTkLabel(card, text=message, font=font(FONT_SCALE["sm"]),
                     text_color=TEXT_SECONDARY).pack(pady=(0, 20))

    def _build_kpi_strip(self, parent):
        outer = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                             border_width=1, border_color=BORDER)
        outer.pack(fill="x", padx=16, pady=(0, 12))
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        inner.grid_columnconfigure(tuple(range(6)), weight=1)
        self._kpi_labels = {}
        defs = [
            ("total", "Cuentas E1 call", "📋", ACCENT),
            ("sin_asignar", "Sin asignar", "⏳", WARNING),
            ("monto", "Monto cartera", "💰", INFO),
            ("pendientes", "Pendientes", "📞", TEXT_SECONDARY),
            ("avance", "Avance global", "✅", SUCCESS),
            ("desv", "Desv. monto", "⚖", DANGER),
        ]
        for i, (key, lbl, icon, clr) in enumerate(defs):
            cell = ctk.CTkFrame(inner, fg_color="transparent")
            cell.grid(row=0, column=i, padx=6, sticky="w")
            ctk.CTkLabel(cell, text=f"{icon} {lbl}", font=font(FONT_SCALE["xs"]),
                         text_color=TEXT_MUTED).pack(anchor="w")
            val = ctk.CTkLabel(cell, text="—", font=font(FONT_SCALE["xl"], "bold"), text_color=clr)
            val.pack(anchor="w", pady=(2, 0))
            self._kpi_labels[key] = val

    def _build_actions(self, parent):
        row = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=10,
                           border_width=1, border_color=BORDER)
        row.pack(fill="x", padx=16, pady=(0, 12))
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            inner,
            text="Algoritmo LPT: las cuentas de mayor deuda van al gestor con menor monto acumulado.",
            font=font(FONT_SCALE["xs"]), text_color=TEXT_MUTED, wraplength=600, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self._btn_preview = ctk.CTkButton(
            btn_row, text="👁 Vista previa", font=font(FONT_SCALE["sm"]),
            fg_color=INFO, hover_color="#2563EB", height=34, width=130, corner_radius=8,
            command=lambda: self._run_preview(self._btn_preview),
        )
        self._btn_preview.pack(side="left", padx=(0, 8))

        self._btn_dist = ctk.CTkButton(
            btn_row, text="📞 Repartir nuevas", font=font(FONT_SCALE["sm"], "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER, height=34, width=150, corner_radius=8,
            command=lambda: self._run_distribute(self._btn_dist, rebalance=False),
        )
        self._btn_dist.pack(side="left", padx=(0, 8))

        self._btn_rebal = ctk.CTkButton(
            btn_row, text="⚖ Re-equilibrar todo", font=font(FONT_SCALE["sm"]),
            fg_color=WARNING, hover_color="#D97706", height=34, width=150, corner_radius=8,
            command=lambda: self._run_distribute(self._btn_rebal, rebalance=True),
        )
        self._btn_rebal.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="🔄 Actualizar", font=font(FONT_SCALE["sm"]),
            fg_color="transparent", text_color=TEXT_SECONDARY, hover_color=ACCENT_LIGHT,
            border_width=1, border_color=BORDER, height=34, width=110, corner_radius=8,
            command=self._load_data,
        ).pack(side="right")

    def _build_client_table(self, parent):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color=ACCENT_LIGHT, corner_radius=0, height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=16, pady=8)
        self._detail_title = ctk.CTkLabel(
            hdr_inner, text="Cartera del gestor — seleccione una tarjeta arriba",
            font=font(FONT_SCALE["base"], "bold"), text_color=ACCENT,
        )
        self._detail_title.pack(side="left")

        self._reassign_var = ctk.StringVar(value="")
        self._reassign_menu = ctk.CTkOptionMenu(
            hdr_inner, variable=self._reassign_var, values=["—"],
            width=180, height=28, font=font(FONT_SCALE["xs"]),
            command=self._on_reassign_selected,
        )
        self._reassign_menu.pack(side="right", padx=(8, 0))
        ctk.CTkLabel(hdr_inner, text="Reasignar a:", font=font(FONT_SCALE["xs"]),
                     text_color=TEXT_SECONDARY).pack(side="right")

        tree_frame = ctk.CTkFrame(card, fg_color="transparent")
        tree_frame.pack(fill="x", padx=8, pady=(0, 12))

        cols = ("codigo", "nombre", "dni", "telefono", "distrito", "estado", "deuda", "promesa")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=8)
        headings = {
            "codigo": ("Código", 90),
            "nombre": ("Cliente", 180),
            "dni": ("DNI", 90),
            "telefono": ("Teléfono", 100),
            "distrito": ("Distrito", 100),
            "estado": ("Estado", 100),
            "deuda": ("Deuda pend.", 95),
            "promesa": ("Promesa", 90),
        }
        for col, (text, width) in headings.items():
            self._tree.heading(col, text=text)
            self._tree.column(col, width=width, minwidth=60)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="x", expand=True)
        scroll.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _load_data(self):
        def work():
            try:
                gestores = []
                if self.app.firebase_connected:
                    gestores = self.app.firebase.list_gestor_users()
                dashboard = self.app.campaign_mgr.get_call_center_dashboard(
                    gestores_firestore=gestores,
                )
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: self._on_data_loaded(gestores, dashboard),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: messagebox.showerror("Call Center", str(e)),
                    )

        threading.Thread(target=work, daemon=True).start()

    def _on_data_loaded(self, gestores: list[dict], dashboard: dict):
        self._gestores = gestores
        self._call_gestores = [
            g for g in gestores
            if g.get("rol") == "gestor" and g.get("canal") == "call" and g.get("activo", True)
        ]
        self._dashboard = dashboard
        self._render_filtered_kpis()
        self._render_gestor_cards(dashboard.get("gestores", []))
        self._update_reassign_menu()
        self._refresh_history()

        if self._selected_uid:
            self._load_gestor_clients(self._selected_uid)
        elif self._call_gestores:
            first = self._call_gestores[0].get("uid") or self._call_gestores[0].get("id", "")
            if first:
                self._select_gestor(first)

    def _render_kpis(self, d: dict):
        self._kpi_labels["total"].configure(text=str(d.get("total_tramo1_call", 0)))
        self._kpi_labels["sin_asignar"].configure(text=str(d.get("sin_asignar", 0)))
        self._kpi_labels["monto"].configure(
            text=f"S/ {float(d.get('monto_total_call', 0)):,.0f}",
        )
        self._kpi_labels["pendientes"].configure(text=str(d.get("pendientes_global", 0)))
        self._kpi_labels["avance"].configure(
            text=f"{float(d.get('pct_avance_global', 0)):.0f}%",
        )
        self._kpi_labels["desv"].configure(
            text=f"S/ {float(d.get('desviacion_monto', 0)):,.0f}",
        )

    def _render_charts(self, gestores: list[dict], dashboard: dict):
        for frame, title, key, fmt in (
            (self._chart_cuentas, "Cuentas por gestor", "num_cuentas", "{}"),
            (self._chart_monto, "Monto pendiente por gestor", "monto_total", "S/ {:,.0f}"),
        ):
            for w in frame.winfo_children():
                w.destroy()
            ctk.CTkLabel(frame, text=title, font=font(FONT_SCALE["base"], "bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="w", padx=16, pady=(14, 8))
            body = ctk.CTkFrame(frame, fg_color="transparent")
            body.pack(fill="x", padx=16, pady=(0, 16))
            if not gestores:
                ctk.CTkLabel(body, text="Sin datos de reparto", font=font(FONT_SCALE["sm"]),
                             text_color=TEXT_MUTED).pack(pady=12)
                continue
            max_val = max(float(g.get(key, 0) or 0) for g in gestores) or 1.0
            colors = [ACCENT, SUCCESS, INFO, WARNING, "#8B5CF6", "#EC4899"]
            for i, g in enumerate(gestores):
                val = float(g.get(key, 0) or 0)
                nombre = (g.get("nombre") or "?")[:22]
                row = ctk.CTkFrame(body, fg_color="transparent")
                row.pack(fill="x", pady=3)
                ctk.CTkLabel(row, text=nombre, font=font(FONT_SCALE["xs"]),
                             text_color=TEXT_SECONDARY, width=120, anchor="w").pack(side="left")
                bar_bg = ctk.CTkFrame(row, fg_color=BORDER, corner_radius=4, height=18)
                bar_bg.pack(side="left", fill="x", expand=True, padx=(6, 6))
                bar_bg.pack_propagate(False)
                pct = val / max_val if max_val else 0
                if pct > 0:
                    bar_fill = ctk.CTkFrame(
                        bar_bg, fg_color=colors[i % len(colors)], corner_radius=4, height=18,
                    )
                    bar_fill.place(relx=0, rely=0, relwidth=max(pct, 0.02), relheight=1)
                ctk.CTkLabel(
                    row, text=fmt.format(val), font=font(FONT_SCALE["xs"], "bold"),
                    text_color=TEXT_PRIMARY, width=80, anchor="e",
                ).pack(side="right")

    def _render_gestor_cards(self, gestores: list[dict]):
        if not self._gestor_cards_frame:
            return
        for w in self._gestor_cards_frame.winfo_children():
            w.destroy()

        if not self._call_gestores:
            ctk.CTkLabel(
                self._gestor_cards_frame,
                text="No hay gestores de call. Créelos en Equipo → Usuarios (tipo «call»).",
                font=font(FONT_SCALE["sm"]), text_color=TEXT_MUTED,
            ).pack(pady=16)
            return

        ctk.CTkLabel(
            self._gestor_cards_frame, text="Gestores de call — toque para ver cartera",
            font=font(FONT_SCALE["sm"], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(self._gestor_cards_frame, fg_color="transparent")
        grid.pack(fill="x")
        cols = 3
        for i in range(cols):
            grid.grid_columnconfigure(i, weight=1)

        gestor_map = {g.get("uid", g.get("id", "")): g for g in gestores}
        for idx, g in enumerate(self._call_gestores):
            uid = g.get("uid") or g.get("id", "")
            stats = gestor_map.get(uid, {})
            self._gestor_card(grid, idx % cols, idx // cols, uid, g, stats)

    def _gestor_card(self, parent, col, row, uid: str, gestor: dict, stats: dict):
        selected = uid == self._selected_uid
        card = ctk.CTkFrame(
            parent,
            fg_color=ACCENT_LIGHT if selected else CARD_BG,
            corner_radius=10,
            border_width=2 if selected else 1,
            border_color=ACCENT if selected else BORDER,
        )
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        nombre = gestor.get("nombre") or gestor.get("email") or uid
        ctk.CTkLabel(inner, text=nombre, font=font(FONT_SCALE["base"], "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")

        num = int(stats.get("num_cuentas", 0))
        monto = float(stats.get("monto_total", 0))
        pend = int(stats.get("pendientes", 0))
        prom = int(stats.get("promesas", 0))
        pct = float(stats.get("pct_avance", stats.get("gestionados", 0) / num * 100 if num else 0))

        ctk.CTkLabel(
            inner,
            text=f"{num} cuentas  ·  S/ {monto:,.0f}",
            font=font(FONT_SCALE["sm"]), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(
            inner,
            text=f"Pend: {pend}  ·  Promesas: {prom}  ·  Avance: {pct:.0f}%",
            font=font(FONT_SCALE["xs"]), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 8))

        pb = ctk.CTkProgressBar(inner, height=8, progress_color=SUCCESS, fg_color=BORDER)
        pb.pack(fill="x")
        pb.set(min(pct / 100, 1.0))

        for w in (card, inner):
            w.bind("<Button-1>", lambda _e, u=uid: self._select_gestor(u))
            w.configure(cursor="hand2")

    def _select_gestor(self, uid: str):
        self._selected_uid = uid
        self._render_gestor_cards(self._dashboard.get("gestores", []))
        self._load_gestor_clients(uid)

    def _load_gestor_clients(self, uid: str):
        nombre = next(
            (g.get("nombre", uid) for g in self._call_gestores
             if (g.get("uid") or g.get("id")) == uid),
            uid,
        )
        if self._detail_title:
            self._detail_title.configure(text=f"Cartera de {nombre}")

        def work():
            try:
                clients = self.app.campaign_mgr.get_call_gestor_clients(uid)
                clients = apply_campana_banco_filter(
                    clients, self._campana_banco_filter
                )
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._fill_tree(clients))
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _fill_tree(self, clients: list[dict]):
        if not self._tree:
            return
        self._client_rows.clear()
        for item in self._tree.get_children():
            self._tree.delete(item)
        for c in clients:
            prom = ""
            if c.get("monto_promesa_pago", 0) > 0:
                prom = f"S/ {c['monto_promesa_pago']:,.0f}"
            elif c.get("fecha_promesa_pago"):
                prom = c["fecha_promesa_pago"]
            iid = str(c["id"])
            self._client_rows[iid] = c
            self._tree.insert("", "end", iid=iid, values=(
                c.get("codigo_cliente", ""),
                (c.get("nombre") or "")[:40],
                c.get("dni", ""),
                c.get("telefono", ""),
                c.get("distrito", ""),
                _STATUS_LABELS.get(c.get("estado_gestion", ""), c.get("estado_gestion", "")),
                f"S/ {float(c.get('importe_deuda_pendiente', 0)):,.2f}",
                prom,
            ))

    def _update_reassign_menu(self):
        names = [
            f"{g.get('nombre', g.get('email', '?'))}|{g.get('uid') or g.get('id', '')}"
            for g in self._call_gestores
        ]
        if not names:
            names = ["—"]
        self._reassign_menu.configure(values=names)
        if names:
            self._reassign_var.set(names[0])

    def _on_tree_select(self, _event=None):
        pass

    def _on_reassign_selected(self, choice: str):
        if not self._tree or "|" not in choice:
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Reasignar", "Seleccione un cliente en la tabla.")
            return
        cliente_id = int(sel[0])
        cliente = self._client_rows.get(sel[0], {})
        nombre_cli = cliente.get("nombre") or cliente.get("codigo_cliente", "")
        _, new_uid = choice.rsplit("|", 1)
        new_nombre = choice.rsplit("|", 1)[0]
        if not messagebox.askyesno(
            "Confirmar reasignación",
            f"¿Mover «{nombre_cli}» al gestor {new_nombre}?",
        ):
            return

        def work():
            admin = self.app._created_by_info()
            ok, msg, _change = self.app.campaign_mgr.reassign_call_client(
                cliente_id, new_uid, new_nombre,
                firebase_service=self.app.firebase if self.app.firebase_connected else None,
                auto_publish=self.app.firebase_connected,
                admin_uid=admin.get("uid", ""),
                admin_nombre=admin.get("nombre", ""),
            )
            if self._container and self._container.winfo_exists():
                self._container.after(
                    0,
                    lambda: (
                        messagebox.showinfo("Call Center", msg) if ok
                        else messagebox.showerror("Error", msg),
                        self._load_data() if ok else None,
                        self._refresh_history() if ok else None,
                    ),
                )

        threading.Thread(target=work, daemon=True).start()

    def _run_preview(self, btn):
        btn.configure(state="disabled", text="Calculando…")

        def work():
            try:
                result = self.app.campaign_mgr.preview_call_center_distribution(
                    gestores_firestore=self._gestores,
                )
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._show_preview(btn, result))
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: (
                        btn.configure(state="normal", text="👁 Vista previa"),
                        messagebox.showerror("Error", str(e)),
                    ))

        threading.Thread(target=work, daemon=True).start()

    def _clear_preview(self):
        if not self._preview_frame:
            return
        for w in self._preview_frame.winfo_children():
            w.destroy()
        self._preview_frame.pack_forget()

    def _show_preview(self, btn, result):
        btn.configure(state="normal", text="👁 Vista previa")
        if not self._preview_frame:
            return
        self._clear_preview()
        if result.errores:
            messagebox.showwarning("Call Center", "\n".join(result.errores))
            return

        self._preview_frame.pack(fill="x", padx=16, pady=(0, 8))
        card = ctk.CTkFrame(
            self._preview_frame, fg_color=ACCENT_LIGHT,
            corner_radius=10, border_width=1, border_color=INFO,
        )
        card.pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            inner, text="Vista previa del reparto",
            font=font(FONT_SCALE["sm"], "bold"), text_color=INFO,
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text=(
                f"Asignaría {result.cuentas_asignadas} cuentas "
                f"(S/ {result.monto_asignado:,.2f}) · "
                f"Desviación estimada: S/ {result.desviacion_monto:,.2f}"
            ),
            font=font(FONT_SCALE["xs"]), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 8))

        for g in result.gestores:
            extra = ""
            if g.nuevas_asignadas:
                extra = f"  (+{g.nuevas_asignadas} nuevas)"
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=f"· {g.nombre}: {g.num_cuentas} cuentas, S/ {g.monto_total:,.2f}{extra}",
                font=font(FONT_SCALE["xs"]), text_color=TEXT_PRIMARY,
            ).pack(anchor="w")

    def _run_distribute(self, btn, *, rebalance: bool):
        action = "re-equilibrar todas las cuentas" if rebalance else "repartir las cuentas sin asignar"
        if not messagebox.askyesno("Confirmar", f"¿Desea {action} entre gestores de call?"):
            return
        label = btn.cget("text")
        btn.configure(state="disabled", text="Procesando…")

        def work():
            try:
                admin = self.app._created_by_info()
                result = self.app.campaign_mgr.distribute_call_center(
                    gestores_firestore=self._gestores,
                    rebalance_all=rebalance,
                    firebase_service=self.app.firebase if self.app.firebase_connected else None,
                    auto_publish=self.app.firebase_connected,
                    admin_uid=admin.get("uid", ""),
                    admin_nombre=admin.get("nombre", ""),
                )
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: self._on_distributed(btn, label, result),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: (
                        btn.configure(state="normal", text=label),
                        messagebox.showerror("Error", str(e)),
                    ))

        threading.Thread(target=work, daemon=True).start()

    def _on_distributed(self, btn, label, result):
        btn.configure(state="normal", text=label)
        if result.errores:
            messagebox.showwarning("Call Center", "\n".join(result.errores))
            return

        lines = [
            f"Asignadas {result.cuentas_asignadas} cuentas "
            f"(S/ {result.monto_asignado:,.2f}).",
            f"Motivo: {result.motivo}",
        ]
        pub = result.firebase_publish or {}
        if self.app.firebase_connected:
            if pub.get("success"):
                lines.append(
                    f"✅ Publicado en Firebase: {pub.get('uploaded', 0)} clientes subidos, "
                    f"{pub.get('moved', 0)} movidos, "
                    f"{pub.get('notifications', 0)} notificaciones enviadas."
                )
            elif result.cambios:
                err = "; ".join(pub.get("errors") or []) or "Error desconocido"
                lines.append(f"⚠️ Reparto local OK pero Firebase falló: {err}")
        else:
            lines.append("⚠️ Firebase no conectado — reparto solo guardado localmente.")

        messagebox.showinfo("Call Center", "\n".join(lines))
        self._load_data()
        self._refresh_history()

    def _build_history_panel(self, parent):
        self._history_frame = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self._history_frame.pack(fill="x", padx=16, pady=(0, 16))
        hdr = ctk.CTkFrame(self._history_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            hdr, text="📜 Historial de repartos",
            font=font(FONT_SCALE["base"], "bold"), text_color=TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="Ver detalle", width=90, height=28, corner_radius=6,
            font=font(FONT_SCALE["xs"]),
            command=self._show_history_detail,
        ).pack(side="right")
        self._history_list = ctk.CTkFrame(self._history_frame, fg_color="transparent")
        self._history_list.pack(fill="x", padx=14, pady=(0, 12))
        self._history_rows: list[dict] = []

    def _refresh_history(self):
        if not getattr(self, "_history_list", None):
            return
        for w in self._history_list.winfo_children():
            w.destroy()
        try:
            self._history_rows = self.app.campaign_mgr.get_call_distribution_history()
        except Exception:
            self._history_rows = []
        if not self._history_rows:
            ctk.CTkLabel(
                self._history_list,
                text="Aún no hay repartos registrados.",
                font=font(FONT_SCALE["xs"]), text_color=TEXT_MUTED,
            ).pack(anchor="w")
            return
        for row in self._history_rows[:8]:
            fecha = (row.get("fecha") or "")[:16].replace("T", " ")
            fb = "✅ Firebase" if row.get("firebase_ok") else "⚠️ Solo local"
            tipo_lbl = {
                "reparto_inicial": "Reparto inicial",
                "reequilibrio": "Re-equilibrio",
                "reasignacion_manual": "Reasignación",
            }.get(row.get("tipo", ""), row.get("tipo", ""))
            line = ctk.CTkFrame(self._history_list, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(
                line,
                text=(
                    f"{fecha} · {tipo_lbl} · {row.get('cuentas_afectadas', 0)} cuentas · "
                    f"S/ {float(row.get('monto_afectado', 0)):,.2f} · {fb}"
                ),
                font=font(FONT_SCALE["xs"]), text_color=TEXT_SECONDARY, anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                line,
                text=row.get("motivo", ""),
                font=font(FONT_SCALE["xs"]), text_color=TEXT_MUTED, anchor="w",
            ).pack(anchor="w")

    def _show_history_detail(self):
        if not self._history_rows:
            messagebox.showinfo("Historial", "No hay repartos registrados.")
            return
        lines = []
        for row in self._history_rows[:5]:
            lines.append(f"── {row.get('fecha', '')[:16]} ──")
            lines.append(f"  {row.get('motivo', '')}")
            lines.append(
                f"  {row.get('cuentas_afectadas', 0)} cuentas · "
                f"S/ {float(row.get('monto_afectado', 0)):,.2f} · "
                f"{'OK Firebase' if row.get('firebase_ok') else 'Sin Firebase'}"
            )
            detalle = row.get("detalle") or {}
            for ch in (detalle.get("cambios") or [])[:15]:
                lines.append(
                    f"    · {ch.get('codigo_cliente')}: "
                    f"{ch.get('gestor_anterior_nombre') or '—'} → "
                    f"{ch.get('gestor_nuevo_nombre')} — {ch.get('razon', '')}"
                )
            lines.append("")
        messagebox.showinfo("Detalle de repartos", "\n".join(lines))
