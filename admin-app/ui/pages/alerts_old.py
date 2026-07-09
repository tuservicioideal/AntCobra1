"""Alerts management page — Redesigned with better organization and advanced features."""
from __future__ import annotations
import customtkinter as ctk
from tkinter import ttk
import threading
from typing import TYPE_CHECKING
from datetime import datetime
from ..theme import *
from ..components import KPICard, SectionHeader, ActionButton

if TYPE_CHECKING:
    from ..app import App


class AlertsPage:
    """Enhanced view and management of field alerts with advanced filtering and organization."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._auto_refresh = False
        self._alertas: list = []
        self._filtered_alertas: list = []
        self._filter_status = "todas"  # todas | pendientes | revisadas
        self._filter_section = "todas"
        self._filter_tipo = "todos"
        self._search_text = ""
        self._sort_by = "fecha_desc"  # fecha_desc | fecha_asc | seccion | tipo
        self._group_by_section = False

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container
        self._auto_refresh = True

        if not self.app.firebase_connected:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            ctk.CTkLabel(container, text="Conecte Firebase para ver alertas.",
                         font=font(14), text_color=TEXT_SECONDARY).pack(pady=20)
            return

        # Main layout: sidebar + content
        main_frame = ctk.CTkFrame(container, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Sidebar for filters
        self._sidebar = ctk.CTkFrame(main_frame, fg_color=CARD_BG,
                                     corner_radius=12, border_width=1,
                                     border_color=BORDER, width=280)
        self._sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._sidebar.grid_propagate(False)

        # Content area
        self._content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self._content_frame.grid(row=0, column=1, sticky="nsew")

        self._build_sidebar()
        self._build_content()

        self._refresh()

    def _build_sidebar(self):
        # Header
        sidebar_hdr = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=60)
        sidebar_hdr.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(sidebar_hdr, text="Filtros", font=font(16, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")

        # Search
        search_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        search_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(search_frame, text="Buscar:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 4))

        self._search_var = ctk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_frame, textvariable=self._search_var,
            placeholder_text="Mensaje, gestor, sección...",
            height=32, corner_radius=8)
        self._search_entry.pack(fill="x")
        self._search_var.trace("w", lambda *args: self._apply_filters())

        # Status filter
        status_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        status_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(status_frame, text="Estado:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))

        self._status_buttons = {}
        for key, label, color in [("todas", "Todas", ACCENT),
                                  ("pendientes", "Pendientes", WARNING),
                                  ("revisadas", "Revisadas", SUCCESS)]:
            btn = ctk.CTkButton(
                status_frame, text=label, font=font(11),
                fg_color=color if key == self._filter_status else "#E2E8F0",
                text_color=WHITE if key == self._filter_status else TEXT_PRIMARY,
                hover_color=_darken(color) if key == self._filter_status else BORDER,
                height=28, corner_radius=6,
                command=lambda k=key: self._set_status_filter(k))
            btn.pack(fill="x", pady=2)
            self._status_buttons[key] = btn

        # Section filter
        section_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        section_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(section_frame, text="Sección:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))

        self._section_var = ctk.StringVar(value="todas")
        sections = ["todas"] + sorted(set(a.get("seccion", "") for a in self._alertas if a.get("seccion")))
        self._section_menu = ctk.CTkOptionMenu(
            section_frame, values=sections, variable=self._section_var,
            command=self._set_section_filter, height=28, corner_radius=6)
        self._section_menu.pack(fill="x")

        # Type filter
        tipo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        tipo_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(tipo_frame, text="Tipo:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))

        self._tipo_var = ctk.StringVar(value="todos")
        tipos = ["todos"] + sorted(set(a.get("tipo", "general") for a in self._alertas))
        self._tipo_menu = ctk.CTkOptionMenu(
            tipo_frame, values=tipos, variable=self._tipo_var,
            command=self._set_tipo_filter, height=28, corner_radius=6)
        self._tipo_menu.pack(fill="x")

        # Sort options
        sort_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        sort_frame.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(sort_frame, text="Ordenar por:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))

        self._sort_var = ctk.StringVar(value="fecha_desc")
        sort_options = [("fecha_desc", "Fecha ↓"), ("fecha_asc", "Fecha ↑"),
                        ("seccion", "Sección"), ("tipo", "Tipo")]
        self._sort_menu = ctk.CTkOptionMenu(
            sort_frame, values=[label for _, label in sort_options],
            variable=ctk.StringVar(value="Fecha ↓"),
            command=self._set_sort, height=28, corner_radius=6)
        self._sort_menu.pack(fill="x")

        # Group by section toggle
        group_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        group_frame.pack(fill="x", padx=16, pady=(0, 16))

        self._group_var = ctk.BooleanVar(value=self._group_by_section)
        self._group_check = ctk.CTkCheckBox(
            group_frame, text="Agrupar por sección", variable=self._group_var,
            command=self._toggle_group, font=font(11))
        self._group_check.pack(anchor="w")

    def _build_content(self):
        # Header with KPIs and actions
        header_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 16))

        # Title and refresh
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")

        SectionHeader(title_frame, "Alertas del Campo",
                      "Gestión organizada de notificaciones").pack(anchor="w")

        # Action buttons
        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.pack(side="right")

        self._refresh_btn = ctk.CTkButton(
            actions_frame, text="🔄 Actualizar", font=font(11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=32, width=120, corner_radius=8,
            command=self._refresh)
        self._refresh_btn.pack(side="left", padx=(0, 8))

        # KPIs
        self._kpi_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._kpi_frame.pack(fill="x", pady=(0, 16))
        self._kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Alerts container
        self._alerts_container = ctk.CTkScrollableFrame(
            self._content_frame, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER)
        self._alerts_container.pack(fill="both", expand=True)

        # Status label
        self._status_lbl = ctk.CTkLabel(
            self._content_frame, text="Cargando alertas...",
            font=font(12), text_color=TEXT_SECONDARY)
        self._status_lbl.pack(pady=8)

    def stop(self):
        self._auto_refresh = False

    def _set_status_filter(self, key):
        self._filter_status = key
        for k, btn in self._status_buttons.items():
            is_active = k == key
            color = {"todas": ACCENT, "pendientes": WARNING, "revisadas": SUCCESS}[k]
            btn.configure(
                fg_color=color if is_active else "#E2E8F0",
                text_color=WHITE if is_active else TEXT_PRIMARY,
                hover_color=_darken(color) if is_active else BORDER)
        self._apply_filters()

    def _set_section_filter(self, value):
        self._filter_section = value
        self._apply_filters()

    def _set_tipo_filter(self, value):
        self._filter_tipo = value
        self._apply_filters()

    def _set_sort(self, value):
        sort_map = {"Fecha ↓": "fecha_desc", "Fecha ↑": "fecha_asc",
                    "Sección": "seccion", "Tipo": "tipo"}
        self._sort_by = sort_map.get(value, "fecha_desc")
        self._apply_filters()

    def _toggle_group(self):
        self._group_by_section = self._group_var.get()
        self._apply_filters()

    def _refresh(self):
        if not self._auto_refresh:
            return
        self._refresh_btn.configure(state="disabled", text="🔄 Cargando…")

        def work():
            alertas = self.app.firebase.get_alerts()
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._on_data(alertas))

        threading.Thread(target=work, daemon=True).start()

    def _on_data(self, alertas):
        self._alertas = alertas or []
        try:
            if self._refresh_btn.winfo_exists():
                self._refresh_btn.configure(state="normal", text="🔄 Actualizar")
        except Exception:
            pass

        # Update filter menus with new data
        self._update_filter_menus()

        # KPIs
        self._update_kpis()

        # Apply filters and display
        self._apply_filters()

        if self._auto_refresh and self._container and self._container.winfo_exists():
            self._container.after(30000, self._refresh)

    def _update_filter_menus(self):
        # Update section menu
        sections = ["todas"] + sorted(set(a.get("seccion", "") for a in self._alertas if a.get("seccion")))
        self._section_menu.configure(values=sections)

        # Update tipo menu
        tipos = ["todos"] + sorted(set(a.get("tipo", "general") for a in self._alertas))
        self._tipo_menu.configure(values=tipos)

    def _update_kpis(self):
        for w in self._kpi_frame.winfo_children():
            w.destroy()

        total = len(self._alertas)
        pendientes = sum(1 for a in self._alertas if not a.get("revisada", False))
        revisadas = total - pendientes
        secciones = len(set(a.get("seccion", "") for a in self._alertas if a.get("seccion")))

        kpis = [
            ("Total", str(total), ACCENT),
            ("Pendientes", str(pendientes), WARNING),
            ("Revisadas", str(revisadas), SUCCESS),
            ("Secciones", str(secciones), INFO),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            KPICard(self._kpi_frame, lbl, val, clr).grid(
                row=0, column=i, padx=4, sticky="nsew")

    def _apply_filters(self):
        # Apply text search
        search_text = self._search_var.get().lower()
        filtered = []
        for a in self._alertas:
            if search_text:
                searchable = f"{a.get('mensaje', '')} {a.get('gestor_nombre', '')} {a.get('seccion', '')}".lower()
                if search_text not in searchable:
                    continue
            filtered.append(a)

        # Apply status filter
        if self._filter_status == "pendientes":
            filtered = [a for a in filtered if not a.get("revisada", False)]
        elif self._filter_status == "revisadas":
            filtered = [a for a in filtered if a.get("revisada", False)]

        # Apply section filter
        if self._filter_section != "todas":
            filtered = [a for a in filtered if a.get("seccion", "") == self._filter_section]

        # Apply tipo filter
        if self._filter_tipo != "todos":
            filtered = [a for a in filtered if a.get("tipo", "general") == self._filter_tipo]

        # Sort
        if self._sort_by == "fecha_desc":
            filtered.sort(key=lambda x: x.get("fecha", ""), reverse=True)
        elif self._sort_by == "fecha_asc":
            filtered.sort(key=lambda x: x.get("fecha", ""))
        elif self._sort_by == "seccion":
            filtered.sort(key=lambda x: x.get("seccion", ""))
        elif self._sort_by == "tipo":
            filtered.sort(key=lambda x: x.get("tipo", "general"))

        self._filtered_alertas = filtered
        self._display_alerts()

    def _display_alerts(self):
        # Clear previous content
        for w in self._alerts_container.winfo_children():
            w.destroy()

        if not self._filtered_alertas:
            ctk.CTkLabel(
                self._alerts_container,
                text="No se encontraron alertas con los filtros aplicados",
                font=font(14), text_color=TEXT_SECONDARY
            ).pack(pady=40)
            self._status_lbl.configure(text="Sin resultados")
            return

        self._status_lbl.configure(
            text=f"{len(self._filtered_alertas)} alertas encontradas",
            text_color=TEXT_SECONDARY)

        if self._group_by_section:
            self._display_grouped_alerts()
        else:
            self._display_flat_alerts()

    def _display_flat_alerts(self):
        for alerta in self._filtered_alertas:
            self._create_alert_card(alerta)

    def _display_grouped_alerts(self):
        sections = {}
        for alerta in self._filtered_alertas:
            seccion = alerta.get("seccion", "Sin sección")
            if seccion not in sections:
                sections[seccion] = []
            sections[seccion].append(alerta)

        for seccion, alertas in sorted(sections.items()):
            # Section header
            section_hdr = ctk.CTkFrame(self._alerts_container, fg_color=ACCENT_LIGHT,
                                       corner_radius=8, height=40)
            section_hdr.pack(fill="x", padx=8, pady=(8, 4))
            section_hdr.pack_propagate(False)

            ctk.CTkLabel(
                section_hdr, text=f"📍 {seccion} ({len(alertas)})",
                font=font(13, "bold"), text_color=ACCENT
            ).pack(side="left", padx=12)

            # Section alerts
            for alerta in alertas:
                self._create_alert_card(alerta, indent=True)

    def _create_alert_card(self, alerta, indent=False):
        card = ctk.CTkFrame(self._alerts_container, fg_color=CARD_BG,
                            corner_radius=10, border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", padx=8 if not indent else 16, pady=2)

        # Header
        hdr = ctk.CTkFrame(card, fg_color="transparent", height=40)
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        hdr.pack_propagate(False)

        # Status indicator
        status_color = SUCCESS if alerta.get("revisada", False) else WARNING
        status_indicator = ctk.CTkFrame(hdr, fg_color=status_color, width=8,
                                        height=8, corner_radius=4)
        status_indicator.pack(side="left", padx=(0, 8))

        # Info
        info_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        gestor = alerta.get("gestor_nombre", alerta.get("gestor_uid", "")[:8])
        fecha = alerta.get("fecha", "")
        tipo = alerta.get("tipo", "general").title()

        title_text = f"{gestor} • {tipo}"
        ctk.CTkLabel(info_frame, text=title_text, font=font(12, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")

        subtitle_text = f"{fecha}"
        if alerta.get("seccion"):
            subtitle_text += f" • {alerta.get('seccion')}"
        ctk.CTkLabel(info_frame, text=subtitle_text, font=font(10),
                     text_color=TEXT_SECONDARY).pack(anchor="w")

        # Actions
        actions_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        actions_frame.pack(side="right")

        if not alerta.get("revisada", False):
            mark_btn = ctk.CTkButton(
                actions_frame, text="✓ Revisar", font=font(10, "bold"),
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                height=24, width=70, corner_radius=6,
                command=lambda: self._mark_reviewed(alerta))
            mark_btn.pack(side="left")

        # Message
        msg_frame = ctk.CTkFrame(card, fg_color="transparent")
        msg_frame.pack(fill="x", padx=12, pady=(0, 8))

        mensaje = alerta.get("mensaje", "")
        msg_label = ctk.CTkLabel(
            msg_frame, text=mensaje, font=font(11),
            text_color=TEXT_PRIMARY, wraplength=600, justify="left")
        msg_label.pack(anchor="w")

    def _mark_reviewed(self, alerta):
        alerta_id = alerta.get("id", "")
        if alerta_id:
            def work():
                self.app.firebase.mark_alerta_revisada(alerta_id)
                if self._container and self._container.winfo_exists():
                    self._container.after(0, self._refresh)
            threading.Thread(target=work, daemon=True).start()


def _darken(color):
    """Helper to darken a color for hover effects."""
    # Simple darkening - in a real app you'd use a proper color manipulation library
    if color == ACCENT:
        return ACCENT_HOVER
    elif color == WARNING:
        return WARNING_HOVER
    elif color == SUCCESS:
        return SUCCESS_HOVER
    return color
            alertas = self.app.firebase.get_alerts()
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._on_data(alertas))

        threading.Thread(target=work, daemon=True).start()

    def _on_data(self, alertas):
        self._alertas = alertas or []
        try:
            if self._refresh_btn.winfo_exists():
                self._refresh_btn.configure(state="normal", text="Actualizar")
        except Exception:
            pass

        # KPIs
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        self._kpi_frame.grid_columnconfigure((0, 1, 2), weight=1)

        total = len(self._alertas)
        pendientes = sum(1 for a in self._alertas
                         if not a.get("revisada", False))
        revisadas = total - pendientes

        kpis = [
            ("Total", str(total), ACCENT),
            ("Pendientes", str(pendientes), WARNING),
            ("Revisadas", str(revisadas), SUCCESS),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            KPICard(self._kpi_frame, lbl, val, clr).grid(
                row=0, column=i, padx=3, sticky="nsew")

        self._status_lbl.configure(
            text=f"{total} alertas encontradas",
            text_color=TEXT_SECONDARY)

        self._apply_filter()

        if self._auto_refresh and self._container and self._container.winfo_exists():
            self._container.after(30000, self._refresh)

    def _apply_filter(self):
        for w in self._table_frame.winfo_children():
            w.destroy()

        if self._filter == "pendientes":
            items = [a for a in self._alertas if not a.get("revisada", False)]
        elif self._filter == "revisadas":
            items = [a for a in self._alertas if a.get("revisada", False)]
        else:
            items = self._alertas

        if not items:
            ctk.CTkLabel(self._table_frame,
                         text=f"Sin alertas {self._filter}",
                         font=font(13), text_color=TEXT_SECONDARY
                         ).pack(pady=30)
            return

        cols = ("fecha", "gestor", "seccion", "tipo", "mensaje", "estado")
        style_name = apply_treeview_style("Alert.Treeview")
        tree = ttk.Treeview(self._table_frame, columns=cols,
                            show="headings", style=style_name,
                            height=min(len(items) + 1, 18))

        for c, h, w in [("fecha", "Fecha", 140), ("gestor", "Gestor", 120),
                         ("seccion", "Sección", 100), ("tipo", "Tipo", 80),
                         ("mensaje", "Mensaje", 300), ("estado", "Estado", 80)]:
            tree.heading(c, text=h)
            tree.column(c, width=w, minwidth=50)

        for a in items:
            rev = a.get("revisada", False)
            tree.insert("", "end", values=(
                a.get("fecha", ""),
                a.get("gestor_nombre", a.get("gestor_uid", "")[:8]),
                a.get("seccion", ""),
                a.get("tipo", "general"),
                a.get("mensaje", ""),
                "✓ Revisada" if rev else "● Pendiente",
            ))

        tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Right-click menu
        menu = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        menu.pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkButton(
            menu, text="Marcar como revisada", font=font(11, "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            height=30, corner_radius=8,
            command=lambda: self._mark_reviewed(tree)
        ).pack(side="left", padx=4)

    def _mark_reviewed(self, tree):
        sel = tree.selection()
        if not sel:
            return
        idx = tree.index(sel[0])

        if self._filter == "pendientes":
            items = [a for a in self._alertas if not a.get("revisada", False)]
        elif self._filter == "revisadas":
            items = [a for a in self._alertas if a.get("revisada", False)]
        else:
            items = self._alertas

        if 0 <= idx < len(items):
            alerta = items[idx]
            alerta_id = alerta.get("id", "")
            if alerta_id:
                def work():
                    self.app.firebase.mark_alerta_revisada(alerta_id)
                    if self._container and self._container.winfo_exists():
                        self._container.after(0, self._refresh)
                threading.Thread(target=work, daemon=True).start()
