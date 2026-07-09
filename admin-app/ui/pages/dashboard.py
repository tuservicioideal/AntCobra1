"""Dashboard / Welcome page — hosts Inicio, Campaña, Monitor, Estadísticas as tabs."""
from __future__ import annotations
import customtkinter as ctk
from typing import TYPE_CHECKING
from ..theme import *
from ..components import (
    KPICard, SmoothScrollableFrame, CampanaBancoFilterBar, CampaignTimelineCard,
)
from services.campana_banco_utils import filter_bar_visible, filter_label

if TYPE_CHECKING:
    from ..app import App

# Tab label → page key mapping (None = rendered directly by DashboardPage)
_TABS: list[tuple[str, str | None]] = [
    ("Inicio",       None),
    ("Campaña",      "campaign"),
    ("Monitor",      "monitor"),
    ("Estadísticas", "stats"),
]

_TAB_FEATURES = {
    "Campaña":      "load_excel",
    "Monitor":      "monitor",
    "Estadísticas": "stats",
}


class DashboardPage:
    """Main hub page — renders Inicio, Campaña, Monitor and Estadísticas as tabs."""

    def __init__(self, app: "App"):
        self.app = app
        self._tabview = None
        self._tab_scrolls: dict = {}
        self._sub_pages: dict = {}
        self._current_tab: str = "Inicio"
        self._campana_banco_filter: str | None = None

    # ── Render ───────────────────────────────────────────────
    def render(self, container):
        for w in container.winfo_children():
            w.destroy()

        self._tabview = None
        self._tab_scrolls = {}
        self._sub_pages = {}

        tabview = ctk.CTkTabview(
            container,
            fg_color=BG,
            segmented_button_fg_color=SIDEBAR_BG,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=SIDEBAR_BG,
            segmented_button_unselected_hover_color=SIDEBAR_HOVER,
            text_color=WHITE,
            corner_radius=8,
        )
        tabview.pack(fill="both", expand=True, padx=0, pady=0)
        self._tabview = tabview
        self._fit_tabview_height_once()

        visible_tabs: list = []
        for tab_label, page_key in _TABS:
            feature = _TAB_FEATURES.get(tab_label)
            if feature and not self.app._role_allows(feature):
                continue
            tabview.add(tab_label)
            visible_tabs.append(tab_label)

            tab_frame = tabview.tab(tab_label)
            tab_frame.grid_rowconfigure(0, weight=1)
            tab_frame.grid_columnconfigure(0, weight=1)

            scroll = SmoothScrollableFrame(tab_frame)
            scroll.grid(row=0, column=0, sticky="nsew")
            self._tab_scrolls[tab_label] = scroll

        initial_tab = "Inicio"
        if self.app._pending_tab and self.app._pending_tab in visible_tabs:
            initial_tab = self.app._pending_tab
        self.app._pending_tab = None

        self._current_tab = initial_tab
        tabview.set(initial_tab)
        self._render_tab(initial_tab)

        # Attach callback AFTER initial render to avoid double-render
        tabview.configure(command=self._on_tab_changed)

    def _fit_tabview_height_once(self):
        """Set tabview height to fill the content area so only the inner tab scrolls."""
        if not self._tabview or not self._tabview.winfo_exists():
            return

        self.app._content.update_idletasks()
        content_h = 0
        try:
            content_h = int(self.app._content.winfo_height())
        except Exception:
            content_h = 0

        if content_h <= 1:
            content_h = max(700, int(self.app.winfo_height()) - 160)

        # Match inner tab viewport to the visible content area (one-shot; no Configure loop).
        target_h = max(680, content_h)
        self._tabview.configure(height=target_h)

    # ── Tab lifecycle ─────────────────────────────────────────
    def _on_tab_changed(self, value: str = ""):
        new_tab = self._tabview.get() if self._tabview else value
        if new_tab == self._current_tab:
            return
        if self._current_tab == "Monitor":
            mon = self._sub_pages.get("monitor")
            if mon and hasattr(mon, "stop"):
                mon.stop()
        self._current_tab = new_tab
        self._render_tab(new_tab)

    def _render_tab(self, tab_label: str):
        scroll = self._tab_scrolls.get(tab_label)
        if scroll is None:
            return
        if hasattr(scroll, "scroll_to_top"):
            scroll.scroll_to_top()
        if tab_label == "Inicio":
            self._render_inicio(scroll)
        else:
            key_map = {
                "Campaña":      "campaign",
                "Monitor":      "monitor",
                "Estadísticas": "stats",
            }
            key = key_map.get(tab_label)
            if key:
                self._get_sub_page(key).render(scroll)

    def _get_sub_page(self, key: str):
        if key not in self._sub_pages:
            self._sub_pages[key] = self._create_sub_page(key)
        return self._sub_pages[key]

    def _create_sub_page(self, key: str):
        from .campaign import CampaignPage
        from .monitor import MonitorPage
        from .stats import StatsPage
        mapping = {
            "campaign": CampaignPage,
            "monitor":  MonitorPage,
            "stats":    StatsPage,
        }
        return mapping[key](self.app)

    def stop(self):
        """Called when navigating away from Inicio — stop all sub-page timers."""
        for page in self._sub_pages.values():
            if hasattr(page, "stop"):
                page.stop()

    # ── Inicio tab content ──────────────────────────────────────
    def _render_inicio(self, container):
        for w in container.winfo_children():
            w.destroy()
        if self.app.active_campaign:
            self._render_overview(container)
        else:
            self._render_welcome(container)

    def _render_welcome(self, container):
        ctk.CTkFrame(container, fg_color="transparent", height=60).pack()

        card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=60)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=CARD_PADDING * 2, pady=CARD_PADDING * 2)

        ctk.CTkLabel(content, text="🚀 Bienvenido a Reacudo Legal",
                     font=font(FONT_SCALE['3xl'], "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w")
        ctk.CTkLabel(content, text="Sistema integral de gestión de cobranzas con IA avanzada",
                     font=font(FONT_SCALE['lg']), text_color=TEXT_SECONDARY
                     ).pack(anchor="w", pady=(8, 32))

        steps = [
            ("1", "📊 Cargar archivo Excel",
             "Importe la cartera del banco desde la pestaña Campaña"),
            ("2", "🔗 Firebase se conecta automáticamente",
             "La conexión se establece al iniciar sesión"),
            ("3", "👥 Distribuir a gestores",
             "Envíe los clientes a Firebase para los gestores de campo"),
            ("4", "⚡ Evaluar tramos",
             "Avance el ciclo de cobranza de 60 días automáticamente"),
        ]
        for num, title, desc in steps:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=8)

            badge = ctk.CTkFrame(row, fg_color=ACCENT_LIGHT, corner_radius=12,
                                 width=40, height=40)
            badge.pack(side="left", padx=(0, 16))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=num, font=font(FONT_SCALE['lg'], "bold"),
                         text_color=ACCENT).place(relx=0.5, rely=0.5, anchor="center")

            text_f = ctk.CTkFrame(row, fg_color="transparent")
            text_f.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text_f, text=title, font=font(FONT_SCALE['lg'], "bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(text_f, text=desc, font=font(FONT_SCALE['base']),
                         text_color=TEXT_SECONDARY).pack(anchor="w")

    def _render_overview(self, container):
        camp = self.app.active_campaign
        if not camp:
            return

        from services.tramo_engine import TramoEngine
        from services.database import TramoEnum

        campana_id = camp.id

        # ── Header: title + asistente ──
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))
        header.grid_columnconfigure(0, weight=1)

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_col, text="📊 Panel de Control",
            font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        subtitle = f"Cartera: {camp.nombre}"
        if self._campana_banco_filter is not None:
            subtitle += f"  ·  Filtrando: {filter_label(self._campana_banco_filter)}"
        ctk.CTkLabel(
            title_col, text=subtitle,
            font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            header,
            text="🚀 Abrir asistente de publicación",
            font=font(FONT_SCALE["sm"], "bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            height=36,
            width=260,
            corner_radius=10,
            command=self._open_wizard,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        # ── Two columns: estado + actualización Excel ──
        top_row = ctk.CTkFrame(container, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(0, 16))
        show_excel = self.app.firebase_connected and self.app._role_allows("upload")
        if show_excel:
            top_row.grid_columnconfigure((0, 1), weight=1, uniform="top")
        else:
            top_row.grid_columnconfigure(0, weight=1)

        self._render_operational_status(top_row, grid_column=0)
        if show_excel:
            self._render_excel_update_card(top_row, camp, grid_column=1)

        # ── KPIs ──
        try:
            kpis_data = self.app.campaign_mgr.get_filtered_campaign_kpis(
                campana_id, self._campana_banco_filter
            )
            dia = kpis_data["dia"]
            total = kpis_data["total"]
            deuda = kpis_data["deuda"]
            secciones = kpis_data["secciones"]
            restantes = kpis_data["restantes"]
            duracion = kpis_data["duracion"]
            tramo = TramoEngine.get_tramo_for_day(dia)
        except Exception:
            dia, total, deuda, secciones, restantes = 1, 0, 0, 0, 60
            tramo = TramoEnum.NONE
            duracion = 60

        kpi_row = ctk.CTkFrame(container, fg_color="transparent")
        kpi_row.pack(fill="x", padx=16, pady=(0, 16))
        kpi_row.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        kpis = [
            ("👥 Clientes",      str(total),          ACCENT),
            ("📍 Secciones",     str(secciones),      SUCCESS),
            ("📅 Día Actual", f"{dia} / {duracion}", WARNING),
            ("💰 Deuda Total",   f"S/ {deuda:,.0f}",  DANGER),
            ("⏰ Días Restantes", str(restantes),    INFO),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            KPICard(kpi_row, lbl, val, clr).grid(row=0, column=i, padx=6, sticky="nsew")

        # ── Filtro campaña banco ──
        campana_options = (
            self.app.campaign_mgr.distinct_campana_banco_for_campaign(campana_id)
        )
        if filter_bar_visible(campana_options):
            filter_card = ctk.CTkFrame(
                container, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
                border_width=1, border_color=BORDER,
            )
            filter_card.pack(fill="x", padx=16, pady=(0, 12))
            filter_inner = ctk.CTkFrame(filter_card, fg_color="transparent")
            filter_inner.pack(fill="x", padx=CARD_PADDING, pady=10)
            CampanaBancoFilterBar(
                filter_inner,
                available=campana_options,
                selected=self._campana_banco_filter,
                on_change=self._on_campana_banco_filter_change,
            ).pack(fill="x")

        # ── Líneas de tiempo por campaña banco ──
        try:
            timelines = self.app.campaign_mgr.get_campana_banco_timelines(campana_id)
        except Exception:
            timelines = []

        if self._campana_banco_filter is not None:
            timelines = [
                t for t in timelines if t["key"] == self._campana_banco_filter
            ]

        cycle_hdr = ctk.CTkFrame(container, fg_color="transparent")
        cycle_hdr.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            cycle_hdr,
            text="🎯 Ciclo de cobranza por campaña banco",
            font=font(FONT_SCALE['lg'], "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkButton(
            cycle_hdr, text="⚙️ Configuración tramos",
            fg_color="transparent", border_width=1, border_color=ACCENT,
            text_color=ACCENT, hover_color=ACCENT_LIGHT,
            width=150, height=28, font=font(11),
            command=lambda: self.app.navigate_to("settings"),
        ).pack(side="right")

        if not timelines:
            empty = ctk.CTkFrame(
                container, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
                border_width=1, border_color=BORDER,
            )
            empty.pack(fill="x", padx=16, pady=(0, 16))
            ctk.CTkLabel(
                empty,
                text="No hay campañas banco activas en la cartera.",
                font=font(FONT_SCALE["sm"]),
                text_color=TEXT_MUTED,
            ).pack(padx=CARD_PADDING, pady=CARD_PADDING)
        else:
            for tl in timelines:
                CampaignTimelineCard(
                    container,
                    tl,
                    on_edit_dates=lambda t=tl: self._open_dates_dialog(t),
                ).pack(fill="x", padx=16, pady=(0, 12))

    def _on_campana_banco_filter_change(self, filtro: str | None):
        self._campana_banco_filter = filtro
        scroll = self._tab_scrolls.get("Inicio")
        if scroll:
            self._render_inicio(scroll)

    def _open_dates_dialog(self, timeline: dict):
        from ..campana_banco_dates_dialog import open_campana_banco_dates_dialog

        camp = self.app.active_campaign
        if not camp:
            return

        def _refresh():
            scroll = self._tab_scrolls.get("Inicio")
            if scroll:
                self._render_inicio(scroll)

        open_campana_banco_dates_dialog(
            self.app, camp.id, timeline, on_saved=_refresh
        )

    def _open_wizard(self):
        from ..campaign_wizard import open_campaign_wizard
        open_campaign_wizard(self.app)

    def _render_excel_update_card(self, parent, camp, *, grid_column: int = 0):
        """Tarjeta de actualización periódica del Excel del banco."""
        excel_card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
            border_width=1, border_color="#0D9488",
        )
        excel_card.grid(row=0, column=grid_column, sticky="nsew", padx=(8, 0) if grid_column else (0, 0))
        excel_inner = ctk.CTkFrame(excel_card, fg_color="transparent")
        excel_inner.pack(fill="both", expand=True, padx=CARD_PADDING, pady=CARD_PADDING)

        origen = getattr(camp, "archivo_origen", "") or "—"
        ctk.CTkLabel(
            excel_inner,
            text="Actualización del banco (Excel)",
            font=font(FONT_SCALE['lg'], "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            excel_inner,
            text=(
                "Suba el Excel periódico del banco. Se detectan altas, "
                "cambios y bajas (clientes que pagaron o salieron de cartera)."
            ),
            font=font(FONT_SCALE['sm']),
            text_color=TEXT_SECONDARY,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", pady=(4, 8))
        ctk.CTkLabel(
            excel_inner,
            text=f"Última referencia: {origen}",
            font=font(FONT_SCALE['sm']),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(
            excel_inner,
            text="Aplicar Excel y notificar",
            font=font(FONT_SCALE['sm'], "bold"),
            fg_color="#0D9488",
            hover_color="#0F766E",
            height=36,
            corner_radius=10,
            command=self.app._on_update_base,
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkButton(
            excel_inner,
            text="Ir a pestaña Campaña",
            font=font(FONT_SCALE['xs']),
            fg_color="transparent",
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SECONDARY,
            height=32,
            command=lambda: (
                setattr(self.app, "_pending_tab", "Campaña"),
                self.app.navigate_to("inicio"),
            ),
        ).pack(anchor="w")

    def _render_operational_status(self, parent, *, grid_column: int = 0):
        gestores = []
        if self.app.firebase_connected:
            try:
                gestores = self.app.firebase.list_gestor_users()
            except Exception:
                pass
        try:
            status = self.app.campaign_mgr.get_operational_status(
                gestores_firestore=gestores,
                firebase_connected=self.app.firebase_connected,
            )
        except Exception:
            return

        card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
            border_width=1, border_color=BORDER,
        )
        padx = (0, 8) if grid_column == 0 else (8, 0)
        card.grid(row=0, column=grid_column, sticky="nsew", padx=padx)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PADDING, pady=CARD_PADDING)

        ctk.CTkLabel(
            inner, text="🚦 Estado de la campaña",
            font=font(FONT_SCALE["lg"], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 10))

        icons = {"ok": "✅", "warn": "⚠️", "error": "❌"}
        colors = {"ok": SUCCESS, "warn": WARNING, "error": DANGER}

        for item in status.get("items", []):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            st = item.get("status", "warn")
            ctk.CTkLabel(
                row,
                text=f"{icons.get(st, '•')} {item.get('label', '')}",
                font=font(FONT_SCALE["sm"], "bold"),
                text_color=colors.get(st, TEXT_PRIMARY),
                width=220,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=item.get("detail", ""),
                font=font(FONT_SCALE["sm"]), text_color=TEXT_SECONDARY, anchor="w",
            ).pack(side="left", fill="x", expand=True)
