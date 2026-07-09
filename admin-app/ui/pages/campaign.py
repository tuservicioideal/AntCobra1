"""Campaign page — Excel loading, data view, distribution, tramo evaluation."""
from __future__ import annotations
import customtkinter as ctk
from tkinter import ttk
import threading
from typing import TYPE_CHECKING
from ..theme import *
from ..components import KPICard, SectionHeader

if TYPE_CHECKING:
    from ..app import App

# Batch size for deferred Treeview inserts
_TREE_BATCH = 80
_DETAIL_PAGE_SIZE = 50


class CampaignPage:
    """Campaign management: load Excel, view data, distribute, evaluate."""

    def __init__(self, app: App):
        self.app = app
        self._cached_hierarchy = None
        self._cached_sec_map = None
        self._cached_data_id = None  # id(parsed_data) to detect changes
        self._tree = None
        self._container = None
        self._detail_clients: list = []
        self._detail_page = 1
        self._detail_fill_gen = 0
        self._detail_summary_label = None
        self._detail_page_label = None
        self._detail_btn_prev = None
        self._detail_btn_next = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        # Recover in-memory data from local SQLite when reopening the app.
        if not self.app.parsed_data and self.app.active_campaign:
            try:
                restored = self.app.campaign_mgr.rebuild_parsed_data(self.app.active_campaign.id)
                if restored:
                    self.app.parsed_data = restored
            except Exception:
                pass

        if self.app.parsed_data:
            self._render_data(container)
        elif self.app.active_campaign:
            self._render_campaign_only(container)
        else:
            self._render_empty(container)

    def _render_empty(self, container):
        ctk.CTkFrame(container, fg_color="transparent", height=30).pack()

        card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=40)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=40)

        ctk.CTkLabel(inner, text="Gestión de Campaña",
                     font=font(20, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text="Cargue un archivo Excel para iniciar una nueva campaña de cobranza.",
                     font=font(13), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(4, 20))

        ctk.CTkButton(
            inner, text="Cargar archivo Excel", font=font(14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=44, width=240, corner_radius=10,
            command=self.app._on_load_excel
        ).pack(anchor="w")

    def _render_campaign_only(self, container):
        SectionHeader(container, "Campaña Activa",
                      "Los datos del Excel no están en memoria. Cargue el archivo nuevamente para ver los detalles."
                      ).pack(anchor="w", padx=8, pady=(8, 12))

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(anchor="w", padx=8, pady=8)

        ctk.CTkButton(
            btn_row, text="Cargar archivo Excel", font=font(13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=40, width=220, corner_radius=10,
            command=self.app._on_load_excel
        ).pack(side="left", padx=(0, 8))

        if self.app.firebase_connected and self.app._role_allows("upload"):
            ctk.CTkButton(
                btn_row, text="Aplicar Excel del banco y notificar", font=font(13, "bold"),
                fg_color="#0D9488", hover_color="#0F766E",
                height=40, width=300, corner_radius=10,
                command=self.app._on_update_base
            ).pack(side="left")

    def _ensure_cache(self, data):
        """Compute hierarchy/summary only when parsed_data changes."""
        from services.excel_parser import get_seccion_summary, get_hierarchy
        data_id = id(data)
        if self._cached_data_id == data_id and self._cached_hierarchy:
            return
        self._cached_hierarchy = get_hierarchy(data["all_clients"])
        secs = get_seccion_summary(data["by_seccion"])
        self._cached_sec_map = {s_item["seccion"]: s_item for s_item in secs}
        self._cached_data_id = data_id

    def _render_data(self, container):
        from services.excel_parser import make_seccion_key

        data = self.app.parsed_data
        s = data["summary"]
        by_sec = data["by_seccion"]

        self._ensure_cache(data)
        hierarchy = self._cached_hierarchy
        sec_map = self._cached_sec_map

        # ── Header + Actions ──
        hdr_row = ctk.CTkFrame(container, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(8, 12))

        title_col = ctk.CTkFrame(hdr_row, fg_color="transparent")
        title_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            title_col, text="Cartera Cargada",
            font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_col,
            text=f"{s['total_clientes']} clientes · {s['total_secciones']} secciones",
            font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        btn_frame = ctk.CTkFrame(hdr_row, fg_color="transparent")
        btn_frame.pack(side="right")

        _BTN_H = 36
        if self.app.firebase_connected and self.app._role_allows("upload"):
            ctk.CTkButton(
                btn_frame, text="Distribuir a Gestores", font=font(FONT_SCALE['sm'], "bold"),
                fg_color="#7C3AED", hover_color="#6D28D9",
                height=_BTN_H, corner_radius=8,
                command=self.app._on_upload,
            ).pack(side="left", padx=(0, 6))

        # ── KPIs ──
        kpi_row = ctk.CTkFrame(container, fg_color="transparent")
        kpi_row.pack(fill="x", padx=16, pady=(0, 12))
        kpi_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        kpis = [
            ("Clientes", str(s["total_clientes"]), ACCENT),
            ("Secciones", str(s["total_secciones"]), "#0D9488"),
            ("Deuda Total", f"S/ {s['total_deuda_asignada']:,.2f}", WARNING),
            ("Pendiente", f"S/ {s['total_deuda_pendiente']:,.2f}", DANGER),
        ]
        for i, (lbl, val, clr) in enumerate(kpis):
            KPICard(kpi_row, lbl, val, clr).grid(row=0, column=i,
                                                  padx=4, sticky="nsew")

        # ── Separador visual: cartera / estructura ──
        sep = ctk.CTkFrame(container, fg_color=BORDER, height=1)
        sep.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(
            container, text="Estructura: Región / Zona / Sección",
            font=font(FONT_SCALE['lg'], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(0, 6))

        for region_key, region_data in hierarchy["regions"].items():
            self._render_region(container, region_key, region_data,
                                sec_map, by_sec)

        # ── Detail Table ──
        ctk.CTkLabel(container, text="Vista Detallada",
                     font=font(FONT_SCALE['lg'], "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", padx=16, pady=(16, 6))

        self._render_table(container, data)

    # ── Cache helpers ────────────────────────────────────────
    def _render_region(self, container, region_key, region_data, sec_map, by_sec):
        from services.excel_parser import make_seccion_key

        r_frame = ctk.CTkFrame(container, fg_color=ACCENT_LIGHT,
                               corner_radius=10, border_width=1,
                               border_color=ACCENT_MUTED)
        r_frame.pack(fill="x", padx=8, pady=(6, 2))
        r_inner = ctk.CTkFrame(r_frame, fg_color="transparent")
        r_inner.pack(fill="x", padx=14, pady=8)

        # Collapse toggle
        toggle_var = {"open": False}
        body_frame = ctk.CTkFrame(container, fg_color="transparent")
        # Start collapsed — body is NOT packed

        def on_toggle():
            if toggle_var["open"]:
                body_frame.pack_forget()
                toggle_btn.configure(text="▶")
                toggle_var["open"] = False
            else:
                body_frame.pack(fill="x", after=r_frame)
                if not body_frame.winfo_children():
                    self._fill_region_body(body_frame, region_key,
                                           region_data, sec_map, by_sec)
                toggle_btn.configure(text="▼")
                toggle_var["open"] = True

        toggle_btn = ctk.CTkButton(
            r_inner, text="▶", width=28, height=28, corner_radius=6,
            fg_color="transparent", hover_color=ACCENT_MUTED,
            text_color=ACCENT, font=font(12, "bold"),
            command=on_toggle)
        toggle_btn.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(r_inner, text=f"Región {region_key}",
                     font=font(13, "bold"), text_color=ACCENT
                     ).pack(side="left")

        n_zonas = len(region_data["zonas"])
        ctk.CTkLabel(r_inner,
                     text=f"{region_data['num_clientes']} clientes  ·  "
                          f"{n_zonas} zona{'s' if n_zonas != 1 else ''}  ·  "
                          f"S/ {region_data['deuda_asignada']:,.2f}",
                     font=font(11), text_color=TEXT_SECONDARY
                     ).pack(side="right")

    def _fill_region_body(self, body, region_key, region_data, sec_map, by_sec):
        """Lazily populate zonas/sections when a region is expanded."""
        from services.excel_parser import make_seccion_key

        for zona_key, zona_data in sorted(region_data["zonas"].items()):
            z_frame = ctk.CTkFrame(body, fg_color="#F0FDFA",
                                   corner_radius=8, border_width=1,
                                   border_color="#99F6E4")
            z_frame.pack(fill="x", pady=(2, 1), padx=(24, 8))
            z_inner = ctk.CTkFrame(z_frame, fg_color="transparent")
            z_inner.pack(fill="x", padx=12, pady=6)
            ctk.CTkLabel(z_inner, text=f"Zona {zona_key}",
                         font=font(12, "bold"), text_color="#0D9488"
                         ).pack(side="left")
            ctk.CTkLabel(z_inner,
                         text=f"{zona_data['num_clientes']} clientes  ·  S/ {zona_data['deuda_asignada']:,.2f}",
                         font=font(10), text_color=TEXT_SECONDARY
                         ).pack(side="right")

            for sec_key in sorted(zona_data["secciones"].keys()):
                composite = make_seccion_key(region_key, zona_key, sec_key)
                sec_info = sec_map.get(composite)
                if not sec_info:
                    continue
                clients = by_sec.get(composite, [])
                self._render_section(body, sec_info, clients)

    def _render_section(self, container, sec, clients):
        card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=2, padx=(44, 8))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=8)

        seccion_badge = sec.get("seccion_letra", sec["seccion"])
        badge = ctk.CTkFrame(hdr, fg_color=ACCENT, corner_radius=6,
                             width=32, height=28)
        badge.pack(side="left", padx=(0, 10))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=seccion_badge, font=font(12, "bold"),
                     text_color=WHITE).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(hdr, text=f"{sec['num_clientes']} clientes",
                     font=font(12, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left")
        ctk.CTkLabel(hdr, text=f"  —  {sec['departamentos']}",
                     font=font(10), text_color=TEXT_SECONDARY
                     ).pack(side="left", padx=4)
        ctk.CTkLabel(hdr, text=f"S/ {sec['deuda_asignada']:,.2f}",
                     font=font(12, "bold"), text_color=ACCENT
                     ).pack(side="right")

        # Show first few clients
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 6))
        for i, c in enumerate(clients[:5]):
            if i == 0:
                ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill="x", padx=12)
            bg = CARD_BG if i % 2 == 0 else "#F8FAFC"
            row_f = ctk.CTkFrame(body, fg_color=bg, corner_radius=0, height=28)
            row_f.pack(fill="x")
            row_f.pack_propagate(False)
            nombre = c.get("nombre_completo", "—")
            deuda = float(c.get("importe_deuda_asignada", 0) or 0)
            ctk.CTkLabel(row_f, text=f"  {nombre}", font=font(10),
                         text_color=TEXT_PRIMARY, anchor="w"
                         ).pack(side="left", fill="x", expand=True, padx=4)
            ctk.CTkLabel(row_f, text=f"S/ {deuda:,.2f}", font=font(10, "bold"),
                         text_color=TEXT_SECONDARY).pack(side="right", padx=8)

        if len(clients) > 5:
            ctk.CTkLabel(body, text=f"  +{len(clients) - 5} más…",
                         font=font(10), text_color=TEXT_MUTED
                         ).pack(anchor="w", padx=4, pady=2)

    def _render_table(self, container, data):
        tf = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tf.pack(fill="x", padx=8, pady=4)

        cols = ("region", "zona", "seccion", "nombre", "dni", "telefono",
                "departamento", "distrito", "dias_atraso",
                "deuda_asignada", "deuda_pendiente")
        hdrs = {"region": "Región", "zona": "Zona", "seccion": "Secc.",
                "nombre": "Nombre", "dni": "DNI",
                "telefono": "Teléfono", "departamento": "Depto.",
                "distrito": "Distrito", "dias_atraso": "Días",
                "deuda_asignada": "Deuda", "deuda_pendiente": "Pendiente"}

        style_name = apply_treeview_style("Campaign.Treeview")

        self._detail_clients = data["all_clients"]
        self._detail_page = 1

        self._tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style=style_name, height=18)
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            w = 180 if c == "nombre" else 100
            self._tree.column(c, width=w, minwidth=60)

        sb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        pag = ctk.CTkFrame(tf, fg_color="transparent")
        pag.pack(fill="x", padx=12, pady=(0, 8))

        self._detail_summary_label = ctk.CTkLabel(
            pag, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._detail_summary_label.pack(side="left")

        ctrl = ctk.CTkFrame(pag, fg_color="transparent")
        ctrl.pack(side="right")

        self._detail_btn_prev = ctk.CTkButton(
            ctrl, text="◀ Anterior", width=100, height=32,
            fg_color=TEXT_SECONDARY, hover_color="#475569",
            command=self._detail_prev_page)
        self._detail_btn_prev.pack(side="left", padx=(0, 8))

        self._detail_page_label = ctk.CTkLabel(
            ctrl, text="Página 1/1", font=font(12, "bold"))
        self._detail_page_label.pack(side="left", padx=(0, 8))

        self._detail_btn_next = ctk.CTkButton(
            ctrl, text="Siguiente ▶", width=100, height=32,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._detail_next_page)
        self._detail_btn_next.pack(side="left")

        self._fill_detail_page()

    def _detail_total_pages(self) -> int:
        total = len(self._detail_clients)
        if not total:
            return 1
        return (total + _DETAIL_PAGE_SIZE - 1) // _DETAIL_PAGE_SIZE

    def _fill_detail_page(self):
        if not self._tree or not self._tree.winfo_exists():
            return
        self._detail_fill_gen += 1
        gen = self._detail_fill_gen
        self._tree.delete(*self._tree.get_children())

        total = len(self._detail_clients)
        total_pages = self._detail_total_pages()
        if self._detail_page > total_pages:
            self._detail_page = total_pages
        if self._detail_page < 1:
            self._detail_page = 1

        start = (self._detail_page - 1) * _DETAIL_PAGE_SIZE
        end = min(start + _DETAIL_PAGE_SIZE, total)
        page_clients = self._detail_clients[start:end]
        self._refresh_detail_pagination_ui(total, start, end, total_pages)
        self._deferred_tree_fill(page_clients, gen)

    def _refresh_detail_pagination_ui(self, total: int, start: int, end: int, total_pages: int):
        if self._detail_page_label and self._detail_page_label.winfo_exists():
            self._detail_page_label.configure(
                text=f"Página {self._detail_page}/{total_pages}")
        if self._detail_summary_label and self._detail_summary_label.winfo_exists():
            if total:
                self._detail_summary_label.configure(
                    text=f"Mostrando {start + 1}-{end} de {total} clientes "
                         f"({_DETAIL_PAGE_SIZE} por página).")
            else:
                self._detail_summary_label.configure(text="Sin clientes en la cartera.")
        if self._detail_btn_prev and self._detail_btn_prev.winfo_exists():
            self._detail_btn_prev.configure(
                state="normal" if self._detail_page > 1 else "disabled")
        if self._detail_btn_next and self._detail_btn_next.winfo_exists():
            self._detail_btn_next.configure(
                state="normal" if self._detail_page < total_pages else "disabled")

    def _detail_prev_page(self):
        if self._detail_page > 1:
            self._detail_page -= 1
            self._fill_detail_page()

    def _detail_next_page(self):
        if self._detail_page < self._detail_total_pages():
            self._detail_page += 1
            self._fill_detail_page()

    def _deferred_tree_fill(self, clients, gen: int):
        """Pre-compute row values on a thread, insert in batches to keep UI responsive."""
        def prepare():
            rows = []
            for cl in clients:
                rows.append((
                    cl.get("region", ""), cl.get("zona", ""),
                    cl.get("seccion", ""), cl.get("nombre_completo", ""),
                    cl.get("numero_documento", ""), cl.get("telefono_movil", ""),
                    cl.get("departamento", ""), cl.get("distrito", ""),
                    cl.get("dias_atraso", ""),
                    f"S/ {float(cl.get('importe_deuda_asignada', 0) or 0):,.2f}",
                    f"S/ {float(cl.get('importe_deuda_pendiente', 0) or 0):,.2f}",
                ))
            if self._container and self._container.winfo_exists():
                self._container.after(
                    0, lambda: self._insert_batch(rows, 0, gen))

        threading.Thread(target=prepare, daemon=True).start()

    def _insert_batch(self, rows, start, gen: int):
        """Insert a batch of rows into the Treeview, schedule next batch."""
        if gen != self._detail_fill_gen:
            return
        if not self._tree or not self._tree.winfo_exists():
            return
        end = min(start + _TREE_BATCH, len(rows))
        for i in range(start, end):
            self._tree.insert("", "end", values=rows[i])
        if end < len(rows):
            self._container.after(1, lambda: self._insert_batch(rows, end, gen))
