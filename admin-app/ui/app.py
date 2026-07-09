from __future__ import annotations

"""
AntCobranzas Admin — Redesigned UI
Dark sidebar navigation + inline pages.
Built with CustomTkinter.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import threading
import os
import sys
import logging
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.excel_parser import parse_excel, get_hierarchy
from services.firebase_service import FirebaseService
from services.auth_service import AuthService, AuthResult
from services.word_generator import generate_all_letters, generate_tramo_letters, generate_final_report
from services.database import db_service, TramoEnum
from services.campaign_manager import CampaignManager
from services.tramo_engine import TramoEngine

from .theme import *
from .components import PageFrame

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# NAV STRUCTURE
# ═══════════════════════════════════════════════════════════════

NAV_ITEMS = [
    ("divider", "PRINCIPAL"),
    ("inicio",       "🏠", "Inicio"),
    ("divider", "HERRAMIENTAS"),
    ("database",     "🗃️", "Base de Datos"),
    ("team",         "👥", "Equipo"),
    ("callcenter",   "📞", "Call Center"),
    ("reparto",      "🧭", "Plan de Reparto"),
    ("alerts",       "🔔", "Alertas"),
    ("returns",      "↩️", "Devoluciones"),
    ("documents",    "📄", "Documentos"),
    ("export",       "📤", "Exportar"),
    ("sync",         "🔄", "Sincronización"),
    ("etiquetas",    "🏷️", "Etiquetas"),
    ("tracking",     "📍", "GPS"),
    ("settings",     "⚙️", "Configuración"),
]

# Features per page (for role checks)
_PAGE_FEATURE = {
    "inicio":    None,
    "database":  "monitor",
    "team":      "users",
    "callcenter": "users",
    "reparto":    "monitor",
    "alerts":      "alertas",
    "returns":     "devoluciones",
    "documents":   "letters",
    "export":    "export",
    "sync":      "sync",
    "etiquetas": "settings",
    "tracking":  "tracking",
    "settings":  "settings",
}


# ═══════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self, auth_result: AuthResult | None = None):
        super().__init__()
        self.auth_result = auth_result
        role_label = auth_result.display_role if auth_result else "Sin sesión"
        user_name = auth_result.nombre if auth_result else ""
        self.title(f"Reacudo Legal  ·  {role_label}: {user_name}")
        self.geometry("1400x900")  # Increased size for better visibility
        self.minsize(1200, 750)    # Increased minimum size
        self.configure(fg_color=BG)

        # ── Shared state ───────────────────────────────────────
        self.parsed_data: dict | None = None
        self.firebase = FirebaseService()
        self.firebase_connected = False
        self.campaign_mgr = CampaignManager()
        self.active_campaign: Any = None

        # ── Pages ──────────────────────────────────────────────
        self._pages: dict = {}
        self._active_page_name: str = ""
        self._active_page = None  # Current page instance
        self._nav_buttons: dict = {}
        self._pending_tab: str | None = None  # Tab to activate on next Inicio render
        self._notif_unread_count: int = 0
        self._notif_poll_job: str | None = None
        self._update_firestore_was_empty: bool = False
        self._pending_update_path: str = ""

        self._init_database()
        self._build()

        if self.auth_result and self.auth_result.success:
            self._auto_connect_firebase()

        if self._can_see_notifications():
            self._start_notif_polling()

    # ── Database ─────────────────────────────────────────────
    def _init_database(self):
        try:
            db_service.initialize()
            logger.info("Database initialized successfully")
            self.active_campaign = self.campaign_mgr.get_active_campaign()
            # Restore parsed_data from SQLite so Campaign page shows data on startup
            if self.active_campaign:
                try:
                    data = self.campaign_mgr.rebuild_parsed_data(self.active_campaign.id)
                    if data:
                        self.parsed_data = data
                        logger.info(
                            "Restored parsed_data from SQLite: %d clients",
                            data["summary"]["total_clientes"],
                        )
                except Exception as e:
                    logger.warning("Could not restore parsed_data from DB: %s", e)
            # Load dynamic campaign config into tramo engine globals
            from services.tramo_engine import load_config
            load_config()
            # Auto-evaluate tramos if enabled in config
            result = self.campaign_mgr.auto_evaluate_on_startup()
            if result and result.transiciones:
                logger.info("Auto-eval: %d tramo transitions applied", len(result.transiciones))
        except Exception as e:
            logger.error("Database initialization failed: %s", e)
            messagebox.showerror("Error de Base de Datos",
                                 f"No se pudo inicializar la base de datos:\n{e}")

    # ── UI Build ─────────────────────────────────────────────
    def _build(self):
        # Master grid: sidebar | content
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────
        self._sidebar = ctk.CTkFrame(self, fg_color=SIDEBAR_BG,
                                     corner_radius=0, width=SIDEBAR_WIDTH)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)

        # Brand
        brand = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=58)
        brand.pack(fill="x")
        brand.pack_propagate(False)
        ctk.CTkLabel(brand, text="🏦 Reacudo Legal",
                     font=font(15, "bold"), text_color=WHITE
                     ).pack(padx=16, pady=(16, 0), anchor="w")
        ctk.CTkLabel(brand, text="Sistema de Cobranzas",
                     font=font(9), text_color=SIDEBAR_TEXT
                     ).pack(padx=16, anchor="w")

        ctk.CTkFrame(self._sidebar, fg_color=SIDEBAR_DIVIDER,
                     height=1).pack(fill="x", padx=12, pady=(6, 2))

        # ── Bottom-anchored: logout + user info (pack before nav so they're always visible)
        ctk.CTkButton(
            self._sidebar, text="⎋ Cerrar sesión",
            font=font(FONT_SCALE['xs']), text_color=SIDEBAR_TEXT,
            fg_color="transparent", hover_color=DANGER_HOVER,
            height=28, corner_radius=6, anchor="center",
            command=self._on_logout
        ).pack(side="bottom", fill="x", padx=8, pady=(0, 8))

        if self.auth_result and self.auth_result.success:
            user_frame = ctk.CTkFrame(self._sidebar, fg_color=SIDEBAR_HOVER,
                                      corner_radius=8)
            user_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 2))
            uf_inner = ctk.CTkFrame(user_frame, fg_color="transparent")
            uf_inner.pack(fill="x", padx=10, pady=6)

            initials = "".join(
                w[0].upper() for w in (self.auth_result.nombre or "U").split()[:2])
            avatar = ctk.CTkFrame(uf_inner, fg_color=ACCENT, corner_radius=14,
                                  width=28, height=28)
            avatar.pack(side="left", padx=(0, 8))
            avatar.pack_propagate(False)
            ctk.CTkLabel(avatar, text=initials, font=font(10, "bold"),
                         text_color=WHITE
                         ).place(relx=0.5, rely=0.5, anchor="center")

            user_info = ctk.CTkFrame(uf_inner, fg_color="transparent")
            user_info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(user_info, text=self.auth_result.nombre or "",
                         font=font(FONT_SCALE['sm'], "bold"), text_color=WHITE
                         ).pack(anchor="w")
            ctk.CTkLabel(user_info, text=self.auth_result.display_role,
                         font=font(FONT_SCALE['xs']), text_color=SIDEBAR_TEXT
                         ).pack(anchor="w")

        # Nav items
        for item in NAV_ITEMS:
            if item[0] == "divider":
                _, label = item
                ctk.CTkLabel(self._sidebar, text=label,
                             font=font(FONT_SCALE['xs'], "bold"), text_color=SIDEBAR_TEXT,
                             anchor="w"
                             ).pack(fill="x", padx=18, pady=(8, 2))
                continue

            page_key, icon, label = item
            feature = _PAGE_FEATURE.get(page_key)
            if feature and not self._role_allows(feature):
                continue  # hide pages the user can't access

            btn = ctk.CTkButton(
                self._sidebar, text=f"{icon}  {label}",
                font=font(FONT_SCALE['sm']), text_color=SIDEBAR_TEXT,
                fg_color="transparent", hover_color=SIDEBAR_HOVER,
                height=SIDEBAR_ITEM_H, corner_radius=8, anchor="w",
                command=lambda k=page_key: self.navigate_to(k))
            btn.pack(fill="x", padx=8, pady=1)
            self._nav_buttons[page_key] = btn

        # ── Right area ───────────────────────────────────────
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Top bar
        top = ctk.CTkFrame(right, fg_color=WHITE, height=56, corner_radius=0)  # Increased height
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        self._page_title = ctk.CTkLabel(top, text="Inicio",
                                        font=font(FONT_SCALE['xl'], "bold"),
                                        text_color=TEXT_PRIMARY)
        self._page_title.pack(side="left", padx=24)

        # Notification bell (admin/supervisor)
        self._notif_bell_frame = ctk.CTkFrame(top, fg_color="transparent")
        self._notif_bell_frame.pack(side="right", padx=(0, 8))
        if self._can_see_notifications():
            self._notif_btn = ctk.CTkButton(
                self._notif_bell_frame, text="🔔", width=40, height=36,
                font=font(16), fg_color="transparent",
                hover_color=ACCENT_LIGHT, text_color=TEXT_PRIMARY,
                command=self._open_notifications,
            )
            self._notif_btn.pack(side="left")
            self._notif_badge = ctk.CTkLabel(
                self._notif_bell_frame, text="", width=22, height=18,
                font=font(9, "bold"), fg_color=DANGER, text_color=WHITE,
                corner_radius=9,
            )
            self._notif_badge.place(relx=0.85, rely=0.08, anchor="ne")
            self._notif_badge.place_forget()

        self._fb_badge = ctk.CTkLabel(top, text="● Firebase desconectado",
                                      font=font(FONT_SCALE['sm']), text_color=TEXT_MUTED)
        self._fb_badge.pack(side="right", padx=20)

        # Campaign mini-bar (only if active)
        self._camp_mini = ctk.CTkLabel(top, text="", font=font(FONT_SCALE['sm']),
                                       text_color=TEXT_SECONDARY)
        self._camp_mini.pack(side="right", padx=(0, 16))

        # Content
        self._content = PageFrame(right)
        self._content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 4))

        # Status bar
        sb = ctk.CTkFrame(right, fg_color=WHITE, height=32, corner_radius=0)  # Increased height
        sb.grid(row=2, column=0, sticky="ew")
        sb.grid_propagate(False)

        self._status = ctk.CTkLabel(sb, text="Listo", font=font(FONT_SCALE['sm']),
                                    text_color=TEXT_SECONDARY)
        self._status.pack(side="left", padx=16)

        self._progress = ctk.CTkProgressBar(sb, width=200, height=8,  # Increased width
                                            progress_color=ACCENT,
                                            fg_color=BORDER)
        self._progress.pack(side="right", padx=16, pady=10)
        self._progress.set(0)

        # Initial page
        self._update_campaign_bar()
        self.navigate_to("inicio")

    # ── Navigation ───────────────────────────────────────────
    def navigate_to(self, page_key: str):
        """Switch to a page by key name."""
        # Redirect tab-only pages to Inicio with pending tab
        _tab_redirect = {
            "campaign": "Campaña",
            "monitor":  "Monitor",
            "stats":    "Estadísticas",
        }
        if page_key in _tab_redirect:
            self._pending_tab = _tab_redirect[page_key]
            page_key = "inicio"

        if self._active_page and hasattr(self._active_page, "stop"):
            self._active_page.stop()

        # Update sidebar highlights
        for key, btn in self._nav_buttons.items():
            if key == page_key:
                btn.configure(fg_color=SIDEBAR_ACTIVE,
                              text_color=SIDEBAR_TEXT_ACT)
            else:
                btn.configure(fg_color="transparent",
                              text_color=SIDEBAR_TEXT)

        # Title map
        titles = {
            "inicio": "Inicio", "database": "Base de Datos", "team": "Equipo",
            "callcenter": "Call Center", "reparto": "Plan de Reparto", "tracking": "GPS",
            "alerts": "Alertas", "returns": "Devoluciones", "documents": "Documentos",
            "export": "Exportar", "sync": "Sincronización",
            "etiquetas": "Etiquetas",
            "settings": "Configuración",
            "notifications": "Notificaciones",
        }
        self._page_title.configure(text=titles.get(page_key, ""))

        # Lazy-load page instances
        if page_key not in self._pages:
            self._pages[page_key] = self._create_page(page_key)

        page = self._pages[page_key]
        self._active_page = page
        self._active_page_name = page_key

        if page:
            # Always scroll to the top before rendering a new module.
            # Pages destroy their own children directly (without calling clear()),
            # so the canvas viewport must be reset here — before render() runs —
            # to prevent the new (possibly shorter) module from appearing blank
            # because the canvas is still scrolled to the bottom of the old page.
            self._content.scroll_to_top()
            page.render(self._content)

    def _create_page(self, key: str):
        from .pages.dashboard import DashboardPage
        from .pages.database import DatabasePage
        from .pages.team import TeamPage
        from .pages.call_center import CallCenterPage
        from .pages.reparto import RepartoPage
        from .pages.tracking import TrackingPage
        from .pages.alerts import AlertsPage
        from .pages.returns import ReturnsPage
        from .pages.documents import DocumentsPage
        from .pages.settings import SettingsPage
        from .pages.export import ExportPage
        from .pages.sync import SyncPage
        from .pages.etiquetas import EtiquetasPage
        from .pages.notifications import NotificationsPage

        mapping = {
            "inicio":    DashboardPage,
            "database":  DatabasePage,
            "team":      TeamPage,
            "callcenter": CallCenterPage,
            "reparto":    RepartoPage,
            "tracking":  TrackingPage,
            "alerts":    AlertsPage,
            "returns":   ReturnsPage,
            "documents": DocumentsPage,
            "export":    ExportPage,
            "sync":      SyncPage,
            "etiquetas": EtiquetasPage,
            "settings":  SettingsPage,
            "notifications": NotificationsPage,
        }
        cls = mapping.get(key)
        return cls(self) if cls else None

    # ── Public API (for pages) ───────────────────────────────
    def set_status(self, text: str, progress: float | None = None):
        self._status.configure(text=text)
        if progress is not None:
            self._progress.set(progress)

    def _can_see_notifications(self) -> bool:
        if not self.auth_result or not self.auth_result.success:
            return False
        return self.auth_result.rol in ("admin", "supervisor")

    def _created_by_info(self) -> dict:
        if self.auth_result and self.auth_result.success:
            return {
                "uid": self.auth_result.uid or "",
                "nombre": self.auth_result.nombre or "",
            }
        return {}

    def _admin_audit_info(self) -> tuple[str, str]:
        """Email y nombre del admin conectado (auditoría Firebase)."""
        ar = self.auth_result
        if ar and ar.success:
            return ar.email or "", ar.nombre or ""
        return "", ""

    def _open_notifications(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase para ver notificaciones.")
            return
        self.navigate_to("notifications")
        page = self._pages.get("notifications")
        if page and hasattr(page, "_refresh"):
            page._refresh()

    def _refresh_notif_badge(self):
        if not self._can_see_notifications():
            return
        if not hasattr(self, "_notif_badge"):
            return
        uid = self.auth_result.uid if self.auth_result else ""
        if not uid or not self.firebase_connected:
            self._notif_badge.place_forget()
            return

        def work():
            try:
                count = self.firebase.count_unread_admin_notifications(uid)
            except Exception:
                count = 0
            self.after(0, lambda: self._apply_notif_badge(count))

        threading.Thread(target=work, daemon=True).start()

    def _apply_notif_badge(self, count: int):
        self._notif_unread_count = count
        if not hasattr(self, "_notif_badge"):
            return
        if count > 0:
            label = "9+" if count > 9 else str(count)
            self._notif_badge.configure(text=label)
            self._notif_badge.place(relx=0.85, rely=0.08, anchor="ne")
        else:
            self._notif_badge.place_forget()

    def _start_notif_polling(self):
        self._refresh_notif_badge()

        def schedule():
            if self.winfo_exists():
                self._notif_poll_job = self.after(60000, poll)

        def poll():
            self._refresh_notif_badge()
            schedule()

        schedule()

    def _role_allows(self, feature: str) -> bool:
        if not self.auth_result:
            return True
        rol = self.auth_result.rol
        rules = {
            "load_excel":   ("admin", "supervisor"),
            "upload":       ("admin", "supervisor"),
            "users":        ("admin", "supervisor"),
            "letters":      ("admin", "supervisor"),
            "settings":     ("admin",),
            "export":       ("admin", "supervisor"),
            "sync":         ("admin", "supervisor"),
            "monitor":      ("admin", "supervisor", "asistente"),
            "stats":        ("admin", "supervisor", "asistente"),
            "alertas":      ("admin", "supervisor", "asistente"),
            "devoluciones": ("admin", "supervisor"),
            "tracking":     ("admin", "supervisor"),
            "distribucion": ("admin", "supervisor"),
            "final_report": ("admin", "supervisor"),
            "eval_tramos":  ("admin", "supervisor"),
            "sync_visits":  ("admin", "supervisor", "asistente"),
            "connect_fb":   ("admin", "supervisor"),
            "delete_campaign": ("admin",),
        }
        allowed = rules.get(feature, ("admin",))
        return rol in allowed

    def _update_campaign_bar(self):
        camp = self.active_campaign
        if not camp:
            self._camp_mini.configure(text="Sin campaña")
            return
        try:
            with db_service.session() as session:
                camp = session.get(type(camp), camp.id)
                if camp is None:
                    self.active_campaign = None
                    self._camp_mini.configure(text="Sin campaña")
                    return
                dia = camp.dia_actual
                tramo = TramoEngine.get_tramo_for_day(dia)
                tramo_short = {
                    TramoEnum.NONE: "N/A",
                    TramoEnum.TRAMO_1: "T1",
                    TramoEnum.TRAMO_2: "T2",
                    TramoEnum.TRAMO_3: "T3",
                }
                self._camp_mini.configure(
                    text=f"{camp.nombre}  ·  Día {dia}/60  ·  "
                         f"{tramo_short.get(tramo, '?')}  ·  "
                         f"{camp.total_clientes} clientes")
        except Exception:
            pass

    # ── Actions (called by pages) ────────────────────────────
    def _on_load_excel(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Excel de cartera",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return

        if self.active_campaign:
            if not messagebox.askyesno(
                "Campaña Existente",
                f"Ya existe una campaña activa: {self.active_campaign.nombre}\n\n"
                "¿Desea cerrarla y crear una nueva con este archivo?"):
                return
            try:
                self.campaign_mgr.close_campaign(self.active_campaign.id)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cerrar la campaña:\n{e}")
                return

        self.set_status("Leyendo Excel y creando campaña…", 0.2)

        def work():
            try:
                campana, summary = self.campaign_mgr.create_campaign_from_excel(
                    file_path=path,
                    nombre=f"Campaña {os.path.basename(path).split('.')[0]}",
                )
                d = parse_excel(path)
                self.after(0, lambda: self._excel_ok(d, path, campana, summary))
            except Exception as e:
                self.after(0, lambda: self._excel_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _excel_ok(self, data, path, campana=None, summary=None):
        self.parsed_data = data
        n = data["summary"]["total_clientes"]

        if campana:
            self.active_campaign = campana
            self.set_status(
                f"Campaña creada: {n} clientes → SQLite  ·  "
                f"{(summary or {}).get('total_secciones', 0)} secciones", 1)
            self._update_campaign_bar()
            self._auto_evaluate_tramos()
            if self.firebase_connected:
                def notify_work():
                    try:
                        count = self.firebase.send_admin_campaign_loaded_notification(
                            data["summary"],
                            by_seccion=data.get("by_seccion", {}),
                            campaign_id="cartera_activa",
                            campana_local_id=campana.id,
                            archivo=os.path.basename(path),
                            created_by=self._created_by_info(),
                        )
                        self.after(0, lambda: self._excel_notif_ok(count))
                    except Exception as e:
                        logger.warning("No se pudo crear notificación de campaña: %s", e)
                        self.after(0, lambda: self._excel_notif_err(str(e)))
                threading.Thread(target=notify_work, daemon=True).start()
            else:
                self.set_status(
                    "Campaña creada · Firebase desconectado (sin notificación)", 1)
        else:
            self.set_status(f"{n} clientes cargados", 1)

        # Re-render current page
        self._invalidate_pages()
        self.navigate_to(self._active_page_name or "campaign")

    def _excel_err(self, msg):
        self.set_status(f"Error: {msg}", 0)
        messagebox.showerror("Error", msg)

    def _excel_notif_ok(self, count: int):
        if count:
            self._refresh_notif_badge()
            self.set_status(f"Campaña creada · {count} notificación(es) admin enviada(s)", 1)

    def _excel_notif_err(self, msg: str):
        self.set_status(f"Campaña creada (notificación no enviada: {msg})", 1)

    def _on_connect_firebase(self):
        path = filedialog.askopenfilename(
            title="Clave de servicio Firebase (.json)",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if not path:
            return
        self.set_status("Conectando con Firebase…", 0.4)

        def work():
            try:
                self.firebase.initialize(path)
                ok = self.firebase.test_connection()
                self.after(0, lambda: self._fb_ok(ok))
            except Exception as e:
                self.after(0, lambda: self._fb_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _fb_ok(self, ok):
        if ok:
            self.firebase_connected = True
            self._fb_badge.configure(text="● Firebase conectado",
                                     text_color=SUCCESS)
            self.set_status("Firebase conectado", 1)
            if self._can_see_notifications():
                self._refresh_notif_badge()
        else:
            self._fb_err("No se pudo verificar la conexión")

    def _fb_err(self, msg):
        self.set_status(f"Firebase: {msg}", 0)
        messagebox.showerror("Firebase", msg)

    def _auto_connect_firebase(self):
        from config import SERVICE_ACCOUNT_KEY_PATH
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(app_dir, SERVICE_ACCOUNT_KEY_PATH)
        if not os.path.exists(key_path):
            self.set_status("No se encontró clave de servicio Firebase", 0)
            return
        self.set_status("Conectando con Firebase…", 0.4)

        def work():
            try:
                self.firebase.initialize(key_path)
                ok = self.firebase.test_connection()
                self.after(0, lambda: self._fb_ok(ok))
            except Exception as e:
                self.after(0, lambda: self._fb_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _on_upload(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign and not self.parsed_data:
            messagebox.showwarning("Datos", "Cargue un Excel primero.")
            return

        if self.active_campaign:
            camp_id = self.active_campaign.id
            stats = self.campaign_mgr.get_campaign_stats(camp_id)
            total = stats.get("total_clientes", 0)
            secciones = len(stats.get("secciones", []))
            if not messagebox.askyesno(
                    "Confirmar",
                    f"Distribuir {total} clientes de {secciones} secciones "
                    f"a Firebase?\n\n"
                    f"Se revisará el plan de reparto antes de publicar."):
                return
            self.set_status("Calculando plan de reparto…", 0.2)

            def prepare():
                try:
                    gestores = (
                        self.firebase.list_gestor_users()
                        if self.firebase_connected else []
                    )
                    plan = self.campaign_mgr.build_reparto_plan_for_campaign(
                        camp_id, gestores,
                    )
                    self.after(0, lambda: self._confirm_upload_with_reparto(
                        camp_id, plan, gestores,
                    ))
                except Exception as e:
                    self.after(0, lambda: self._upload_err(str(e)))

            threading.Thread(target=prepare, daemon=True).start()
        else:
            s = self.parsed_data["summary"]
            if not messagebox.askyesno(
                    "Confirmar",
                    f"Distribuir {s['total_clientes']} clientes "
                    f"a {s['total_secciones']} gestores?"):
                return

            def cb(cur, tot, msg):
                p = cur / tot if tot else 0
                self.after(0, lambda: self.set_status(
                    f"Subiendo {cur}/{tot}: {msg}", p))

            def work():
                try:
                    r = self.firebase.upload_cartera(
                        self.parsed_data["by_seccion"], progress_callback=cb)
                    # Upload territorial catalog
                    if self.parsed_data and "all_clients" in self.parsed_data:
                        hierarchy = get_hierarchy(self.parsed_data["all_clients"])
                        self.firebase.upload_estructura_territorial(hierarchy)
                    try:
                        cleanup = self.firebase.cleanup_old_campaigns()
                        r["cleaned_campaigns"] = len(cleanup.get("deleted", []))
                    except Exception:
                        r["cleaned_campaigns"] = 0
                    self.after(0, lambda: self._upload_ok(r))
                except Exception as e:
                    self.after(0, lambda: self._upload_err(str(e)))
            threading.Thread(target=work, daemon=True).start()

    def _confirm_upload_with_reparto(self, camp_id: str, plan, gestores: list):
        def on_confirm(final_plan, _overrides):
            self.set_status("Publicando a Firebase…", 0.3)

            def cb(cur, tot, msg):
                p = cur / tot if tot else 0
                self.after(0, lambda: self.set_status(
                    f"Subiendo {cur}/{tot}: {msg}", 0.3 + 0.6 * p))

            def do_upload():
                payload = self.campaign_mgr.get_firebase_payload(camp_id)
                tramo_info = self.campaign_mgr.build_etapa_summary(camp_id)
                r = self.firebase.upload_cartera_filtered(
                    by_seccion=payload["by_seccion"],
                    campaign_id="cartera_activa",
                    tramo_info=tramo_info,
                    progress_callback=cb,
                )
                if self.parsed_data and "all_clients" in self.parsed_data:
                    hierarchy = get_hierarchy(self.parsed_data["all_clients"])
                    self.firebase.upload_estructura_territorial(hierarchy)
                try:
                    cleanup = self.firebase.cleanup_old_campaigns()
                    r["cleaned_campaigns"] = len(cleanup.get("deleted", []))
                except Exception:
                    r["cleaned_campaigns"] = 0
                return r

            def on_ok(r, _cambios):
                self._upload_ok(r)

            self._publish_after_reparto_upload(
                camp_id, final_plan, upload_fn=do_upload, success_fn=on_ok,
            )

        def on_cancel():
            self.set_status("Distribución cancelada", 0)

        self._show_reparto_confirm(plan, gestores, on_confirm, on_cancel=on_cancel)

    def _upload_ok(self, r):
        if r["success"]:
            pv = r.get("preserved_visits", 0)
            pv_txt = f"  ·  {pv} visitas conservadas" if pv else ""
            self.campaign_mgr._record_sync(
                "upload",
                r.get("total_uploaded", 0),
                "ok",
                f"Campaña {r.get('campaign_id', 'cartera_activa')}",
            )
            self.set_status(
                f"{r['total_uploaded']} clientes distribuidos{pv_txt}", 1)
            pv_msg = (f"\n({pv} clientes ya visitados — su estado fue "
                      f"conservado)") if pv else ""
            messagebox.showinfo("Distribución Exitosa",
                f"Se distribuyeron {r['total_uploaded']} clientes.{pv_msg}\n"
                f"Campaña: {r['campaign_id']}")
        else:
            self.set_status(f"Errores: {r['errors']}", 0)

    def _upload_err(self, msg):
        self.set_status(f"Error: {msg}", 0)
        messagebox.showerror("Error", msg)

    def _show_reparto_confirm(
        self,
        plan,
        gestores: list,
        on_confirm_publish,
        *,
        on_cancel=None,
    ):
        from .pages.reparto import show_reparto_confirm_dialog

        show_reparto_confirm_dialog(
            self,
            plan,
            gestores,
            on_confirm=on_confirm_publish,
            on_cancel=on_cancel,
        )

    def _publish_after_reparto_upload(
        self,
        camp_id: str,
        plan,
        *,
        upload_fn,
        success_fn,
    ):
        """Aplica plan en SQLite y ejecuta upload_fn() -> result dict."""
        admin_uid, admin_nombre = self._admin_audit_info()

        def work():
            try:
                cambios = self.campaign_mgr.apply_reparto_plan(
                    camp_id,
                    plan,
                    admin_uid=admin_uid,
                    admin_nombre=admin_nombre,
                )
                r = upload_fn()
                recon = self.campaign_mgr.reconcile_call_sections_after_update(
                    camp_id,
                    plan,
                    self.firebase,
                    cambios=cambios,
                )
                r["reparto_reconciled"] = recon.get("uploaded", 0)
                if recon.get("errors"):
                    r.setdefault("warnings", []).extend(recon["errors"])
                self.after(0, lambda: success_fn(r, cambios))
            except Exception as e:
                self.after(0, lambda: self._upload_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    # ── Update Base (new Excel → diff → selective upload → notify) ──
    def _on_update_base(self):
        """Load a new Excel, compare with current Firestore data,
        show a summary dialog, and upload only the changes."""
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign:
            messagebox.showwarning("Campaña",
                                   "No hay campaña activa para actualizar.")
            return

        path = filedialog.askopenfilename(
            title="Seleccionar Excel actualizado",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return

        self.set_status("Analizando cambios en la base de datos…", 0.2)

        def work():
            try:
                old_by_seccion = self.firebase.read_current_cartera("cartera_activa")
                self._update_firestore_was_empty = not bool(old_by_seccion)
                # Always pull latest field updates (visits/contact) before diffing a new base.
                visit_data = self.firebase.pull_visit_data("cartera_activa")
                self.campaign_mgr.sync_visits_from_firebase(
                    campana_id=self.active_campaign.id,
                    firebase_data=visit_data,
                )
                new_data, report = self.campaign_mgr.update_campaign_from_excel(
                    file_path=path,
                    firebase_service=self.firebase,
                    old_by_seccion=old_by_seccion,
                )
                self.after(0, lambda: self._show_update_summary(
                    new_data, report, path))
            except Exception as e:
                self.after(0, lambda: self._update_base_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _show_update_summary(self, new_data, report, path):
        """Show a dialog with the change report and ask to proceed."""
        self.set_status("Análisis completo", 0.5)

        if not report.has_changes:
            messagebox.showinfo(
                "Sin Cambios",
                "La base de datos está idéntica al Excel cargado.\n"
                "No hay cambios que aplicar.")
            self.set_status("Sin cambios detectados", 0)
            return

        # Build summary message
        lines = [
            f"Archivo: {os.path.basename(path)}\n",
            f"Clientes nuevos: {report.total_new}",
            f"Clientes actualizados: {report.total_updated}",
            f"Clientes removidos: {report.total_removed}",
            f"Sin cambios: {report.total_unchanged}",
            f"\nSecciones afectadas: {len(report.affected_sections)}",
        ]

        # Show up to 10 important changes
        important = []
        for sk, sec in report.sections.items():
            for cc in sec.updated_clients:
                for fc in cc.important_changes:
                    important.append(
                        f"  • {cc.nombre_completo}: {fc.label} {fc.format_values()}"
                    )
        if important:
            lines.append("\nCambios destacados:")
            lines.extend(important[:10])
            if len(important) > 10:
                lines.append(f"  … y {len(important) - 10} más")

        msg = "\n".join(lines)
        checklist = (
            "\n\nAntes de aplicar:\n"
            f"  ✓ Firebase conectado\n"
            f"  ✓ Visitas del campo sincronizadas a SQLite\n"
            f"  ✓ Resumen revisado ({report.total_new} nuevos, "
            f"{report.total_updated} actualizados, "
            f"{report.total_removed} removidos)"
        )

        if not messagebox.askyesno(
            "Confirmar Actualización",
            f"{msg}{checklist}\n\n"
            "¿Desea aplicar estos cambios a SQLite y revisar el plan de reparto?"
        ):
            self.set_status("Actualización cancelada", 0)
            return

        self.parsed_data = new_data
        self._pending_update_path = path
        self.set_status("Aplicando Excel a SQLite…", 0.4)

        def sqlite_work():
            try:
                archivo = os.path.basename(path)
                camp_id = self.active_campaign.id
                prev_sections = self.campaign_mgr.apply_excel_update_to_sqlite(
                    camp_id,
                    new_data,
                    report,
                    ultimo_excel=archivo,
                )
                self._pending_seccion_snapshot = prev_sections
                admin_email, admin_name = self._admin_audit_info()
                self.campaign_mgr.evaluate_tramos(
                    campana_id=camp_id,
                    auto_apply=True,
                    firebase_service=self.firebase if self.firebase_connected else None,
                    admin_email=admin_email,
                    admin_name=admin_name,
                )
                gestores = (
                    self.firebase.list_gestor_users()
                    if self.firebase_connected else []
                )
                plan = self.campaign_mgr.build_reparto_plan_for_campaign(
                    camp_id,
                    gestores,
                    seccion_keys_anteriores=prev_sections,
                )
                self.after(0, lambda: self._confirm_update_with_reparto(
                    new_data, report, path, plan, gestores,
                ))
            except Exception as e:
                self.after(0, lambda: self._update_base_err(str(e)))

        threading.Thread(target=sqlite_work, daemon=True).start()

    def _confirm_update_with_reparto(
        self, new_data, report, path, plan, gestores: list,
    ):
        def on_confirm(final_plan, _overrides):
            self.set_status("Publicando cambios a Firebase…", 0.6)
            archivo = os.path.basename(path)
            camp_id = self.active_campaign.id

            def do_upload():
                tramo_info = self.campaign_mgr.build_etapa_summary(camp_id)
                payload = self.campaign_mgr.get_firebase_payload(
                    camp_id, solo_activos=True,
                )
                r = self.firebase.upload_cartera_update(
                    by_seccion=payload["by_seccion"],
                    change_report=report,
                    campaign_id="cartera_activa",
                    excel_by_seccion=new_data["by_seccion"],
                    ultimo_excel=archivo,
                    tramo_info=tramo_info,
                    progress_callback=lambda c, t, m: self.after(
                        0, lambda: self.set_status(
                            f"Subiendo {c}/{t}: {m}",
                            0.6 + 0.3 * (c / t if t else 0))),
                )
                notif_result = self.firebase.send_update_notifications(
                    report, "cartera_activa",
                )
                r["notifications_sent"] = notif_result.get("notifications_sent", 0)
                r["notif_warnings"] = notif_result.get("warnings", [])
                r["sections_without_gestor"] = notif_result.get(
                    "sections_without_gestor", [],
                )
                admin_notif = self.firebase.send_admin_base_update_notification(
                    report,
                    campaign_id="cartera_activa",
                    archivo=archivo,
                    created_by=self._created_by_info(),
                    firestore_was_empty=self._update_firestore_was_empty,
                )
                r["admin_notifications_sent"] = admin_notif
                return r

            def on_ok(r, _cambios):
                self._pending_seccion_snapshot = None
                self._update_base_ok(r, report)

            self._publish_after_reparto_upload(
                camp_id, final_plan, upload_fn=do_upload, success_fn=on_ok,
            )

        def on_cancel():
            self.set_status(
                "Publicación cancelada (SQLite ya actualizado con el Excel)", 0,
            )

        self._show_reparto_confirm(plan, gestores, on_confirm, on_cancel=on_cancel)

    def _update_base_ok(self, r, report):
        if r["success"]:
            pv = r.get("preserved_visits", 0)
            archived = r.get("archived_clients", 0)
            notif = r.get("notifications_sent", 0)
            admin_notif = r.get("admin_notifications_sent", 0)
            warnings = r.get("notif_warnings") or []
            self.set_status(
                f"Base actualizada: {r['total_written']} clientes  ·  "
                f"{notif} notif. gestores  ·  {admin_notif} notif. admin", 1)
            extra = ""
            if archived:
                extra += f"\nClientes archivados (baja banco): {archived}"
            if warnings:
                extra += "\n\nAdvertencias:\n" + "\n".join(f"  • {w}" for w in warnings[:5])
            messagebox.showinfo(
                "Actualización Exitosa",
                f"Base de datos actualizada correctamente.\n\n"
                f"Resumen: {report.summary_text}\n"
                f"Visitas conservadas: {pv}\n"
                f"Notificaciones gestores: {notif}\n"
                f"Notificaciones admin: {admin_notif}{extra}")

            self._refresh_notif_badge()
            self._update_campaign_bar()
            self._invalidate_pages()
            self.navigate_to(self._active_page_name or "campaign")
        else:
            self.set_status(f"Errores: {r['errors']}", 0)
            messagebox.showerror("Error",
                                 f"Errores durante la actualización:\n"
                                 f"{chr(10).join(r['errors'])}")

    def _update_base_err(self, msg):
        self.set_status(f"Error: {msg}", 0)
        messagebox.showerror("Error", f"Error actualizando la base:\n{msg}")

    # ── Delete campaign + Firebase data ──────────────────────
    def _on_delete_campaign(self):
        """Delete all campaign data from SQLite and Firebase after double confirmation."""
        # First confirmation
        ok = messagebox.askyesno(
            "Eliminar Campaña",
            "¿Está seguro de que desea ELIMINAR toda la campaña?\n\n"
            "Esto borrará:\n"
            "  • Todos los clientes y datos de gestión locales\n"
            "  • La cartera activa en Firebase\n"
            "  • El historial de tramos y cartas generadas\n\n"
            "Esta acción NO se puede deshacer.",
            icon="warning",
        )
        if not ok:
            return

        # Second confirmation — must type ELIMINAR
        dialog = ctk.CTkInputDialog(
            text="Escriba ELIMINAR para confirmar:",
            title="Confirmación Final",
        )
        typed = (dialog.get_input() or "").strip()
        if typed != "ELIMINAR":
            messagebox.showinfo("Cancelado", "Operación cancelada. No escribió ELIMINAR.")
            return

        self.set_status("Eliminando todos los datos…", 0.1)

        def work():
            try:
                fb = self.firebase if self.firebase_connected else None
                result = self.campaign_mgr.delete_all_campaign_data(
                    firebase_service=fb,
                    progress_callback=lambda s, t, m: self.after(
                        0, lambda _m=m, _s=s, _t=t: self.set_status(
                            f"Eliminando ({_s}/{_t}): {_m}",
                            0.1 + 0.8 * (_s / _t if _t else 0))),
                )
                self.after(0, lambda: self._delete_campaign_ok(result))
            except Exception as e:
                self.after(0, lambda: self._delete_campaign_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _delete_campaign_ok(self, result):
        self.active_campaign = None
        self.parsed_data = None
        self._invalidate_pages()
        self._update_campaign_bar()
        self.set_status("Datos eliminados correctamente", 1)

        fb_info = ""
        if result.get("firebase"):
            fb = result["firebase"]
            if fb.get("error"):
                fb_info = f"\nFirebase: Error — {fb['error']}"
            elif fb.get("campaign_deleted"):
                fb_info = (f"\nFirebase: {fb['deleted_clients']} clientes, "
                           f"{fb['deleted_secciones']} secciones eliminadas")
            else:
                fb_info = "\nFirebase: No había datos que eliminar"

        messagebox.showinfo(
            "Eliminación Completa",
            f"Todos los datos han sido eliminados.\n\n"
            f"Local: {result['local_campaigns_deleted']} campaña(s), "
            f"{result['local_clients_deleted']} clientes"
            f"{fb_info}\n\n"
            f"La plataforma está lista para recibir nuevos datos.",
        )
        self.navigate_to("campaign")

    def _delete_campaign_err(self, msg):
        self.set_status(f"Error eliminando: {msg}", 0)
        messagebox.showerror("Error", f"Error durante la eliminación:\n{msg}")

    def _auto_evaluate_tramos(self):
        if not self.active_campaign:
            return

        def work():
            try:
                admin_email, admin_name = self._admin_audit_info()
                result = self.campaign_mgr.evaluate_tramos(
                    campana_id=self.active_campaign.id,
                    auto_apply=True,
                    firebase_service=self.firebase if self.firebase_connected else None,
                    admin_email=admin_email,
                    admin_name=admin_name,
                )
                self.after(0, lambda: self._tramo_eval_done(result, silent=True))
            except Exception as e:
                logger.error("Auto-evaluate tramos failed: %s", e)
        threading.Thread(target=work, daemon=True).start()

    def _on_evaluate_tramos(self):
        if not self.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return
        self.set_status("Evaluando tramos…", 0.5)

        def work():
            try:
                admin_email, admin_name = self._admin_audit_info()
                result = self.campaign_mgr.evaluate_tramos(
                    campana_id=self.active_campaign.id,
                    auto_apply=True,
                    firebase_service=self.firebase if self.firebase_connected else None,
                    admin_email=admin_email,
                    admin_name=admin_name,
                )
                self.after(0, lambda: self._tramo_eval_done(result))
            except Exception as e:
                self.after(0, lambda: self._tramo_eval_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _tramo_eval_done(self, result, silent=False):
        self._update_campaign_bar()
        n_trans = len(result.transiciones)
        n_cartas = len([c for c in result.cartas_pendientes
                        if not c.omitida_por_monto])
        n_cierres = result.clientes_cerrados
        n_retornos = result.clientes_retornados
        self.set_status(
            f"Evaluación día cartera {result.dia_campana}: "
            f"{n_trans} transiciones, {n_cierres} cierres, "
            f"{n_cartas} cartas pendientes", 1)

        if not silent and (n_trans > 0 or n_cartas > 0 or n_cierres or n_retornos):
            messagebox.showinfo(
                "Evaluación de Tramos",
                f"Día cartera {result.dia_campana}\n\n"
                f"Clientes evaluados: {result.clientes_evaluados}\n"
                f"Excluidos (saldo < S/ 10): {result.clientes_excluidos}\n"
                f"Transiciones: {n_trans}\n"
                f"Cierres ciclo (día 60): {n_cierres}\n"
                f"Retornos banco (día 70): {n_retornos}\n"
                f"Cartas pendientes: {n_cartas}\n"
                f"Errores: {len(result.errores)}")

    def _tramo_eval_err(self, msg):
        self.set_status(f"Error evaluando tramos: {msg}", 0)

    def _on_sync_visits(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return
        self.set_status("Descargando visitas de Firebase…", 0.4)

        def work():
            try:
                visit_data = self.firebase.pull_visit_data("cartera_activa")
                updated = self.campaign_mgr.sync_visits_from_firebase(
                    campana_id=self.active_campaign.id,
                    firebase_data=visit_data)
                self.after(0, lambda: self._sync_done(updated))
            except Exception as e:
                self.after(0, lambda: self._sync_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, updated):
        self.set_status(
            f"Sincronización: {updated} clientes actualizados", 1)
        if updated > 0:
            messagebox.showinfo("Sincronización",
                f"Se actualizaron {updated} registros de visitas\n"
                f"desde Firebase hacia la base de datos local.")

    def _sync_err(self, msg):
        self.set_status(f"Error sincronizando: {msg}", 0)
        messagebox.showerror("Error", f"Error de sincronización:\n{msg}")

    def _on_logout(self):
        self.destroy()
        _show_login()

    def _invalidate_pages(self):
        """Clear cached page instances so they re-render with fresh data."""
        if self._active_page and hasattr(self._active_page, "stop"):
            self._active_page.stop()
        self._pages.clear()
        self._active_page = None


# ═══════════════════════════════════════════════════════════════
# LOGIN WINDOW
# ═══════════════════════════════════════════════════════════════

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Reacudo Legal — Iniciar Sesión")
        self.geometry("420x520")
        self.resizable(False, False)
        self.configure(fg_color=SIDEBAR_BG)

        self.auth_service = AuthService()
        self.firebase = FirebaseService()
        self._init_firebase()
        self._build()

        # Center
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (210)
        y = (self.winfo_screenheight() // 2) - (260)
        self.geometry(f"+{x}+{y}")

    def _init_firebase(self):
        from config import SERVICE_ACCOUNT_KEY_PATH
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(app_dir, SERVICE_ACCOUNT_KEY_PATH)
        if os.path.exists(key_path):
            try:
                self.firebase.initialize(key_path)
            except Exception:
                pass

    def _build(self):
        # Top area — dark with brand
        top = ctk.CTkFrame(self, fg_color="transparent", height=90)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text="Reacudo Legal",
                     font=font(24, "bold"), text_color=WHITE
                     ).pack(pady=(30, 2))
        ctk.CTkLabel(top, text="Sistema de Gestión de Cobranzas",
                     font=font(11), text_color=ACCENT_MUTED
                     ).pack()

        # Card
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=20,
                            border_width=0)
        card.pack(fill="both", expand=True, padx=28, pady=(12, 28))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28, pady=28)

        ctk.CTkLabel(inner, text="Iniciar Sesión",
                     font=font(18, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w")
        ctk.CTkLabel(inner, text="Ingrese sus credenciales",
                     font=font(11), text_color=TEXT_SECONDARY
                     ).pack(anchor="w", pady=(2, 16))

        ctk.CTkLabel(inner, text="Correo electrónico", font=font(11),
                     text_color=TEXT_SECONDARY).pack(anchor="w")
        self._email = ctk.CTkEntry(inner, font=font(13), height=40,
                                   corner_radius=10, border_color=BORDER,
                                   placeholder_text="usuario@ejemplo.com")
        self._email.pack(fill="x", pady=(2, 10))

        ctk.CTkLabel(inner, text="Contraseña", font=font(11),
                     text_color=TEXT_SECONDARY).pack(anchor="w")
        self._password = ctk.CTkEntry(inner, font=font(13), height=40,
                                      corner_radius=10, border_color=BORDER,
                                      show="*", placeholder_text="••••••••")
        self._password.pack(fill="x", pady=(2, 14))

        self._error_lbl = ctk.CTkLabel(inner, text="", font=font(11),
                                       text_color=DANGER, wraplength=320)
        self._error_lbl.pack(pady=(0, 4))

        self._btn_login = ctk.CTkButton(
            inner, text="Ingresar", font=font(14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=44, corner_radius=10, command=self._on_login)
        self._btn_login.pack(fill="x")

        self._password.bind("<Return>", lambda e: self._on_login())
        self._email.bind("<Return>", lambda e: self._password.focus())
        self.after(100, self._email.focus)

    def _on_login(self):
        email = self._email.get().strip()
        password = self._password.get().strip()
        if not email or not password:
            self._error_lbl.configure(text="Ingrese correo y contraseña")
            return

        self._btn_login.configure(state="disabled", text="Verificando…")
        self._error_lbl.configure(text="")

        def do_login():
            result = self.auth_service.sign_in(email, password, self.firebase)
            self.after(0, lambda: self._on_result(result))
        threading.Thread(target=do_login, daemon=True).start()

    def _on_result(self, result):
        self._btn_login.configure(state="normal", text="Ingresar")
        if not result.success:
            self._error_lbl.configure(text=result.error)
            return
        self.destroy()
        app = App(auth_result=result)
        app.mainloop()


def _show_login():
    login = LoginWindow()
    login.mainloop()


def run_app():
    _show_login()
