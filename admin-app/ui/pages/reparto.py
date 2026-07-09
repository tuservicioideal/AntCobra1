"""Plan de Reparto — panel de afinidad cliente-asesor (campo + call)."""
from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
from typing import TYPE_CHECKING, Any, Callable

from services.reparto_planner import (
    RepartoPlan,
    ClienteReparto,
    build_reparto_plan,
    MANTIENE,
    NUEVO,
    REASIGNADO_HUERFANO,
    AFINIDAD_ROTA_CAMPO,
    SIN_GESTOR_CAMPO,
    OVERRIDE_MANUAL,
    NA_CAMPO,
)
from services.call_center_service import filter_call_gestores
from ..theme import *

if TYPE_CHECKING:
    from ..app import App

_PAGE_SIZE = 50

_AFINIDAD_LABELS = {
    MANTIENE: "Mantiene",
    NUEVO: "Nuevo",
    REASIGNADO_HUERFANO: "Reasignado",
    AFINIDAD_ROTA_CAMPO: "Sección cambió",
    SIN_GESTOR_CAMPO: "Sin gestor campo",
    OVERRIDE_MANUAL: "Override manual",
    NA_CAMPO: "Solo campo",
}


class RepartoPlanView:
    """Vista reutilizable del plan (página o modal de confirmación)."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        app: App,
        *,
        readonly: bool = False,
        on_override: Callable[[str, str], None] | None = None,
        show_table: bool = True,
    ):
        self.parent = parent
        self.app = app
        self.readonly = readonly
        self.on_override = on_override
        self.show_table = show_table
        self._plan: RepartoPlan | None = None
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        self._tree: ttk.Treeview | None = None
        self._page = 1
        self._filtered: list[ClienteReparto] = []
        self._call_gestores: list[dict] = []

    def render(self, plan: RepartoPlan, call_gestores: list[dict] | None = None):
        self._plan = plan
        self._call_gestores = call_gestores or []
        self._filtered = list(plan.clientes)
        self._page = 1

        for w in self.parent.winfo_children():
            w.destroy()

        if plan.conflictos_campo or plan.sin_gestor_campo:
            self._render_warnings(plan)

        self._build_kpis(plan)
        self._build_summaries(plan)
        if self.show_table:
            self._build_table()

    def _render_warnings(self, plan: RepartoPlan):
        box = ctk.CTkFrame(
            self.parent, fg_color=WARNING_LIGHT, corner_radius=10,
            border_width=1, border_color=WARNING,
        )
        box.pack(fill="x", padx=16, pady=(0, 8))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)
        lines = []
        if plan.conflictos_campo:
            lines.append(
                f"Conflictos de sección ({len(plan.conflictos_campo)}): "
                + ", ".join(plan.conflictos_campo[:5])
                + ("…" if len(plan.conflictos_campo) > 5 else "")
            )
        if plan.sin_gestor_campo:
            lines.append(
                f"Secciones sin gestor de campo ({len(plan.sin_gestor_campo)}): "
                + ", ".join(plan.sin_gestor_campo[:5])
                + ("…" if len(plan.sin_gestor_campo) > 5 else "")
            )
        ctk.CTkLabel(
            inner, text="\n".join(lines),
            font=font(FONT_SCALE["sm"]), text_color=TEXT_PRIMARY,
            justify="left", wraplength=900,
        ).pack(anchor="w")

    def _build_kpis(self, plan: RepartoPlan):
        strip = ctk.CTkFrame(self.parent, fg_color="transparent")
        strip.pack(fill="x", padx=16, pady=(0, 8))
        strip.grid_columnconfigure(tuple(range(6)), weight=1)

        nuevos = sum(1 for c in plan.clientes if c.estado_afinidad == NUEVO)
        reasig = sum(1 for c in plan.clientes if c.estado_afinidad == REASIGNADO_HUERFANO)
        mantiene = sum(1 for c in plan.clientes if c.estado_afinidad == MANTIENE)

        kpis = [
            ("total", "Clientes", str(plan.total_clientes), TEXT_PRIMARY),
            ("mantiene", "% Mantiene", f"{plan.pct_mantiene}%", SUCCESS),
            ("nuevos", "Nuevos call", str(nuevos), ACCENT),
            ("reasig", "Reasignados", str(reasig), WARNING),
            ("sin_gestor", "Sin gestor", str(len(plan.sin_gestor_campo)), DANGER),
            ("conflictos", "Conflictos", str(len(plan.conflictos_campo)), DANGER),
        ]
        for i, (key, label, value, color) in enumerate(kpis):
            card = ctk.CTkFrame(
                strip, fg_color=CARD_BG, corner_radius=10,
                border_width=1, border_color=BORDER,
            )
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            ctk.CTkLabel(
                card, text=label, font=font(FONT_SCALE["xs"]),
                text_color=TEXT_MUTED,
            ).pack(pady=(10, 0))
            lbl = ctk.CTkLabel(
                card, text=value, font=font(FONT_SCALE["lg"], "bold"),
                text_color=color,
            )
            lbl.pack(pady=(2, 10))
            self._kpi_labels[key] = lbl

    def _build_summaries(self, plan: RepartoPlan):
        row = ctk.CTkFrame(self.parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 8))
        row.grid_columnconfigure((0, 1), weight=1)

        for col, title, items in (
            (0, "Resumen gestores de campo", self._campo_summary_lines(plan)),
            (1, "Resumen asesores call", self._call_summary_lines(plan)),
        ):
            card = ctk.CTkFrame(
                row, fg_color=CARD_BG, corner_radius=10,
                border_width=1, border_color=BORDER,
            )
            card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 6 if col == 0 else 0))
            ctk.CTkLabel(
                card, text=title, font=font(FONT_SCALE["base"], "bold"),
                text_color=TEXT_PRIMARY,
            ).pack(anchor="w", padx=12, pady=(10, 4))
            body = ctk.CTkTextbox(
                card, height=120, font=font(FONT_SCALE["sm"]),
                fg_color="transparent", activate_scrollbars=True,
            )
            body.pack(fill="x", padx=10, pady=(0, 10))
            body.insert("1.0", items or "Sin datos")
            body.configure(state="disabled")

    def _campo_summary_lines(self, plan: RepartoPlan) -> str:
        lines = []
        for _key, r in sorted(
            plan.resumen_campo.items(),
            key=lambda x: x[1].get("gestor_nombre", ""),
        ):
            lines.append(
                f"• {r['gestor_nombre']}: {r['n']} cli · "
                f"S/ {r['monto']:,.0f} · rotos {r['rotos']}"
            )
        return "\n".join(lines[:20])

    def _call_summary_lines(self, plan: RepartoPlan) -> str:
        lines = []
        for g in plan.resumen_call:
            if g.num_cuentas <= 0:
                continue
            lines.append(
                f"• {g.nombre}: {g.num_cuentas} cli · "
                f"S/ {g.monto_total:,.0f} · nuevas {g.nuevas_asignadas}"
            )
        return "\n".join(lines[:20])

    def _build_table(self):
        tf = ctk.CTkFrame(
            self.parent, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        tf.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        cols = ("codigo", "nombre", "seccion", "gestor_campo", "asesor_call", "afinidad", "importe")
        hdrs = {
            "codigo": "Código", "nombre": "Nombre", "seccion": "Sección",
            "gestor_campo": "Gestor campo", "asesor_call": "Asesor call",
            "afinidad": "Afinidad", "importe": "Deuda",
        }
        style = apply_treeview_style("Reparto.Treeview")
        self._tree = ttk.Treeview(tf, columns=cols, show="headings", style=style, height=16)
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            w = 200 if c == "nombre" else 110
            self._tree.column(c, width=w, minwidth=60)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        if not self.readonly and self.on_override:
            self._tree.bind("<Double-1>", self._on_row_double_click)

        pag = ctk.CTkFrame(tf, fg_color="transparent")
        pag.pack(fill="x", padx=12, pady=(0, 8))
        self._page_label = ctk.CTkLabel(pag, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._page_label.pack(side="left")
        ctrl = ctk.CTkFrame(pag, fg_color="transparent")
        ctrl.pack(side="right")
        ctk.CTkButton(
            ctrl, text="◀", width=36, height=28,
            command=self._prev_page,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            ctrl, text="▶", width=36, height=28,
            command=self._next_page,
        ).pack(side="left", padx=2)
        self._fill_page()

    def _total_pages(self) -> int:
        n = len(self._filtered)
        return max(1, (n + _PAGE_SIZE - 1) // _PAGE_SIZE)

    def _fill_page(self):
        if not self._tree or not self._tree.winfo_exists():
            return
        self._tree.delete(*self._tree.get_children())
        total_pages = self._total_pages()
        if self._page > total_pages:
            self._page = total_pages
        start = (self._page - 1) * _PAGE_SIZE
        end = min(start + _PAGE_SIZE, len(self._filtered))
        for row in self._filtered[start:end]:
            self._tree.insert("", "end", values=(
                row.codigo_cliente,
                row.nombre[:40],
                row.seccion_key,
                row.gestor_campo_nombre or "—",
                row.call_gestor_nombre or "—",
                _AFINIDAD_LABELS.get(row.estado_afinidad, row.estado_afinidad),
                f"S/ {row.importe:,.2f}",
            ))
        if self._page_label and self._page_label.winfo_exists():
            self._page_label.configure(
                text=f"Mostrando {start + 1}-{end} de {len(self._filtered)} · "
                     f"Página {self._page}/{total_pages}",
            )

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self._fill_page()

    def _next_page(self):
        if self._page < self._total_pages():
            self._page += 1
            self._fill_page()

    def _on_row_double_click(self, _event=None):
        if not self._tree or not self.on_override:
            return
        sel = self._tree.selection()
        if not sel:
            return
        vals = self._tree.item(sel[0], "values")
        codigo = vals[0]
        row = next((c for c in self._filtered if c.codigo_cliente == codigo), None)
        if not row or row.fase_gestion != "call" or row.tramo_actual != 1:
            messagebox.showinfo("Reparto", "Solo se puede reasignar clientes en call tramo 1.")
            return
        names = [
            f"{g.get('nombre', g.get('uid'))} ({g.get('uid') or g.get('id')})"
            for g in self._call_gestores
        ]
        if not names:
            messagebox.showwarning("Reparto", "No hay asesores call activos.")
            return
        choice = simpledialog.askstring(
            "Reasignar asesor call",
            f"Cliente {codigo}\nAsesor actual: {row.call_gestor_nombre or '—'}\n\n"
            f"Gestores disponibles:\n" + "\n".join(names) + "\n\nIngrese UID del gestor:",
            parent=self.parent.winfo_toplevel(),
        )
        if not choice:
            return
        uid = choice.strip()
        valid = {g.get("uid") or g.get("id", "") for g in self._call_gestores}
        if uid not in valid:
            messagebox.showerror("Reparto", "UID no válido o gestor inactivo.")
            return
        self.on_override(codigo, uid)


class RepartoPage:
    """Página standalone del plan de reparto."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._plan_view: RepartoPlanView | None = None
        self._plan: RepartoPlan | None = None
        self._gestores: list[dict] = []
        self._overrides: dict[str, str] = {}
        self.confirm_mode = False
        self.on_confirm: Callable[[], None] | None = None
        self.on_cancel: Callable[[], None] | None = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="🧭 Plan de Reparto",
            font=font(FONT_SCALE["xl"], "bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            hdr,
            text="Vista previa del reparto con preservación de afinidad cliente-asesor",
            font=font(FONT_SCALE["sm"]), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        if not self.app.active_campaign:
            ctk.CTkLabel(
                container, text="Sin campaña activa.",
                font=font(FONT_SCALE["base"]), text_color=TEXT_MUTED,
            ).pack(pady=40)
            return

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkButton(
            actions, text="🔄 Actualizar plan", width=140,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._load_data,
        ).pack(side="left")

        if self.confirm_mode:
            ctk.CTkButton(
                actions, text="Confirmar y publicar", width=160,
                fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
                command=self._handle_confirm,
            ).pack(side="right", padx=(8, 0))
            ctk.CTkButton(
                actions, text="Cancelar", width=100,
                fg_color=TEXT_SECONDARY,
                command=self._handle_cancel,
            ).pack(side="right")

        self._plan_frame = ctk.CTkFrame(container, fg_color="transparent")
        self._plan_frame.pack(fill="both", expand=True)
        self._plan_view = RepartoPlanView(
            self._plan_frame, self.app,
            readonly=not self.confirm_mode,
            on_override=self._on_override if self.confirm_mode else None,
        )
        self._load_data()

    def set_plan(self, plan: RepartoPlan, gestores: list[dict], overrides: dict | None = None):
        """Carga un plan precalculado (flujo de confirmación post-Excel)."""
        self._plan = plan
        self._gestores = gestores
        self._overrides = dict(overrides or plan.overrides)
        if self._plan_view and self._container:
            call_g = filter_call_gestores(gestores)
            self._plan_view.render(plan, call_g)

    def _handle_confirm(self):
        if self.on_confirm:
            self.on_confirm()

    def _handle_cancel(self):
        if self.on_cancel:
            self.on_cancel()

    def _on_override(self, codigo: str, uid: str):
        self._overrides[codigo] = uid
        self._rebuild_plan()

    def _rebuild_plan(self):
        if not self.app.active_campaign:
            return
        camp_id = self.app.active_campaign.id
        prev = getattr(self.app, "_pending_seccion_snapshot", None)

        def work():
            try:
                gestores = self._gestores
                if not gestores and self.app.firebase_connected:
                    gestores = self.app.firebase.list_gestor_users()
                with self.app.campaign_mgr.db.session() as session:
                    plan = build_reparto_plan(
                        session, camp_id, gestores,
                        overrides=self._overrides,
                        seccion_keys_anteriores=prev,
                    )
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: self._on_plan_loaded(plan, gestores),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: messagebox.showerror("Reparto", str(e)),
                    )

        threading.Thread(target=work, daemon=True).start()

    def _load_data(self):
        self.app.set_status("Calculando plan de reparto…", 0.3)

        def work():
            try:
                gestores = []
                if self.app.firebase_connected:
                    gestores = self.app.firebase.list_gestor_users()
                camp_id = self.app.active_campaign.id
                prev = getattr(self.app, "_pending_seccion_snapshot", None)
                with self.app.campaign_mgr.db.session() as session:
                    plan = build_reparto_plan(
                        session, camp_id, gestores,
                        overrides=self._overrides,
                        seccion_keys_anteriores=prev,
                    )
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: self._on_plan_loaded(plan, gestores),
                    )
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(
                        0, lambda: messagebox.showerror("Reparto", str(e)),
                    )

        threading.Thread(target=work, daemon=True).start()

    def _on_plan_loaded(self, plan: RepartoPlan, gestores: list[dict]):
        self._plan = plan
        self._gestores = gestores
        self.app.set_status(
            f"Plan: {plan.total_clientes} clientes · {plan.pct_mantiene}% mantiene afinidad",
            1,
        )
        if self._plan_view:
            self._plan_view.render(plan, filter_call_gestores(gestores))


