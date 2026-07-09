"""Sync page — Cloud synchronization controls."""
from __future__ import annotations

import datetime
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk
from tkinter import messagebox

from ..theme import *
from ..components import SectionHeader

if TYPE_CHECKING:
    from ..app import App


class SyncPage:
    """Page for managing cloud synchronization (download/upload/restore)."""

    _AUTO_SYNC_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes

    def __init__(self, app: App):
        self.app = app
        self._auto_sync_enabled: bool = False
        self._last_auto_sync_time: datetime.datetime | None = None
        self._auto_sync_after_id: str | None = None
        self._auto_sync_lbl: ctk.CTkLabel | None = None
        self._auto_sync_switch: ctk.CTkSwitch | None = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 12))
        SectionHeader(hdr, "Sincronización",
                      "Descarga y restauración de datos desde Firebase"
                      ).pack(side="left")

        # ── Connection status ────────────────────────────────
        status_card = ctk.CTkFrame(container, fg_color=CARD_BG,
                                   corner_radius=12, border_width=1,
                                   border_color=BORDER)
        status_card.pack(fill="x", padx=8, pady=8)
        sf = ctk.CTkFrame(status_card, fg_color="transparent")
        sf.pack(fill="x", padx=20, pady=12)

        fb_ok = self.app.firebase_connected
        fb_text = "Firebase conectado" if fb_ok else "Firebase desconectado"
        fb_color = SUCCESS if fb_ok else DANGER
        ctk.CTkLabel(sf, text=f"● {fb_text}", font=font(12, "bold"),
                     text_color=fb_color).pack(side="left")

        # Last sync info
        last = self.app.campaign_mgr.get_last_sync()
        if last:
            sync_text = (
                f"Última: {last['tipo']}  ·  {last['fecha']}  ·  "
                f"{last['registros_afectados']} registros ({last['resultado']})")
        else:
            sync_text = "Sin sincronizaciones registradas"
        ctk.CTkLabel(sf, text=sync_text, font=font(10),
                     text_color=TEXT_SECONDARY).pack(side="right")

        # ── Auto-sync toggle row ─────────────────────────────
        af = ctk.CTkFrame(status_card, fg_color="transparent")
        af.pack(fill="x", padx=20, pady=(0, 12))

        can_auto = self.app.firebase_connected and bool(self.app.active_campaign)
        self._auto_sync_switch = ctk.CTkSwitch(
            af,
            text="Sincronización automática (cada 5 min)",
            font=font(11),
            onvalue=True,
            offvalue=False,
            command=self._toggle_auto_sync,
        )
        if self._auto_sync_enabled:
            self._auto_sync_switch.select()
        if not can_auto:
            self._auto_sync_switch.configure(state="disabled")
        self._auto_sync_switch.pack(side="left")

        if self._last_auto_sync_time is not None:
            lbl_text = f"Última auto-sync: {self._time_ago(self._last_auto_sync_time)}"
        else:
            lbl_text = "Auto-sync: nunca ejecutado"
        self._auto_sync_lbl = ctk.CTkLabel(
            af, text=lbl_text, font=font(10), text_color=TEXT_SECONDARY)
        self._auto_sync_lbl.pack(side="right")

        # ── Sync Visits card ─────────────────────────────────
        self._section(container, "Sincronizar Visitas",
                      "Descarga las visitas y niveles de gestión realizadas en campo. "
                      "Actualiza los registros locales sin modificar la información base.",
                      btn_text="Sincronizar Visitas",
                      btn_command=self._on_sync_visits,
                      requires_campaign=True, requires_firebase=True)

        # ── Upload Catalog card ──────────────────────────────
        self._section(container, "Subir Catálogo de Niveles",
                      "Publica el catálogo de niveles de gestión (Nivel 1-4) a Firebase "
                      "para que los gestores vean las opciones correctas en sus apps.",
                      btn_text="Subir Catálogo",
                      btn_command=self._on_upload_catalog,
                      requires_campaign=False, requires_firebase=True)

        # ── Restore from Cloud card ──────────────────────────
        self._section(container, "Restaurar desde la Nube",
                      "Para instalaciones nuevas: descarga TODA la cartera activa "
                      "de Firebase y crea una campaña local completa. "
                      "Incluye datos de visitas, GPS y niveles de gestión.\n\n"
                      "Requiere que NO exista una campaña activa local.",
                      btn_text="Restaurar Cartera Completa",
                      btn_command=self._on_restore,
                      btn_color="#059669", btn_hover="#047857",
                      requires_campaign=False, requires_firebase=True,
                      warn_if_campaign=True)

        # Progress area
        self._progress_frame = ctk.CTkFrame(container, fg_color=CARD_BG,
                                            corner_radius=12, border_width=1,
                                            border_color=BORDER)
        self._progress_frame.pack(fill="x", padx=8, pady=8)
        pf = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
        pf.pack(fill="x", padx=20, pady=12)

        self._progress_lbl = ctk.CTkLabel(pf, text="", font=font(11),
                                          text_color=TEXT_SECONDARY)
        self._progress_lbl.pack(anchor="w")
        self._progress_bar = ctk.CTkProgressBar(pf, width=400, height=8,
                                                progress_color=ACCENT,
                                                fg_color=BORDER)
        self._progress_bar.pack(fill="x", pady=(4, 0))
        self._progress_bar.set(0)
        self._progress_frame.pack_forget()  # hidden initially

    # ── Helpers ──────────────────────────────────────────────
    def _section(self, parent, title, description, btn_text, btn_command,
                 btn_color=None, btn_hover=None,
                 requires_campaign=False, requires_firebase=False,
                 warn_if_campaign=False):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=8, pady=8)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text=title, font=font(13, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text=description, font=font(11),
                     text_color=TEXT_SECONDARY, wraplength=600, justify="left"
                     ).pack(anchor="w", pady=(4, 10))

        # Determine if button should be disabled
        disabled = False
        hint = ""
        if requires_firebase and not self.app.firebase_connected:
            disabled = True
            hint = "Conecte Firebase primero"
        elif requires_campaign and not self.app.active_campaign:
            disabled = True
            hint = "No hay campaña activa"
        elif warn_if_campaign and self.app.active_campaign:
            disabled = True
            hint = f"Cierre la campaña activa ({self.app.active_campaign.nombre}) primero"

        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.pack(anchor="w")

        btn = ctk.CTkButton(
            bf, text=btn_text, font=font(12, "bold"),
            fg_color=btn_color or ACCENT,
            hover_color=btn_hover or ACCENT_HOVER,
            height=38, corner_radius=10,
            command=btn_command,
            state="disabled" if disabled else "normal")
        btn.pack(side="left")

        if hint:
            ctk.CTkLabel(bf, text=f"  ({hint})", font=font(10),
                         text_color=TEXT_MUTED).pack(side="left", padx=4)

    def _show_progress(self, text: str, value: float = 0):
        self._progress_frame.pack(fill="x", padx=8, pady=8)
        self._progress_lbl.configure(text=text)
        self._progress_bar.set(value)

    def _hide_progress(self):
        self._progress_frame.pack_forget()

    # ── Actions ──────────────────────────────────────────────
    def _on_sync_visits(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.app.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return

        self._show_progress("Descargando visitas de Firebase…", 0.3)
        self.app.set_status("Sincronizando visitas…", 0.3)

        def work():
            try:
                visit_data = self.app.firebase.pull_visit_data("cartera_activa")
                updated = self.app.campaign_mgr.sync_visits_from_firebase(
                    campana_id=self.app.active_campaign.id,
                    firebase_data=visit_data)
                self.app.after(0, lambda: self._sync_visits_done(updated))
            except Exception as e:
                self.app.after(0, lambda: self._action_error("Sync visitas", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _sync_visits_done(self, updated):
        self._hide_progress()
        self.app.set_status(f"Visitas sincronizadas: {updated} actualizados", 1)
        messagebox.showinfo(
            "Sincronización",
            f"Se actualizaron {updated} registros de visitas desde Firebase.")

    def _on_upload_catalog(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return

        self._show_progress("Subiendo catálogo de niveles…", 0.5)
        self.app.set_status("Subiendo catálogo…", 0.5)

        def work():
            try:
                ok = self.app.campaign_mgr.upload_catalogo_niveles(
                    self.app.firebase)
                self.app.after(0, lambda: self._catalog_done(ok))
            except Exception as e:
                self.app.after(0, lambda: self._action_error("Catálogo", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _catalog_done(self, ok):
        self._hide_progress()
        if ok:
            self.app.set_status("Catálogo de niveles subido a Firebase", 1)
            messagebox.showinfo("Catálogo", "Catálogo de niveles subido correctamente.")
        else:
            self.app.set_status("Error subiendo catálogo", 0)
            messagebox.showerror("Error", "No se pudo subir el catálogo.")

    def _on_restore(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if self.app.active_campaign:
            messagebox.showwarning(
                "Campaña Activa",
                f"Ya existe una campaña activa: {self.app.active_campaign.nombre}\n\n"
                "Ciérrela antes de restaurar desde la nube.")
            return

        if not messagebox.askyesno(
            "Restaurar desde Firebase",
            "Se descargará TODA la cartera activa de Firebase y se creará "
            "una campaña local completa.\n\n"
            "Esto puede tomar unos minutos. ¿Continuar?"):
            return

        self._show_progress("Descargando cartera completa…", 0.1)
        self.app.set_status("Descargando cartera de Firebase…", 0.1)

        def progress_cb(current, total, msg):
            p = current / total if total else 0
            self.app.after(0, lambda: self._show_progress(
                f"Descargando: {msg} ({current}/{total})", p * 0.6))

        def work():
            try:
                firebase_data = self.app.firebase.download_full_cartera(
                    campaign_id="cartera_activa",
                    progress_callback=progress_cb)

                self.app.after(0, lambda: self._show_progress(
                    "Creando campaña local…", 0.7))

                campana, summary = self.app.campaign_mgr.restore_campaign_from_firebase(
                    firebase_data=firebase_data)

                self.app.after(0, lambda: self._restore_done(campana, summary))
            except Exception as e:
                self.app.after(0, lambda: self._action_error("Restaurar", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _restore_done(self, campana, summary):
        self._hide_progress()
        self.app.active_campaign = campana
        self.app.set_status(
            f"Restaurada: {summary['total_clientes']} clientes en "
            f"{summary['total_secciones']} secciones", 1)
        self.app._update_campaign_bar()
        self.app._invalidate_pages()

        messagebox.showinfo(
            "Restauración Completa",
            f"Campaña restaurada desde Firebase:\n\n"
            f"Nombre: {summary['nombre']}\n"
            f"Clientes: {summary['total_clientes']}\n"
            f"Secciones: {summary['total_secciones']}\n"
            f"Deuda asignada: S/ {summary['deuda_asignada']:,.2f}")

        self.app.navigate_to("campaign")

    def _action_error(self, context: str, msg: str):
        self._hide_progress()
        self.app.set_status(f"Error {context}: {msg}", 0)
        messagebox.showerror(f"Error — {context}", msg)

    # ── Auto-sync ─────────────────────────────────────────────
    def _toggle_auto_sync(self):
        """Called by the CTkSwitch when the user flips the toggle."""
        if self._auto_sync_switch is None:
            return
        self._auto_sync_enabled = bool(self._auto_sync_switch.get())
        if self._auto_sync_enabled:
            # Fire first sync immediately, then repeat on interval
            self._auto_sync_tick()
        else:
            if self._auto_sync_after_id is not None:
                try:
                    self.app.after_cancel(self._auto_sync_after_id)
                except Exception:
                    pass
                self._auto_sync_after_id = None

    def _schedule_next_auto_sync(self):
        if not self._auto_sync_enabled:
            return
        self._auto_sync_after_id = self.app.after(
            self._AUTO_SYNC_INTERVAL_MS, self._auto_sync_tick)

    def _auto_sync_tick(self):
        """Background polling entry point — runs silently every 5 min."""
        self._auto_sync_after_id = None
        if not self._auto_sync_enabled:
            return
        if not self.app.firebase_connected or not self.app.active_campaign:
            # Conditions not met — reschedule and wait
            self._schedule_next_auto_sync()
            return

        def work():
            try:
                visit_data = self.app.firebase.pull_visit_data("cartera_activa")
                updated = self.app.campaign_mgr.sync_visits_from_firebase(
                    campana_id=self.app.active_campaign.id,
                    firebase_data=visit_data,
                )
                self.app.after(0, lambda: self._auto_sync_done(updated))
            except Exception:
                # Silent failure — just reschedule
                self.app.after(0, self._schedule_next_auto_sync)

        threading.Thread(target=work, daemon=True).start()

    def _auto_sync_done(self, updated: int):
        self._last_auto_sync_time = datetime.datetime.now()
        self._update_auto_sync_label()
        if updated > 0:
            self.app.set_status(
                f"Auto-sync: {updated} visita(s) actualizadas "
                f"({self._time_ago(self._last_auto_sync_time)})",
                0.8)
        self._schedule_next_auto_sync()

    def _update_auto_sync_label(self):
        """Refresh the status label if the widget is still alive."""
        if self._auto_sync_lbl is None:
            return
        try:
            if not self._auto_sync_lbl.winfo_exists():
                self._auto_sync_lbl = None
                return
        except Exception:
            self._auto_sync_lbl = None
            return
        if self._last_auto_sync_time is not None:
            text = f"Última auto-sync: {self._time_ago(self._last_auto_sync_time)}"
        else:
            text = "Auto-sync: nunca ejecutado"
        self._auto_sync_lbl.configure(text=text)

    @staticmethod
    def _time_ago(dt: datetime.datetime) -> str:
        """Human-readable relative time, e.g. 'hace 3 min'."""
        minutes = int((datetime.datetime.now() - dt).total_seconds() / 60)
        if minutes < 1:
            return "hace menos de 1 min"
        if minutes == 1:
            return "hace 1 min"
        if minutes < 60:
            return f"hace {minutes} min"
        hours, rem = divmod(minutes, 60)
        return f"hace {hours}h {rem}min"

    def stop(self):
        """Called when navigating away — clear stale widget refs.
        The auto-sync timer keeps running so polling continues in background.
        """
        self._auto_sync_lbl = None
        self._auto_sync_switch = None
