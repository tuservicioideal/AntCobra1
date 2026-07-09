"""Local database browser page (SQLite source of truth, paginated)."""
from __future__ import annotations

import threading
from datetime import datetime

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from typing import TYPE_CHECKING, Any

from services.campana_banco_utils import display_label_for_key
from ..theme import *
from ..components import SectionHeader

if TYPE_CHECKING:
    from ..app import App


_FICHA_SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Identificación", [
        ("codigo_cliente", "Código"),
        ("digito_control", "Dígito control"),
        ("numero_documento", "DNI"),
        ("nombres", "Nombres"),
        ("apellido_paterno", "Ap. paterno"),
        ("apellido_materno", "Ap. materno"),
        ("nombre_completo", "Nombre completo"),
        ("genero", "Género"),
        ("edad", "Edad"),
    ]),
    ("Contacto", [
        ("telefono_fijo", "Tel. fijo"),
        ("telefono_trabajo", "Tel. trabajo"),
        ("telefono_movil", "Tel. móvil"),
        ("correo", "Correo"),
        ("ultima_nota_contacto", "Última nota contacto"),
        ("fecha_actualizacion_contacto_iso", "Actualización contacto"),
        ("actualizado_por_nombre", "Actualizado por"),
        ("origen_actualizacion", "Origen"),
    ]),
    ("Ubicación", [
        ("direccion", "Dirección (banco)"),
        ("referencia", "Referencia"),
        ("departamento", "Departamento"),
        ("provincia", "Provincia"),
        ("distrito", "Distrito"),
        ("coordenada_x", "Longitud"),
        ("coordenada_y", "Latitud"),
        ("ubicacion_verificada_lat", "GPS verificado (lat)"),
        ("ubicacion_verificada_lng", "GPS verificado (lng)"),
        ("ubicacion_verificada_fecha", "GPS verificado (fecha)"),
        ("ubicacion_verificada_gestor", "GPS verificado (gestor)"),
    ]),
    ("Cartera", [
        ("region", "Región"),
        ("zona", "Zona"),
        ("seccion", "Sección"),
        ("territorio", "Territorio"),
        ("segmentacion", "Segmentación"),
        ("segmento_cartera", "Segmento cartera"),
        ("etapa_deuda", "Etapa deuda"),
        ("dias_atraso", "Días atraso"),
        ("importe_deuda_original", "Deuda original"),
        ("importe_deuda_asignada", "Deuda asignada"),
        ("importe_deuda_pendiente", "Deuda pendiente"),
        ("tramo_actual", "Tramo"),
    ]),
    ("Gestión", [
        ("estado_gestion", "Estado gestión"),
        ("nota_gestor", "Nota gestor"),
        ("fecha_gestion", "Fecha gestión"),
        ("gps_latitud", "GPS lat"),
        ("gps_longitud", "GPS lng"),
        ("nivel_1", "Nivel 1"),
        ("nivel_2", "Nivel 2"),
        ("nivel_3", "Nivel 3"),
        ("nivel_4", "Nivel 4"),
        ("canal_gestion", "Canal"),
        ("fecha_promesa_pago", "Fecha promesa"),
        ("monto_promesa_pago", "Monto promesa"),
    ]),
]


