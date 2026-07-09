"""Devoluciones — client return requests from field gestores (zona inaccesible)."""

from __future__ import annotations

import threading

from tkinter import messagebox

from typing import TYPE_CHECKING

import customtkinter as ctk

from services.database import POOL_REASIGNACION_SECTION, GESTION_ESPECIAL_SECTION

from ..components import SectionHeader

from ..theme import *

if TYPE_CHECKING:

    from ..app import App

_MOTIVO_LABELS = {

    "zona_inaccesible": "Zona inaccesible",

    "ruta_bloqueada": "Ruta bloqueada",

    "riesgo_seguridad": "Riesgo de seguridad",

    "otro": "Otro",

}

class ReturnsPage:

    """Queue of clients returned by gestores for reassignment."""

    def __init__(self, app: App):

        self.app = app

        self._container = None

        self._items: list[dict] = []

        self._pool_items: list[dict] = []

        self._especial_items: list[dict] = []

        self._section_keys: list[str] = []

        self._busy = False

        self._loading_lbl: ctk.CTkLabel | None = None

        self._dest_var: ctk.StringVar | None = None

        self._refresh_btn = None

    def render(self, container: ctk.CTkScrollableFrame):

        for w in container.winfo_children():

            w.destroy()

        self._container = container

        if not self.app.firebase_connected:

            ctk.CTkLabel(container, text="Conecte Firebase para gestionar devoluciones.",

                         font=font(14), text_color=TEXT_SECONDARY).pack(pady=24)

            return

        hdr = ctk.CTkFrame(container, fg_color="transparent")

        hdr.pack(fill="x", padx=8, pady=(8, 12))

        SectionHeader(hdr, "Devoluciones y Gestión Especial",

                      "Devoluciones de gestores y cuentas derivadas a gestión especial").pack(side="left")

        btn_row = ctk.CTkFrame(hdr, fg_color="transparent")

        btn_row.pack(side="right")

        self._sync_btn = ctk.CTkButton(

            btn_row, text="Sincronizar", width=120, height=32,

            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8,

            command=self._sync_and_refresh,

        )

        self._sync_btn.pack(side="right", padx=4)

        self._refresh_btn = ctk.CTkButton(

            btn_row, text="Actualizar", width=100, height=32,

            fg_color=TEXT_SECONDARY, hover_color="#64748B", corner_radius=8,

            command=self._refresh,

        )

        self._refresh_btn.pack(side="right", padx=4)

        self._kpi_frame = ctk.CTkFrame(container, fg_color=CARD_BG,

                                       corner_radius=12, border_width=1,

                                       border_color=BORDER)

        self._kpi_frame.pack(fill="x", padx=8, pady=(0, 8))

        kpi_inner = ctk.CTkFrame(self._kpi_frame, fg_color="transparent")

        kpi_inner.pack(fill="x", padx=20, pady=12)

        self._kpi_pending = ctk.CTkLabel(kpi_inner, text="Pendientes: —",

                                           font=font(13, "bold"), text_color=WARNING)

        self._kpi_pending.pack(side="left", padx=(0, 24))

        self._kpi_pool = ctk.CTkLabel(kpi_inner, text="En pool: —",

                                      font=font(13, "bold"), text_color=ACCENT)

        self._kpi_pool.pack(side="left", padx=(0, 24))

        self._kpi_especial = ctk.CTkLabel(kpi_inner, text="Gestión especial: —",

                                          font=font(13, "bold"), text_color=WARNING)

        self._kpi_especial.pack(side="left")

        self._loading_lbl = ctk.CTkLabel(

            container, text="Cargando devoluciones…",

            font=font(13), text_color=TEXT_SECONDARY,

        )

        self._loading_lbl.pack(pady=(4, 0))

        self._list_frame = ctk.CTkFrame(container, fg_color="transparent")

        self._list_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._dest_var = ctk.StringVar(value="")

        self._refresh()

    def _sync_and_refresh(self):

        if self._busy or not self.app.active_campaign:

            messagebox.showwarning("Campaña", "Seleccione una campaña activa.")

            return

        self._busy = True

        self._sync_btn.configure(state="disabled", text="Sincronizando…")

        campana_id = self.app.active_campaign.id

        def work():

            try:

                fb_data = self.app.firebase.pull_visit_data("cartera_activa")

                updated = self.app.campaign_mgr.sync_visits_from_firebase(

                    campana_id, fb_data

                )

                msg = f"Sincronizados {updated} registros."

            except Exception as e:

                msg = str(e)

            if self._container and self._container.winfo_exists():

                self._container.after(0, lambda: self._on_sync_done(msg))

        threading.Thread(target=work, daemon=True).start()

    def _on_sync_done(self, msg: str):

        self._busy = False

        self._sync_btn.configure(state="normal", text="Sincronizar")

        self.app.set_status(msg)

        self._refresh()

    def _set_loading(self, loading: bool):

        if self._loading_lbl and self._loading_lbl.winfo_exists():

            if loading:

                self._loading_lbl.configure(text="Cargando devoluciones…")

                self._loading_lbl.pack(pady=(4, 0))

            else:

                self._loading_lbl.pack_forget()

        if self._refresh_btn and self._refresh_btn.winfo_exists():

            self._refresh_btn.configure(state="disabled" if loading else "normal")

    def _refresh(self):

        if not self._container or not self._container.winfo_exists():

            return

        if self._busy:

            return

        self._busy = True

        self._set_loading(True)

        campaign_id = "cartera_activa"

        campana_id = self.app.active_campaign.id if self.app.active_campaign else None

        def work():

            try:

                section_keys = self._load_sections_sync(campana_id, campaign_id)

                items = self.app.firebase.list_pending_returns(campaign_id)

                pool_items = self.app.firebase.list_pool_clients(campaign_id)

                if campana_id:

                    especial_items = self.app.campaign_mgr.get_gestion_especial_local(

                        campana_id

                    )

                else:

                    especial_items = []

                payload = (section_keys, items, pool_items, especial_items)

                if self._container and self._container.winfo_exists():

                    self._container.after(0, lambda: self._apply_refresh(payload))

            except Exception as e:

                if self._container and self._container.winfo_exists():

                    self._container.after(0, lambda: self._on_refresh_error(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_refresh_error(self, msg: str):

        self._busy = False

        self._set_loading(False)

        self.app.set_status(f"Error devoluciones: {msg}")

    def _apply_refresh(self, payload: tuple):

        if not self._container or not self._container.winfo_exists():

            return

        self._section_keys, self._items, self._pool_items, self._especial_items = payload

        self._busy = False

        self._set_loading(False)

        self._kpi_pending.configure(text=f"Pendientes: {len(self._items)}")

        self._kpi_pool.configure(text=f"En pool: {len(self._pool_items)}")

        self._kpi_especial.configure(text=f"Gestión especial: {len(self._especial_items)}")

        if self._section_keys and (

            not self._dest_var.get() or self._dest_var.get() not in self._section_keys

        ):

            self._dest_var.set(self._section_keys[0])

        self._render_lists()

    def _load_sections_sync(self, campana_id: str | None, campaign_id: str) -> list[str]:
        """Secciones destino para reasignación (sin expandir catálogo territorial)."""
        keys: set[str] = set()

        try:
            for sec in self.app.firebase.list_campaign_sections(campaign_id):

                sid = str(sec.get("id") or "")

                if sid and sid not in (POOL_REASIGNACION_SECTION, GESTION_ESPECIAL_SECTION):

                    keys.add(sid)

        except Exception:

            pass

        if campana_id:

            try:

                keys.update(
                    self.app.campaign_mgr.distinct_seccion_keys_for_campaign(campana_id)
                )

            except Exception:

                pass

        try:

            for user in self.app.firebase.list_gestor_users():

                rol = str(user.get("rol") or "")

                if rol not in ("gestor", "supervisor", "admin", ""):

                    continue

                for sk in (user.get("secciones") or []):

                    sks = str(sk)

                    if sks and sks not in (POOL_REASIGNACION_SECTION, GESTION_ESPECIAL_SECTION):

                        keys.add(sks)

        except Exception:

            pass

        keys.discard(POOL_REASIGNACION_SECTION)

        keys.discard(GESTION_ESPECIAL_SECTION)

        return sorted(keys)

    def _render_lists(self):

        for w in self._list_frame.winfo_children():

            w.destroy()

        if not self._items and not self._pool_items and not self._especial_items:

            ctk.CTkLabel(

                self._list_frame,

                text="No hay devoluciones pendientes.\n"

                     "Los gestores solicitan devolución desde la app móvil.",

                font=font(13), text_color=TEXT_SECONDARY, justify="center",

            ).pack(pady=40)

            return

        needs_dest = bool(self._items or self._pool_items)

        if needs_dest and self._section_keys:

            dest_bar = ctk.CTkFrame(self._list_frame, fg_color=CARD_BG,

                                    corner_radius=10, border_width=1,

                                    border_color=BORDER)

            dest_bar.pack(fill="x", pady=(0, 12))

            inner = ctk.CTkFrame(dest_bar, fg_color="transparent")

            inner.pack(fill="x", padx=16, pady=10)

            ctk.CTkLabel(

                inner, text="Sección destino para reasignación:",

                font=font(12, "bold"), text_color=TEXT_PRIMARY,

            ).pack(side="left", padx=(0, 10))

            ctk.CTkOptionMenu(

                inner, values=self._section_keys, variable=self._dest_var,

                width=260, height=30, corner_radius=6,

            ).pack(side="left")

        if self._items:

            ctk.CTkLabel(self._list_frame, text="Solicitudes pendientes",

                         font=font(14, "bold"), text_color=TEXT_PRIMARY

                         ).pack(anchor="w", pady=(0, 8))

            for item in self._items:

                self._render_card(item, in_pool=False)

        if self._pool_items:

            ctk.CTkLabel(self._list_frame, text="Pool de reasignación",

                         font=font(14, "bold"), text_color=TEXT_PRIMARY

                         ).pack(anchor="w", pady=(16, 8))

            for item in self._pool_items:

                self._render_card(item, in_pool=True)

        if self._especial_items:

            ctk.CTkLabel(self._list_frame, text="Gestión especial",

                         font=font(14, "bold"), text_color=TEXT_PRIMARY

                         ).pack(anchor="w", pady=(16, 8))

            for item in self._especial_items:

                self._render_especial_card(item)

    def _render_card(self, item: dict, in_pool: bool):

        codigo = str(item.get("codigo_cliente") or item.get("client_id") or "")

        nombre = str(item.get("nombre_completo") or "—")

        seccion = str(item.get("seccion_key") or "")

        motivo = _MOTIVO_LABELS.get(str(item.get("motivo_devolucion") or ""),

                                    item.get("motivo_devolucion") or "—")

        nota = str(item.get("nota_devolucion") or item.get("nota_gestor") or "")

        gestor = str(item.get("devolucion_gestor_nombre") or item.get("gestor_devolucion_nombre") or "—")

        fecha = str(item.get("devolucion_solicitada_at") or item.get("fecha_devolucion_solicitud") or "")

        card = ctk.CTkFrame(self._list_frame, fg_color=CARD_BG, corner_radius=10,

                            border_width=1, border_color=BORDER)

        card.pack(fill="x", pady=4)

        top = ctk.CTkFrame(card, fg_color="transparent")

        top.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text=f"{nombre}  ·  {codigo}",

                     font=font(13, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")

        ctk.CTkLabel(

            top,

            text=f"Sección: {seccion}  ·  Gestor: {gestor}  ·  {motivo}",

            font=font(11), text_color=TEXT_SECONDARY,

        ).pack(anchor="w", pady=(2, 0))

        if nota:

            ctk.CTkLabel(top, text=f"Nota: {nota[:200]}",

                         font=font(11), text_color=TEXT_MUTED, wraplength=900,

                         justify="left").pack(anchor="w", pady=(4, 0))

        if fecha:

            ctk.CTkLabel(top, text=f"Solicitado: {fecha[:19]}",

                         font=font(10), text_color=TEXT_MUTED).pack(anchor="w")

        actions = ctk.CTkFrame(card, fg_color="transparent")

        actions.pack(fill="x", padx=16, pady=(8, 12))

        if not in_pool:

            ctk.CTkButton(

                actions, text="Gestión especial", width=130, height=28,

                fg_color=WARNING, hover_color="#D97706", corner_radius=6,

                command=lambda i=item: self._to_gestion_especial(i),

            ).pack(side="left", padx=4)

            ctk.CTkButton(

                actions, text="Mover a pool", width=110, height=28,

                fg_color=TEXT_SECONDARY, hover_color="#64748B", corner_radius=6,

                command=lambda i=item: self._move_pool(i),

            ).pack(side="left", padx=4)

            ctk.CTkButton(

                actions, text="Rechazar", width=90, height=28,

                fg_color=DANGER, hover_color="#BE123C", corner_radius=6,

                command=lambda i=item: self._reject(i),

            ).pack(side="left", padx=4)

        ctk.CTkButton(

            actions, text="Reasignar", width=100, height=28,

            fg_color=SUCCESS, hover_color="#059669", corner_radius=6,

            command=lambda i=item: self._reassign(i, self._dest_var.get() if self._dest_var else ""),

        ).pack(side="right", padx=4)

    def _render_especial_card(self, item: dict):

        codigo = str(item.get("codigo_cliente") or "")

        nombre = str(item.get("nombre_completo") or "—")

        motivo = str(item.get("motivo_gestion_especial") or "—")

        origen = str(item.get("seccion_origen") or "—")

        dia = item.get("dia_ciclo", "—")

        etapa = item.get("tramo_actual", "—")

        card = ctk.CTkFrame(self._list_frame, fg_color=CARD_BG, corner_radius=10,

                            border_width=1, border_color=BORDER)

        card.pack(fill="x", pady=4)

        top = ctk.CTkFrame(card, fg_color="transparent")

        top.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(top, text=f"{nombre}  ·  {codigo}",

                     font=font(13, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")

        ctk.CTkLabel(

            top,

            text=f"Origen: {origen}  ·  Día {dia}  ·  Etapa {etapa}  ·  {motivo}",

            font=font(11), text_color=TEXT_SECONDARY,

        ).pack(anchor="w", pady=(2, 0))

        actions = ctk.CTkFrame(card, fg_color="transparent")

        actions.pack(fill="x", padx=16, pady=(8, 12))

        ctk.CTkButton(

            actions, text="Restituir a origen", width=140, height=28,

            fg_color=SUCCESS, hover_color="#059669", corner_radius=6,

            command=lambda i=item: self._restore_especial(i),

        ).pack(side="right", padx=4)

    def _to_gestion_especial(self, item: dict):

        codigo = str(item.get("codigo_cliente") or item.get("client_id"))

        origen = str(item.get("seccion_key") or "")

        motivo = str(item.get("motivo_devolucion") or "zona_inaccesible")

        if not self.app.active_campaign:

            messagebox.showwarning("Campaña", "No hay campaña activa.")

            return

        if not messagebox.askyesno(

            "Gestión especial",

            f"¿Derivar {codigo} a gestión especial?\n"

            f"Se quitará del gestor actual y pasará a {GESTION_ESPECIAL_SECTION}.",

        ):

            return

        camp_id = self.app.active_campaign.id

        email, name = self._admin_identity()

        def work():

            local = self.app.campaign_mgr.mark_gestion_especial(

                camp_id, codigo, motivo, GESTION_ESPECIAL_SECTION,

            )

            if not local.get("success"):

                self._container.after(0, lambda: self._action_done(local))

                return

            result = self.app.firebase.update_client_zone(

                self._campaign_id(), origen, codigo, GESTION_ESPECIAL_SECTION,

                email, name, motivo="gestion_especial",

                reset_gestion=True,

                extra_fields={

                    "gestion_especial": True,

                    "motivo_gestion_especial": motivo,

                    "seccion_origen": local.get("seccion_origen", origen),

                },

            )

            if result.get("success"):

                self.app.campaign_mgr.update_local_client_section(

                    camp_id, codigo, GESTION_ESPECIAL_SECTION, reset_gestion=True,

                )

            self._container.after(0, lambda: self._action_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _restore_especial(self, item: dict):

        codigo = str(item.get("codigo_cliente") or "")

        if not self.app.active_campaign:

            return

        if not messagebox.askyesno(

            "Restituir",

            f"¿Restituir {codigo} a su sección de origen?",

        ):

            return

        camp_id = self.app.active_campaign.id

        origen_actual = str(item.get("seccion_key") or GESTION_ESPECIAL_SECTION)

        email, name = self._admin_identity()

        def work():

            local = self.app.campaign_mgr.restore_from_gestion_especial(camp_id, codigo)

            if not local.get("success"):

                self._container.after(0, lambda: self._action_done(local))

                return

            dest = local.get("seccion_destino", "")

            result = self.app.firebase.update_client_zone(

                self._campaign_id(), origen_actual, codigo, dest,

                email, name, motivo="restitucion_gestion_especial",

                extra_fields={

                    "gestion_especial": False,

                    "motivo_gestion_especial": "",

                    "seccion_origen": "",

                },

            )

            if result.get("success"):

                self.app.campaign_mgr.update_local_client_section(

                    camp_id, codigo, dest, reset_gestion=False,

                )

            self._container.after(0, lambda: self._action_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _admin_identity(self) -> tuple[str, str]:

        auth = getattr(self.app, "auth_result", None)

        email = auth.email if auth else ""

        name = auth.nombre if auth else ""

        return email, name

    def _campaign_id(self) -> str:

        """ID Firestore operativo (cartera publicada a gestores)."""

        return "cartera_activa"

    def _move_pool(self, item: dict):

        codigo = str(item.get("codigo_cliente") or item.get("client_id"))

        seccion = str(item.get("seccion_key") or "")

        if not messagebox.askyesno("Confirmar", f"¿Mover {codigo} al pool de reasignación?"):

            return

        email, name = self._admin_identity()

        def work():

            result = self.app.firebase.move_client_to_pool(

                self._campaign_id(), seccion, codigo, email, name)

            if result.get("success") and self.app.active_campaign:

                self.app.campaign_mgr.update_local_client_section(

                    self.app.active_campaign.id, codigo, POOL_REASIGNACION_SECTION,

                    reset_gestion=False,

                )

            self._container.after(0, lambda: self._action_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _reassign(self, item: dict, dest: str):

        if not dest or dest == POOL_REASIGNACION_SECTION:

            messagebox.showwarning("Destino", "Seleccione una sección de gestor válida.")

            return

        codigo = str(item.get("codigo_cliente") or item.get("client_id"))

        origen = str(item.get("seccion_key") or "")

        if not messagebox.askyesno(

                "Confirmar reasignación",

                f"¿Reasignar {codigo}\n{origen} → {dest}?"):

            return

        email, name = self._admin_identity()

        def work():

            result = self.app.firebase.reassign_returned_client(

                self._campaign_id(), origen, codigo, dest, email, name)

            if result.get("success") and self.app.active_campaign:

                self.app.campaign_mgr.update_local_client_section(

                    self.app.active_campaign.id, codigo, dest, reset_gestion=True,

                )

            self._container.after(0, lambda: self._action_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _reject(self, item: dict):

        codigo = str(item.get("codigo_cliente") or item.get("client_id"))

        seccion = str(item.get("seccion_key") or "")

        if not messagebox.askyesno(

                "Rechazar devolución",

                f"¿Rechazar la devolución de {codigo}?\nEl gestor deberá continuar la gestión."):

            return

        email, name = self._admin_identity()

        def work():

            result = self.app.firebase.reject_return_request(

                self._campaign_id(), seccion, codigo, email, name)

            self._container.after(0, lambda: self._action_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _action_done(self, result: dict):

        if result.get("success"):

            self.app.set_status("Operación completada.")

            self._refresh()

        else:

            messagebox.showerror("Error", result.get("error", "Error desconocido"))

