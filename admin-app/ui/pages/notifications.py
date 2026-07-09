"""Admin inbox — Excel update and campaign load notifications from Firestore."""
from __future__ import annotations

import customtkinter as ctk
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from ..theme import *
from ..components import SectionHeader

if TYPE_CHECKING:
    from ..app import App

_DETAIL_COLORS = {
    "nuevo": SUCCESS,
    "actualizado": ACCENT,
    "removido": DANGER,
    "seccion": INFO,
}

_DETAIL_ICONS = {
    "nuevo": "➕",
    "actualizado": "🔄",
    "removido": "➖",
    "seccion": "📍",
}


class NotificationsPage:
    """Inbox for admin/supervisor: base updates and campaign loads."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._list_frame = None
        self._status_lbl = None
        self._filter_var = ctk.StringVar(value="todas")
        self._notifications: list[dict] = []
        self._expanded_id: str | None = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        if not self.app.firebase_connected:
            ctk.CTkLabel(
                container,
                text="Conecte Firebase para ver notificaciones.",
                font=font(14),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            return

        if not self.app._can_see_notifications():
            ctk.CTkLabel(
                container,
                text="Su rol no tiene acceso al inbox de notificaciones.",
                font=font(14),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            return

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        SectionHeader(
            hdr,
            title="Notificaciones",
            subtitle="Actualizaciones de Excel y cargas de campaña",
            icon="🔔",
        ).pack(fill="x")

        toolbar = ctk.CTkFrame(container, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(toolbar, text="Filtrar:", font=font(12, "bold"),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 8))
        ctk.CTkSegmentedButton(
            toolbar,
            values=["todas", "no_leidas", "base_actualizada", "campana_cargada"],
            variable=self._filter_var,
            command=lambda _: self._apply_filter(),
            font=font(11),
        ).pack(side="left")

        if self.app._role_allows("upload"):
            ctk.CTkButton(
                toolbar, text="Subir Excel del banco", width=160, height=32,
                font=font(11, "bold"), fg_color="#0D9488", hover_color="#0F766E",
                command=self._go_upload_excel,
            ).pack(side="right", padx=(0, 8))

        self._refresh_btn = ctk.CTkButton(
            toolbar, text="🔄 Actualizar", width=120, height=32,
            font=font(11), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._refresh,
        )
        self._refresh_btn.pack(side="right")

        self._status_lbl = ctk.CTkLabel(
            container, text="", font=font(11), text_color=TEXT_MUTED,
        )
        self._status_lbl.pack(anchor="w", padx=12)

        self._list_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._list_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh()

    def _refresh(self):
        uid = self._user_uid()
        if not uid:
            return
        self._refresh_btn.configure(state="disabled", text="Cargando…")

        def work():
            items = self.app.firebase.list_admin_notifications(uid, limit=50)
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._on_data(items))

        threading.Thread(target=work, daemon=True).start()

    def _go_upload_excel(self):
        """Shortcut: open bank Excel update flow from notifications inbox."""
        self.app._pending_tab = "Campaña"
        self.app.navigate_to("inicio")
        if self.app.firebase_connected and self.app.active_campaign:
            self.app.after(400, self.app._on_update_base)

    def _user_uid(self) -> str:
        if self.app.auth_result and self.app.auth_result.success:
            return self.app.auth_result.uid or ""
        return ""

    def _on_data(self, items: list[dict]):
        self._notifications = items or []
        try:
            if self._refresh_btn.winfo_exists():
                self._refresh_btn.configure(state="normal", text="🔄 Actualizar")
        except Exception:
            pass
        self._apply_filter()
        self.app._refresh_notif_badge()

    def _apply_filter(self):
        filt = self._filter_var.get()
        filtered = list(self._notifications)
        if filt == "no_leidas":
            filtered = [n for n in filtered if not n.get("leida")]
        elif filt == "base_actualizada":
            filtered = [n for n in filtered if n.get("tipo") == "base_actualizada_admin"]
        elif filt == "campana_cargada":
            filtered = [n for n in filtered if n.get("tipo") == "campana_cargada_admin"]
        self._render_list(filtered)

    def _render_list(self, items: list[dict]):
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not items:
            ctk.CTkLabel(
                self._list_frame,
                text="No hay notificaciones",
                font=font(14),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            self._set_status("Sin notificaciones")
            return

        unread = sum(1 for n in items if not n.get("leida"))
        self._set_status(f"{len(items)} notificación(es) · {unread} sin leer")

        for notif in items:
            self._build_card(notif)

    def _set_status(self, text: str):
        if self._status_lbl and self._status_lbl.winfo_exists():
            self._status_lbl.configure(text=text)

    @staticmethod
    def _format_fecha(notif: dict) -> str:
        f = notif.get("fecha")
        if f is None:
            return ""
        try:
            if hasattr(f, "timestamp"):
                return datetime.fromtimestamp(f.timestamp()).strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
        return str(f)

    def _build_card(self, notif: dict):
        nid = notif.get("id", "")
        leida = bool(notif.get("leida"))
        expanded = self._expanded_id == nid
        bg = CARD_BG if leida else ACCENT_LIGHT
        border = BORDER if leida else ACCENT_MUTED

        card = ctk.CTkFrame(
            self._list_frame, fg_color=bg, corner_radius=12,
            border_width=1, border_color=border,
        )
        card.pack(fill="x", padx=8, pady=4)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        tipo = notif.get("tipo", "")
        tipo_label = {
            "base_actualizada_admin": "Base actualizada",
            "campana_cargada_admin": "Campaña cargada",
        }.get(tipo, tipo)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        title_row = ctk.CTkFrame(left, fg_color="transparent")
        title_row.pack(anchor="w", fill="x")
        if not leida:
            ctk.CTkLabel(title_row, text="●", font=font(10, "bold"),
                         text_color=ACCENT).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            title_row, text=notif.get("titulo", tipo_label),
            font=font(14, "bold"), text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            left, text=tipo_label,
            font=font(10), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        meta_parts = []
        fecha_txt = self._format_fecha(notif)
        if fecha_txt:
            meta_parts.append(fecha_txt)
        archivo = notif.get("archivo", "")
        if archivo:
            meta_parts.append(archivo)
        autor = notif.get("created_by_nombre", "")
        if autor:
            meta_parts.append(f"por {autor}")
        if meta_parts:
            ctk.CTkLabel(
                left, text=" · ".join(meta_parts),
                font=font(10), text_color=TEXT_SECONDARY,
            ).pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            left, text=notif.get("mensaje", ""),
            font=font(12), text_color=TEXT_SECONDARY,
            wraplength=720, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_row.pack(side="right")

        if not leida:
            ctk.CTkButton(
                btn_row, text="✓", width=36, height=32,
                font=font(14, "bold"), fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                command=lambda n=nid: self._mark_read(n),
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row,
            text="▲" if expanded else "▼",
            width=36, height=32,
            font=font(12),
            fg_color="#E2E8F0", hover_color=BORDER, text_color=TEXT_PRIMARY,
            command=lambda n=nid: self._toggle_expand(n),
        ).pack(side="left")

        detalles = notif.get("detalles") or []
        resumen = notif.get("resumen") or {}
        if resumen and expanded:
            res_frame = ctk.CTkFrame(card, fg_color=WHITE, corner_radius=8)
            res_frame.pack(fill="x", padx=14, pady=(0, 6))
            res_txt = []
            if tipo == "base_actualizada_admin":
                res_txt.append(
                    f"Nuevos: {resumen.get('total_new', 0)} · "
                    f"Actualizados: {resumen.get('total_updated', 0)} · "
                    f"Removidos: {resumen.get('total_removed', 0)} · "
                    f"Secciones: {resumen.get('secciones_afectadas', 0)}"
                )
                if resumen.get("truncated"):
                    res_txt.append(
                        f"(detalle truncado: {resumen.get('detalles_omitidos', 0)} más)"
                    )
            elif tipo == "campana_cargada_admin":
                res_txt.append(
                    f"Clientes: {resumen.get('total_clientes', 0)} · "
                    f"Secciones: {resumen.get('total_secciones', 0)} · "
                    f"Deuda: S/ {float(resumen.get('deuda_total_asignada', 0) or 0):,.2f}"
                )
            ctk.CTkLabel(
                res_frame, text="\n".join(res_txt),
                font=font(11, "bold"), text_color=TEXT_PRIMARY,
            ).pack(anchor="w", padx=10, pady=8)

        if expanded and detalles:
            det_frame = ctk.CTkFrame(card, fg_color=WHITE, corner_radius=8)
            det_frame.pack(fill="x", padx=14, pady=(0, 12))
            max_show = 80
            for i, det in enumerate(detalles[:max_show]):
                self._build_detail_row(det_frame, det)
            if len(detalles) > max_show:
                ctk.CTkLabel(
                    det_frame,
                    text=f"… y {len(detalles) - max_show} entradas más",
                    font=font(10), text_color=TEXT_MUTED,
                ).pack(anchor="w", padx=10, pady=6)

    def _build_detail_row(self, parent, det: dict):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)

        subtipo = det.get("tipo", "")
        color = _DETAIL_COLORS.get(subtipo, TEXT_SECONDARY)
        icon = _DETAIL_ICONS.get(subtipo, "•")

        ctk.CTkLabel(row, text=icon, font=font(12), width=24,
                     text_color=color).pack(side="left")

        name = det.get("nombre") or det.get("seccion_key", "")
        code = det.get("codigo_cliente", "")
        label = name
        if code:
            label = f"{name} ({code})" if name else code
        if subtipo == "seccion":
            label = det.get("seccion_key", name)

        ctk.CTkLabel(
            row, text=label, font=font(11, "bold"),
            text_color=TEXT_PRIMARY, width=220, anchor="w",
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            row, text=det.get("mensaje", ""),
            font=font(10), text_color=TEXT_SECONDARY,
            wraplength=480, justify="left", anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _toggle_expand(self, notif_id: str):
        self._expanded_id = None if self._expanded_id == notif_id else notif_id
        self._apply_filter()

    def _mark_read(self, notif_id: str):
        def work():
            ok = self.app.firebase.mark_notification_read(notif_id)
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._after_mark_read(notif_id, ok))

        threading.Thread(target=work, daemon=True).start()

    def _after_mark_read(self, notif_id: str, ok: bool):
        if ok:
            for n in self._notifications:
                if n.get("id") == notif_id:
                    n["leida"] = True
                    break
            self._apply_filter()
            self.app._refresh_notif_badge()