class DatabasePage:
    """Browse local clients with server-side pagination and client history."""

    def __init__(self, app: "App"):
        self.app = app
        self._container = None
        self._tree = None
        self._page = 1
        self._page_size = 100
        self._total_pages = 1
        self._total = 0
        self._page_label = None
        self._summary_label = None
        self._btn_prev = None
        self._btn_next = None
        self._search_var = ctk.StringVar(value="")
        self._estado_var = ctk.StringVar(value="(Todos)")
        self._region_var = ctk.StringVar(value="(Todas)")
        self._zona_var = ctk.StringVar(value="(Todas)")
        self._seccion_var = ctk.StringVar(value="(Todas)")
        self._campana_banco_var = ctk.StringVar(value="(Todas)")
        self._carta_pub_var = ctk.StringVar(value="(Todas)")
        self._formato_pub_var = ctk.StringVar(value="(Todos)")
        self._estado_pub_var = ctk.StringVar(value="(Todos)")
        self._gestor_pub_var = ctk.StringVar(value="(Todos)")
        self._estado_menu = None
        self._region_menu = None
        self._zona_menu = None
        self._seccion_menu = None
        self._campana_banco_menu = None
        self._campana_banco_label_to_key: dict[str, str] = {}
        self._carta_pub_menu = None
        self._formato_pub_menu = None
        self._estado_pub_menu = None
        self._gestor_pub_menu = None
        self._detail_box = None
        self._code_by_item: dict[str, str] = {}
        self._selected_code: str | None = None
        self._sync_status = None
        self._contact_phone_var = ctk.StringVar(value="")
        self._contact_addr_var = ctk.StringVar(value="")
        self._contact_note_var = ctk.StringVar(value="")
        self._usar_principal_var = ctk.BooleanVar(value=False)
        self._detail_popup: ctk.CTkToplevel | None = None
        self._filters_popup: ctk.CTkToplevel | None = None
        self._contact_popup: ctk.CTkToplevel | None = None
        self._filters_btn = None
        self._contact_btn = None
        self._etiquetas_btn = None
        self._browse_campana_id: str | None = None
        self._campaign_var = ctk.StringVar(value="")
        self._campaign_menu = None
        self._campaign_label_to_id: dict[str, str] = {}
        self._storage_label = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        SectionHeader(
            container,
            "Base de Datos de Clientes",
            "Datos persistentes en SQLite. Se conservan aunque no haya campaña activa.",
        ).pack(anchor="w", padx=8, pady=(8, 12))

        self._render_storage_banner(container)

        campaigns = self.app.campaign_mgr.list_campaigns()
        self._browse_campana_id = self.app.campaign_mgr.resolve_browse_campaign_id(
            self._browse_campana_id
        )

        if not self._browse_campana_id:
            ctk.CTkLabel(
                container,
                text="No hay campañas almacenadas en la base local. Cargue un Excel o restaure desde la nube.",
                font=font(13),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=12, pady=12)
            self._render_data_tools(container, compact=True)
            return

        camp_row = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=10, border_width=1, border_color=BORDER)
        camp_row.pack(fill="x", padx=8, pady=(0, 8))
        inner_camp = ctk.CTkFrame(camp_row, fg_color="transparent")
        inner_camp.pack(fill="x", padx=12, pady=10)

        ctk.CTkLabel(
            inner_camp,
            text="Campaña almacenada:",
            font=font(12, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=(0, 8))

        labels, mapping = self._campaign_options(campaigns)
        self._campaign_label_to_id = mapping
        current_label = self._label_for_campaign_id(self._browse_campana_id, campaigns)
        self._campaign_var.set(current_label)
        self._campaign_menu = ctk.CTkOptionMenu(
            inner_camp,
            values=labels,
            variable=self._campaign_var,
            width=420,
            height=32,
            command=self._on_campaign_change,
        )
        self._campaign_menu.pack(side="left", padx=(0, 12))

        if not self.app.active_campaign:
            ctk.CTkLabel(
                inner_camp,
                text="Sin campaña activa — mostrando datos guardados",
                font=font(11),
                text_color=WARNING,
            ).pack(side="left")

        self._render_data_tools(container, compact=False)

        top = ctk.CTkFrame(container, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(0, 8))

        self._summary_label = ctk.CTkLabel(
            top, text="", font=font(12), text_color=TEXT_SECONDARY
        )
        self._summary_label.pack(side="left")

        ctrl = ctk.CTkFrame(top, fg_color="transparent")
        ctrl.pack(side="right")

        ctk.CTkButton(
            ctrl,
            text="Sincronizar visitas",
            width=140,
            height=32,
            fg_color=SUCCESS,
            hover_color="#16a34a",
            command=self._sync_visits_now,
        ).pack(side="left", padx=(0, 8))

        self._sync_status = ctk.CTkLabel(ctrl, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._sync_status.pack(side="left", padx=(0, 8))

        self._btn_prev = ctk.CTkButton(
            ctrl,
            text="◀ Anterior",
            width=100,
            height=32,
            fg_color=TEXT_SECONDARY,
            hover_color="#475569",
            command=self._prev_page,
        )
        self._btn_prev.pack(side="left", padx=(0, 8))

        self._page_label = ctk.CTkLabel(ctrl, text="Página 1/1", font=font(12, "bold"))
        self._page_label.pack(side="left", padx=(0, 8))

        self._btn_next = ctk.CTkButton(
            ctrl,
            text="Siguiente ▶",
            width=100,
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._next_page,
        )
        self._btn_next.pack(side="left")

        filters = ctk.CTkFrame(container, fg_color="transparent")
        filters.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(filters, text="Buscar:", font=font(12)).pack(side="left", padx=(0, 6))
        search_entry = ctk.CTkEntry(
            filters,
            textvariable=self._search_var,
            width=280,
            height=32,
            placeholder_text="Código, nombre o DNI",
        )
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<Return>", lambda _e: self._apply_filters())

        ctk.CTkButton(
            filters,
            text="Filtrar",
            width=90,
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._apply_filters,
        ).pack(side="left", padx=(0, 8))

        self._filters_btn = ctk.CTkButton(
            filters,
            text="Filtros",
            width=110,
            height=32,
            fg_color=TEXT_SECONDARY,
            hover_color="#475569",
            command=self._open_filters_dialog,
        )
        self._filters_btn.pack(side="left", padx=(0, 12))

        self._estado_menu = None
        self._region_menu = None
        self._zona_menu = None
        self._seccion_menu = None
        self._campana_banco_menu = None
        self._carta_pub_menu = None
        self._formato_pub_menu = None
        self._estado_pub_menu = None
        self._gestor_pub_menu = None

        table = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER)
        table.pack(fill="x", padx=8, pady=4)
        tree_wrap = ctk.CTkFrame(table, fg_color="transparent")
        tree_wrap.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        cols = (
            "codigo", "nombre", "dni", "campana_banco", "telefono", "direccion",
            "region", "zona", "seccion", "estado", "fecha_gestion", "origen",
        )
        hdrs = {
            "codigo": "Código",
            "nombre": "Nombre",
            "dni": "DNI",
            "campana_banco": "Nº Campaña",
            "telefono": "Teléfono",
            "direccion": "Dirección",
            "region": "Región",
            "zona": "Zona",
            "seccion": "Sección",
            "estado": "Estado",
            "fecha_gestion": "Últ. gestión",
            "origen": "Origen",
        }

        style_name = apply_treeview_style("DB.Treeview")
        self._tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", style=style_name, height=22)
        widths = {
            "codigo": 90, "nombre": 150, "dni": 85, "campana_banco": 90,
            "telefono": 95, "direccion": 120,
            "region": 70, "zona": 70, "seccion": 60, "estado": 90,
            "fecha_gestion": 110, "origen": 70,
        }
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            self._tree.column(c, width=widths.get(c, 100), minwidth=50, stretch=True)

        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y", padx=(8, 0))
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Button-1>", self._on_tree_click, add="+")
        self._tree.bind("<Double-1>", self._on_tree_double_click, add="+")

        ctk.CTkLabel(
            table,
            text="Clic en el nombre o doble clic en la fila para abrir la ficha completa del cliente.",
            font=font(11),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        detail = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER)
        detail.pack(fill="x", padx=8, pady=(8, 4))

        detail_actions = ctk.CTkFrame(detail, fg_color="transparent")
        detail_actions.pack(fill="x", padx=12, pady=(10, 6))

        self._contact_btn = ctk.CTkButton(
            detail_actions,
            text="Registrar dato de campo",
            width=180,
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            state="disabled",
            command=self._open_contact_dialog,
        )
        self._contact_btn.pack(side="right", padx=(8, 0))

        self._etiquetas_btn = ctk.CTkButton(
            detail_actions,
            text="Editar etiquetas",
            width=140,
            height=32,
            state="disabled",
            command=self._open_etiquetas_dialog,
        )
        self._etiquetas_btn.pack(side="right")

        self._detail_box = ctk.CTkTextbox(detail, height=240, wrap="word")
        self._detail_box.pack(fill="x", padx=12, pady=(0, 12))
        self._detail_box.insert("1.0", "Seleccione un cliente para ver ficha, direcciones conocidas e historial.")
        self._detail_box.configure(state="disabled")

        self._load_filter_options()
        self._load_page(1)
        self._update_filters_btn()

    def _get_browse_campana_id(self) -> str | None:
        return self._browse_campana_id or self.app.campaign_mgr.resolve_browse_campaign_id()

    def _campaign_options(self, campaigns: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
        labels: list[str] = []
        mapping: dict[str, str] = {}
        estado_labels = {
            "activa": "activa",
            "cerrada": "cerrada",
            "pausada": "pausada",
        }
        for c in campaigns:
            estado = estado_labels.get(str(c.get("estado", "")), str(c.get("estado", "")))
            label = (
                f"{c.get('nombre', c.get('id', ''))} ({estado}) · "
                f"{c.get('total_clientes', 0)} clientes"
            )
            labels.append(label)
            mapping[label] = str(c["id"])
        return labels, mapping

    def _label_for_campaign_id(self, campana_id: str, campaigns: list[dict[str, Any]]) -> str:
        labels, mapping = self._campaign_options(campaigns)
        for label, cid in mapping.items():
            if cid == campana_id:
                return label
        return labels[0] if labels else ""

    def _format_bytes(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _render_storage_banner(self, container):
        info = self.app.campaign_mgr.db.get_storage_info()
        path = info.get("path", "")
        size_txt = self._format_bytes(int(info.get("size_bytes") or 0))
        text = (
            f"Archivo SQLite: {path} · {size_txt} · "
            f"{info.get('campaign_count', 0)} campaña(s) · "
            f"{info.get('client_count', 0)} cliente(s)"
        )
        banner = ctk.CTkFrame(container, fg_color=ACCENT_LIGHT, corner_radius=8)
        banner.pack(fill="x", padx=8, pady=(0, 8))
        self._storage_label = ctk.CTkLabel(
            banner,
            text=text,
            font=font(11),
            text_color=TEXT_SECONDARY,
            wraplength=980,
            justify="left",
        )
        self._storage_label.pack(anchor="w", padx=12, pady=8)

    def _render_data_tools(self, container, *, compact: bool):
        tools = ctk.CTkFrame(container, fg_color="transparent")
        tools.pack(fill="x", padx=8, pady=(0, 8 if compact else 4))

        ctk.CTkButton(
            tools,
            text="Exportar base SQLite",
            width=150,
            height=32,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._export_sqlite,
        ).pack(side="left", padx=(0, 8))

        if not compact:
            ctk.CTkButton(
                tools,
                text="Exportar campaña Excel",
                width=170,
                height=32,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                command=self._export_campaign_excel,
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                tools,
                text="Eliminar campaña",
                width=140,
                height=32,
                fg_color=WARNING,
                hover_color=WARNING_HOVER,
                command=self._delete_selected_campaign,
            ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            tools,
            text="Vaciar base local",
            width=140,
            height=32,
            fg_color=DANGER,
            hover_color=DANGER_HOVER,
            command=self._delete_all_local,
        ).pack(side="left")

    def _refresh_storage_banner(self):
        if not self._storage_label or not self._storage_label.winfo_exists():
            return
        info = self.app.campaign_mgr.db.get_storage_info()
        path = info.get("path", "")
        size_txt = self._format_bytes(int(info.get("size_bytes") or 0))
        self._storage_label.configure(
            text=(
                f"Archivo SQLite: {path} · {size_txt} · "
                f"{info.get('campaign_count', 0)} campaña(s) · "
                f"{info.get('client_count', 0)} cliente(s)"
            )
        )

    def _on_campaign_change(self, selected_label: str):
        campana_id = self._campaign_label_to_id.get(selected_label)
        if not campana_id:
            return
        self._browse_campana_id = campana_id
        self._selected_code = None
        self._load_filter_options()
        self._load_page(1)
        self._set_detail_text("Seleccione un cliente para ver ficha, direcciones conocidas e historial.")
        self._update_contact_btn()

    def _export_sqlite(self):
        info = self.app.campaign_mgr.db.get_storage_info()
        if not info.get("exists"):
            messagebox.showwarning("Exportar", "No existe archivo de base de datos local.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"antcobranzas_{timestamp}.db"
        path = filedialog.asksaveasfilename(
            title="Exportar base SQLite",
            defaultextension=".db",
            initialfile=default_name,
            filetypes=[("SQLite", "*.db"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            written = self.app.campaign_mgr.db.export_database_file(path)
            messagebox.showinfo("Exportar", f"Base de datos exportada en:\n{written}")
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo exportar la base:\n{e}")

    def _export_campaign_excel(self):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            messagebox.showwarning("Exportar", "No hay campaña almacenada para exportar.")
            return
        campaigns = {c["id"]: c for c in self.app.campaign_mgr.list_campaigns()}
        camp = campaigns.get(campana_id, {})
        nombre = str(camp.get("nombre", campana_id)).replace(" ", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Gestion_{nombre}_{timestamp}.xlsx"
        path = filedialog.asksaveasfilename(
            title="Exportar campaña a Excel",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        def work():
            try:
                from services.excel_exporter import export_gestion_excel
                clients = self.app.campaign_mgr.get_all_clients(campana_id)
                export_gestion_excel(clients, path, nombre_proveedor="PERECAUDOL")
                msg = path
            except Exception as e:
                msg = None
                err = str(e)

            def done():
                if msg:
                    messagebox.showinfo("Exportar", f"Excel generado en:\n{msg}")
                else:
                    messagebox.showerror("Exportar", f"No se pudo exportar:\n{err}")

            if self.app.winfo_exists():
                self.app.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _delete_selected_campaign(self):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            messagebox.showwarning("Eliminar", "No hay campaña seleccionada.")
            return
        campaigns = {c["id"]: c for c in self.app.campaign_mgr.list_campaigns()}
        camp = campaigns.get(campana_id, {})
        nombre = camp.get("nombre", campana_id)
        n_clients = camp.get("total_clientes", 0)
        if not messagebox.askyesno(
            "Eliminar campaña",
            f"Se eliminará la campaña almacenada:\n\n"
            f"• {nombre}\n"
            f"• {n_clients} cliente(s) y su historial local\n\n"
            f"No se modificará Firebase.\n\n¿Continuar?",
            icon="warning",
        ):
            return

        try:
            result = self.app.campaign_mgr.delete_campaign_local(campana_id)
        except Exception as e:
            messagebox.showerror("Eliminar", str(e))
            return

        if self.app.active_campaign and getattr(self.app.active_campaign, "id", None) == campana_id:
            self.app.active_campaign = None
            self.app.parsed_data = None
            self.app._update_campaign_bar()

        self._browse_campana_id = None
        self._selected_code = None
        messagebox.showinfo(
            "Eliminar",
            f"Campaña eliminada.\n\nClientes eliminados: {result.get('clients_deleted', 0)}",
        )
        self.app._invalidate_pages()

    def _delete_all_local(self):
        if not messagebox.askyesno(
            "Vaciar base local",
            "Se eliminarán TODOS los datos de la base local:\n\n"
            "• Campañas, clientes, historial y logs\n"
            "• No se tocará Firebase\n\n"
            "Esta acción NO se puede deshacer.\n\n¿Continuar?",
            icon="warning",
        ):
            return

        dialog = ctk.CTkInputDialog(
            text="Escriba ELIMINAR LOCAL para confirmar:",
            title="Confirmación final",
        )
        typed = (dialog.get_input() or "").strip().upper()
        if typed != "ELIMINAR LOCAL":
            messagebox.showinfo("Cancelado", "Operación cancelada: confirmación no válida.")
            return

        try:
            result = self.app.campaign_mgr.delete_all_local_data()
        except Exception as e:
            messagebox.showerror("Eliminar", str(e))
            return

        self.app.active_campaign = None
        self.app.parsed_data = None
        self._browse_campana_id = None
        self._selected_code = None
        self.app._invalidate_pages()
        messagebox.showinfo(
            "Base local vaciada",
            f"Local: {result.get('local_campaigns_deleted', 0)} campaña(s), "
            f"{result.get('local_clients_deleted', 0)} cliente(s), "
            f"{result.get('local_sync_logs_deleted', 0)} log(s)\n"
            f"Firebase: sin cambios",
        )

    def _truncate(self, text: str, max_len: int = 40) -> str:
        t = (text or "").strip()
        if len(t) <= max_len:
            return t
        return t[: max_len - 1] + "…"

    def _sync_visits_now(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Sync", "Conecte Firebase primero.")
            return
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            messagebox.showwarning("Sync", "No hay campaña almacenada para sincronizar.")
            return
        if self._sync_status and self._sync_status.winfo_exists():
            self._sync_status.configure(text="Sincronizando…")

        def work():
            try:
                visit_data = self.app.firebase.pull_visit_data("cartera_activa")
                updated = self.app.campaign_mgr.sync_visits_from_firebase(
                    campana_id=campana_id,
                    firebase_data=visit_data,
                )
                msg = f"OK: {updated} clientes actualizados"
            except Exception as e:
                msg = f"Error: {e}"

            def done():
                if self._sync_status and self._sync_status.winfo_exists():
                    self._sync_status.configure(text=msg)
                self._refresh_storage_banner()
                self._load_page(self._page)
                if self._selected_code:
                    self._refresh_detail(self._selected_code)

            if self.app.winfo_exists():
                self.app.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _save_contact_update(self, *, close_popup: bool = False):
        campana_id = self._get_browse_campana_id()
        if not campana_id or not self._selected_code:
            messagebox.showinfo("Contacto", "Seleccione un cliente primero.")
            return
        try:
            auth = getattr(self.app, "auth_result", None)
            self.app.campaign_mgr.save_client_contact_update(
                campana_id,
                self._selected_code,
                telefono_nuevo=self._contact_phone_var.get(),
                direccion_nueva=self._contact_addr_var.get(),
                nota=self._contact_note_var.get(),
                usar_como_principal=bool(self._usar_principal_var.get()),
                editor_nombre=str(getattr(auth, "nombre", None) or "Admin"),
                editor_email=str(getattr(auth, "email", None) or ""),
                editor_uid=str(getattr(auth, "uid", None) or ""),
            )
            self._contact_phone_var.set("")
            self._contact_addr_var.set("")
            self._contact_note_var.set("")
            self._usar_principal_var.set(False)
            self._refresh_detail(self._selected_code)
            if close_popup and self._contact_popup and self._contact_popup.winfo_exists():
                self._contact_popup.destroy()
                self._contact_popup = None
            messagebox.showinfo("Contacto", "Dato registrado correctamente.")
        except Exception as e:
            messagebox.showerror("Contacto", str(e))

    def _load_page(self, page: int):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            return
        self._code_by_item = {}
        payload = self.app.campaign_mgr.get_clients_page(
            campana_id,
            page=page,
            page_size=self._page_size,
            search=self._search_var.get().strip(),
            estado=self._estado_value(),
            region=self._region_value(),
            zona=self._zona_value(),
            seccion=self._seccion_value(),
            campana_banco=self._campana_banco_value(),
            carta_numero=self._carta_publicacion_value(),
            formato_publicacion=self._formato_publicacion_value(),
            estado_publicacion=self._estado_publicacion_value(),
            gestor_publicacion=self._gestor_publicacion_value(),
        )

        self._page = payload["page"]
        self._total_pages = payload["total_pages"]
        self._total = payload["total"]

        if self._tree and self._tree.winfo_exists():
            self._tree.delete(*self._tree.get_children())
            for c in payload["items"]:
                fg = c.get("fecha_gestion", "") or ""
                if fg and "T" in str(fg):
                    fg = str(fg)[:16].replace("T", " ")
                item_id = self._tree.insert(
                    "",
                    "end",
                    values=(
                        c.get("codigo_cliente", ""),
                        c.get("nombre_completo", ""),
                        c.get("numero_documento", ""),
                        c.get("campana_banco", "") or "—",
                        c.get("telefono_movil", ""),
                        self._truncate(str(c.get("direccion", "")), 35),
                        c.get("region", ""),
                        c.get("zona", ""),
                        c.get("seccion", ""),
                        c.get("estado_gestion", "pendiente"),
                        fg,
                        c.get("origen_actualizacion", "") or "",
                    ),
                )
                self._code_by_item[item_id] = str(c.get("codigo_cliente", ""))

        self._refresh_pagination_ui()

    def _refresh_pagination_ui(self):
        if self._page_label and self._page_label.winfo_exists():
            self._page_label.configure(text=f"Página {self._page}/{self._total_pages}")
        if self._summary_label and self._summary_label.winfo_exists():
            start = (self._page - 1) * self._page_size + 1 if self._total else 0
            end = min(self._page * self._page_size, self._total)
            browse_note = ""
            if not self.app.active_campaign and self._browse_campana_id:
                browse_note = " · datos almacenados (sin campaña activa)"
            self._summary_label.configure(
                text=f"Mostrando {start}-{end} de {self._total} clientes{browse_note}."
            )
        if self._btn_prev and self._btn_prev.winfo_exists():
            self._btn_prev.configure(state="normal" if self._page > 1 else "disabled")
        if self._btn_next and self._btn_next.winfo_exists():
            self._btn_next.configure(state="normal" if self._page < self._total_pages else "disabled")

    def _prev_page(self):
        if self._page > 1:
            self._load_page(self._page - 1)

    def _next_page(self):
        if self._page < self._total_pages:
            self._load_page(self._page + 1)

    def _apply_filters(self):
        self._load_page(1)
        self._update_filters_btn()

    def _active_filter_count(self) -> int:
        count = 0
        if self._estado_var.get() not in ("", "(Todos)"):
            count += 1
        if self._region_var.get() not in ("", "(Todas)"):
            count += 1
        if self._zona_var.get() not in ("", "(Todas)"):
            count += 1
        if self._seccion_var.get() not in ("", "(Todas)"):
            count += 1
        if self._campana_banco_var.get() not in ("", "(Todas)"):
            count += 1
        if self._carta_pub_var.get() not in ("", "(Todas)"):
            count += 1
        if self._formato_pub_var.get() not in ("", "(Todos)"):
            count += 1
        if self._estado_pub_var.get() not in ("", "(Todos)"):
            count += 1
        if self._gestor_pub_var.get() not in ("", "(Todos)"):
            count += 1
        return count

    def _update_filters_btn(self):
        if not self._filters_btn or not self._filters_btn.winfo_exists():
            return
        n = self._active_filter_count()
        label = f"Filtros ({n})" if n else "Filtros"
        self._filters_btn.configure(
            text=label,
            fg_color=ACCENT if n else TEXT_SECONDARY,
            hover_color=ACCENT_HOVER if n else "#475569",
        )

    def _update_contact_btn(self):
        if not self._contact_btn or not self._contact_btn.winfo_exists():
            return
        state = "normal" if self._selected_code else "disabled"
        self._contact_btn.configure(state=state)
        if self._etiquetas_btn and self._etiquetas_btn.winfo_exists():
            self._etiquetas_btn.configure(state=state)

    def _clear_filters(self):
        self._estado_var.set("(Todos)")
        self._region_var.set("(Todas)")
        self._zona_var.set("(Todas)")
        self._seccion_var.set("(Todas)")
        self._campana_banco_var.set("(Todas)")
        self._carta_pub_var.set("(Todas)")
        self._formato_pub_var.set("(Todos)")
        self._estado_pub_var.set("(Todos)")
        self._gestor_pub_var.set("(Todos)")
        self._load_filter_options()
        self._apply_filters()

    def _close_filters_dialog(self):
        if self._filters_popup and self._filters_popup.winfo_exists():
            self._filters_popup.destroy()
        self._filters_popup = None
        self._estado_menu = None
        self._region_menu = None
        self._zona_menu = None
        self._seccion_menu = None
        self._campana_banco_menu = None
        self._carta_pub_menu = None
        self._formato_pub_menu = None
        self._estado_pub_menu = None
        self._gestor_pub_menu = None

    def _create_filter_menus_in(self, parent: ctk.CTkFrame):
        def add_row(row: int, label: str, menu_attr: str, var: ctk.StringVar, width: int, *, command=None):
            ctk.CTkLabel(parent, text=label, font=font(12), anchor="w").grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=6
            )
            opts = ctk.CTkOptionMenu(
                parent,
                values=["(Todos)"],
                variable=var,
                width=width,
                height=32,
                command=command,
            )
            opts.grid(row=row, column=1, sticky="ew", pady=6)
            setattr(self, menu_attr, opts)

        parent.grid_columnconfigure(1, weight=1)
        add_row(0, "Estado:", "_estado_menu", self._estado_var, 280)
        add_row(1, "Región:", "_region_menu", self._region_var, 280, command=self._on_region_change)
        add_row(2, "Zona:", "_zona_menu", self._zona_var, 280, command=self._on_zona_change)
        add_row(3, "Sección:", "_seccion_menu", self._seccion_var, 280)
        add_row(4, "Nº campaña:", "_campana_banco_menu", self._campana_banco_var, 280)
        add_row(5, "Carta:", "_carta_pub_menu", self._carta_pub_var, 280)
        add_row(6, "Formato:", "_formato_pub_menu", self._formato_pub_var, 280)
        add_row(7, "Estado publicación:", "_estado_pub_menu", self._estado_pub_var, 280)
        add_row(8, "Gestor destino:", "_gestor_pub_menu", self._gestor_pub_var, 280)
        self._load_filter_options(preserve_selection=True)

    def _open_filters_dialog(self):
        if self._filters_popup and self._filters_popup.winfo_exists():
            self._filters_popup.focus_force()
            return

        root = self._container.winfo_toplevel() if self._container else self.app
        win = ctk.CTkToplevel(root)
        self._filters_popup = win
        win.title("Filtros avanzados")
        win.geometry("480x520")
        win.minsize(420, 460)
        win.configure(fg_color=BG)
        win.transient(root)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", self._close_filters_dialog)

        ctk.CTkLabel(
            win,
            text="Filtros avanzados",
            font=font(16, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            win,
            text="Refine la lista por estado, ubicación, campaña banco o publicación de cartas.",
            font=font(11),
            text_color=TEXT_SECONDARY,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        body = ctk.CTkFrame(win, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=16, pady=12)
        self._create_filter_menus_in(form)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="Limpiar",
            width=100,
            height=34,
            fg_color=TEXT_SECONDARY,
            hover_color="#475569",
            command=self._clear_filters,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=100,
            height=34,
            fg_color=TEXT_SECONDARY,
            hover_color="#475569",
            command=self._close_filters_dialog,
        ).pack(side="right", padx=(8, 0))

        def apply_and_close():
            self._apply_filters()
            self._close_filters_dialog()

        ctk.CTkButton(
            btn_row,
            text="Aplicar",
            width=100,
            height=34,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=apply_and_close,
        ).pack(side="right")

        win.focus_force()

    def _open_contact_dialog(self):
        if not self._selected_code:
            messagebox.showinfo("Contacto", "Seleccione un cliente primero.")
            return
        if self._contact_popup and self._contact_popup.winfo_exists():
            self._contact_popup.focus_force()
            return

        root = self._container.winfo_toplevel() if self._container else self.app
        win = ctk.CTkToplevel(root)
        self._contact_popup = win
        win.title("Registrar dato de campo")
        win.geometry("520x340")
        win.minsize(480, 300)
        win.configure(fg_color=BG)
        win.transient(root)
        win.grab_set()

        def close_contact():
            if self._contact_popup and self._contact_popup.winfo_exists():
                self._contact_popup.destroy()
            self._contact_popup = None

        win.protocol("WM_DELETE_WINDOW", close_contact)

        ctk.CTkLabel(
            win,
            text="Registrar dato de campo",
            font=font(16, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            win,
            text="Alternativa por defecto; marque principal para reemplazar banco en escritorio.",
            font=font(11),
            text_color=TEXT_SECONDARY,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        body = ctk.CTkFrame(win, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(form, text="Teléfono nuevo", font=font(11), text_color=TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkEntry(
            form,
            textvariable=self._contact_phone_var,
            height=32,
            placeholder_text="Teléfono nuevo",
        ).pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(form, text="Dirección nueva", font=font(11), text_color=TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkEntry(
            form,
            textvariable=self._contact_addr_var,
            height=32,
            placeholder_text="Dirección nueva",
        ).pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(form, text="Nota (obligatoria)", font=font(11), text_color=TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkEntry(
            form,
            textvariable=self._contact_note_var,
            height=32,
            placeholder_text="Nota obligatoria",
        ).pack(fill="x", pady=(2, 10))

        ctk.CTkCheckBox(
            form,
            text="Usar como principal",
            variable=self._usar_principal_var,
            font=font(11),
        ).pack(anchor="w", pady=(4, 0))

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=100,
            height=34,
            fg_color=TEXT_SECONDARY,
            hover_color="#475569",
            command=close_contact,
        ).pack(side="right", padx=(8, 0))

        def save_and_close():
            self._save_contact_update(close_popup=True)

        ctk.CTkButton(
            btn_row,
            text="Guardar",
            width=100,
            height=34,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=save_and_close,
        ).pack(side="right")

        win.focus_force()

    def _estado_value(self) -> str:
        return "" if self._estado_var.get() in ("", "(Todos)") else self._estado_var.get()

    def _seccion_value(self) -> str:
        return "" if self._seccion_var.get() in ("", "(Todas)") else self._seccion_var.get()

    def _region_value(self) -> str:
        return "" if self._region_var.get() in ("", "(Todas)") else self._region_var.get()

    def _zona_value(self) -> str:
        return "" if self._zona_var.get() in ("", "(Todas)") else self._zona_var.get()

    def _campana_banco_value(self) -> str:
        label = self._campana_banco_var.get()
        if label in ("", "(Todas)"):
            return ""
        return self._campana_banco_label_to_key.get(label, label)

    def _carta_publicacion_value(self) -> int | None:
        raw = self._carta_pub_var.get()
        if raw in ("", "(Todas)"):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _formato_publicacion_value(self) -> str:
        return "" if self._formato_pub_var.get() in ("", "(Todos)") else self._formato_pub_var.get()

    def _estado_publicacion_value(self) -> str:
        return "" if self._estado_pub_var.get() in ("", "(Todos)") else self._estado_pub_var.get()

    def _gestor_publicacion_value(self) -> str:
        return "" if self._gestor_pub_var.get() in ("", "(Todos)") else self._gestor_pub_var.get()

    def _load_filter_options(self, preserve_selection: bool = False):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            return

        prev_estado = self._estado_var.get()
        prev_region = self._region_var.get()
        prev_zona = self._zona_var.get()
        prev_seccion = self._seccion_var.get()
        prev_campana_banco = self._campana_banco_var.get()
        prev_carta_pub = self._carta_pub_var.get()
        prev_formato_pub = self._formato_pub_var.get()
        prev_estado_pub = self._estado_pub_var.get()
        prev_gestor_pub = self._gestor_pub_var.get()

        opts = self.app.campaign_mgr.get_filter_options(
            campana_id,
            region=self._region_value(),
            zona=self._zona_value(),
            seccion=self._seccion_value(),
        )
        estados = ["(Todos)"] + opts.get("estados", [])
        regiones = ["(Todas)"] + opts.get("regiones", [])
        zonas = ["(Todas)"] + opts.get("zonas", [])
        secciones = ["(Todas)"] + opts.get("secciones", [])
        campanas_banco_keys = opts.get("campanas_banco", [])
        campana_labels = ["(Todas)"]
        self._campana_banco_label_to_key = {}
        for key in campanas_banco_keys:
            label = display_label_for_key(key)
            campana_labels.append(label)
            self._campana_banco_label_to_key[label] = key
        cartas_pub = ["(Todas)"] + opts.get("cartas_publicadas", [])
        formatos_pub = ["(Todos)"] + opts.get("formatos_publicacion", [])
        estados_pub = ["(Todos)"] + opts.get("estados_publicacion", [])
        gestores_pub = ["(Todos)"] + opts.get("gestores_publicacion", [])

        estado_sel = prev_estado if preserve_selection and prev_estado in estados else "(Todos)"
        region_sel = prev_region if preserve_selection and prev_region in regiones else "(Todas)"
        zona_sel = prev_zona if preserve_selection and prev_zona in zonas else "(Todas)"
        seccion_sel = prev_seccion if preserve_selection and prev_seccion in secciones else "(Todas)"
        campana_sel = (
            prev_campana_banco
            if preserve_selection and prev_campana_banco in campana_labels
            else "(Todas)"
        )
        carta_pub_sel = prev_carta_pub if preserve_selection and prev_carta_pub in cartas_pub else "(Todas)"
        formato_pub_sel = prev_formato_pub if preserve_selection and prev_formato_pub in formatos_pub else "(Todos)"
        estado_pub_sel = prev_estado_pub if preserve_selection and prev_estado_pub in estados_pub else "(Todos)"
        gestor_pub_sel = prev_gestor_pub if preserve_selection and prev_gestor_pub in gestores_pub else "(Todos)"

        if self._estado_menu and self._estado_menu.winfo_exists():
            self._estado_menu.configure(values=estados)
            self._estado_var.set(estado_sel)
        if self._region_menu and self._region_menu.winfo_exists():
            self._region_menu.configure(values=regiones)
            self._region_var.set(region_sel)
        if self._zona_menu and self._zona_menu.winfo_exists():
            self._zona_menu.configure(values=zonas)
            self._zona_var.set(zona_sel)
        if self._seccion_menu and self._seccion_menu.winfo_exists():
            self._seccion_menu.configure(values=secciones)
            self._seccion_var.set(seccion_sel)
        if self._campana_banco_menu and self._campana_banco_menu.winfo_exists():
            self._campana_banco_menu.configure(values=campana_labels)
            self._campana_banco_var.set(campana_sel)
        if self._carta_pub_menu and self._carta_pub_menu.winfo_exists():
            self._carta_pub_menu.configure(values=cartas_pub)
            self._carta_pub_var.set(carta_pub_sel)
        if self._formato_pub_menu and self._formato_pub_menu.winfo_exists():
            self._formato_pub_menu.configure(values=formatos_pub)
            self._formato_pub_var.set(formato_pub_sel)
        if self._estado_pub_menu and self._estado_pub_menu.winfo_exists():
            self._estado_pub_menu.configure(values=estados_pub)
            self._estado_pub_var.set(estado_pub_sel)
        if self._gestor_pub_menu and self._gestor_pub_menu.winfo_exists():
            self._gestor_pub_menu.configure(values=gestores_pub)
            self._gestor_pub_var.set(gestor_pub_sel)
        self._update_filters_btn()

    def _on_region_change(self, _value: str):
        self._zona_var.set("(Todas)")
        self._seccion_var.set("(Todas)")
        self._load_filter_options(preserve_selection=True)
        self._apply_filters()

    def _on_zona_change(self, _value: str):
        self._seccion_var.set("(Todas)")
        self._load_filter_options(preserve_selection=True)
        self._apply_filters()

    def _on_tree_click(self, event):
        """Open ficha popup when clicking the Nombre column."""
        if not self._tree or not self._tree.winfo_exists():
            return
        if self._tree.identify_region(event.x, event.y) != "cell":
            return
        if self._tree.identify_column(event.x) != "#2":
            return
        item = self._tree.identify_row(event.y)
        if not item:
            return
        code = self._code_by_item.get(item)
        if code:
            self._selected_code = code
            self._update_contact_btn()
            self._open_client_popup(code)

    def _on_tree_double_click(self, event):
        """Open ficha popup on double-click anywhere on the row."""
        if not self._tree or not self._tree.winfo_exists():
            return
        if self._tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return
        item = self._tree.identify_row(event.y)
        if not item:
            return
        code = self._code_by_item.get(item)
        if code:
            self._selected_code = code
            self._update_contact_btn()
            self._open_client_popup(code)

    def _format_money(self, value: Any) -> str:
        try:
            return f"S/ {float(value or 0):,.2f}"
        except (TypeError, ValueError):
            return "—"

    def _format_date_short(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "—"
        return text[:16].replace("T", " ")

    def _build_client_detail_text(self, timeline: dict[str, Any]) -> str:
        c = timeline["cliente"]
        eventos = timeline.get("eventos", [])
        historial_contacto = timeline.get("historial_contacto", [])
        direcciones = timeline.get("direcciones_conocidas", [])
        contacto_agenda = timeline.get("contacto_agenda", [])
        historial_tramos = timeline.get("historial_tramos", [])
        cartas = timeline.get("cartas", [])
        historial_zona = timeline.get("historial_zona", [])
        cuentas_relacionadas = timeline.get("cuentas_relacionadas", [])
        historial_visitas = timeline.get("historial_visitas", [])

        visitas_campo = sum(1 for e in eventos if e.get("tipo") in ("gestion", "contacto", "visita"))
        notas_campo = [h for h in historial_contacto if (h.get("origen_actualizacion") or "") == "mobile"]
        if not notas_campo:
            notas_campo = historial_contacto

        lines: list[str] = [
            "═══ RESUMEN ═══",
            "",
            f"  Cliente: {c.get('nombre_completo', '—')}",
            f"  Código: {c.get('codigo_cliente', '—')} · DNI: {c.get('numero_documento', '—')}",
            f"  Estado gestión: {c.get('estado_gestion', 'pendiente')}",
            f"  Visitas / notas registradas: {visitas_campo}",
            f"  Última gestión: {self._format_date_short(c.get('fecha_gestion'))}",
            f"  Deuda pendiente: {self._format_money(c.get('importe_deuda_pendiente'))}",
            f"  Deuda asignada: {self._format_money(c.get('importe_deuda_asignada'))}",
            "",
        ]

        if cuentas_relacionadas and len(cuentas_relacionadas) > 1:
            total_pend = sum(
                float(x.get("importe_deuda_pendiente", 0) or 0)
                for x in cuentas_relacionadas
            )
            total_asig = sum(
                float(x.get("importe_deuda_asignada", 0) or 0)
                for x in cuentas_relacionadas
            )
            lines.extend([
                "═══ OTRAS DEUDAS (MISMO DNI) ═══",
                "",
                f"  Cuentas activas con este DNI: {len(cuentas_relacionadas)}",
                f"  Total deuda pendiente (todas): {self._format_money(total_pend)}",
                f"  Total deuda asignada (todas): {self._format_money(total_asig)}",
                "",
            ])
            for cuenta in cuentas_relacionadas:
                marker = " ← actual" if cuenta.get("codigo_cliente") == c.get("codigo_cliente") else ""
                lines.append(
                    f"  · {cuenta.get('codigo_cliente', '—')}{marker}: "
                    f"pend. {self._format_money(cuenta.get('importe_deuda_pendiente'))} · "
                    f"asig. {self._format_money(cuenta.get('importe_deuda_asignada'))} · "
                    f"Sección {cuenta.get('seccion_key', '—')} · "
                    f"Estado {cuenta.get('estado_gestion', 'pendiente')}"
                )
            lines.append("")

        tag_ids = c.get("etiquetas") or []
        if tag_ids:
            catalog = {t["id"]: t for t in self.app.campaign_mgr.list_etiquetas()}
            tag_names = [
                catalog.get(tid, {}).get("nombre", tid) for tid in tag_ids
            ]
            lines.extend([
                "═══ ETIQUETAS ═══",
                "",
                f"  {', '.join(tag_names) if tag_names else '—'}",
                "",
            ])

        lines.extend(["═══ NOTAS DE CAMPO (gestor) ═══", ""])
        if not notas_campo:
            lines.append("  Sin notas de campo sincronizadas.")
            if c.get("ultima_nota_contacto"):
                lines.append(f"  Última nota (resumen): {c.get('ultima_nota_contacto')}")
        else:
            for h in notas_campo[:30]:
                fecha_h = self._format_date_short(h.get("fecha_evento"))
                lines.append(f"  [{fecha_h}] {h.get('usuario_nombre', 'Gestor')} ({h.get('origen_actualizacion', '')})")
                if h.get("direccion_nueva"):
                    lines.append(f"      Dirección observada: {h.get('direccion_nueva')}")
                if h.get("telefono_nuevo"):
                    lines.append(f"      Teléfono observado: {h.get('telefono_nuevo')}")
                if h.get("nota"):
                    lines.append(f"      Nota: {h['nota']}")
                lat, lng = h.get("latitud"), h.get("longitud")
                if lat and lng:
                    lines.append(f"      GPS: {lat:.5f}, {lng:.5f}")
                lines.append("")
        lines.append("")

        lines.extend(["═══ DIRECCIONES CONOCIDAS ═══", ""])
        if not direcciones:
            lines.append("  (ninguna registrada)")
        else:
            for i, d in enumerate(direcciones, 1):
                nivel = d.get("nivel_confianza", "confiable")
                principal = " [principal]" if d.get("es_principal") else ""
                oculto = " [oculta]" if d.get("oculto") else ""
                lines.append(f"  {i}. {d.get('direccion', '') or d.get('telefono', '')}{principal}{oculto}")
                if d.get("telefono") and d.get("direccion"):
                    lines.append(f"     Tel: {d['telefono']}")
                lines.append(f"     Confianza: {nivel} · Orden: {d.get('orden', 0)}")
                lines.append(f"     Fuente: {d.get('fuente', '')}")
                if d.get("fecha"):
                    lines.append(f"     Fecha: {d['fecha']}")
        lines.append("")

        if contacto_agenda:
            campana_actual = str(c.get("campana_id", "") or "")
            lines.extend(["═══ AGENDA PERSONA (DNI — entre campañas) ═══", ""])
            for i, a in enumerate(contacto_agenda, 1):
                origen = a.get("campana_origen", "")
                otra = " · otra campaña" if origen and origen != campana_actual else ""
                lines.append(
                    f"  {i}. {(a.get('direccion') or a.get('telefono') or '—')}{otra}"
                )
                if a.get("telefono") and a.get("direccion"):
                    lines.append(f"     Tel: {a['telefono']}")
                lines.append(
                    f"     Confianza: {a.get('nivel_confianza', 'confiable')} · "
                    f"Orden: {a.get('orden', 0)}"
                    f"{' · principal' if a.get('es_principal') else ''}"
                    f"{' · oculta' if a.get('oculto') else ''}"
                )
                if a.get("nota"):
                    lines.append(f"     Nota: {a['nota']}")
                if a.get("fecha") or a.get("fecha_evento"):
                    lines.append(f"     Fecha: {a.get('fecha') or a.get('fecha_evento')}")
            lines.append("")

        lines.extend(["═══ GESTIÓN Y VISITAS ═══", ""])
        lines.append(f"  Nota del gestor (última visita): {c.get('nota_gestor') or '—'}")
        lines.append(f"  Canal: {c.get('canal_gestion') or '—'}")
        lines.append(
            f"  Niveles: {c.get('nivel_1') or '—'} › {c.get('nivel_2') or '—'} › "
            f"{c.get('nivel_3') or '—'} › {c.get('nivel_4') or '—'}"
        )
        if c.get("gps_latitud") and c.get("gps_longitud"):
            lines.append(f"  GPS última visita: {c.get('gps_latitud'):.5f}, {c.get('gps_longitud'):.5f}")
        lines.append("")

        if historial_visitas:
            lines.extend(["═══ HISTORIAL DE VISITAS ═══", ""])
            for hv in historial_visitas[:30]:
                fecha_h = self._format_date_short(hv.get("fecha_evento"))
                gestor = hv.get("gestor_nombre") or hv.get("gestor_uid") or "Gestor"
                lines.append(
                    f"  [{fecha_h}] {gestor} · {hv.get('estado_gestion', '—')}"
                )
                if hv.get("nivel_1"):
                    lines.append(f"      Nivel: {hv.get('nivel_1')}")
                if hv.get("nota_gestor"):
                    lines.append(f"      Nota: {hv.get('nota_gestor')}")
            lines.append("")

        lines.extend(["═══ PROMESAS Y DEUDA ═══", ""])
        lines.append(f"  Fecha promesa: {c.get('fecha_promesa_pago') or '—'}")
        lines.append(f"  Monto promesa: {self._format_money(c.get('monto_promesa_pago'))}")
        lines.append(f"  Tramo actual: {c.get('tramo_actual') or '—'}")
        lines.append(f"  Días atraso: {c.get('dias_atraso') or '—'}")
        if historial_tramos:
            lines.extend(["", "  ── Historial de tramos / saldo ──"])
            for h in historial_tramos[:20]:
                fecha_t = self._format_date_short(h.get("fecha_transicion"))
                saldo = h.get("saldo_al_momento")
                saldo_txt = self._format_money(saldo) if saldo not in (None, "") else "—"
                lines.append(
                    f"    [{fecha_t}] Tramo {h.get('tramo_anterior', '—')} → {h.get('tramo_nuevo', '—')} · "
                    f"Día {h.get('dia_campana', '—')} · Saldo: {saldo_txt} · {h.get('motivo', '')}"
                )
        lines.append("")

        if cartas:
            lines.extend(["═══ CARTAS GENERADAS ═══", ""])
            for ca in cartas[:20]:
                fecha_pub = self._format_date_short(ca.get("fecha_publicacion"))
                fecha_gen = self._format_date_short(ca.get("fecha_generacion"))
                fecha_c = fecha_pub if fecha_pub != "—" else fecha_gen
                estado_pub = (
                    ca.get("estado_publicacion")
                    or ("impresa" if ca.get("fue_impresa") else "pendiente")
                )
                formato = ca.get("formato") or "—"
                gestor = ca.get("gestor_nombre") or ca.get("gestor_uid") or "—"
                lines.append(
                    f"  [{fecha_c}] Carta #{ca.get('numero_carta', '—')} · Tramo {ca.get('tramo', '—')} · Estado: {estado_pub}"
                )
                lines.append(f"      Formato: {formato} · Gestor destino: {gestor}")
                if ca.get("nombre_archivo"):
                    lines.append(f"      Archivo: {ca.get('nombre_archivo')}")
                if ca.get("archivo_path"):
                    lines.append(f"      Ruta local: {ca.get('archivo_path')}")
                if ca.get("storage_path"):
                    lines.append(f"      Ruta Firebase: {ca.get('storage_path')}")
                if ca.get("publicado_por_nombre") or ca.get("publicado_por_uid"):
                    lines.append(
                        f"      Publicado por: {ca.get('publicado_por_nombre') or ca.get('publicado_por_uid')}"
                    )
            lines.append("")

        lines.extend(self._format_ficha(c))

        lines.extend(["═══ HISTORIAL DE EVENTOS ═══", ""])
        if not eventos:
            lines.append("  Sin eventos registrados.")
        else:
            for e in eventos[:50]:
                fecha = self._format_date_short(e.get("fecha"))
                lines.append(f"  [{fecha}] {e.get('titulo', '')}")
                lines.append(f"      {e.get('detalle', '')}")

        if historial_zona:
            lines.extend(["", "── Cambios de zona/sección ──"])
            for z in historial_zona[:15]:
                fecha_z = self._format_date_short(z.get("fecha_evento"))
                lines.append(
                    f"  [{fecha_z}] Sección {z.get('seccion_anterior', '—')} → {z.get('seccion_nueva', '—')} · "
                    f"Zona {z.get('zona_anterior', '—')} → {z.get('zona_nueva', '—')} · "
                    f"{z.get('usuario_nombre', '')}"
                )

        return "\n".join(lines)

    def _open_client_popup(self, code: str):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            return
        timeline = self.app.campaign_mgr.get_client_timeline(campana_id, code)
        if not timeline:
            messagebox.showinfo("Cliente", "No se encontró información del cliente.")
            return

        c = timeline["cliente"]
        nombre = str(c.get("nombre_completo") or c.get("codigo_cliente") or code)
        detail_text = self._build_client_detail_text(timeline)

        if self._detail_popup and self._detail_popup.winfo_exists():
            self._detail_popup.destroy()

        root = self._container.winfo_toplevel() if self._container else self.app
        win = ctk.CTkToplevel(root)
        self._detail_popup = win
        win.title(f"Ficha — {nombre}")
        win.geometry("920x720")
        win.minsize(720, 520)
        win.transient(root)
        win.grab_set()

        header = ctk.CTkFrame(win, fg_color=CARD_BG, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text=nombre,
            font=font(18, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        meta_parts = [
            f"Código: {c.get('codigo_cliente', code)}",
            f"DNI: {c.get('numero_documento', '—')}",
            f"Estado: {c.get('estado_gestion', 'pendiente')}",
            f"Deuda: {self._format_money(c.get('importe_deuda_pendiente'))}",
        ]
        ctk.CTkLabel(
            header,
            text=" · ".join(meta_parts),
            font=font(12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(0, 12))

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        textbox = ctk.CTkTextbox(body, wrap="word", font=font(12))
        textbox.pack(fill="both", expand=True)
        textbox.insert("1.0", detail_text)
        textbox.configure(state="disabled")

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_row,
            text="Cerrar",
            width=120,
            height=34,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=win.destroy,
        ).pack(side="right")

        self._refresh_detail(code)
        win.focus_force()

    def _open_etiquetas_dialog(self):
        if not self._selected_code:
            return
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            return
        timeline = self.app.campaign_mgr.get_client_timeline(campana_id, self._selected_code)
        if not timeline:
            return
        cliente = timeline["cliente"]
        current_ids = set(cliente.get("etiquetas") or [])

        win = ctk.CTkToplevel(self._container)
        win.title("Etiquetas del cliente")
        win.geometry("400x420")
        win.transient(self._container.winfo_toplevel())
        win.grab_set()

        ctk.CTkLabel(
            win, text=f"Cliente: {cliente.get('nombre_completo', '—')}",
            font=font(12, "bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        scroll = ctk.CTkScrollableFrame(win, height=280)
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        vars_map: dict[str, ctk.BooleanVar] = {}
        all_tags = self.app.campaign_mgr.list_etiquetas()
        for tag in all_tags:
            var = ctk.BooleanVar(value=tag["id"] in current_ids)
            vars_map[tag["id"]] = var
            label = tag["nombre"]
            if not tag.get("activa"):
                label += " (inactiva)"
            ctk.CTkCheckBox(scroll, text=label, variable=var).pack(anchor="w", pady=4)

        if not all_tags:
            ctk.CTkLabel(
                scroll, text="No hay etiquetas. Créelas en la página Etiquetas.",
                text_color=TEXT_MUTED,
            ).pack(anchor="w")

        def save():
            selected = [tid for tid, v in vars_map.items() if v.get()]
            self.app.campaign_mgr.set_client_etiquetas(
                campana_id,
                self._selected_code,
                selected,
                firebase_service=self.app.firebase if self.app.firebase_connected else None,
            )
            win.destroy()
            self._refresh_detail(self._selected_code)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(
            btn_row, text="Guardar", width=100,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=save,
        ).pack(side="right")
        ctk.CTkButton(btn_row, text="Cancelar", width=100, command=win.destroy).pack(side="right", padx=8)

    def _on_row_select(self, _event=None):
        if not self._tree or not self._tree.winfo_exists():
            return
        selected = self._tree.selection()
        if not selected:
            return
        code = self._code_by_item.get(selected[0])
        if not code:
            return
        self._selected_code = code
        self._refresh_detail(code)
        self._update_contact_btn()

    def _format_ficha(self, c: dict[str, Any]) -> list[str]:
        lines: list[str] = ["═══ FICHA COMPLETA ═══", ""]
        for title, fields in _FICHA_SECTIONS:
            lines.append(f"── {title} ──")
            for key, label in fields:
                val = c.get(key, "")
                if isinstance(val, float) and key.startswith("importe"):
                    val = f"S/ {val:,.2f}"
                elif isinstance(val, float) and key.startswith("monto"):
                    val = f"S/ {val:,.2f}"
                lines.append(f"  {label}: {val if val not in (None, '') else '—'}")
            lines.append("")
        return lines

    def _refresh_detail(self, code: str):
        campana_id = self._get_browse_campana_id()
        if not campana_id:
            return
        timeline = self.app.campaign_mgr.get_client_timeline(campana_id, code)
        if not timeline:
            return
        self._set_detail_text(self._build_client_detail_text(timeline))

    def _set_detail_text(self, text: str):
        if not self._detail_box or not self._detail_box.winfo_exists():
            return
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("1.0", text)
        self._detail_box.configure(state="disabled")
