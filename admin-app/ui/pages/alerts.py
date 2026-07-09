"""Alerts management page — field alerts from Firestore."""
from __future__ import annotations
import customtkinter as ctk
import threading
import webbrowser
from tkinter import messagebox
from typing import TYPE_CHECKING
from ..theme import *
from ..components import KPICard, SectionHeader

if TYPE_CHECKING:
    from ..app import App

_TIPO_LABELS = {
    "suplantacion": ("Suplantación", "#E11D48"),
    "pago_no_registrado": ("Pago no registrado", "#3B82F6"),
    "zona_inaccesible_devolucion": ("Zona inaccesible — devolución", "#7C3AED"),
}


class AlertsPage:
    """View and manage field alerts (Firestore `alertas` collection)."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._auto_refresh = False
        self._alertas: list = []
        self._filtered_alertas: list = []
        self._filter_status = "todas"
        self._filter_section = "todas"
        self._filter_tipo = "todos"
        self._sort_by = "fecha_desc"
        self._group_by_section = False
        self._busy = False

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

        main_frame = ctk.CTkFrame(container, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        self._sidebar = ctk.CTkFrame(main_frame, fg_color=CARD_BG,
                                     corner_radius=12, border_width=1,
                                     border_color=BORDER, width=280)
        self._sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._sidebar.grid_propagate(False)

        self._content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self._content_frame.grid(row=0, column=1, sticky="nsew")

        self._build_sidebar()
        self._build_content()
        self._refresh()

    def _build_sidebar(self):
        sidebar_hdr = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=60)
        sidebar_hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(sidebar_hdr, text="Filtros", font=font(16, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")

        search_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        search_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(search_frame, text="Buscar:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 4))
        self._search_var = ctk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_frame, textvariable=self._search_var,
            placeholder_text="Mensaje, gestor, cliente, sección...",
            height=32, corner_radius=8)
        self._search_entry.pack(fill="x")
        self._search_var.trace("w", lambda *args: self._apply_filters())

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

        section_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        section_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(section_frame, text="Sección:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))
        self._section_var = ctk.StringVar(value="todas")
        self._section_menu = ctk.CTkOptionMenu(
            section_frame, values=["todas"], variable=self._section_var,
            command=self._set_section_filter, height=28, corner_radius=6)
        self._section_menu.pack(fill="x")

        tipo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        tipo_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(tipo_frame, text="Tipo:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))
        self._tipo_var = ctk.StringVar(value="todos")
        self._tipo_menu = ctk.CTkOptionMenu(
            tipo_frame, values=["todos"], variable=self._tipo_var,
            command=self._set_tipo_filter, height=28, corner_radius=6)
        self._tipo_menu.pack(fill="x")

        sort_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        sort_frame.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(sort_frame, text="Ordenar por:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))
        self._sort_menu = ctk.CTkOptionMenu(
            sort_frame, values=["Fecha ↓", "Fecha ↑", "Sección", "Tipo"],
            command=self._set_sort, height=28, corner_radius=6)
        self._sort_menu.pack(fill="x")
        self._sort_menu.set("Fecha ↓")

        group_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        group_frame.pack(fill="x", padx=16, pady=(0, 16))
        self._group_var = ctk.BooleanVar(value=self._group_by_section)
        ctk.CTkCheckBox(
            group_frame, text="Agrupar por sección", variable=self._group_var,
            command=self._toggle_group, font=font(11)).pack(anchor="w")

    def _build_content(self):
        header_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 16))

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left")
        SectionHeader(title_frame, "Alertas del Campo",
                      "Suplantaciones y pagos no registrados desde gestores").pack(anchor="w")

        actions_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        actions_frame.pack(side="right")

        self._mark_all_btn = ctk.CTkButton(
            actions_frame, text="✓ Revisar visibles", font=font(11, "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            height=32, width=130, corner_radius=8,
            command=self._mark_all_visible_reviewed)
        self._mark_all_btn.pack(side="left", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            actions_frame, text="🔄 Actualizar", font=font(11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=32, width=120, corner_radius=8,
            command=self._refresh)
        self._refresh_btn.pack(side="left")

        self._kpi_frame = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        self._kpi_frame.pack(fill="x", pady=(0, 16))
        self._kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._alerts_container = ctk.CTkScrollableFrame(
            self._content_frame, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER)
        self._alerts_container.pack(fill="both", expand=True)

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

    def _set_status_message(self, text: str, color=None):
        if self._status_lbl.winfo_exists():
            self._status_lbl.configure(text=text, text_color=color or TEXT_SECONDARY)

    def _refresh(self):
        if not self._auto_refresh:
            return
        self._refresh_btn.configure(state="disabled", text="🔄 Cargando…")

        def work():
            alertas = self.app.firebase.get_alerts(estado="", limit=500)
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
        self._update_filter_menus()
        self._update_kpis()
        self._apply_filters()
        if self._auto_refresh and self._container and self._container.winfo_exists():
            self._container.after(30000, self._refresh)

    def _update_filter_menus(self):
        sections = ["todas"] + sorted(
            {a.get("seccion", "") for a in self._alertas if a.get("seccion")})
        self._section_menu.configure(values=sections)
        tipos = ["todos"] + sorted({a.get("tipo", "general") for a in self._alertas})
        self._tipo_menu.configure(values=tipos)

    def _update_kpis(self):
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        total = len(self._alertas)
        pendientes = sum(1 for a in self._alertas if not a.get("revisada", False))
        revisadas = total - pendientes
        secciones = len({a.get("seccion", "") for a in self._alertas if a.get("seccion")})
        kpis = [
            ("Total", str(total), ACCENT),
            ("Pendientes", str(pendientes), WARNING),
            ("Revisadas", str(revisadas), SUCCESS),
            ("Secciones", str(secciones), INFO),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            KPICard(self._kpi_frame, lbl, val, clr).grid(row=0, column=i, padx=4, sticky="nsew")

    def _apply_filters(self):
        search_text = self._search_var.get().lower()
        filtered = []
        for a in self._alertas:
            if search_text:
                searchable = (
                    f"{a.get('mensaje', '')} {a.get('gestor_nombre', '')} "
                    f"{a.get('cliente_nombre', '')} {a.get('seccion', '')} "
                    f"{a.get('tipo', '')}"
                ).lower()
                if search_text not in searchable:
                    continue
            filtered.append(a)

        if self._filter_status == "pendientes":
            filtered = [a for a in filtered if not a.get("revisada", False)]
        elif self._filter_status == "revisadas":
            filtered = [a for a in filtered if a.get("revisada", False)]

        if self._filter_section != "todas":
            filtered = [a for a in filtered if a.get("seccion", "") == self._filter_section]
        if self._filter_tipo != "todos":
            filtered = [a for a in filtered if a.get("tipo", "general") == self._filter_tipo]

        if self._sort_by == "fecha_desc":
            filtered.sort(key=lambda x: x.get("fecha_str", ""), reverse=True)
        elif self._sort_by == "fecha_asc":
            filtered.sort(key=lambda x: x.get("fecha_str", ""))
        elif self._sort_by == "seccion":
            filtered.sort(key=lambda x: x.get("seccion", ""))
        elif self._sort_by == "tipo":
            filtered.sort(key=lambda x: x.get("tipo", "general"))

        self._filtered_alertas = filtered
        self._display_alerts()

    def _display_alerts(self):
        for w in self._alerts_container.winfo_children():
            w.destroy()

        if not self._filtered_alertas:
            ctk.CTkLabel(
                self._alerts_container,
                text="No se encontraron alertas con los filtros aplicados",
                font=font(14), text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            self._set_status_message("Sin resultados")
            return

        self._set_status_message(f"{len(self._filtered_alertas)} alertas encontradas")
        if self._group_by_section:
            self._display_grouped_alerts()
        else:
            self._display_flat_alerts()

    def _display_flat_alerts(self):
        for alerta in self._filtered_alertas:
            self._create_alert_card(alerta)

    def _display_grouped_alerts(self):
        sections: dict[str, list] = {}
        for alerta in self._filtered_alertas:
            seccion = alerta.get("seccion", "Sin sección") or "Sin sección"
            sections.setdefault(seccion, []).append(alerta)
        for seccion, alertas in sorted(sections.items()):
            section_hdr = ctk.CTkFrame(self._alerts_container, fg_color=ACCENT_LIGHT,
                                       corner_radius=8, height=40)
            section_hdr.pack(fill="x", padx=8, pady=(8, 4))
            section_hdr.pack_propagate(False)
            ctk.CTkLabel(
                section_hdr, text=f"📍 {seccion} ({len(alertas)})",
                font=font(13, "bold"), text_color=ACCENT,
            ).pack(side="left", padx=12)
            for alerta in alertas:
                self._create_alert_card(alerta, indent=True)

    def _tipo_display(self, alerta: dict) -> tuple[str, str]:
        tipo_raw = alerta.get("tipo", "general")
        label, color = _TIPO_LABELS.get(tipo_raw, (tipo_raw.replace("_", " ").title(), TEXT_SECONDARY))
        return label, color

    def _create_alert_card(self, alerta, indent=False):
        card = ctk.CTkFrame(self._alerts_container, fg_color=CARD_BG,
                            corner_radius=10, border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=8 if not indent else 16, pady=2)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))

        status_color = SUCCESS if alerta.get("revisada", False) else WARNING
        ctk.CTkFrame(hdr, fg_color=status_color, width=8, height=8,
                     corner_radius=4).pack(side="left", padx=(0, 8))

        info_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        tipo_label, tipo_color = self._tipo_display(alerta)
        gestor = alerta.get("gestor_nombre", "—")
        cliente = alerta.get("cliente_nombre", "")
        title_text = f"{gestor} — {tipo_label}"
        if cliente:
            title_text = f"{cliente} — {tipo_label}"

        ctk.CTkLabel(info_frame, text=title_text, font=font(12, "bold"),
                     text_color=tipo_color).pack(anchor="w")

        subtitle = alerta.get("fecha_str", "—")
        if alerta.get("seccion"):
            subtitle += f" • {alerta.get('seccion')}"
        subtitle += f" • {alerta.get('estado_label', '')}"
        ctk.CTkLabel(info_frame, text=subtitle, font=font(10),
                     text_color=TEXT_SECONDARY).pack(anchor="w")

        actions_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        actions_frame.pack(side="right")

        ctk.CTkButton(
            actions_frame, text="Detalle", font=font(10),
            fg_color="#E2E8F0", text_color=TEXT_PRIMARY, hover_color=BORDER,
            height=24, width=58, corner_radius=6,
            command=lambda a=alerta: self._show_detail(a),
        ).pack(side="left", padx=2)

        if alerta.get("gps_lat") is not None and alerta.get("gps_lng") is not None:
            ctk.CTkButton(
                actions_frame, text="Mapa", font=font(10),
                fg_color=INFO, hover_color=ACCENT_HOVER,
                height=24, width=50, corner_radius=6,
                command=lambda a=alerta: self._open_map(a),
            ).pack(side="left", padx=2)

        if not alerta.get("revisada", False):
            ctk.CTkButton(
                actions_frame, text="✓ Revisar", font=font(10, "bold"),
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                height=24, width=72, corner_radius=6,
                command=lambda a=alerta: self._mark_reviewed(a),
            ).pack(side="left", padx=2)
        else:
            ctk.CTkButton(
                actions_frame, text="↩ Pendiente", font=font(10),
                fg_color=WARNING, hover_color=WARNING_HOVER,
                height=24, width=80, corner_radius=6,
                command=lambda a=alerta: self._mark_pending(a),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions_frame, text="Eliminar", font=font(10, "bold"),
            fg_color=DANGER, hover_color="#B91C1C",
            height=24, width=68, corner_radius=6,
            command=lambda a=alerta: self._delete_alert(a),
        ).pack(side="left", padx=2)

        msg_frame = ctk.CTkFrame(card, fg_color="transparent")
        msg_frame.pack(fill="x", padx=12, pady=(0, 8))
        mensaje = alerta.get("mensaje", "") or alerta.get("nota", "")
        if mensaje:
            ctk.CTkLabel(
                msg_frame, text=mensaje, font=font(11),
                text_color=TEXT_PRIMARY, wraplength=600, justify="left",
            ).pack(anchor="w")

    def _run_firebase_action(self, action, on_done):
        if self._busy:
            return
        self._busy = True
        self._refresh_btn.configure(state="disabled")

        def work():
            ok, err = False, None
            try:
                ok = bool(action())
            except Exception as exc:
                err = str(exc)
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._action_done(ok, err, on_done))

        threading.Thread(target=work, daemon=True).start()

    def _action_done(self, ok: bool, err: str | None, on_done):
        self._busy = False
        try:
            self._refresh_btn.configure(state="normal")
        except Exception:
            pass
        on_done(ok, err)
        if ok:
            self._refresh()

    def _mark_reviewed(self, alerta):
        alerta_id = alerta.get("id", "")
        if not alerta_id:
            self._set_status_message("Alerta sin ID", DANGER)
            return

        def on_done(ok, err):
            if ok:
                self._set_status_message("Alerta marcada como revisada", SUCCESS)
            else:
                self._set_status_message(
                    f"No se pudo marcar (permisos admin/supervisor o red): {err or ''}".strip(),
                    DANGER,
                )

        self._run_firebase_action(
            lambda: self.app.firebase.mark_alert_reviewed(alerta_id),
            on_done,
        )

    def _mark_pending(self, alerta):
        alerta_id = alerta.get("id", "")
        if not alerta_id:
            return

        def on_done(ok, err):
            if ok:
                self._set_status_message("Alerta devuelta a pendiente", WARNING)
            else:
                self._set_status_message(f"Error al actualizar: {err or ''}", DANGER)

        self._run_firebase_action(
            lambda: self.app.firebase.mark_alert_pending(alerta_id),
            on_done,
        )

    def _delete_alert(self, alerta):
        alerta_id = alerta.get("id", "")
        if not alerta_id:
            return
        tipo_label, _ = self._tipo_display(alerta)
        if not messagebox.askyesno(
            "Eliminar alerta",
            f"¿Eliminar permanentemente esta alerta?\n\n{tipo_label}\n{alerta.get('mensaje', '')[:80]}",
            parent=self.app,
        ):
            return

        def on_done(ok, err):
            if ok:
                self._set_status_message("Alerta eliminada", SUCCESS)
            else:
                self._set_status_message(f"No se pudo eliminar: {err or ''}", DANGER)

        self._run_firebase_action(
            lambda: self.app.firebase.delete_alert(alerta_id),
            on_done,
        )

    def _mark_all_visible_reviewed(self):
        pending = [a for a in self._filtered_alertas if not a.get("revisada", False)]
        if not pending:
            messagebox.showinfo("Revisar", "No hay alertas pendientes en la lista actual.", parent=self.app)
            return
        if not messagebox.askyesno(
            "Revisar todas",
            f"¿Marcar como revisadas las {len(pending)} alertas visibles (filtro actual)?",
            parent=self.app,
        ):
            return

        ids = [a["id"] for a in pending if a.get("id")]

        def work():
            ok_count = 0
            for aid in ids:
                if self.app.firebase.mark_alert_reviewed(aid):
                    ok_count += 1
            if self._container and self._container.winfo_exists():
                self._container.after(
                    0,
                    lambda: self._mark_all_done(ok_count, len(ids)),
                )

        self._busy = True
        self._refresh_btn.configure(state="disabled")
        threading.Thread(target=work, daemon=True).start()

    def _mark_all_done(self, ok_count: int, total: int):
        self._busy = False
        try:
            self._refresh_btn.configure(state="normal")
        except Exception:
            pass
        self._set_status_message(
            f"{ok_count}/{total} alertas marcadas como revisadas",
            SUCCESS if ok_count == total else WARNING,
        )
        self._refresh()

    def _open_map(self, alerta):
        lat, lng = alerta.get("gps_lat"), alerta.get("gps_lng")
        if lat is None or lng is None:
            messagebox.showinfo("Mapa", "Esta alerta no tiene coordenadas GPS.", parent=self.app)
            return
        webbrowser.open(f"https://www.google.com/maps?q={lat},{lng}")

    def _show_detail(self, alerta):
        win = ctk.CTkToplevel(self.app)
        win.title("Detalle de alerta")
        win.geometry("520x480")
        win.configure(fg_color=BG)
        win.transient(self.app)
        win.grab_set()

        tipo_label, _ = self._tipo_display(alerta)
        ctk.CTkLabel(win, text=tipo_label, font=font(18, "bold"),
                    text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(win, fg_color=CARD_BG, corner_radius=10,
                                        border_width=1, border_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        fields = [
            ("Estado", alerta.get("estado_label", "")),
            ("Fecha", alerta.get("fecha_str", "—")),
            ("Gestor", alerta.get("gestor_nombre", "—")),
            ("Email gestor", alerta.get("gestor_email", "—")),
            ("Sección", alerta.get("seccion", "—")),
            ("Cliente", alerta.get("cliente_nombre", "—")),
            ("Código cliente", alerta.get("cliente_codigo", alerta.get("cliente_id", "—"))),
            ("Deuda", self._format_deuda(alerta.get("cliente_deuda"))),
            ("Nota", alerta.get("nota", "") or "—"),
            ("Campaña", alerta.get("campaign_id", alerta.get("campaña_id", "—"))),
            ("ID", alerta.get("id", "—")),
        ]
        lat, lng = alerta.get("gps_lat"), alerta.get("gps_lng")
        if lat is not None and lng is not None:
            fields.append(("GPS", f"{lat:.6f}, {lng:.6f}"))

        for label, value in fields:
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=f"{label}:", font=font(11, "bold"),
                         text_color=TEXT_SECONDARY, width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=str(value), font=font(11),
                         text_color=TEXT_PRIMARY, wraplength=340, justify="left").pack(
                side="left", fill="x", expand=True)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        if lat is not None and lng is not None:
            ctk.CTkButton(btn_row, text="Abrir en mapa", font=font(11, "bold"),
                          fg_color=INFO, height=32,
                          command=lambda: self._open_map(alerta)).pack(side="left", padx=(0, 8))
        if not alerta.get("revisada", False):
            ctk.CTkButton(btn_row, text="Marcar revisada", font=font(11, "bold"),
                          fg_color=SUCCESS, height=32,
                          command=lambda: (win.destroy(), self._mark_reviewed(alerta))).pack(
                side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cerrar", font=font(11),
                      fg_color="#E2E8F0", text_color=TEXT_PRIMARY, height=32,
                      command=win.destroy).pack(side="right")

    @staticmethod
    def _format_deuda(value) -> str:
        if value is None or value == "":
            return "—"
        try:
            return f"S/ {float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)


def _darken(color):
    if color == ACCENT:
        return ACCENT_HOVER
    if color == WARNING:
        return WARNING_HOVER
    if color == SUCCESS:
        return SUCCESS_HOVER
    return color
