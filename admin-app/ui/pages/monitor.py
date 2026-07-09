"""Real-time field visit monitor page."""
from __future__ import annotations
import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
from typing import TYPE_CHECKING
from services.campana_banco_utils import apply_campana_banco_filter, filter_bar_visible
from ..theme import *
from ..components import KPICard, CampanaBancoFilterBar

if TYPE_CHECKING:
    from ..app import App

_STATUS_LABELS = {
    "pendiente": ("Pendiente", TEXT_SECONDARY),
    "visitado_habido": ("Habido", SUCCESS),
    "visitado_no_habido": ("No Habido", WARNING),
    "fallecido_inubicable": ("Inubicable", DANGER),
    "suplantacion": ("Suplantación", "#E11D48"),
    "pago_no_registrado": ("Pago No Reg.", INFO),
}

_TREE_BATCH = 100
_MONITOR_PAGE_SIZE = 50


class MonitorPage:
    """Real-time field visit monitoring dashboard."""

    def __init__(self, app: App):
        self.app = app
        self._auto_refresh = False
        self._tree = None
        self._kpi_widgets: list[KPICard] = []
        self._status_lbl = None
        self._container = None
        self._refresh_btn = None
        self._after_id = None
        # Cached row data for zone editing (maps treeview iid → client info)
        self._row_data: list[dict] = []
        self._all_display_rows: list[tuple] = []
        self._all_raw_rows: list[dict] = []
        self._monitor_page = 1
        self._monitor_page_label = None
        self._monitor_summary_label = None
        self._monitor_btn_prev = None
        self._monitor_btn_next = None
        self._campana_banco_filter: str | None = None
        self._campana_options: list[str] = []
        self._filter_frame = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container
        self._auto_refresh = True
        self._kpi_widgets = []
        self._after_id = None

        if not self.app.firebase_connected and not self.app.active_campaign:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            # "No connected" card
            card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
                                border_width=1, border_color=BORDER)
            card.pack(fill="x", padx=40, pady=20)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=40, pady=48)
            ctk.CTkLabel(inner, text="📡", font=font(40)).pack()
            ctk.CTkLabel(inner, text="Sin conexión Firebase",
                         font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY).pack(pady=(12, 4))
            ctk.CTkLabel(inner, text="Conecte Firebase o cargue campaña local para ver el monitor.",
                         font=font(FONT_SCALE['base']), text_color=TEXT_SECONDARY).pack()
            return

        # ── Header ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 12))

        title_side = ctk.CTkFrame(hdr, fg_color="transparent")
        title_side.pack(side="left")
        ctk.CTkLabel(title_side, text="📡 Monitor de Campo",
                     font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(title_side, text="Progreso de visitas en tiempo real",
                     font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        btn_side = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_side.pack(side="right", anchor="center")

        self._status_lbl = ctk.CTkLabel(btn_side, text="",
                                        font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY)
        self._status_lbl.pack(side="left", padx=(0, 12))

        self._refresh_btn = ctk.CTkButton(
            btn_side, text="🔄 Actualizar", font=font(FONT_SCALE['base'], "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=BUTTON_HEIGHT, width=140, corner_radius=BUTTON_CORNER_RADIUS,
            command=self._refresh)
        self._refresh_btn.pack(side="left")

        if self.app.active_campaign:
            self._campana_options = (
                self.app.campaign_mgr.distinct_campana_banco_for_campaign(
                    self.app.active_campaign.id
                )
            )
            if filter_bar_visible(self._campana_options):
                self._filter_frame = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                                    border_width=1, border_color=BORDER)
                self._filter_frame.pack(fill="x", padx=16, pady=(0, 8))
                inner_f = ctk.CTkFrame(self._filter_frame, fg_color="transparent")
                inner_f.pack(fill="x", padx=16, pady=8)
                CampanaBancoFilterBar(
                    inner_f,
                    available=self._campana_options,
                    selected=self._campana_banco_filter,
                    on_change=self._on_campana_filter_change,
                ).pack(fill="x")

        # ── KPI Row ───────────────────────────────────────────────
        kpi_row = ctk.CTkFrame(container, fg_color="transparent")
        kpi_row.pack(fill="x", padx=16, pady=(0, 12))
        kpi_row.grid_columnconfigure(tuple(range(6)), weight=1)

        kpi_defs = [
            ("Total", "…", ACCENT),
            ("Pendientes", "…", TEXT_SECONDARY),
            ("Habidos", "…", SUCCESS),
            ("No Habidos", "…", WARNING),
            ("Inubicables", "…", DANGER),
            ("Deuda Gest.", "…", SUCCESS),
        ]
        self._kpi_widgets = []
        for i, (lbl, val, clr) in enumerate(kpi_defs):
            kw = KPICard(kpi_row, lbl, val, clr)
            kw.grid(row=0, column=i, padx=4, sticky="nsew")
            self._kpi_widgets.append(kw)

        # ── Data Table ─────────────────────────────────────────────
        tf = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tf.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Table header label
        tbl_hdr = ctk.CTkFrame(tf, fg_color=ACCENT_LIGHT, corner_radius=0,
                               height=38)
        tbl_hdr.pack(fill="x", padx=0, pady=0)
        tbl_hdr.pack_propagate(False)
        ctk.CTkLabel(tbl_hdr, text="Registro de Visitas",
                     font=font(FONT_SCALE['base'], "bold"), text_color=ACCENT
                     ).pack(side="left", padx=16, pady=8)

        cols = ("seccion", "nombre", "codigo", "distrito", "deuda",
                "estado", "nota", "fecha")
        hdrs = {"seccion": "Sección", "nombre": "Nombre Completo", "codigo": "Código",
                "distrito": "Distrito", "deuda": "Deuda",
                "estado": "Estado", "nota": "Nota del Gestor", "fecha": "Fecha"}

        style_name = apply_treeview_style("Mon.Treeview")

        tree_frame = ctk.CTkFrame(tf, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  style=style_name, height=22)

        col_weights = {
            "seccion": 1, "nombre": 3, "codigo": 1, "distrito": 1,
            "deuda": 1, "estado": 1, "nota": 2, "fecha": 1,
        }
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            self._tree.column(c, width=100, minwidth=60, stretch=True)

        def _resize_tree_columns(event=None):
            if not self._tree or not self._tree.winfo_exists():
                return
            total_w = max(self._tree.winfo_width() - 20, 400)
            weight_sum = sum(col_weights.values())
            for c in cols:
                self._tree.column(c, width=max(
                    int(total_w * col_weights[c] / weight_sum), 60))

        self._tree.bind("<Configure>", _resize_tree_columns)

        # Color tags for status
        self._tree.tag_configure("habido",      background="#ECFDF5", foreground="#065F46")
        self._tree.tag_configure("no_habido",   background="#FFFBEB", foreground="#92400E")
        self._tree.tag_configure("inubicable",  background="#FEF2F2", foreground="#991B1B")
        self._tree.tag_configure("suplantacion",background="#FFF1F2", foreground="#9F1239")
        self._tree.tag_configure("pago_noreg",  background="#EFF6FF", foreground="#1E40AF")
        self._tree.tag_configure("pendiente",   background=WHITE,     foreground=TEXT_PRIMARY)
        self._tree.tag_configure("odd",         background="#F8FAFC")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)

        pag = ctk.CTkFrame(tf, fg_color="transparent")
        pag.pack(fill="x", padx=12, pady=(0, 8))

        self._monitor_summary_label = ctk.CTkLabel(
            pag, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._monitor_summary_label.pack(side="left")

        ctrl = ctk.CTkFrame(pag, fg_color="transparent")
        ctrl.pack(side="right")

        self._monitor_btn_prev = ctk.CTkButton(
            ctrl, text="◀ Anterior", width=100, height=32,
            fg_color=TEXT_SECONDARY, hover_color="#475569",
            command=self._monitor_prev_page)
        self._monitor_btn_prev.pack(side="left", padx=(0, 8))

        self._monitor_page_label = ctk.CTkLabel(
            ctrl, text="Página 1/1", font=font(12, "bold"))
        self._monitor_page_label.pack(side="left", padx=(0, 8))

        self._monitor_btn_next = ctk.CTkButton(
            ctrl, text="Siguiente ▶", width=100, height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._monitor_next_page)
        self._monitor_btn_next.pack(side="left")

        # Double-click to edit client zone (admin/supervisor only)
        self._tree.bind("<Double-1>", self._on_tree_dblclick)

        self._refresh()

    def _on_campana_filter_change(self, filtro: str | None):
        self._campana_banco_filter = filtro
        self._refresh()

    def stop(self):
        self._auto_refresh = False
        if self._after_id and self._container and self._container.winfo_exists():
            try:
                self._container.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None

    def _refresh(self):
        if not self._auto_refresh or not self._refresh_btn:
            return
        self._refresh_btn.configure(state="disabled", text="⏳ Cargando…")

        def work():
            try:
                if self.app.firebase_connected:
                    data = self.app.firebase.get_campaign_status()
                    data = self.app.campaign_mgr.filter_firebase_status(
                        data, self._campana_banco_filter
                    )
                else:
                    data = self._build_local_status(self._campana_banco_filter)
                # Pre-compute flat row list on the worker thread
                rows = self._prepare_rows(data)
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._apply_data(data, rows))
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _build_local_status(self, campana_banco: str | None = None) -> dict:
        """Build monitor-compatible payload from local SQLite data."""
        if not self.app.active_campaign:
            return {"resumen": {"total": 0, "pendiente": 0, "visitado_habido": 0,
                                "visitado_no_habido": 0, "fallecido_inubicable": 0,
                                "suplantacion": 0, "pago_no_registrado": 0,
                                "deuda_total": 0, "deuda_visitada": 0}, "secciones": {}}
        clients = self.app.campaign_mgr.get_all_clients(self.app.active_campaign.id)
        clients = apply_campana_banco_filter(clients, campana_banco)
        secciones = {}
        resumen = {
            "total": 0,
            "pendiente": 0,
            "visitado_habido": 0,
            "visitado_no_habido": 0,
            "fallecido_inubicable": 0,
            "suplantacion": 0,
            "pago_no_registrado": 0,
            "deuda_total": 0.0,
            "deuda_visitada": 0.0,
        }
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
    def _prepare_rows(data) -> tuple[list[tuple], list[dict]]:
        """Build Treeview value tuples off the main thread.
        Returns (display_rows, raw_data) where raw_data[i] has client info."""
        rows = []
        raw = []
        for sec_id in sorted(data["secciones"]):
            sec = data["secciones"][sec_id]
            for c in sec["clientes"]:
                estado = c.get("estado_gestion", "pendiente")
                lbl, _ = _STATUS_LABELS.get(estado, ("?", TEXT_SECONDARY))
                fecha = ""
                fg = c.get("fecha_gestion")
                if fg:
                    try:
                        fecha = fg.strftime("%d/%m %H:%M") if hasattr(fg, 'strftime') else str(fg)[:16]
                    except Exception:
                        fecha = str(fg)[:16]

                rows.append((
                    sec_id,
                    c.get("nombre_completo", ""),
                    c.get("codigo_cliente", ""),
                    c.get("distrito", ""),
                    f"S/ {float(c.get('importe_deuda_asignada', 0) or 0):,.2f}",
                    lbl,
                    (c.get("nota_gestor", "") or "")[:40],
                    fecha,
                ))
                raw.append({
                    "seccion_key": sec_id,
                    "codigo_cliente": c.get("codigo_cliente", c.get("_id", "")),
                    "nombre_completo": c.get("nombre_completo", ""),
                })
        return rows, raw

    def _apply_data(self, data, rows_and_raw):
        """Update KPIs in-place and refill Treeview in batches."""
        if not self._refresh_btn or not self._refresh_btn.winfo_exists():
            return
        self._refresh_btn.configure(state="normal", text="🔄 Actualizar")
        res = data["resumen"]

        rows, raw = rows_and_raw
        self._all_display_rows = rows
        self._all_raw_rows = raw
        self._monitor_page = 1

        # Update KPI values in-place (no widget destruction)
        kpi_vals = [
            str(res["total"]),
            str(res["pendiente"]),
            str(res["visitado_habido"]),
            str(res["visitado_no_habido"]),
            str(res["fallecido_inubicable"]),
            f"S/ {res['deuda_visitada']:,.0f}",
        ]
        for widget, val in zip(self._kpi_widgets, kpi_vals):
            widget.set(val)

        self._fill_monitor_page()

        avance = res["total"] - res["pendiente"]
        pct = round(avance / res["total"] * 100) if res["total"] else 0
        if self._status_lbl and self._status_lbl.winfo_exists():
            self._status_lbl.configure(
                text=f"Avance: {avance}/{res['total']} ({pct}%)  ·  Actualización cada 30s",
                text_color=SUCCESS if pct >= 50 else TEXT_SECONDARY)

        if self._auto_refresh and self._container and self._container.winfo_exists():
            self._after_id = self._container.after(30000, self._refresh)

    def _monitor_total_pages(self) -> int:
        total = len(self._all_display_rows)
        if not total:
            return 1
        return (total + _MONITOR_PAGE_SIZE - 1) // _MONITOR_PAGE_SIZE

    def _fill_monitor_page(self):
        if not self._tree or not self._tree.winfo_exists():
            return
        self._tree.delete(*self._tree.get_children())

        total = len(self._all_display_rows)
        total_pages = self._monitor_total_pages()
        if self._monitor_page > total_pages:
            self._monitor_page = total_pages
        if self._monitor_page < 1:
            self._monitor_page = 1

        start = (self._monitor_page - 1) * _MONITOR_PAGE_SIZE
        end = min(start + _MONITOR_PAGE_SIZE, total)
        page_rows = self._all_display_rows[start:end]
        self._row_data = self._all_raw_rows[start:end]
        self._refresh_monitor_pagination_ui(total, start, end, total_pages)
        self._insert_batch(page_rows, 0)

    def _refresh_monitor_pagination_ui(self, total: int, start: int, end: int, total_pages: int):
        if self._monitor_page_label and self._monitor_page_label.winfo_exists():
            self._monitor_page_label.configure(
                text=f"Página {self._monitor_page}/{total_pages}")
        if self._monitor_summary_label and self._monitor_summary_label.winfo_exists():
            if total:
                self._monitor_summary_label.configure(
                    text=f"Mostrando {start + 1}-{end} de {total} visitas "
                         f"({_MONITOR_PAGE_SIZE} por página).")
            else:
                self._monitor_summary_label.configure(text="Sin registros de visita.")
        if self._monitor_btn_prev and self._monitor_btn_prev.winfo_exists():
            self._monitor_btn_prev.configure(
                state="normal" if self._monitor_page > 1 else "disabled")
        if self._monitor_btn_next and self._monitor_btn_next.winfo_exists():
            self._monitor_btn_next.configure(
                state="normal" if self._monitor_page < total_pages else "disabled")

    def _monitor_prev_page(self):
        if self._monitor_page > 1:
            self._monitor_page -= 1
            self._fill_monitor_page()

    def _monitor_next_page(self):
        if self._monitor_page < self._monitor_total_pages():
            self._monitor_page += 1
            self._fill_monitor_page()

    def _insert_batch(self, rows, start):
        """Insert rows in batches with color tags based on status."""
        if not self._tree or not self._tree.winfo_exists():
            return
        end = min(start + _TREE_BATCH, len(rows))
        _tag_map = {
            "Habido":       "habido",
            "No Habido":    "no_habido",
            "Inubicable":   "inubicable",
            "Suplantación": "suplantacion",
            "Pago No Reg.": "pago_noreg",
        }
        total_inserted = len(self._tree.get_children())
        for i in range(start, end):
            estado_val = rows[i][5] if len(rows[i]) > 5 else ""
            tag = _tag_map.get(estado_val, "pendiente")
            # Alternating row color only for pendiente
            if tag == "pendiente" and total_inserted % 2 == 1:
                tag = "odd"
            self._tree.insert("", "end", values=rows[i], tags=(tag,))
            total_inserted += 1
        if end < len(rows):
            self._container.after(1, lambda: self._insert_batch(rows, end))

    def _on_error(self, msg):
        if self._refresh_btn and self._refresh_btn.winfo_exists():
            self._refresh_btn.configure(state="normal", text="🔄 Actualizar")
        if self._status_lbl and self._status_lbl.winfo_exists():
            self._status_lbl.configure(text=f"Error: {msg}", text_color=DANGER)

    # ── Zone Editing (double-click on client row) ─────────────────

    def _on_tree_dblclick(self, event):
        """Open zone-editing dialog when admin double-clicks a client row."""
        if not self.app._role_allows("upload"):
            return  # Only admin/supervisor

        item = self._tree.identify_row(event.y)
        if not item:
            return

        # Get the row index
        children = self._tree.get_children()
        try:
            idx = list(children).index(item)
        except ValueError:
            return

        if idx >= len(self._row_data):
            return

        info = self._row_data[idx]
        self._open_zone_edit_dialog(info)

    def _open_zone_edit_dialog(self, client_info: dict):
        """Show a dialog to change a client's zone/section."""
        seccion_key = client_info["seccion_key"]
        codigo = client_info["codigo_cliente"]
        nombre = client_info["nombre_completo"]

        # Load available sections from territorial catalog
        try:
            catalogo = self.app.firebase.get_estructura_territorial()
        except Exception:
            catalogo = {}

        available_keys = []
        for r, rdata in catalogo.items():
            for z, zdata in (rdata.get("zonas") or {}).items():
                for s in (zdata.get("secciones") or []):
                    available_keys.append(f"{r}_{z}_{s}")
        available_keys.sort()

        if not available_keys:
            messagebox.showinfo("Sin catálogo",
                "No se encontró el catálogo territorial.\n"
                "Suba una cartera primero para generar el catálogo.")
            return

        # Build dialog
        win = ctk.CTkToplevel(self._container)
        win.title("Editar Zona del Cliente")
        win.geometry("500x400")
        win.transient(self._container.winfo_toplevel())
        win.grab_set()

        # Content
        ctk.CTkLabel(win, text="Editar Zona / Sección",
                      font=font(16, "bold"), text_color=TEXT_PRIMARY).pack(pady=(20, 5))

        info_frame = ctk.CTkFrame(win, fg_color=CARD_BG, corner_radius=10)
        info_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(info_frame, text=nombre, font=font(13, "bold"),
                      text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(info_frame, text=f"Código: {codigo}",
                      font=font(11), text_color=TEXT_SECONDARY).pack(anchor="w", padx=12)
        ctk.CTkLabel(info_frame, text=f"Sección actual: {seccion_key}",
                      font=font(11), text_color=ACCENT).pack(anchor="w", padx=12, pady=(2, 8))

        ctk.CTkLabel(win, text="Nueva sección:", font=font(12),
                      text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(10, 4))

        # Filter/search for section
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(win, textvariable=search_var,
                                     placeholder_text="Buscar sección...",
                                     height=32, corner_radius=8)
        search_entry.pack(fill="x", padx=20, pady=(0, 6))

        # Listbox for sections (using Treeview as dropdown)
        list_frame = ctk.CTkFrame(win, fg_color="white", corner_radius=8,
                                   border_width=1, border_color=BORDER)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        lb = ttk.Treeview(list_frame, columns=("key",), show="headings", height=8,
                          style=apply_treeview_style("ZoneEdit.Treeview"))
        lb.heading("key", text="Sección (región_zona_letra)")
        lb.column("key", width=350)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def fill_list(*_):
            lb.delete(*lb.get_children())
            q = search_var.get().strip().lower()
            for k in available_keys:
                if k == seccion_key:
                    continue  # Skip current section
                if q and q not in k.lower():
                    continue
                lb.insert("", "end", values=(k,))

        fill_list()
        search_var.trace_add("write", fill_list)

        # Buttons
        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        status_lbl = ctk.CTkLabel(btn_frame, text="", font=font(11),
                                   text_color=DANGER)
        status_lbl.pack(side="left", padx=4)

        def do_save():
            sel = lb.selection()
            if not sel:
                status_lbl.configure(text="Seleccione una sección destino.")
                return
            new_key = lb.item(sel[0])["values"][0]
            if new_key == seccion_key:
                return

            ok = messagebox.askyesno(
                "Confirmar cambio de zona",
                f"¿Mover al cliente «{nombre}» (código {codigo})\n"
                f"de sección {seccion_key} → {new_key}?",
                parent=win)
            if not ok:
                return

            save_btn.configure(state="disabled", text="Guardando…")
            admin_email = getattr(self.app, "auth_result", None)
            email = admin_email.email if admin_email else ""
            admin_name = admin_email.nombre if admin_email else ""

            def _save():
                try:
                    result = self.app.firebase.update_client_zone(
                        campaign_id="cartera_activa",
                        current_seccion_key=seccion_key,
                        client_id=codigo,
                        new_seccion_key=new_key,
                        admin_email=email,
                        admin_name=admin_name,
                    )
                    if self._container and self._container.winfo_exists():
                        self._container.after(0, lambda: _on_save_result(result))
                except Exception as e:
                    if self._container and self._container.winfo_exists():
                        self._container.after(0, lambda: _on_save_result(
                            {"success": False, "error": str(e)}))

            def _on_save_result(result):
                if result.get("success"):
                    messagebox.showinfo("Zona actualizada",
                        f"Cliente movido correctamente a {new_key}.",
                        parent=win)
                    win.destroy()
                    self._refresh()
                else:
                    status_lbl.configure(text=result.get("error", "Error desconocido"))
                    save_btn.configure(state="normal", text="Guardar")

            threading.Thread(target=_save, daemon=True).start()

        ctk.CTkButton(btn_frame, text="Cancelar", fg_color=TEXT_SECONDARY,
                       hover_color="#64748B", width=100, height=32,
                       corner_radius=8, command=win.destroy).pack(side="right", padx=4)
        save_btn = ctk.CTkButton(btn_frame, text="Guardar", fg_color=ACCENT,
                                  hover_color=ACCENT_HOVER, width=100, height=32,
                                  corner_radius=8, command=do_save)
        save_btn.pack(side="right", padx=4)