def show_reparto_confirm_dialog(
    app: App,
    plan: RepartoPlan,
    gestores: list[dict],
    *,
    on_confirm: Callable[[RepartoPlan, dict[str, str]], None],
    on_cancel: Callable[[], None] | None = None,
) -> ctk.CTkToplevel:
    """Modal compacto para confirmar reparto antes de publicar."""
    dlg = ctk.CTkToplevel(app)
    dlg.title("Confirmar plan de reparto")
    dlg.geometry("1100x720")
    dlg.transient(app)
    dlg.grab_set()

    overrides: dict[str, str] = dict(plan.overrides)

    hdr = ctk.CTkFrame(dlg, fg_color="transparent")
    hdr.pack(fill="x", padx=16, pady=12)
    ctk.CTkLabel(
        hdr, text="Revise el reparto antes de publicar a Firebase",
        font=font(FONT_SCALE["lg"], "bold"),
    ).pack(anchor="w")

    body = ctk.CTkScrollableFrame(dlg, fg_color=BG)
    body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def do_override(codigo: str, uid: str):
        overrides[codigo] = uid
        with app.campaign_mgr.db.session() as session:
            new_plan = build_reparto_plan(
                session, plan.campana_id, gestores,
                overrides=overrides,
                seccion_keys_anteriores=getattr(app, "_pending_seccion_snapshot", None),
            )
        view.render(new_plan, filter_call_gestores(gestores))

    view = RepartoPlanView(
        body, app, readonly=False, on_override=do_override, show_table=True,
    )
    view.render(plan, filter_call_gestores(gestores))

    footer = ctk.CTkFrame(dlg, fg_color="transparent")
    footer.pack(fill="x", padx=16, pady=12)

    def cancel():
        dlg.grab_release()
        dlg.destroy()
        if on_cancel:
            on_cancel()

    def confirm():
        with app.campaign_mgr.db.session() as session:
            final_plan = build_reparto_plan(
                session, plan.campana_id, gestores,
                overrides=overrides,
                seccion_keys_anteriores=getattr(app, "_pending_seccion_snapshot", None),
            )
        dlg.grab_release()
        dlg.destroy()
        on_confirm(final_plan, overrides)

    ctk.CTkButton(
        footer, text="Cancelar", width=120, fg_color=TEXT_SECONDARY,
        command=cancel,
    ).pack(side="right", padx=(8, 0))
    ctk.CTkButton(
        footer, text="Confirmar y publicar", width=160,
        fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
        command=confirm,
    ).pack(side="right")

    return dlg
