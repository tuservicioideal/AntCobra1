"""Asistente de publicación de campaña — wizard de 5 pasos."""
from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox
import threading
from typing import TYPE_CHECKING

from .theme import *

if TYPE_CHECKING:
    from .app import App

_STATUS_COLORS = {
    "ok": SUCCESS,
    "warn": WARNING,
    "error": DANGER,
}
_STATUS_ICONS = {
    "ok": "✅",
    "warn": "⚠️",
    "error": "❌",
}


class CampaignWizardDialog(ctk.CTkToplevel):
    """Modal wizard para guiar publicación de campaña."""

    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.title("Asistente de campaña")
        self.geometry("640x520")
        self.minsize(560, 460)
        self.configure(fg_color=BG)
        self.transient(app)
        self.grab_set()

        self._gestores: list[dict] = []
        self._body = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._body.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            self._body,
            text="🚀 Asistente de publicación",
            font=font(FONT_SCALE["xl"], "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            self._body,
            text="Siga los pasos para publicar la campaña a gestores call y campo.",
            font=font(FONT_SCALE["sm"]),
            text_color=TEXT_SECONDARY,
            wraplength=580,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        self._steps_frame = ctk.CTkFrame(self._body, fg_color="transparent")
        self._steps_frame.pack(fill="x", pady=(0, 12))

        self._blockers_lbl = ctk.CTkLabel(
            self._body, text="", font=font(FONT_SCALE["sm"]),
            text_color=DANGER, wraplength=580, justify="left",
        )
        self._blockers_lbl.pack(anchor="w", pady=(0, 8))

        btn_row = ctk.CTkFrame(self._body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            btn_row, text="Cerrar", width=100, height=36,
            fg_color="transparent", border_width=1, border_color=BORDER,
            text_color=TEXT_SECONDARY, command=self.destroy,
        ).pack(side="right")

        self._load_readiness()

    def _load_readiness(self):
        def work():
            gestores = []
            if self.app.firebase_connected:
                try:
                    gestores = self.app.firebase.list_gestor_users()
                except Exception:
                    pass
            readiness = self.app.campaign_mgr.get_campaign_readiness(
                gestores_firestore=gestores,
                firebase_connected=self.app.firebase_connected,
            )
            if self.winfo_exists():
                self.after(0, lambda: self._render_steps(readiness, gestores))

        threading.Thread(target=work, daemon=True).start()

    def _render_steps(self, readiness: dict, gestores: list):
        self._gestores = gestores
        for w in self._steps_frame.winfo_children():
            w.destroy()

        blockers = readiness.get("blockers") or []
        if blockers:
            self._blockers_lbl.configure(text="Bloqueos: " + " · ".join(blockers))
        else:
            self._blockers_lbl.configure(text="")

        for step in readiness.get("steps", []):
            status = step.get("status", "warn")
            card = ctk.CTkFrame(
                self._steps_frame, fg_color=CARD_BG, corner_radius=10,
                border_width=1, border_color=BORDER,
            )
            card.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)

            left = ctk.CTkFrame(inner, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                left,
                text=f"{_STATUS_ICONS.get(status, '•')} {step.get('label', '')}",
                font=font(FONT_SCALE["base"], "bold"),
                text_color=_STATUS_COLORS.get(status, TEXT_PRIMARY),
            ).pack(anchor="w")
            ctk.CTkLabel(
                left, text=step.get("detail", ""),
                font=font(FONT_SCALE["xs"]), text_color=TEXT_SECONDARY,
            ).pack(anchor="w")

            action = step.get("action_key")
            if action:
                ctk.CTkButton(
                    inner, text="Ejecutar", width=90, height=30,
                    font=font(FONT_SCALE["xs"]),
                    command=lambda a=action: self._run_action(a),
                ).pack(side="right")

    def _run_action(self, action_key: str):
        if action_key == "evaluate_tramos":
            self._evaluate_tramos()
        elif action_key == "open_team":
            self.destroy()
            self.app.navigate_to("team")
        elif action_key == "call_distribute":
            self._distribute_call()
        elif action_key == "upload_full":
            self.destroy()
            self.app._on_upload()
        else:
            messagebox.showinfo("Asistente", "Paso informativo — no requiere acción.")

    def _evaluate_tramos(self):
        if not self.app.active_campaign:
            messagebox.showwarning("Tramos", "No hay campaña activa.")
            return

        def work():
            try:
                admin_email, admin_name = self.app._admin_audit_info()
                result = self.app.campaign_mgr.evaluate_tramos(
                    firebase_service=self.app.firebase if self.app.firebase_connected else None,
                    admin_email=admin_email,
                    admin_name=admin_name,
                )
                msg = result.resumen if hasattr(result, "resumen") else "Evaluación completada."
                if self.winfo_exists():
                    self.after(0, lambda: (
                        messagebox.showinfo("Tramos", msg[:2000]),
                        self._load_readiness(),
                    ))
            except Exception as e:
                if self.winfo_exists():
                    self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _distribute_call(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Call Center", "Conecte Firebase primero.")
            return
        if not messagebox.askyesno(
            "Repartir call",
            "¿Repartir cuentas tramo 1 sin asignar y publicar en Firebase?",
        ):
            return

        def work():
            try:
                admin = self.app._created_by_info()
                result = self.app.campaign_mgr.distribute_call_center(
                    gestores_firestore=self._gestores,
                    rebalance_all=False,
                    firebase_service=self.app.firebase,
                    auto_publish=True,
                    admin_uid=admin.get("uid", ""),
                    admin_nombre=admin.get("nombre", ""),
                )
                if self.winfo_exists():
                    self.after(0, lambda: self._on_distribute_done(result))
            except Exception as e:
                if self.winfo_exists():
                    self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _on_distribute_done(self, result):
        if result.errores:
            messagebox.showwarning("Call Center", "\n".join(result.errores))
        else:
            pub = result.firebase_publish or {}
            msg = (
                f"Asignadas {result.cuentas_asignadas} cuentas.\n"
                f"Motivo: {result.motivo}"
            )
            if pub.get("success"):
                msg += "\n✅ Publicado en Firebase."
            messagebox.showinfo("Call Center", msg)
        self._load_readiness()


def open_campaign_wizard(app: "App"):
    """Abre el asistente de campaña."""
    if not app.active_campaign:
        messagebox.showwarning(
            "Asistente",
            "Cargue un Excel y active una campaña primero.",
        )
        return
    CampaignWizardDialog(app)
