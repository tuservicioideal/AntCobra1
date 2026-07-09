from __future__ import annotations

"""
Main Application UI — AntCobranzas Admin
Desktop admin panel for managing debt-collection portfolios.
Built with CustomTkinter — clean, light-themed design.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import threading
import os
import sys
import logging
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.excel_parser import parse_excel, get_seccion_summary, get_hierarchy, make_seccion_key
from services.firebase_service import FirebaseService
from services.auth_service import AuthService, AuthResult
from services.word_generator import generate_all_letters, generate_tramo_letters, generate_final_report
from services.database import db_service, TramoEnum
from services.campaign_manager import CampaignManager
from services.tramo_engine import TramoEngine, TRAMO_BOUNDARIES

logger = logging.getLogger(__name__)

# ── Theme ────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Palette — light & professional
WHITE        = "#FFFFFF"
BG           = "#F4F6F9"
CARD_BG      = "#FFFFFF"
BORDER       = "#E2E8F0"
TEXT_PRIMARY  = "#1E293B"
TEXT_SECONDARY= "#64748B"
ACCENT       = "#4F46E5"
ACCENT_HOVER = "#4338CA"
SUCCESS      = "#16A34A"
WARNING      = "#F59E0B"
DANGER       = "#DC2626"
BADGE_BG     = "#EEF2FF"


def _font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)  # type: ignore[arg-type]


class KPICard(ctk.CTkFrame):
    def __init__(self, parent, label, value, icon="", accent=None, **kw):
        accent = accent or ACCENT
        super().__init__(parent, corner_radius=14, fg_color=CARD_BG,
                         border_width=1, border_color=BORDER, **kw)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=20, pady=16, fill="both", expand=True)
        ctk.CTkLabel(inner, text=f"{icon}  {label}", font=_font(11),
                     text_color=TEXT_SECONDARY).pack(anchor="w")
        self._val = ctk.CTkLabel(inner, text=value, font=_font(24, "bold"),
                                 text_color=accent)
        self._val.pack(anchor="w", pady=(4, 0))

    def set(self, v):
        self._val.configure(text=v)


class ClientRow(ctk.CTkFrame):
    def __init__(self, parent, client, idx):
        bg = CARD_BG if idx % 2 == 0 else "#F8FAFC"
        super().__init__(parent, fg_color=bg, corner_radius=0, height=34)
        self.pack_propagate(False)
        nombre = client.get("nombre_completo", "—")
        tel = client.get("telefono_movil", "")
        deuda = float(client.get("importe_deuda_asignada", 0) or 0)
        pendiente = float(client.get("importe_deuda_pendiente", 0) or 0)
        distrito = client.get("distrito", "")

        ctk.CTkLabel(self, text=f"   {nombre}", font=_font(11),
                     text_color=TEXT_PRIMARY, anchor="w"
                     ).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkLabel(self, text=distrito, font=_font(10),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=8)
        ctk.CTkLabel(self, text=tel, font=_font(10),
                     text_color=TEXT_SECONDARY).pack(side="left", padx=8)
        color = DANGER if pendiente > 0 else SUCCESS
        ctk.CTkLabel(self, text=f"S/ {deuda:,.2f}", font=_font(11, "bold"),
                     text_color=color).pack(side="right", padx=14)


class GestorSection(ctk.CTkFrame):
    def __init__(self, parent, sec, clients):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=12,
                         border_width=1, border_color=BORDER)
        seccion_badge = sec.get("seccion_letra", sec["seccion"])

        hdr = ctk.CTkFrame(self, fg_color="transparent", height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        badge = ctk.CTkFrame(hdr, fg_color=ACCENT, corner_radius=8,
                              width=40, height=28)
        badge.pack(side="left", padx=(14, 10), pady=10)
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=seccion_badge, font=_font(13, "bold"),
                     text_color=WHITE).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(hdr, text=f"{sec['num_clientes']} clientes",
                     font=_font(13, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left")
        ctk.CTkLabel(hdr, text=f"  —  {sec['departamentos']}",
                     font=_font(11), text_color=TEXT_SECONDARY
                     ).pack(side="left", padx=4)
        ctk.CTkLabel(hdr, text=f"S/ {sec['deuda_asignada']:,.2f}",
                     font=_font(13, "bold"), text_color=ACCENT
                     ).pack(side="right", padx=14)

        pend = sec["deuda_pendiente"]
        ctk.CTkLabel(hdr, text=f"Pendiente: S/ {pend:,.2f}",
                     font=_font(11),
                     text_color=DANGER if pend > 0 else SUCCESS
                     ).pack(side="right", padx=(0, 8))

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x")
        for i, c in enumerate(clients):
            ClientRow(body, c, i).pack(fill="x")


class App(ctk.CTk):
    def __init__(self, auth_result: AuthResult | None = None):
        super().__init__()
        self.auth_result = auth_result
        role_label = auth_result.display_role if auth_result else "Sin sesión"
        user_name = auth_result.nombre if auth_result else ""
        self.title(f"AntCobranzas  ·  {role_label}: {user_name}")
        self.geometry("1280x820")
        self.minsize(1000, 650)
        self.configure(fg_color=BG)

        self.parsed_data: dict | None = None
        self.firebase = FirebaseService()
        self.firebase_connected = False

        # ── New: SQLite database + campaign manager ──
        self.campaign_mgr = CampaignManager()
        self.active_campaign: Any = None
        self._init_database()

        self._build()

        # Auto-connect Firebase if user is authenticated
        if self.auth_result and self.auth_result.success:
            self._auto_connect_firebase()

    def _init_database(self):
        """Initialize SQLite database on startup."""
        try:
            db_service.initialize()
            logger.info("Database initialized successfully")
            self.active_campaign = self.campaign_mgr.get_active_campaign()
        except Exception as e:
            logger.error("Database initialization failed: %s", e)
            messagebox.showerror(
                "Error de Base de Datos",
                f"No se pudo inicializar la base de datos:\n{e}"
            )

    def _build(self):
        # Top bar
        top = ctk.CTkFrame(self, fg_color=WHITE, height=56, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="AntCobranzas",
                     font=_font(18, "bold"), text_color=ACCENT
                     ).pack(side="left", padx=20)
        ctk.CTkLabel(top, text="Sistema de Gestión de Cobranzas",
                     font=_font(12), text_color=TEXT_SECONDARY
                     ).pack(side="left", padx=6)

        # User info badge (right side)
        if self.auth_result and self.auth_result.success:
            user_txt = f"{self.auth_result.nombre}  ({self.auth_result.display_role})"
            self._user_badge = ctk.CTkLabel(top, text=user_txt,
                                            font=_font(11, "bold"), text_color=ACCENT)
            self._user_badge.pack(side="right", padx=(0, 8))

            btn_logout = ctk.CTkButton(top, text="Cerrar sesion", font=_font(10),
                                       fg_color=DANGER, hover_color="#B91C1C",
                                       height=28, width=100, corner_radius=6,
                                       command=self._on_logout)
            btn_logout.pack(side="right", padx=(0, 8))

        self._fb_badge = ctk.CTkLabel(top, text="*  Firebase desconectado",
                                      font=_font(11), text_color=TEXT_SECONDARY)
        self._fb_badge.pack(side="right", padx=20)

        ctk.CTkFrame(self, fg_color=ACCENT, height=3, corner_radius=0).pack(fill="x")

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=BG, height=58, corner_radius=0)
        tb.pack(fill="x", padx=24, pady=(12, 0))
        tb.pack_propagate(False)

        self.btn_load = ctk.CTkButton(
            tb, text="  Cargar Excel", font=_font(13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=38, width=170, corner_radius=10,
            command=self._on_load_excel)
        self.btn_load.pack(side="left", padx=(0, 8))

        self.btn_fb = ctk.CTkButton(
            tb, text="  Conectar Firebase", font=_font(13, "bold"),
            fg_color="#0D9488", hover_color="#0F766E",
            height=38, width=190, corner_radius=10,
            command=self._on_connect_firebase)
        self.btn_fb.pack(side="left", padx=(0, 8))

        self.btn_upload = ctk.CTkButton(
            tb, text="  Distribuir a Gestores", font=_font(13, "bold"),
            fg_color="#7C3AED", hover_color="#6D28D9",
            height=38, width=210, corner_radius=10,
            command=self._on_upload, state="disabled")
        self.btn_upload.pack(side="left", padx=(0, 8))

        self.btn_users = ctk.CTkButton(
            tb, text="  Gestionar Usuarios", font=_font(13, "bold"),
            fg_color="#D97706", hover_color="#B45309",
            height=38, width=200, corner_radius=10,
            command=self._on_manage_users, state="disabled")
        self.btn_users.pack(side="left", padx=(0, 8))

        self.btn_letters = ctk.CTkButton(
            tb, text="  Generar Cartas", font=_font(13, "bold"),
            fg_color="#0891B2", hover_color="#0E7490",
            height=38, width=170, corner_radius=10,
            command=self._on_generate_letters, state="disabled")
        self.btn_letters.pack(side="left", padx=(0, 8))

        self.btn_monitor = ctk.CTkButton(
            tb, text="  Monitor Gestión", font=_font(13, "bold"),
            fg_color="#059669", hover_color="#047857",
            height=38, width=190, corner_radius=10,
            command=self._on_monitor, state="disabled")
        self.btn_monitor.pack(side="left", padx=(0, 8))

        self.btn_stats = ctk.CTkButton(
            tb, text="  Estadísticas", font=_font(13, "bold"),
            fg_color="#7C3AED", hover_color="#6D28D9",
            height=38, width=160, corner_radius=10,
            command=self._on_show_stats, state="disabled")
        self.btn_stats.pack(side="left", padx=(0, 8))

        self.btn_alertas = ctk.CTkButton(
            tb, text="[!]  Alertas", font=_font(13, "bold"),
            fg_color="#E11D48", hover_color="#BE123C",
            height=38, width=140, corner_radius=10,
            command=self._on_show_alertas, state="disabled")
        self.btn_alertas.pack(side="left", padx=(0, 8))

        self.btn_tracking = ctk.CTkButton(
            tb, text="[GPS]  GPS Gestores", font=_font(13, "bold"),
            fg_color="#0891B2", hover_color="#0E7490",
            height=38, width=170, corner_radius=10,
            command=self._on_show_tracking, state="disabled")
        self.btn_tracking.pack(side="left", padx=(0, 8))

        self.btn_distribucion = ctk.CTkButton(
            tb, text="[>] Configurar Distribución", font=_font(13, "bold"),
            fg_color="#B45309", hover_color="#92400E",
            height=38, width=230, corner_radius=10,
            command=self._on_distribucion, state="disabled")
        self.btn_distribucion.pack(side="left", padx=(0, 8))

        self.btn_final_report = ctk.CTkButton(
            tb, text="[#]  Informe Final", font=_font(13, "bold"),
            fg_color="#7C3AED", hover_color="#6D28D9",
            height=38, width=160, corner_radius=10,
            command=self._on_final_report, state="disabled")
        self.btn_final_report.pack(side="left", padx=(0, 8))

        self._file_label = ctk.CTkLabel(tb, text="Sin archivo cargado",
                                        font=_font(11), text_color=TEXT_SECONDARY)
        self._file_label.pack(side="right", padx=8)

        # ── Campaign Info Bar ────────────────────────────────────
        self._camp_bar = ctk.CTkFrame(self, fg_color="#EEF2FF", height=44,
                                       corner_radius=0, border_width=1,
                                       border_color=BORDER)
        self._camp_bar.pack(fill="x", padx=24, pady=(6, 0))
        self._camp_bar.pack_propagate(False)

        self._camp_label = ctk.CTkLabel(
            self._camp_bar, text="", font=_font(12, "bold"),
            text_color=ACCENT)
        self._camp_label.pack(side="left", padx=16)

        self._tramo_label = ctk.CTkLabel(
            self._camp_bar, text="", font=_font(11),
            text_color=TEXT_PRIMARY)
        self._tramo_label.pack(side="left", padx=8)

        self._dia_label = ctk.CTkLabel(
            self._camp_bar, text="", font=_font(11),
            text_color=TEXT_SECONDARY)
        self._dia_label.pack(side="left", padx=8)

        self.btn_eval_tramos = ctk.CTkButton(
            self._camp_bar, text="~ Evaluar Tramos", font=_font(11, "bold"),
            fg_color="#059669", hover_color="#047857",
            height=30, width=150, corner_radius=8,
            command=self._on_evaluate_tramos, state="disabled")
        self.btn_eval_tramos.pack(side="right", padx=(4, 16))

        self.btn_sync_visits = ctk.CTkButton(
            self._camp_bar, text="v Sync Visitas", font=_font(11, "bold"),
            fg_color="#0891B2", hover_color="#0E7490",
            height=30, width=140, corner_radius=8,
            command=self._on_sync_visits, state="disabled")
        self.btn_sync_visits.pack(side="right", padx=4)

        self._update_campaign_bar()

        # Main scrollable area
        self._main = ctk.CTkScrollableFrame(
            self, fg_color=BG,
            scrollbar_button_color="#CBD5E1",
            scrollbar_button_hover_color=ACCENT)
        self._main.pack(fill="both", expand=True, padx=24, pady=12)
        self._show_welcome()

        # Status bar
        sf = ctk.CTkFrame(self, fg_color=WHITE, height=32, corner_radius=0)
        sf.pack(fill="x", side="bottom")
        sf.pack_propagate(False)

        self._status = ctk.CTkLabel(sf, text="Listo", font=_font(11),
                                    text_color=TEXT_SECONDARY)
        self._status.pack(side="left", padx=16)

        self._progress = ctk.CTkProgressBar(sf, width=220, height=8,
                                            progress_color=ACCENT,
                                            fg_color=BORDER)
        self._progress.pack(side="right", padx=16, pady=8)
        self._progress.set(0)

    # ── Welcome view ─────────────────────────────────────────────
    def _show_welcome(self):
        for w in self._main.winfo_children():
            w.destroy()

        box = ctk.CTkFrame(self._main, fg_color=CARD_BG, corner_radius=16,
                           border_width=1, border_color=BORDER)
        box.pack(fill="x", pady=40, padx=60)

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(padx=40, pady=40)

        ctk.CTkLabel(inner, text="Bienvenido", font=_font(26, "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text="Sistema Integral de Gestión de Cobranzas",
                     font=_font(14), text_color=TEXT_SECONDARY
                     ).pack(anchor="w", pady=(2, 16))

        steps = [
            ("1", "Cargue el archivo Excel con la cartera del banco"),
            ("2", "Conecte Firebase con la clave de servicio (.json)"),
            ("3", "Presione «Distribuir» para asignar clientes a los gestores"),
            ("4", "Use «Evaluar Tramos» para avanzar el ciclo de cobranza"),
        ]
        for num, txt in steps:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=4)
            b = ctk.CTkFrame(row, fg_color=BADGE_BG, corner_radius=6,
                              width=28, height=28)
            b.pack(side="left", padx=(0, 10))
            b.pack_propagate(False)
            ctk.CTkLabel(b, text=num, font=_font(12, "bold"),
                         text_color=ACCENT).place(relx=0.5, rely=0.5,
                                                  anchor="center")
            ctk.CTkLabel(row, text=txt, font=_font(13),
                         text_color=TEXT_PRIMARY).pack(side="left")

    # ── Data view ────────────────────────────────────────────────
    def _display(self, data):
        for w in self._main.winfo_children():
            w.destroy()

        s = data["summary"]
        by_sec = data["by_seccion"]

        # KPIs
        row = ctk.CTkFrame(self._main, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        row.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        kpis = [
            ("Clientes", str(s["total_clientes"]), "[#]", ACCENT),
            ("Gestores", str(s["total_secciones"]), "[U]", "#0D9488"),
            ("Deuda Total", f"S/ {s['total_deuda_asignada']:,.2f}", "[$]", WARNING),
            ("Pendiente", f"S/ {s['total_deuda_pendiente']:,.2f}", "[t]", DANGER),
            ("Dptos.", str(len(s["departamentos"])), "[GPS]", "#6366F1"),
        ]
        for i, (lbl, val, ico, clr) in enumerate(kpis):
            KPICard(row, lbl, val, ico, clr).grid(row=0, column=i,
                                                   padx=4, sticky="nsew")

        ctk.CTkLabel(self._main, text="Cartera por Región / Zona / Sección",
                     font=_font(17, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(8, 6))

        hierarchy = get_hierarchy(data["all_clients"])
        secs = get_seccion_summary(by_sec)
        sec_map = {s["seccion"]: s for s in secs}

        for region_key, region_data in hierarchy["regions"].items():
            # ── Region header ──
            r_frame = ctk.CTkFrame(self._main, fg_color="#EEF2FF",
                                   corner_radius=10, border_width=1,
                                   border_color=ACCENT)
            r_frame.pack(fill="x", pady=(8, 2))
            r_inner = ctk.CTkFrame(r_frame, fg_color="transparent")
            r_inner.pack(fill="x", padx=14, pady=8)
            ctk.CTkLabel(
                r_inner,
                text=f"Región {region_key}",
                font=_font(14, "bold"), text_color=ACCENT,
            ).pack(side="left")
            ctk.CTkLabel(
                r_inner,
                text=f"{region_data['num_clientes']} clientes  ·  "
                     f"S/ {region_data['deuda_asignada']:,.2f}  ·  "
                     f"Pendiente S/ {region_data['deuda_pendiente']:,.2f}",
                font=_font(11), text_color=TEXT_SECONDARY,
            ).pack(side="right")

            for zona_key, zona_data in sorted(region_data["zonas"].items()):
                # ── Zona sub-header ──
                z_frame = ctk.CTkFrame(self._main, fg_color="#F8FAFC",
                                       corner_radius=8, border_width=1,
                                       border_color=BORDER)
                z_frame.pack(fill="x", pady=(2, 1), padx=(20, 0))
                z_inner = ctk.CTkFrame(z_frame, fg_color="transparent")
                z_inner.pack(fill="x", padx=12, pady=6)
                ctk.CTkLabel(
                    z_inner,
                    text=f"Zona {zona_key}",
                    font=_font(12, "bold"), text_color="#0D9488",
                ).pack(side="left")
                ctk.CTkLabel(
                    z_inner,
                    text=f"{zona_data['num_clientes']} clientes  ·  "
                         f"S/ {zona_data['deuda_asignada']:,.2f}",
                    font=_font(10), text_color=TEXT_SECONDARY,
                ).pack(side="right")

                # ── Section cards under this Zona ──
                for sec_key in sorted(zona_data["secciones"].keys()):
                    composite = make_seccion_key(region_key, zona_key, sec_key)
                    sec_info = sec_map.get(composite)
                    if sec_info:
                        clients = by_sec.get(composite, [])
                        s_frame = ctk.CTkFrame(self._main, fg_color="transparent")
                        s_frame.pack(fill="x", padx=(40, 0))
                        GestorSection(s_frame, sec_info, clients).pack(
                            fill="x", pady=2)

        # Table
        ctk.CTkLabel(self._main, text="Vista Detallada",
                     font=_font(17, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(16, 6))

        tf = ctk.CTkFrame(self._main, fg_color=CARD_BG, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tf.pack(fill="x", pady=4)

        cols = ("region", "zona", "seccion", "nombre", "dni", "telefono",
                "departamento", "distrito", "dias_atraso",
                "deuda_asignada", "deuda_pendiente")
        hdrs = {"region": "Región", "zona": "Zona", "seccion": "Secc.",
                "nombre": "Nombre", "dni": "DNI",
                "telefono": "Teléfono", "departamento": "Departam.",
                "distrito": "Distrito", "dias_atraso": "Días",
                "deuda_asignada": "Deuda", "deuda_pendiente": "Pendiente"}

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("AC.Treeview", background=WHITE,
                         foreground=TEXT_PRIMARY, fieldbackground=WHITE,
                         font=("Segoe UI", 10), rowheight=30, borderwidth=0)
        style.configure("AC.Treeview.Heading", background="#EEF2FF",
                         foreground=ACCENT, font=("Segoe UI", 10, "bold"),
                         borderwidth=0, relief="flat")
        style.map("AC.Treeview",
                   background=[("selected", "#E0E7FF")],
                   foreground=[("selected", ACCENT)])

        tree = ttk.Treeview(tf, columns=cols, show="headings",
                            style="AC.Treeview",
                            height=min(len(data["all_clients"]) + 1, 18))
        for c in cols:
            tree.heading(c, text=hdrs[c])
            w = 180 if c == "nombre" else 100
            tree.column(c, width=w, minwidth=60)

        for cl in data["all_clients"]:
            tree.insert("", "end", values=(
                cl.get("region", ""), cl.get("zona", ""),
                cl.get("seccion", ""), cl.get("nombre_completo", ""),
                cl.get("numero_documento", ""), cl.get("telefono_movil", ""),
                cl.get("departamento", ""), cl.get("distrito", ""),
                cl.get("dias_atraso", ""),
                f"S/ {float(cl.get('importe_deuda_asignada', 0) or 0):,.2f}",
                f"S/ {float(cl.get('importe_deuda_pendiente', 0) or 0):,.2f}",
            ))

        sb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

    # ── Helpers ──────────────────────────────────────────────────
    def _set_status(self, text, progress=None):
        self._status.configure(text=text)
        if progress is not None:
            self._progress.set(progress)

    def _update_campaign_bar(self):
        """Refresh the campaign info bar based on active campaign."""
        camp = self.active_campaign
        if camp is None:
            self._camp_label.configure(text="Sin campaña activa")
            self._tramo_label.configure(text="")
            self._dia_label.configure(text="Cargue un Excel para crear una campaña")
            self.btn_eval_tramos.configure(state="disabled")
            self.btn_sync_visits.configure(state="disabled")
            return

        # Refresh from DB
        try:
            with db_service.session() as session:
                camp = session.get(type(camp), camp.id)
                if camp is None:
                    self.active_campaign = None
                    self._camp_label.configure(text="Sin campaña activa")
                    return
                dia = camp.dia_actual
                tramo = TramoEngine.get_tramo_for_day(dia)
                tramo_names = {
                    TramoEnum.NONE: "Sin asignar",
                    TramoEnum.TRAMO_1: "Tramo 1 · Cobranza Normal",
                    TramoEnum.TRAMO_2: "Tramo 2 · Seguimiento Medio",
                    TramoEnum.TRAMO_3: "Tramo 3 · Cierre de Gestión",
                }
                self._camp_label.configure(
                    text=f"[#] {camp.nombre}  ({camp.total_clientes} clientes)")
                self._tramo_label.configure(
                    text=f"> {tramo_names.get(tramo, '?')}")
                self._dia_label.configure(
                    text=f"Día {dia}/60  ·  {camp.dias_restantes} días restantes")
        except Exception:
            pass

        self.btn_eval_tramos.configure(state="normal")
        if self.firebase_connected:
            self.btn_sync_visits.configure(state="normal")

    # ── Actions ──────────────────────────────────────────────────
    def _on_load_excel(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Excel de cartera",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return

        # Check if there's already an active campaign
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

        self.btn_load.configure(state="disabled")
        self._set_status("Leyendo Excel y creando campaña…", 0.2)

        def work():
            try:
                # Parse Excel + create campaign in SQLite
                campana, summary = self.campaign_mgr.create_campaign_from_excel(
                    file_path=path,
                    nombre=f"Campaña {os.path.basename(path).split('.')[0]}",
                )
                # Also parse for display (backward compat)
                d = parse_excel(path)
                self.after(0, lambda: self._excel_ok(d, path, campana, summary))
            except Exception as e:
                self.after(0, lambda: self._excel_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _excel_ok(self, data, path, campana=None, summary=None):
        self.parsed_data = data
        self.btn_load.configure(state="normal")
        name = os.path.basename(path)
        n = data["summary"]["total_clientes"]
        self._file_label.configure(text=f"{name}  ·  {n} clientes",
                                   text_color=SUCCESS)

        # Update active campaign reference
        if campana:
            self.active_campaign = campana
            self._set_status(
                f"[OK]  Campaña creada: {n} clientes → SQLite  ·  {(summary or {}).get('total_secciones', 0)} secciones",
                1)
            self._update_campaign_bar()
            # Auto-evaluate tramos (day 1)
            self._auto_evaluate_tramos()
        else:
            self._set_status(f"[OK]  {n} clientes cargados", 1)

        if self._role_allows("letters"):
            self.btn_letters.configure(state="normal")
        if self.firebase_connected and self._role_allows("upload"):
            self.btn_upload.configure(state="normal")
        if self.firebase_connected and self._role_allows("distribucion"):
            self.btn_distribucion.configure(state="normal")
        self._display(data)

    def _excel_err(self, msg):
        self.btn_load.configure(state="normal")
        self._set_status(f"Error: {msg}", 0)
        messagebox.showerror("Error", msg)

    def _on_connect_firebase(self):
        path = filedialog.askopenfilename(
            title="Clave de servicio Firebase (.json)",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if not path:
            return
        self._set_status("Conectando con Firebase…", 0.4)

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
            self._fb_badge.configure(text="*  Firebase conectado",
                                     text_color=SUCCESS)
            self.btn_fb.configure(text="[OK]  Conectado", fg_color=SUCCESS,
                                  state="disabled")
            self._set_status("Firebase conectado", 1)
            # Apply role-based button visibility
            self._apply_role_permissions()
            if self.parsed_data or self.active_campaign:
                if self._role_allows("upload"):
                    self.btn_upload.configure(state="normal")
                if self._role_allows("distribucion"):
                    self.btn_distribucion.configure(state="normal")
            if self.active_campaign:
                self.btn_sync_visits.configure(state="normal")
        else:
            self._fb_err("No se pudo verificar la conexión")

    def _fb_err(self, msg):
        self._set_status(f"Firebase: {msg}", 0)
        messagebox.showerror("Firebase", msg)

    def _auto_connect_firebase(self):
        """Auto-connect Firebase using the service account key after login."""
        from config import SERVICE_ACCOUNT_KEY_PATH
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(app_dir, SERVICE_ACCOUNT_KEY_PATH)
        if not os.path.exists(key_path):
            self._set_status("No se encontro clave de servicio Firebase", 0)
            return

        self._set_status("Conectando con Firebase...", 0.4)

        def work():
            try:
                self.firebase.initialize(key_path)
                ok = self.firebase.test_connection()
                self.after(0, lambda: self._fb_ok(ok))
            except Exception as e:
                self.after(0, lambda: self._fb_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _role_allows(self, feature: str) -> bool:
        """Check if the current user's role allows a feature."""
        if not self.auth_result:
            return True  # No auth = unrestricted (legacy mode)
        rol = self.auth_result.rol
        rules = {
            "load_excel":   ("admin", "supervisor"),
            "upload":       ("admin", "supervisor"),
            "users":        ("admin", "supervisor"),
            "letters":      ("admin", "supervisor"),
            "monitor":      ("admin", "supervisor", "asistente"),
            "stats":        ("admin", "supervisor", "asistente"),
            "alertas":      ("admin", "supervisor", "asistente"),
            "tracking":     ("admin", "supervisor"),
            "distribucion": ("admin", "supervisor"),
            "final_report": ("admin", "supervisor"),
            "eval_tramos":  ("admin", "supervisor"),
            "sync_visits":  ("admin", "supervisor", "asistente"),
            "connect_fb":   ("admin", "supervisor"),
        }
        allowed_roles = rules.get(feature, ("admin",))
        return rol in allowed_roles

    def _apply_role_permissions(self):
        """Enable/disable toolbar buttons based on the user's role."""
        role_map = {
            "users":        self.btn_users,
            "monitor":      self.btn_monitor,
            "distribucion": self.btn_distribucion,
            "stats":        self.btn_stats,
            "alertas":      self.btn_alertas,
            "tracking":     self.btn_tracking,
            "final_report": self.btn_final_report,
        }
        for feature, btn in role_map.items():
            if self._role_allows(feature):
                btn.configure(state="normal")
            else:
                btn.configure(state="disabled")

        # Hide connect-firebase button if already auto-connected
        if self.firebase_connected:
            self.btn_fb.configure(text="[OK]  Conectado", fg_color=SUCCESS,
                                  state="disabled")

        # Load/upload/letters require both role + data
        if not self._role_allows("load_excel"):
            self.btn_load.configure(state="disabled")
        if not self._role_allows("letters"):
            self.btn_letters.configure(state="disabled")
        if not self._role_allows("connect_fb"):
            self.btn_fb.configure(state="disabled")

    def _on_logout(self):
        """Close the app and return to the login screen."""
        self.destroy()
        _show_login()

    def _on_upload(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign and not self.parsed_data:
            messagebox.showwarning("Datos", "Cargue un Excel primero.")
            return

        # Prefer SQLite-first flow if campaign exists
        if self.active_campaign:
            camp_id = self.active_campaign.id
            stats = self.campaign_mgr.get_campaign_stats(camp_id)
            total = stats.get("total_clientes", 0)
            secciones = len(stats.get("secciones", []))
            if not messagebox.askyesno(
                    "Confirmar",
                    f"Distribuir {total} clientes de {secciones} secciones "
                    f"a Firebase?\n\n"
                    f"Nota: Los datos sensibles (DNI) NO se enviarán a la nube."):
                return
            self.btn_upload.configure(state="disabled")
            self._set_status("Preparando datos para Firebase…", 0.2)

            def cb(cur, tot, msg):
                p = cur / tot if tot else 0
                self.after(0, lambda: self._set_status(
                    f"Subiendo {cur}/{tot}: {msg}", p))

            def work():
                try:
                    payload = self.campaign_mgr.get_firebase_payload(camp_id)
                    r = self.firebase.upload_cartera_filtered(
                        by_seccion=payload["by_seccion"],
                        campaign_id="cartera_activa",
                        tramo_info={
                            "dia_actual": self.active_campaign.dia_actual
                                if self.active_campaign else 0,
                            "campana_sqlite_id": camp_id,
                        },
                        progress_callback=cb,
                    )
                    try:
                        cleanup = self.firebase.cleanup_old_campaigns()
                        r["cleaned_campaigns"] = len(cleanup.get("deleted", []))
                    except Exception:
                        r["cleaned_campaigns"] = 0
                    self.after(0, lambda: self._upload_ok(r))
                except Exception as e:
                    self.after(0, lambda: self._upload_err(str(e)))
            threading.Thread(target=work, daemon=True).start()
        else:
            # Fallback: legacy direct Excel → Firebase upload
            s = self.parsed_data["summary"]  # type: ignore[index]
            if not messagebox.askyesno(
                    "Confirmar",
                    f"Distribuir {s['total_clientes']} clientes "
                    f"a {s['total_secciones']} gestores?"):
                return
            self.btn_upload.configure(state="disabled")

            def cb(cur, tot, msg):
                p = cur / tot if tot else 0
                self.after(0, lambda: self._set_status(
                    f"Subiendo {cur}/{tot}: {msg}", p))

            def work():
                try:
                    r = self.firebase.upload_cartera(
                        self.parsed_data["by_seccion"], progress_callback=cb)  # type: ignore[index]
                    try:
                        cleanup = self.firebase.cleanup_old_campaigns()
                        r["cleaned_campaigns"] = len(cleanup.get("deleted", []))
                    except Exception:
                        r["cleaned_campaigns"] = 0
                    self.after(0, lambda: self._upload_ok(r))
                except Exception as e:
                    self.after(0, lambda: self._upload_err(str(e)))
            threading.Thread(target=work, daemon=True).start()

    def _upload_ok(self, r):
        self.btn_upload.configure(state="normal")
        if r["success"]:
            pv = r.get("preserved_visits", 0)
            pv_txt = f"  ·  {pv} visitas conservadas" if pv else ""
            self._set_status(
                f"[OK]  {r['total_uploaded']} clientes distribuidos{pv_txt}  — "
                f"Campaña: {r['campaign_id']}", 1)
            # Ask if user wants to generate collection letters
            pv_msg = f"\n({pv} clientes ya visitados — su estado fue conservado)" if pv else ""
            generate = messagebox.askyesno("Generar Cartas",
                f"Se distribuyeron {r['total_uploaded']} clientes.{pv_msg}\n"
                f"Campaña: {r['campaign_id']}\n\n"
                f"¿Desea generar las cartas de cobranza en Word\n"
                f"para cada gestor?")
            if generate:
                self._on_generate_letters()
        else:
            self._set_status(f"Errores: {r['errors']}", 0)

    def _upload_err(self, msg):
        self.btn_upload.configure(state="normal")
        self._set_status(f"Error: {msg}", 0)
        messagebox.showerror("Error", msg)

    # ── Word Letter Generation ─────────────────────────────────
    def _on_generate_letters(self):
        if not self.parsed_data:
            messagebox.showwarning("Cartas", "Cargue un archivo Excel primero.")
            return

        # Ask user which carta number to generate
        carta_win = ctk.CTkToplevel(self)
        carta_win.title("Seleccionar Carta")
        carta_win.geometry("380x320")
        carta_win.resizable(False, False)
        carta_win.transient(self)
        carta_win.grab_set()

        ctk.CTkLabel(carta_win, text="¿Qué carta desea generar?",
                     font=("Segoe UI", 14, "bold")).pack(pady=(18, 10))

        carta_var = tk.IntVar(value=1)
        opciones = [
            (1, "Carta 1 — Notificación (Tramo 1, Día 1)"),
            (2, "Carta 2 — Recordatorio (Tramo 2, Día 9)"),
            (3, "Carta 3 — Advertencia (Tramo 2, Día 38)"),
            (4, "Carta 4 — Último Aviso (Tramo 3, Día 44)"),
        ]
        for val, label in opciones:
            ctk.CTkRadioButton(carta_win, text=label,
                               variable=carta_var, value=val,
                               font=("Segoe UI", 11)).pack(
                                   anchor="w", padx=30, pady=4)

        use_tramo = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(carta_win,
                        text="Solo clientes pendientes (tramo engine)",
                        variable=use_tramo,
                        font=("Segoe UI", 10)).pack(pady=(12, 6), padx=30,
                                                     anchor="w")

        def on_ok():
            carta_win.destroy()
            self._do_generate_letters(carta_var.get(), use_tramo.get())

        ctk.CTkButton(carta_win, text="Generar", command=on_ok,
                      fg_color="#4F46E5", width=160).pack(pady=14)

    def _do_generate_letters(self, numero_carta: int, use_tramo: bool):
        """Execute letter generation in background thread."""
        output_dir = filedialog.askdirectory(
            title="Seleccionar carpeta para guardar las cartas")
        if not output_dir:
            return

        # Get gestor names from Firebase if connected
        gestores_info = {}
        if self.firebase_connected:
            try:
                users = self.firebase.list_gestor_users()
                for u in users:
                    name = u.get("nombre", "")
                    if not name:
                        continue
                    # Map composite keys from secciones array
                    for sk in (u.get("secciones") or []):
                        gestores_info[sk] = name
                    # Also map legacy letter key for tramo-based generation
                    sec = u.get("seccion", "")
                    if sec:
                        gestores_info[sec] = name
            except Exception:
                pass

        self.btn_letters.configure(state="disabled", text="Generando…")
        self._set_status(
            f"Generando Carta N° {numero_carta} de cobranza…", 0.3)

        campaign_id = ""
        if hasattr(self, 'campaign_manager') and self.parsed_data and self.parsed_data.get("campaign_id"):
            campaign_id = self.parsed_data["campaign_id"]

        def work():
            try:
                if use_tramo and campaign_id:
                    # Use tramo engine: only pending clients for this carta
                    cm = CampaignManager()
                    pending = cm.get_pending_letters(
                        campaign_id, numero_carta=numero_carta)
                    if not pending:
                        self.after(0, lambda: self._letters_err(
                            f"No hay cartas N° {numero_carta} pendientes "
                            f"según el motor de tramos."))
                        return
                    result = generate_tramo_letters(
                        pending_list=pending,
                        output_dir=output_dir,
                        gestores_info=gestores_info,
                        campaign_id=campaign_id,
                    )
                else:
                    # Fallback: all clients, specified carta number
                    result = generate_all_letters(
                        by_seccion=self.parsed_data["by_seccion"],  # type: ignore[index]
                        output_dir=output_dir,
                        gestores_info=gestores_info,
                        campaign_id=campaign_id,
                        numero_carta=numero_carta,
                    )
                self.after(0, lambda: self._letters_ok(result))
            except Exception as e:
                self.after(0, lambda: self._letters_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _letters_ok(self, result):
        self.btn_letters.configure(state="normal", text="  Generar Cartas")
        n_files = result["total_files"]
        n_letters = result["total_letters"]
        out = result["output_dir"]
        by_carta = result.get("by_carta", {})
        detail = ""
        if by_carta:
            detail = " | ".join(
                f"Carta {k}: {v}" for k, v in sorted(by_carta.items()))
            detail = f"\n\nDetalle: {detail}"
        self._set_status(
            f"[OK]  {n_files} archivos generados — {n_letters} cartas en total", 1)
        messagebox.showinfo("Cartas Generadas",
            f"Se generaron {n_files} documentos Word con "
            f"{n_letters} cartas.{detail}\n\n"
            f"Ubicación:\n{out}")
        # Open the folder
        os.startfile(out)

    def _letters_err(self, msg):
        self.btn_letters.configure(state="normal", text="  Generar Cartas")
        self._set_status(f"Error generando cartas: {msg}", 0)
        messagebox.showerror("Error", f"Error al generar cartas:\n{msg}")

    # ── Distribution Configuration ───────────────────────────────
    def _on_distribucion(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.parsed_data:
            messagebox.showwarning("Datos", "Cargue un Excel primero.")
            return
        DistribucionWindow(self, self.firebase, self.parsed_data)

    # ── User Management ──────────────────────────────────────────
    def _on_manage_users(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        UserManagerWindow(self, self.firebase)

    # ── Real-time Monitor ────────────────────────────────────────
    def _on_monitor(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        MonitorWindow(self, self.firebase)

    # ── Statistics ───────────────────────────────────────────────
    def _on_show_stats(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        StatsWindow(self, self.firebase)

    # ── Alertas ──────────────────────────────────────────────────
    def _on_show_alertas(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        AlertasWindow(self, self.firebase)

    # ── GPS Tracking ─────────────────────────────────────────────
    def _on_show_tracking(self):
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        TrackingWindow(self, self.firebase)

    # ── Final Report ─────────────────────────────────────────────
    def _on_final_report(self):
        """Generate a Day-60 (or current day) campaign final report."""
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign:
            messagebox.showwarning("Campaña",
                "No hay una campaña activa. Cargue un Excel primero.")
            return

        output_dir = filedialog.askdirectory(
            title="Seleccionar carpeta para guardar el informe")
        if not output_dir:
            return

        campaign = self.active_campaign
        self.btn_final_report.configure(state="disabled", text="Generando…")
        self._set_status("Generando informe final de campaña…", 0.3)

        def work():
            try:
                # Get campaign status from Firebase
                resumen = self.firebase.get_campaign_status(campaign.id)

                # Get alerts
                alertas = []
                try:
                    alertas = self.firebase.get_alerts(limit=500)
                except Exception:
                    pass

                # Build per-section stats
                secciones_stats = []
                try:
                    by_sec = self.campaign_mgr.get_clients_by_section(
                        campaign.id)
                    gestores = {}
                    try:
                        users = self.firebase.list_gestor_users()
                        for u in users:
                            # Map each composite key in secciones to nombre
                            secs = u.get("secciones") or []
                            if isinstance(secs, list):
                                for sk in secs:
                                    gestores[sk] = u.get("nombre", "")
                            # Fallback: legacy single seccion
                            s = u.get("seccion", "")
                            if s and s not in gestores:
                                gestores[s] = u.get("nombre", "")
                    except Exception:
                        pass

                    for sec, clients in sorted(by_sec.items()):
                        sec_data = {"seccion": sec,
                                    "gestor": gestores.get(sec, ""),
                                    "total": len(clients)}
                        counts = {"visitados": 0, "pagados": 0,
                                  "morosos": 0, "no_ubica": 0,
                                  "suplantacion": 0,
                                  "pago_no_registrado": 0}
                        for c in clients:
                            eg = c.get("estado_gestion", "")
                            if eg in ("pagado", "compromiso_pago"):
                                counts["pagados"] += 1
                                counts["visitados"] += 1
                            elif eg == "moroso":
                                counts["morosos"] += 1
                                counts["visitados"] += 1
                            elif eg == "no_ubica":
                                counts["no_ubica"] += 1
                                counts["visitados"] += 1
                            elif eg == "suplantacion":
                                counts["suplantacion"] += 1
                                counts["visitados"] += 1
                            elif eg == "pago_no_registrado":
                                counts["pago_no_registrado"] += 1
                                counts["visitados"] += 1
                        sec_data.update(counts)
                        secciones_stats.append(sec_data)
                except Exception:
                    pass

                # Calculate campaign day
                from datetime import date
                delta = (date.today() - campaign.fecha_inicio).days + 1
                dia_campana = max(1, min(delta, 60))

                path = generate_final_report(
                    campaign_id=campaign.id,
                    campaign_name=campaign.nombre,
                    dia_campana=dia_campana,
                    resumen=resumen,
                    secciones_stats=secciones_stats,
                    alertas=alertas,
                    output_dir=output_dir,
                )
                self.after(0, lambda: self._final_report_ok(path))
            except Exception as e:
                self.after(0, lambda: self._final_report_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _final_report_ok(self, path):
        self.btn_final_report.configure(
            state="normal", text="[#]  Informe Final")
        self._set_status(f"[OK]  Informe final generado", 1)
        messagebox.showinfo("Informe Final",
            f"El informe fue generado exitosamente.\n\n{path}")
        os.startfile(os.path.dirname(path))

    def _final_report_err(self, msg):
        self.btn_final_report.configure(
            state="normal", text="[#]  Informe Final")
        self._set_status(f"Error generando informe: {msg}", 0)
        messagebox.showerror("Error", f"Error al generar informe:\n{msg}")

    # ── Tramo Evaluation ─────────────────────────────────────────
    def _auto_evaluate_tramos(self):
        """Run tramo evaluation in background after campaign creation."""
        if not self.active_campaign:
            return
        def work():
            try:
                result = self.campaign_mgr.evaluate_tramos(
                    campana_id=self.active_campaign.id,
                    auto_apply=True,
                )
                self.after(0, lambda: self._tramo_eval_done(result, silent=True))
            except Exception as e:
                logger.error("Auto-evaluate tramos failed: %s", e)
        threading.Thread(target=work, daemon=True).start()

    def _on_evaluate_tramos(self):
        """Manual tramo evaluation triggered by button."""
        if not self.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return

        self.btn_eval_tramos.configure(state="disabled", text="Evaluando…")
        self._set_status("Evaluando tramos…", 0.5)

        def work():
            try:
                result = self.campaign_mgr.evaluate_tramos(
                    campana_id=self.active_campaign.id,
                    auto_apply=True,
                )
                self.after(0, lambda: self._tramo_eval_done(result))
            except Exception as e:
                self.after(0, lambda: self._tramo_eval_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _tramo_eval_done(self, result, silent=False):
        self.btn_eval_tramos.configure(state="normal", text="~ Evaluar Tramos")
        self._update_campaign_bar()

        n_trans = len(result.transiciones)
        n_cartas = len([c for c in result.cartas_pendientes if not c.omitida_por_monto])
        self._set_status(
            f"[OK]  Evaluación día {result.dia_campana}: "
            f"{n_trans} transiciones, {n_cartas} cartas pendientes",
            1)

        if not silent and (n_trans > 0 or n_cartas > 0):
            messagebox.showinfo(
                "Evaluación de Tramos",
                f"Día {result.dia_campana} de la campaña\n\n"
                f"Clientes evaluados: {result.clientes_evaluados}\n"
                f"Excluidos (saldo < S/ 10): {result.clientes_excluidos}\n"
                f"Transiciones de tramo: {n_trans}\n"
                f"Cartas pendientes: {n_cartas}\n"
                f"Errores: {len(result.errores)}"
            )

    def _tramo_eval_err(self, msg):
        self.btn_eval_tramos.configure(state="normal", text="~ Evaluar Tramos")
        self._set_status(f"Error evaluando tramos: {msg}", 0)

    # ── Firebase Visit Sync ──────────────────────────────────────
    def _on_sync_visits(self):
        """Pull visit data from Firebase → SQLite."""
        if not self.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return

        self.btn_sync_visits.configure(state="disabled", text="Sincronizando…")
        self._set_status("Descargando visitas de Firebase…", 0.4)

        def work():
            try:
                visit_data = self.firebase.pull_visit_data("cartera_activa")
                updated = self.campaign_mgr.sync_visits_from_firebase(
                    campana_id=self.active_campaign.id,
                    firebase_data=visit_data,
                )
                self.after(0, lambda: self._sync_done(updated))
            except Exception as e:
                self.after(0, lambda: self._sync_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _sync_done(self, updated):
        self.btn_sync_visits.configure(state="normal", text="v Sync Visitas")
        self._set_status(
            f"[OK]  Sincronización completada: {updated} clientes actualizados", 1)
        if updated > 0:
            messagebox.showinfo(
                "Sincronización",
                f"Se actualizaron {updated} registros de visitas\n"
                f"desde Firebase hacia la base de datos local."
            )

    def _sync_err(self, msg):
        self.btn_sync_visits.configure(state="normal", text="v Sync Visitas")
        self._set_status(f"Error sincronizando: {msg}", 0)
        messagebox.showerror("Error", f"Error de sincronización:\n{msg}")


class MonitorWindow(ctk.CTkToplevel):
    """Real-time monitor: shows gestor field-visit progress synced from Firestore."""

    _STATUS_LABELS = {
        "pendiente": ("Pendiente", TEXT_SECONDARY),
        "visitado_habido": ("Habido [OK]", SUCCESS),
        "visitado_no_habido": ("No Habido", WARNING),
        "fallecido_inubicable": ("Inubicable", DANGER),
        "suplantacion": ("Suplantación [!]", "#E11D48"),
        "pago_no_registrado": ("Pago No Reg. [$]", "#3B82F6"),
    }

    def __init__(self, parent, firebase):
        super().__init__(parent)
        self.firebase = firebase
        self.title("Monitor de Gestión en Campo — Tiempo Real")
        self.geometry("1100x700")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()
        self._auto_refresh = True

        self._build()
        self._refresh()

    def destroy(self):
        self._auto_refresh = False
        super().destroy()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Monitor de Gestión en Campo",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)

        self._refresh_btn = ctk.CTkButton(
            hdr, text="~ Actualizar", font=_font(12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=34, width=130, corner_radius=8,
            command=self._refresh)
        self._refresh_btn.pack(side="right", padx=20, pady=8)

        ctk.CTkFrame(self, fg_color=ACCENT, height=2, corner_radius=0).pack(fill="x")

        # KPI row
        self._kpi_frame = ctk.CTkFrame(self, fg_color=BG, height=80)
        self._kpi_frame.pack(fill="x", padx=16, pady=(10, 4))

        # Treeview
        tf = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tf.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        cols = ("seccion", "nombre", "codigo", "distrito", "deuda",
                "estado", "nota", "fecha", "gps")
        hdrs = {"seccion": "Secc.", "nombre": "Nombre", "codigo": "Código",
                "distrito": "Distrito", "deuda": "Deuda",
                "estado": "Estado", "nota": "Nota Gestor",
                "fecha": "Fecha Gestión", "gps": "GPS"}

        style = ttk.Style()
        style.configure("Mon.Treeview", background=WHITE,
                         foreground=TEXT_PRIMARY, fieldbackground=WHITE,
                         font=("Segoe UI", 10), rowheight=30, borderwidth=0)
        style.configure("Mon.Treeview.Heading", background="#EEF2FF",
                         foreground=ACCENT, font=("Segoe UI", 10, "bold"),
                         borderwidth=0, relief="flat")
        style.map("Mon.Treeview",
                   background=[("selected", "#E0E7FF")],
                   foreground=[("selected", ACCENT)])

        self._tree = ttk.Treeview(tf, columns=cols, show="headings",
                                   style="Mon.Treeview", height=20)
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            w = 180 if c == "nombre" else 120 if c == "nota" else 90
            self._tree.column(c, width=w, minwidth=50)

        sb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        self._status_lbl = ctk.CTkLabel(self, text="", font=_font(11),
                                         text_color=TEXT_SECONDARY)
        self._status_lbl.pack(padx=16, pady=(0, 6))

    def _refresh(self):
        self._refresh_btn.configure(state="disabled", text="Cargando…")

        def work():
            try:
                data = self.firebase.get_campaign_status()
                self.after(0, lambda: self._render(data))
            except Exception as e:
                self.after(0, lambda: self._render_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _render(self, data):
        self._refresh_btn.configure(state="normal", text="~ Actualizar")
        res = data["resumen"]

        # KPIs
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        self._kpi_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)
        kpis = [
            ("Total", str(res["total"]), "[#]", ACCENT),
            ("Pendientes", str(res["pendiente"]), "[t]", WARNING),
            ("Habidos", str(res["visitado_habido"]), "[+]", SUCCESS),
            ("No Habidos", str(res["visitado_no_habido"]), "[!]", "#F59E0B"),
            ("Inubicables", str(res["fallecido_inubicable"]), "[x]", DANGER),
            ("Suplantación", str(res.get("suplantacion", 0)), "[!]", "#E11D48"),
            ("Pago No Reg.", str(res.get("pago_no_registrado", 0)), "[$]", "#3B82F6"),
            ("Deuda Gestion.", f"S/ {res['deuda_visitada']:,.2f}", "[$]", "#059669"),
        ]
        for i, (lbl, val, ico, clr) in enumerate(kpis):
            KPICard(self._kpi_frame, lbl, val, ico, clr).grid(
                row=0, column=i, padx=3, pady=4, sticky="nsew")

        # Tree
        self._tree.delete(*self._tree.get_children())
        for sec_id in sorted(data["secciones"]):
            sec = data["secciones"][sec_id]
            for c in sec["clientes"]:
                estado = c.get("estado_gestion", "pendiente")
                lbl, _ = self._STATUS_LABELS.get(estado, ("?", TEXT_SECONDARY))
                gps = c.get("gps_gestor")
                gps_str = ""
                if gps:
                    gps_str = f"{gps.get('latitude', 0):.4f}, {gps.get('longitude', 0):.4f}"
                fecha = ""
                fg = c.get("fecha_gestion")
                if fg:
                    try:
                        fecha = fg.strftime("%d/%m %H:%M") if hasattr(fg, 'strftime') else str(fg)[:16]
                    except Exception:
                        fecha = str(fg)[:16]

                self._tree.insert("", "end", values=(
                    sec_id,
                    c.get("nombre_completo", ""),
                    c.get("codigo_cliente", ""),
                    c.get("distrito", ""),
                    f"S/ {float(c.get('importe_deuda_asignada', 0) or 0):,.2f}",
                    lbl,
                    (c.get("nota_gestor", "") or "")[:40],
                    fecha,
                    gps_str,
                ))

        avance = res["total"] - res["pendiente"]
        pct = round(avance / res["total"] * 100) if res["total"] else 0
        self._status_lbl.configure(
            text=f"Avance global: {avance}/{res['total']} ({pct}%)  ·  Última actualización: ahora")

        # Auto-refresh every 30 seconds
        if self._auto_refresh:
            self.after(30000, self._refresh)

    def _render_err(self, msg):
        self._refresh_btn.configure(state="normal", text="~ Actualizar")
        self._status_lbl.configure(text=f"Error: {msg}", text_color=DANGER)


class StatsWindow(ctk.CTkToplevel):
    """Statistical overview with visual charts drawn on tkinter Canvas."""

    def __init__(self, parent, firebase):
        super().__init__(parent)
        self.firebase = firebase
        self.title("Estadísticas — Resumen de Campaña")
        self.geometry("1000x720")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()

        self._build()
        self._load()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Estadísticas de la Campaña",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)
        ctk.CTkFrame(self, fg_color=ACCENT, height=2, corner_radius=0).pack(fill="x")

        self._body = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._body.pack(fill="both", expand=True, padx=16, pady=12)

        self._status_lbl = ctk.CTkLabel(self, text="Cargando...", font=_font(11),
                                         text_color=TEXT_SECONDARY)
        self._status_lbl.pack(padx=16, pady=(0, 8))

    def _load(self):
        def work():
            try:
                data = self.firebase.get_campaign_status()
                self.after(0, lambda: self._render(data))
            except Exception as e:
                self.after(0, lambda: self._status_lbl.configure(
                    text=f"Error: {e}", text_color=DANGER))
        threading.Thread(target=work, daemon=True).start()

    def _render(self, data):
        for w in self._body.winfo_children():
            w.destroy()

        res = data["resumen"]
        secciones = data["secciones"]

        # ── KPIs ─────────────────────────────────────────────
        kpi_row = ctk.CTkFrame(self._body, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 12))
        kpi_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        avance = res["total"] - res["pendiente"]
        pct = round(avance / res["total"] * 100) if res["total"] else 0
        kpis = [
            ("Total Clientes", str(res["total"]), "[#]", ACCENT),
            ("Avance", f"{avance} ({pct}%)", "[%]", SUCCESS),
            ("Deuda Total", f"S/ {res['deuda_total']:,.2f}", "[$]", WARNING),
            ("Deuda Gestionada", f"S/ {res['deuda_visitada']:,.2f}", "[+]", "#059669"),
        ]
        for i, (lbl, val, ico, clr) in enumerate(kpis):
            KPICard(kpi_row, lbl, val, ico, clr).grid(
                row=0, column=i, padx=4, sticky="nsew")

        # ── Pie chart: status distribution ────────────────────
        ctk.CTkLabel(self._body, text="Distribución por Estado",
                     font=_font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(8, 4))

        pie_frame = ctk.CTkFrame(self._body, fg_color=CARD_BG, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        pie_frame.pack(fill="x", pady=4)

        canvas = tk.Canvas(pie_frame, width=360, height=280, bg=WHITE,
                           highlightthickness=0)
        canvas.pack(side="left", padx=20, pady=16)

        slices = [
            (res["pendiente"], "#94A3B8", "Pendiente"),
            (res["visitado_habido"], "#22C55E", "Habido"),
            (res["visitado_no_habido"], "#F59E0B", "No Habido"),
            (res["fallecido_inubicable"], "#EF4444", "Inubicable"),
            (res.get("suplantacion", 0), "#E11D48", "Suplantación"),
            (res.get("pago_no_registrado", 0), "#3B82F6", "Pago No Reg."),
        ]
        total_pie = sum(s[0] for s in slices) or 1
        start = 0
        cx, cy, r = 160, 140, 110
        for val, color, _ in slices:
            if val == 0:
                continue
            extent = val / total_pie * 360
            canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                              start=start, extent=extent,
                              fill=color, outline=WHITE, width=2)
            start += extent

        legend = ctk.CTkFrame(pie_frame, fg_color="transparent")
        legend.pack(side="left", padx=20, pady=16, anchor="n")
        for val, color, label in slices:
            row = ctk.CTkFrame(legend, fg_color="transparent")
            row.pack(fill="x", pady=3)
            dot = ctk.CTkFrame(row, fg_color=color, corner_radius=4,
                                width=14, height=14)
            dot.pack(side="left", padx=(0, 8))
            dot.pack_propagate(False)
            pct_s = round(val / total_pie * 100, 1) if total_pie else 0
            ctk.CTkLabel(row, text=f"{label}: {val} ({pct_s}%)",
                         font=_font(12), text_color=TEXT_PRIMARY
                         ).pack(side="left")

        # ── Bar chart: progress per section ───────────────────
        ctk.CTkLabel(self._body, text="Avance por Sección / Gestor",
                     font=_font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(16, 4))

        bar_frame = ctk.CTkFrame(self._body, fg_color=CARD_BG, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        bar_frame.pack(fill="x", pady=4)

        num_secs = len(secciones)
        bar_h = max(280, num_secs * 46 + 40)
        bar_canvas = tk.Canvas(bar_frame, width=700, height=bar_h, bg=WHITE,
                               highlightthickness=0)
        bar_canvas.pack(padx=20, pady=16)

        left_margin = 60
        bar_width_max = 580
        y = 20
        for sec_id in sorted(secciones):
            sec = secciones[sec_id]
            clients = sec["clientes"]
            total_sec = len(clients)
            done_sec = sum(1 for c in clients if c.get("estado_gestion", "pendiente") != "pendiente")
            pct_sec = done_sec / total_sec if total_sec else 0

            bar_canvas.create_text(left_margin - 10, y + 12, anchor="e",
                                    text=f"Secc. {sec_id}", font=("Segoe UI", 11, "bold"),
                                    fill=TEXT_PRIMARY)
            # Background bar
            bar_canvas.create_rectangle(left_margin, y,
                                         left_margin + bar_width_max, y + 24,
                                         fill="#E2E8F0", outline="")
            # Progress bar
            if pct_sec > 0:
                bar_canvas.create_rectangle(left_margin, y,
                                             left_margin + bar_width_max * pct_sec, y + 24,
                                             fill=ACCENT, outline="")
            # Label
            bar_canvas.create_text(left_margin + bar_width_max + 8, y + 12,
                                    anchor="w",
                                    text=f"{done_sec}/{total_sec} ({round(pct_sec*100)}%)",
                                    font=("Segoe UI", 10),
                                    fill=TEXT_PRIMARY)
            y += 40

        # ── Deuda by section table ────────────────────────────
        ctk.CTkLabel(self._body, text="Deuda por Sección",
                     font=_font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(16, 4))

        tbl = ctk.CTkFrame(self._body, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        tbl.pack(fill="x", pady=4)

        cols = ("seccion", "clientes", "deuda_asig", "gestionados", "avance")
        tbl_tree = ttk.Treeview(tbl, columns=cols, show="headings",
                                 style="AC.Treeview", height=min(num_secs + 1, 15))
        for c, h, w in [("seccion", "Sección", 80), ("clientes", "Clientes", 90),
                         ("deuda_asig", "Deuda Asignada", 160),
                         ("gestionados", "Gestionados", 120), ("avance", "Avance %", 100)]:
            tbl_tree.heading(c, text=h)
            tbl_tree.column(c, width=w, minwidth=60)

        for sec_id in sorted(secciones):
            sec = secciones[sec_id]
            clients = sec["clientes"]
            total_sec = len(clients)
            done_sec = sum(1 for c in clients if c.get("estado_gestion", "pendiente") != "pendiente")
            deuda_sec = sum(float(c.get("importe_deuda_asignada", 0) or 0) for c in clients)
            pct_sec = round(done_sec / total_sec * 100) if total_sec else 0
            tbl_tree.insert("", "end", values=(
                sec_id, total_sec,
                f"S/ {deuda_sec:,.2f}",
                f"{done_sec}/{total_sec}",
                f"{pct_sec}%",
            ))
        tbl_tree.pack(fill="x", padx=8, pady=8)

        self._status_lbl.configure(text="Datos cargados correctamente")


class AlertasWindow(ctk.CTkToplevel):
    """Window for viewing and managing real-time alerts from field gestors."""

    _TIPO_LABELS = {
        "suplantacion": ("[!] Suplantación", "#E11D48"),
        "pago_no_registrado": ("[$] Pago No Registrado", "#3B82F6"),
    }

    def __init__(self, parent, firebase):
        super().__init__(parent)
        self.firebase = firebase
        self.title("Alertas en Tiempo Real — Gestión de Cobranzas")
        self.geometry("1000x650")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()
        self._filter = "pendiente"  # pendiente | revisada | all
        self._alert_data = []

        self._build()
        self._refresh()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="[!] Alertas de Campo",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)

        self._count_label = ctk.CTkLabel(
            hdr, text="", font=_font(12, "bold"),
            text_color=DANGER)
        self._count_label.pack(side="left", padx=8)

        # Filter buttons
        filter_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        filter_frame.pack(side="right", padx=20, pady=8)

        self._btn_pendientes = ctk.CTkButton(
            filter_frame, text="Pendientes", font=_font(11, "bold"),
            fg_color=DANGER, hover_color="#B91C1C",
            height=30, width=100, corner_radius=6,
            command=lambda: self._set_filter("pendiente"))
        self._btn_pendientes.pack(side="left", padx=2)

        self._btn_revisadas = ctk.CTkButton(
            filter_frame, text="Revisadas", font=_font(11, "bold"),
            fg_color=TEXT_SECONDARY, hover_color="#475569",
            height=30, width=100, corner_radius=6,
            command=lambda: self._set_filter("revisada"))
        self._btn_revisadas.pack(side="left", padx=2)

        self._btn_todas = ctk.CTkButton(
            filter_frame, text="Todas", font=_font(11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=30, width=80, corner_radius=6,
            command=lambda: self._set_filter(""))
        self._btn_todas.pack(side="left", padx=2)

        ctk.CTkFrame(self, fg_color="#E11D48", height=2, corner_radius=0).pack(fill="x")

        # Treeview
        tf = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tf.pack(fill="both", expand=True, padx=16, pady=(10, 4))

        cols = ("tipo", "cliente", "seccion", "gestor", "gps", "nota", "fecha", "estado")
        hdrs = {
            "tipo": "Tipo", "cliente": "Cliente", "seccion": "Secc.",
            "gestor": "Gestor", "gps": "GPS", "nota": "Nota",
            "fecha": "Fecha", "estado": "Estado",
        }
        widths = {
            "tipo": 140, "cliente": 180, "seccion": 60,
            "gestor": 150, "gps": 150, "nota": 130,
            "fecha": 120, "estado": 80,
        }

        style = ttk.Style()
        style.configure("Alert.Treeview", background=WHITE,
                         foreground=TEXT_PRIMARY, fieldbackground=WHITE,
                         font=("Segoe UI", 10), rowheight=32, borderwidth=0)
        style.configure("Alert.Treeview.Heading", background="#FFF1F2",
                         foreground="#E11D48", font=("Segoe UI", 10, "bold"),
                         borderwidth=0, relief="flat")
        style.map("Alert.Treeview",
                   background=[("selected", "#FFE4E6")],
                   foreground=[("selected", "#E11D48")])

        self._tree = ttk.Treeview(tf, columns=cols, show="headings",
                                   style="Alert.Treeview", height=18)
        for c in cols:
            self._tree.heading(c, text=hdrs[c])
            self._tree.column(c, width=widths.get(c, 100), minwidth=50)

        sb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

        # Bottom action bar
        action_bar = ctk.CTkFrame(self, fg_color=BG, height=50)
        action_bar.pack(fill="x", padx=16, pady=(4, 12))
        action_bar.pack_propagate(False)

        self._btn_review = ctk.CTkButton(
            action_bar, text="[OK] Marcar como Revisada", font=_font(12, "bold"),
            fg_color=SUCCESS, hover_color="#15803D",
            height=36, width=220, corner_radius=8,
            command=self._on_mark_reviewed)
        self._btn_review.pack(side="left", padx=(0, 8))

        self._btn_refresh = ctk.CTkButton(
            action_bar, text="~ Actualizar", font=_font(12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=36, width=130, corner_radius=8,
            command=self._refresh)
        self._btn_refresh.pack(side="left")

        self._status_lbl = ctk.CTkLabel(action_bar, text="",
                                         font=_font(11), text_color=TEXT_SECONDARY)
        self._status_lbl.pack(side="right", padx=8)

    def _set_filter(self, estado):
        self._filter = estado
        self._refresh()

    def _refresh(self):
        self._btn_refresh.configure(state="disabled", text="Cargando…")

        def work():
            try:
                alerts = self.firebase.get_alerts(estado=self._filter, limit=200)
                self.after(0, lambda: self._render(alerts))
            except Exception as e:
                self.after(0, lambda: self._render_err(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _render(self, alerts):
        self._btn_refresh.configure(state="normal", text="~ Actualizar")
        self._alert_data = alerts
        self._tree.delete(*self._tree.get_children())

        pending_count = sum(1 for a in alerts if a.get("estado_alerta") == "pendiente")
        self._count_label.configure(
            text=f"{pending_count} pendientes" if pending_count else "Sin alertas pendientes",
            text_color=DANGER if pending_count else SUCCESS)

        for a in alerts:
            tipo_raw = a.get("tipo", "?")
            tipo_label, _ = self._TIPO_LABELS.get(tipo_raw, (tipo_raw, TEXT_SECONDARY))
            gps = a.get("gps", {})
            gps_str = ""
            if isinstance(gps, dict) and gps.get("latitude"):
                gps_str = f"{gps['latitude']:.5f}, {gps['longitude']:.5f}"

            self._tree.insert("", "end", values=(
                tipo_label,
                a.get("cliente_nombre", "—"),
                a.get("seccion", "—"),
                a.get("gestor_nombre", a.get("gestor_email", "—")),
                gps_str,
                (a.get("nota", "") or "")[:50],
                a.get("fecha_str", "—"),
                "Pendiente" if a.get("estado_alerta") == "pendiente" else "Revisada",
            ), iid=a.get("id", ""))

        filter_label = {"pendiente": "pendientes", "revisada": "revisadas", "": "todas"}
        self._status_lbl.configure(
            text=f"{len(alerts)} alertas ({filter_label.get(self._filter, 'todas')})")

    def _render_err(self, msg):
        self._btn_refresh.configure(state="normal", text="~ Actualizar")
        self._status_lbl.configure(text=f"Error: {msg}", text_color=DANGER)

    def _on_mark_reviewed(self):
        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("Selección", "Seleccione una alerta para marcar como revisada.")
            return
        alert_id = selected[0]

        def work():
            ok = self.firebase.mark_alert_reviewed(alert_id)
            self.after(0, lambda: self._review_done(ok, alert_id))
        threading.Thread(target=work, daemon=True).start()

    def _review_done(self, ok, alert_id):
        if ok:
            self._status_lbl.configure(
                text=f"[OK] Alerta {alert_id[:8]}… marcada como revisada",
                text_color=SUCCESS)
            self._refresh()
        else:
            self._status_lbl.configure(
                text="Error al marcar alerta", text_color=DANGER)


class TrackingWindow(ctk.CTkToplevel):
    """GPS Tracking panel — shows gestor locations, trail history and km."""

    # Colors per section (up to 10 sections)
    _SEC_COLORS = [
        "#4F46E5", "#0D9488", "#D97706", "#DC2626", "#7C3AED",
        "#059669", "#E11D48", "#0891B2", "#B45309", "#6366F1",
    ]

    def __init__(self, parent, firebase):
        super().__init__(parent)
        self.firebase = firebase
        self.title("[GPS]  GPS Tracking — Ubicación de Gestores")
        self.geometry("1200x780")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()
        self._auto_refresh = True
        self._gestores = []        # Tracking summary docs
        self._selected_uid = None  # Currently selected gestor UID
        self._trail_points = []    # Trail for selected gestor
        self._color_map = {}       # seccion → color

        self._build()
        self._refresh()

    def destroy(self):
        self._auto_refresh = False
        super().destroy()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="[GPS]  GPS Tracking — Ubicación de Gestores",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)

        self._refresh_btn = ctk.CTkButton(
            hdr, text="~ Actualizar", font=_font(12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=34, width=130, corner_radius=8,
            command=self._refresh)
        self._refresh_btn.pack(side="right", padx=20, pady=8)

        # Open in browser button
        ctk.CTkButton(
            hdr, text="[W] Ver Mapa Web", font=_font(12, "bold"),
            fg_color="#059669", hover_color="#047857",
            height=34, width=150, corner_radius=8,
            command=self._open_web_map
        ).pack(side="right", padx=4, pady=8)

        ctk.CTkFrame(self, fg_color=ACCENT, height=2,
                      corner_radius=0).pack(fill="x")

        # Status
        self._status_lbl = ctk.CTkLabel(
            self, text="Cargando datos GPS…", font=_font(11),
            text_color=TEXT_SECONDARY, anchor="w")
        self._status_lbl.pack(fill="x", padx=20, pady=(8, 0))

        # Main content: left list + right detail
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        # ── Left panel: Gestor list ──
        left = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=12,
                             border_width=1, border_color=BORDER, width=320)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Gestores con GPS",
                     font=_font(14, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=14, pady=(12, 4), anchor="w")

        self._gestor_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent")
        self._gestor_list.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Right panel: Detail ──
        right = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=12,
                              border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")

        # KPIs row
        self._kpi_frame = ctk.CTkFrame(right, fg_color="transparent",
                                        height=90)
        self._kpi_frame.pack(fill="x", padx=12, pady=(12, 4))

        # Trail detail area
        self._detail_area = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._detail_area.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._show_no_selection()

    def _show_no_selection(self):
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        for w in self._detail_area.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail_area,
                     text="Seleccione un gestor para ver su recorrido",
                     font=_font(14), text_color=TEXT_SECONDARY
                     ).pack(pady=60)

    def _open_web_map(self):
        import webbrowser
        webbrowser.open("https://clase-001.web.app")

    def _refresh(self):
        if not self._auto_refresh:
            return
        self._refresh_btn.configure(state="disabled", text="Cargando…")
        self._status_lbl.configure(text="Actualizando datos GPS…",
                                   text_color=TEXT_SECONDARY)

        def work():
            gestores = self.firebase.get_tracking_summary()
            self.after(0, lambda: self._on_data(gestores))

        threading.Thread(target=work, daemon=True).start()

    def _on_data(self, gestores):
        self._gestores = gestores
        self._refresh_btn.configure(state="normal", text="~ Actualizar")

        # Build color map by section
        secciones = sorted(set(g.get("seccion", "?") for g in gestores))
        self._color_map = {s: self._SEC_COLORS[i % len(self._SEC_COLORS)]
                           for i, s in enumerate(secciones)}

        # Render gestor list
        for w in self._gestor_list.winfo_children():
            w.destroy()

        if not gestores:
            ctk.CTkLabel(self._gestor_list,
                         text="No hay datos de GPS disponibles",
                         font=_font(12), text_color=TEXT_SECONDARY
                         ).pack(pady=20)
            self._status_lbl.configure(
                text="Sin datos de tracking. Los gestores aún no han "
                     "registrado ubicación.", text_color=WARNING)
            return

        self._status_lbl.configure(
            text=f"[OK] {len(gestores)} gestores con tracking GPS",
            text_color=SUCCESS)

        for g in sorted(gestores, key=lambda x: x.get("seccion", "")):
            uid = g.get("uid", "")
            nombre = g.get("gestor_nombre", "") or uid[:8]
            seccion = g.get("seccion", "?")
            color = self._color_map.get(seccion, ACCENT)

            # Last seen
            ts = ""
            if g.get("ultimo_timestamp"):
                try:
                    ts = g["ultimo_timestamp"].strftime("%H:%M %d/%m")
                except Exception:
                    ts = str(g.get("ultimo_timestamp", ""))

            card = ctk.CTkFrame(self._gestor_list, fg_color="transparent",
                                 cursor="hand2")
            card.pack(fill="x", pady=2)

            # Section badge
            badge = ctk.CTkFrame(card, fg_color=color, corner_radius=6,
                                  width=30, height=30)
            badge.pack(side="left", padx=(4, 8))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=seccion, font=_font(12, "bold"),
                         text_color=WHITE).place(relx=0.5, rely=0.5,
                                                  anchor="center")

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=nombre, font=_font(12, "bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(info, text=ts if ts else "Sin timestamp",
                         font=_font(10), text_color=TEXT_SECONDARY
                         ).pack(anchor="w")

            # Lat/Lng
            lat = g.get("ultima_lat", 0)
            lng = g.get("ultima_lng", 0)
            if lat and lng:
                ctk.CTkLabel(info,
                             text=f"({lat:.5f}, {lng:.5f})",
                             font=_font(9), text_color=TEXT_SECONDARY
                             ).pack(anchor="w")

            # Click handler
            for widget in [card, info]:
                widget.bind("<Button-1>",
                            lambda e, _uid=uid: self._select_gestor(_uid))

        # Auto-refresh after 30 seconds
        if self._auto_refresh:
            self.after(30000, self._refresh)

    def _select_gestor(self, uid):
        self._selected_uid = uid
        self._status_lbl.configure(
            text=f"Cargando recorrido de {uid[:12]}…",
            text_color=TEXT_SECONDARY)

        for w in self._detail_area.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail_area, text="Cargando puntos…",
                     font=_font(12), text_color=TEXT_SECONDARY).pack(pady=20)

        def work():
            points = self.firebase.get_tracking_points(uid, limit=300)
            self.after(0, lambda: self._render_trail(uid, points))

        threading.Thread(target=work, daemon=True).start()

    def _render_trail(self, uid, points):
        for w in self._kpi_frame.winfo_children():
            w.destroy()
        for w in self._detail_area.winfo_children():
            w.destroy()

        # Find gestor info
        gestor = next((g for g in self._gestores if g.get("uid") == uid), {})
        nombre = gestor.get("gestor_nombre", "") or uid[:12]
        seccion = gestor.get("seccion", "?")

        # Calculate total km
        total_km = 0.0
        if len(points) >= 2:
            for i in range(1, len(points)):
                p1 = points[i - 1]
                p2 = points[i]
                try:
                    d = self.firebase.haversine_km(
                        float(p1.get("lat", 0)), float(p1.get("lng", 0)),
                        float(p2.get("lat", 0)), float(p2.get("lng", 0)))
                    total_km += d
                except (TypeError, ValueError):
                    pass

        # Count visit points vs auto
        auto_pts = sum(1 for p in points if p.get("tipo") == "auto")
        visit_pts = sum(1 for p in points if p.get("tipo") != "auto")

        # KPIs
        self._kpi_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        kpis = [
            ("Gestor", nombre, "[U]", ACCENT),
            ("Sección", seccion, "[S]", "#0D9488"),
            ("Km Recorridos", f"{total_km:.2f} km", "[km]", WARNING),
            ("Puntos Auto", str(auto_pts), "[GPS]", "#7C3AED"),
            ("Visitas GPS", str(visit_pts), "[OK]", SUCCESS),
        ]
        for i, (lbl, val, ico, clr) in enumerate(kpis):
            KPICard(self._kpi_frame, lbl, val, ico, clr).grid(
                row=0, column=i, padx=3, sticky="nsew")

        self._status_lbl.configure(
            text=f"[OK] {nombre} — {len(points)} puntos, "
                 f"{total_km:.2f} km recorridos", text_color=SUCCESS)

        if not points:
            ctk.CTkLabel(self._detail_area,
                         text="No hay puntos de tracking para este gestor",
                         font=_font(13), text_color=TEXT_SECONDARY
                         ).pack(pady=30)
            return

        # ── Map-like canvas showing route ──
        map_frame = ctk.CTkFrame(self._detail_area, fg_color="#F1F5F9",
                                  corner_radius=12, border_width=1,
                                  border_color=BORDER, height=300)
        map_frame.pack(fill="x", pady=(4, 8))
        map_frame.pack_propagate(False)

        canvas = tk.Canvas(map_frame, bg="#F1F5F9", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=8, pady=8)

        # Draw after layout
        self.after(100, lambda: self._draw_route(canvas, points))

        # ── Google Maps / OSM links ──
        link_frame = ctk.CTkFrame(self._detail_area, fg_color="transparent")
        link_frame.pack(fill="x", pady=(0, 6))

        if points:
            last = points[-1]
            lat, lng = last.get("lat", 0), last.get("lng", 0)
            ctk.CTkButton(
                link_frame, text=f"[map] Abrir última ubicación en Google Maps",
                font=_font(11), fg_color="#0D9488", hover_color="#0F766E",
                height=30, corner_radius=8,
                command=lambda: self._open_gmaps(lat, lng)
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                link_frame, text="[map] Ver ruta completa en Google Maps",
                font=_font(11), fg_color="#4F46E5", hover_color="#4338CA",
                height=30, corner_radius=8,
                command=lambda: self._open_gmaps_route(points)
            ).pack(side="left")

        # ── Point-by-point table ──
        ctk.CTkLabel(self._detail_area, text="Historial de Puntos",
                     font=_font(14, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(8, 4))

        # Table
        table_frame = ctk.CTkFrame(self._detail_area, fg_color=CARD_BG,
                                    corner_radius=10, border_width=1,
                                    border_color=BORDER)
        table_frame.pack(fill="x", pady=4)

        cols = ("hora", "lat", "lng", "tipo", "cliente", "estado", "km")
        hdrs = {"hora": "Hora", "lat": "Latitud", "lng": "Longitud",
                "tipo": "Tipo", "cliente": "Cliente", "estado": "Estado",
                "km": "Dist. (m)"}

        style = ttk.Style()
        style.configure("Tracking.Treeview", background=WHITE,
                         foreground=TEXT_PRIMARY, fieldbackground=WHITE,
                         font=("Segoe UI", 9), rowheight=26, borderwidth=0)
        style.configure("Tracking.Treeview.Heading", background="#EEF2FF",
                         foreground=ACCENT, font=("Segoe UI", 9, "bold"),
                         borderwidth=0, relief="flat")

        tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                            style="Tracking.Treeview",
                            height=min(len(points) + 1, 15))

        col_widths = {"hora": 140, "lat": 100, "lng": 100, "tipo": 60,
                       "cliente": 160, "estado": 100, "km": 70}
        for c in cols:
            tree.heading(c, text=hdrs[c])
            tree.column(c, width=col_widths.get(c, 100), minwidth=50)

        prev_lat, prev_lng = None, None
        for pt in points:
            lat = pt.get("lat", 0)
            lng = pt.get("lng", 0)
            dist_m = ""
            if prev_lat is not None:
                try:
                    d = self.firebase.haversine_km(prev_lat, prev_lng,
                                                    float(lat), float(lng))
                    dist_m = f"{d * 1000:.0f}"
                except (TypeError, ValueError):
                    pass
            prev_lat, prev_lng = float(lat), float(lng)

            tree.insert("", "end", values=(
                pt.get("timestamp_str", pt.get("fecha", "")),
                f"{lat:.5f}" if lat else "",
                f"{lng:.5f}" if lng else "",
                pt.get("tipo", "visita"),
                pt.get("cliente_nombre", ""),
                pt.get("estado", ""),
                dist_m,
            ))

        tree.pack(fill="x", padx=2, pady=2)

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)

    def _draw_route(self, canvas, points):
        """Draw a simplified route visualization on a tkinter Canvas."""
        canvas.update_idletasks()
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        # Filter valid coordinates
        coords = []
        for p in points:
            try:
                lat, lng = float(p["lat"]), float(p["lng"])
                if lat != 0 and lng != 0:
                    coords.append((lat, lng, p.get("tipo", "auto")))
            except (KeyError, TypeError, ValueError):
                continue

        if len(coords) < 1:
            canvas.create_text(cw // 2, ch // 2, text="Sin coordenadas válidas",
                               font=("Segoe UI", 12), fill=TEXT_SECONDARY)
            return

        # Determine bounding box
        lats = [c[0] for c in coords]
        lngs = [c[1] for c in coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)

        # Add padding
        pad = 30
        lat_range = max_lat - min_lat or 0.001
        lng_range = max_lng - min_lng or 0.001

        def to_xy(lat, lng):
            x = pad + (lng - min_lng) / lng_range * (cw - 2 * pad)
            y = pad + (max_lat - lat) / lat_range * (ch - 2 * pad)
            return x, y

        # Draw gridlines lightly
        for i in range(5):
            y = pad + i * (ch - 2 * pad) / 4
            canvas.create_line(pad, y, cw - pad, y, fill="#E2E8F0", dash=(2, 4))
            lat_v = max_lat - i * lat_range / 4
            canvas.create_text(3, y, text=f"{lat_v:.4f}", anchor="w",
                               font=("Segoe UI", 7), fill=TEXT_SECONDARY)

        for i in range(5):
            x = pad + i * (cw - 2 * pad) / 4
            canvas.create_line(x, pad, x, ch - pad, fill="#E2E8F0", dash=(2, 4))
            lng_v = min_lng + i * lng_range / 4
            canvas.create_text(x, ch - 5, text=f"{lng_v:.4f}", anchor="s",
                               font=("Segoe UI", 7), fill=TEXT_SECONDARY)

        # Draw route line
        if len(coords) >= 2:
            line_pts = []
            for lat, lng, _ in coords:
                x, y = to_xy(lat, lng)
                line_pts.extend([x, y])
            canvas.create_line(line_pts, fill=ACCENT, width=2, smooth=True)

        # Draw dots
        for i, (lat, lng, tipo) in enumerate(coords):
            x, y = to_xy(lat, lng)
            r = 4 if tipo == "auto" else 6
            color = "#7C3AED" if tipo == "auto" else SUCCESS
            if i == 0:
                color = "#059669"
                r = 7
            elif i == len(coords) - 1:
                color = DANGER
                r = 7
            canvas.create_oval(x - r, y - r, x + r, y + r,
                               fill=color, outline=WHITE, width=1)

        # Legend
        canvas.create_oval(cw - 180, 10, cw - 174, 16, fill="#059669")
        canvas.create_text(cw - 170, 13, text="Inicio", anchor="w",
                           font=("Segoe UI", 8), fill=TEXT_PRIMARY)
        canvas.create_oval(cw - 120, 10, cw - 114, 16, fill=DANGER)
        canvas.create_text(cw - 110, 13, text="Último", anchor="w",
                           font=("Segoe UI", 8), fill=TEXT_PRIMARY)
        canvas.create_oval(cw - 60, 10, cw - 54, 16, fill="#7C3AED")
        canvas.create_text(cw - 50, 13, text="Auto", anchor="w",
                           font=("Segoe UI", 8), fill=TEXT_PRIMARY)

    @staticmethod
    def _open_gmaps(lat, lng):
        import webbrowser
        webbrowser.open(f"https://www.google.com/maps?q={lat},{lng}")

    @staticmethod
    def _open_gmaps_route(points):
        import webbrowser
        # Use first, last, and up to 8 waypoints
        valid = [(p.get("lat"), p.get("lng")) for p in points
                 if p.get("lat") and p.get("lng")]
        if not valid:
            return
        origin = f"{valid[0][0]},{valid[0][1]}"
        dest = f"{valid[-1][0]},{valid[-1][1]}"
        # Sample waypoints evenly
        waypoints = ""
        if len(valid) > 2:
            step = max(1, len(valid) // 8)
            wps = valid[1:-1:step][:8]
            waypoints = "&waypoints=" + "|".join(
                f"{w[0]},{w[1]}" for w in wps)
        url = (f"https://www.google.com/maps/dir/{origin}/{dest}"
               f"?travelmode=driving{waypoints}")
        webbrowser.open(url)


# ═══════════════════════════════════════════════════════════════════
# DISTRIBUTION CONFIGURATION WINDOW
# ═══════════════════════════════════════════════════════════════════

class DistribucionWindow(ctk.CTkToplevel):
    """
    Configurable distribution window.
    Shows the Region → Zona → Sección hierarchy from the loaded Excel,
    displays current gestor assignments from Firebase, and allows
    re-assigning gestors to sections.
    """

    def __init__(self, parent, firebase, parsed_data):
        super().__init__(parent)
        self.firebase = firebase
        self.parsed_data = parsed_data
        self.title("Configurar Distribución — Región / Zona / Sección")
        self.geometry("1200x750")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()

        self._gestores = []  # List of dicts from Firebase
        self._assignments = {}  # seccion -> gestor_uid
        self._gestor_names = {}  # uid -> nombre

        self._build()
        self._load_data()

    def _build(self):
        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=56, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Configurar Distribución de Cartera",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)

        self._save_btn = ctk.CTkButton(
            hdr, text="Guardar Asignaciones", font=_font(12, "bold"),
            fg_color=SUCCESS, hover_color="#15803D",
            height=36, width=200, corner_radius=8,
            command=self._save_assignments)
        self._save_btn.pack(side="right", padx=20, pady=10)

        ctk.CTkFrame(self, fg_color=ACCENT, height=2, corner_radius=0).pack(fill="x")

        # ── Info bar ──
        info = ctk.CTkFrame(self, fg_color="#FEF3C7", height=40, corner_radius=0)
        info.pack(fill="x")
        info.pack_propagate(False)
        ctk.CTkLabel(info,
                     text="Seleccione un gestor del menú desplegable en cada sección "
                          "para asignar/reasignar la distribución. "
                          "Los cambios se guardan en los perfiles de Firebase.",
                     font=_font(11), text_color="#92400E",
                     ).pack(side="left", padx=16, pady=8)

        # ── Split: hierarchy (left) + legend (right) ──
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=16, pady=12)
        split.grid_columnconfigure(0, weight=3)
        split.grid_columnconfigure(1, weight=1)
        split.grid_rowconfigure(0, weight=1)

        # Left: Scrollable hierarchy
        self._tree_frame = ctk.CTkScrollableFrame(
            split, fg_color=BG,
            scrollbar_button_color="#CBD5E1",
            scrollbar_button_hover_color=ACCENT)
        self._tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Right: Gesture summary panel
        right_panel = ctk.CTkFrame(split, fg_color=CARD_BG, corner_radius=12,
                                   border_width=1, border_color=BORDER)
        right_panel.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(right_panel, text="Gestores Registrados",
                     font=_font(14, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=14, pady=(14, 6), anchor="w")

        self._gestor_list_frame = ctk.CTkScrollableFrame(
            right_panel, fg_color="transparent")
        self._gestor_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Status
        self._status = ctk.CTkLabel(self, text="Cargando...", font=_font(11),
                                     text_color=TEXT_SECONDARY)
        self._status.pack(padx=16, pady=(0, 8))

    def _load_data(self):
        """Load gestors from Firebase and build the hierarchy display."""
        def work():
            gestores = self.firebase.list_gestor_users()
            self.after(0, lambda: self._on_data_loaded(gestores))

        threading.Thread(target=work, daemon=True).start()

    def _on_data_loaded(self, gestores):
        self._gestores = [g for g in gestores
                          if g.get("rol") in ("gestor", "asistente", "supervisor", "admin")]
        self._gestor_names = {}
        self._assignments = {}  # seccion_key -> gestor_uid

        for g in self._gestores:
            uid = g.get("uid") or g.get("id", "")
            name = g.get("nombre", g.get("email", "???"))
            self._gestor_names[uid] = name
            # Build assignments from the secciones array (composite keys)
            secciones = g.get("secciones") or []
            if isinstance(secciones, list):
                for sk in secciones:
                    self._assignments[sk] = uid
            else:
                # Fallback: old single seccion field
                sec = g.get("seccion", "")
                if sec:
                    self._assignments[sec] = uid

        self._render_hierarchy()
        self._render_gestor_list()
        self._status.configure(
            text=f"{len(self._gestores)} gestores cargados  ·  "
                 f"{len(self._assignments)} secciones asignadas")

    def _render_gestor_list(self):
        """Render the right-panel gestor summary."""
        for w in self._gestor_list_frame.winfo_children():
            w.destroy()

        if not self._gestores:
            ctk.CTkLabel(self._gestor_list_frame,
                         text="No hay gestores registrados",
                         font=_font(11), text_color=TEXT_SECONDARY
                         ).pack(pady=20)
            return

        for g in sorted(self._gestores, key=lambda x: x.get("nombre", "")):
            card = ctk.CTkFrame(self._gestor_list_frame, fg_color="#F8FAFC",
                                corner_radius=8, border_width=1,
                                border_color=BORDER)
            card.pack(fill="x", pady=2)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=8, pady=6)

            # Show first section letter or "?" as badge
            secciones = g.get("secciones") or []
            sec_display = g.get("seccion", "?") or "?"
            badge = ctk.CTkFrame(inner, fg_color=BADGE_BG, corner_radius=5,
                                  width=26, height=26)
            badge.pack(side="left", padx=(0, 6))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=sec_display[:2], font=_font(11, "bold"),
                         text_color=ACCENT
                         ).place(relx=0.5, rely=0.5, anchor="center")

            info_f = ctk.CTkFrame(inner, fg_color="transparent")
            info_f.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info_f, text=g.get("nombre", ""),
                         font=_font(11, "bold"), text_color=TEXT_PRIMARY
                         ).pack(anchor="w")
            meta_parts = []
            if g.get("region"):
                meta_parts.append(f"R:{g['region']}")
            if g.get("zona"):
                meta_parts.append(f"Z:{g['zona']}")
            if g.get("rol"):
                meta_parts.append(g["rol"])
            if secciones:
                meta_parts.append(f"{len(secciones)} secc.")
            ctk.CTkLabel(info_f, text="  ·  ".join(meta_parts),
                         font=_font(9), text_color=TEXT_SECONDARY
                         ).pack(anchor="w")
            # Show composite keys under name
            if secciones:
                ctk.CTkLabel(info_f, text=", ".join(secciones),
                             font=_font(8), text_color=TEXT_SECONDARY
                             ).pack(anchor="w")

    def _render_hierarchy(self):
        """Render the Region → Zona → Sección tree with gestor selectors."""
        for w in self._tree_frame.winfo_children():
            w.destroy()

        hierarchy = get_hierarchy(self.parsed_data["all_clients"])

        # Build the options list for dropdowns: "nombre (email)" keyed by uid
        gestor_options = ["Sin asignar"]
        gestor_uid_map = {"Sin asignar": None}
        for g in sorted(self._gestores, key=lambda x: x.get("nombre", "")):
            uid = g.get("uid") or g.get("id", "")
            label = f"{g.get('nombre', '?')}  ({g.get('email', '')})"
            gestor_options.append(label)
            gestor_uid_map[label] = uid

        # Reverse map: uid -> label
        uid_to_label = {v: k for k, v in gestor_uid_map.items() if v}

        self._section_vars = {}  # seccion -> StringVar
        self._uid_map = gestor_uid_map

        for region_key, region_data in hierarchy["regions"].items():
            # ── Region Card ──
            r_card = ctk.CTkFrame(self._tree_frame, fg_color="#EEF2FF",
                                  corner_radius=10, border_width=1,
                                  border_color=ACCENT)
            r_card.pack(fill="x", pady=(8, 2))

            r_row = ctk.CTkFrame(r_card, fg_color="transparent")
            r_row.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(r_row, text=f"REGIÓN {region_key}",
                         font=_font(14, "bold"), text_color=ACCENT
                         ).pack(side="left")
            ctk.CTkLabel(r_row,
                         text=f"{region_data['num_clientes']} clientes  ·  "
                              f"S/ {region_data['deuda_asignada']:,.2f}  ·  "
                              f"Pend. S/ {region_data['deuda_pendiente']:,.2f}",
                         font=_font(11), text_color=TEXT_SECONDARY
                         ).pack(side="right")

            for zona_key, zona_data in sorted(region_data["zonas"].items()):
                # ── Zona Card ──
                z_card = ctk.CTkFrame(self._tree_frame, fg_color="#F0FDFA",
                                      corner_radius=8, border_width=1,
                                      border_color="#99F6E4")
                z_card.pack(fill="x", pady=(2, 1), padx=(24, 0))

                z_row = ctk.CTkFrame(z_card, fg_color="transparent")
                z_row.pack(fill="x", padx=12, pady=8)
                ctk.CTkLabel(z_row, text=f"Zona {zona_key}",
                             font=_font(12, "bold"), text_color="#0D9488"
                             ).pack(side="left")
                ctk.CTkLabel(z_row,
                             text=f"{zona_data['num_clientes']} clientes  ·  "
                                  f"S/ {zona_data['deuda_asignada']:,.2f}",
                             font=_font(10), text_color=TEXT_SECONDARY
                             ).pack(side="right")

                for sec_key, sec_data in sorted(zona_data["secciones"].items()):
                    # Build composite key for this unique section
                    sec_composite = make_seccion_key(region_key, zona_key, sec_key)

                    # ── Section Row with gestor dropdown ──
                    s_card = ctk.CTkFrame(self._tree_frame, fg_color=CARD_BG,
                                          corner_radius=8, border_width=1,
                                          border_color=BORDER)
                    s_card.pack(fill="x", pady=1, padx=(48, 0))

                    s_row = ctk.CTkFrame(s_card, fg_color="transparent")
                    s_row.pack(fill="x", padx=12, pady=8)

                    # Section badge
                    badge = ctk.CTkFrame(s_row, fg_color=BADGE_BG,
                                          corner_radius=6, width=32, height=32)
                    badge.pack(side="left", padx=(0, 8))
                    badge.pack_propagate(False)
                    ctk.CTkLabel(badge, text=sec_key,
                                 font=_font(13, "bold"), text_color=ACCENT
                                 ).place(relx=0.5, rely=0.5, anchor="center")

                    # Section info
                    s_info = ctk.CTkFrame(s_row, fg_color="transparent")
                    s_info.pack(side="left", fill="x", expand=True)
                    ctk.CTkLabel(s_info,
                                 text=f"Sección {sec_key}  ·  "
                                      f"{sec_data['num_clientes']} clientes  ·  "
                                      f"S/ {sec_data['deuda_asignada']:,.2f}",
                                 font=_font(11), text_color=TEXT_PRIMARY
                                 ).pack(anchor="w")
                    ctk.CTkLabel(s_info,
                                 text=sec_composite,
                                 font=_font(9), text_color=TEXT_SECONDARY
                                 ).pack(anchor="w")

                    # Gestor dropdown — keyed by composite key
                    current_uid = self._assignments.get(sec_composite)
                    current_label = uid_to_label.get(current_uid, "Sin asignar")  # type: ignore[arg-type]

                    var = ctk.StringVar(value=current_label)
                    self._section_vars[sec_composite] = var

                    dropdown = ctk.CTkOptionMenu(
                        s_row, variable=var,
                        values=gestor_options,
                        font=_font(11), height=32, width=280,
                        corner_radius=6,
                        fg_color="#F1F5F9", button_color=ACCENT,
                        button_hover_color=ACCENT_HOVER,
                        text_color=TEXT_PRIMARY,
                    )
                    dropdown.pack(side="right")

    def _save_assignments(self):
        """Save all gestor assignments to Firebase user profiles.

        Each section dropdown maps a composite key (region_zona_seccion) to
        a gestor UID.  We aggregate all composite keys per gestor into a
        ``secciones`` array and store it on the profile.  The legacy
        ``seccion`` field is set to the first letter for backward compat.
        """
        self._save_btn.configure(state="disabled", text="Guardando...")

        # Build the new assignments: seccion_key -> uid
        new_assignments = {}
        for sec_key, var in self._section_vars.items():
            label = var.get()
            uid = self._uid_map.get(label)
            if uid:
                new_assignments[sec_key] = uid

        # Invert: uid -> list of composite keys
        uid_to_keys: dict[str, list[str]] = {}
        for sec_key, uid in new_assignments.items():
            uid_to_keys.setdefault(uid, []).append(sec_key)

        # Parse region/zona from composite key for the "primary" assignment
        def _parse_key(key: str):
            parts = key.split("_", 2)
            if len(parts) == 3:
                return parts[0], parts[1], parts[2]
            return "", "", key

        def work():
            errors = []
            updated = 0

            # First, clear secciones for gestors no longer assigned to anything
            for g in self._gestores:
                uid = g.get("uid") or g.get("id", "")
                if uid not in uid_to_keys:
                    old_secs = g.get("secciones") or []
                    old_sec = g.get("seccion", "")
                    if old_secs or old_sec:
                        try:
                            self.firebase.update_user(uid, {
                                "seccion": "",
                                "secciones": [],
                                "region": "",
                                "zona": "",
                            })
                            updated += 1
                        except Exception as e:
                            errors.append(f"{uid}: {e}")

            # Now assign composite keys to each gestor
            for uid, keys in uid_to_keys.items():
                keys_sorted = sorted(keys)
                # Use the first key for legacy seccion/region/zona fields
                primary_r, primary_z, primary_s = _parse_key(keys_sorted[0])
                try:
                    result = self.firebase.update_user(uid, {
                        "secciones": keys_sorted,
                        "seccion": primary_s,
                        "region": primary_r,
                        "zona": primary_z,
                    })
                    if result.get("success"):
                        updated += 1
                    else:
                        errors.append(f"{uid}: {result.get('error', '?')}")
                except Exception as e:
                    errors.append(f"{uid}: {e}")

            self.after(0, lambda: self._save_done(updated, errors))

        threading.Thread(target=work, daemon=True).start()

    def _save_done(self, updated, errors):
        self._save_btn.configure(state="normal", text="Guardar Asignaciones")
        if errors:
            self._status.configure(
                text=f"Guardado con {len(errors)} errores: {errors[0]}",
                text_color=DANGER)
        else:
            self._status.configure(
                text=f"[OK] {updated} asignaciones guardadas exitosamente",
                text_color=SUCCESS)
        # Refresh data
        self._load_data()


class UserManagerWindow(ctk.CTkToplevel):
    """Window for creating/managing gestor accounts."""

    def __init__(self, parent, firebase):
        super().__init__(parent)
        self.firebase = firebase
        self.title("Gestionar Usuarios — Gestores de Campo")
        self.geometry("700x600")
        self.configure(fg_color=BG)
        self.transient(parent)
        self.grab_set()

        self._build()
        self._refresh_users()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=WHITE, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Gestión de Usuarios",
                     font=_font(16, "bold"), text_color=TEXT_PRIMARY
                     ).pack(side="left", padx=20)
        ctk.CTkButton(hdr, text="+ Nuevo Gestor", font=_font(12, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      height=34, width=140, corner_radius=8,
                      command=self._new_user
                      ).pack(side="right", padx=20, pady=8)

        ctk.CTkFrame(self, fg_color=ACCENT, height=2, corner_radius=0).pack(fill="x")

        # User list
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=BG)
        self._list_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # Status
        self._status_lbl = ctk.CTkLabel(self, text="", font=_font(11),
                                         text_color=TEXT_SECONDARY)
        self._status_lbl.pack(padx=16, pady=(0, 8))

    def _refresh_users(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        users = self.firebase.list_gestor_users()
        if not users:
            ctk.CTkLabel(self._list_frame, text="No hay usuarios registrados",
                         font=_font(13), text_color=TEXT_SECONDARY
                         ).pack(pady=30)
            return

        for u in users:
            card = ctk.CTkFrame(self._list_frame, fg_color=CARD_BG,
                                corner_radius=10, border_width=1,
                                border_color=BORDER)
            card.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=10)

            # Badge with section letter
            badge = ctk.CTkFrame(inner, fg_color=BADGE_BG, corner_radius=6,
                                  width=32, height=32)
            badge.pack(side="left", padx=(0, 10))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=u.get("seccion", "?"),
                         font=_font(13, "bold"), text_color=ACCENT
                         ).place(relx=0.5, rely=0.5, anchor="center")

            info = ctk.CTkFrame(inner, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)

            # Name + role tag
            name_row = ctk.CTkFrame(info, fg_color="transparent")
            name_row.pack(anchor="w", fill="x")
            ctk.CTkLabel(name_row, text=u.get("nombre", "---"),
                         font=_font(13, "bold"), text_color=TEXT_PRIMARY
                         ).pack(side="left")
            rol_text = u.get("rol", "gestor")
            rol_color = {"admin": "#DC2626", "supervisor": "#7C3AED",
                         "asistente": "#0891B2"}.get(rol_text, TEXT_SECONDARY)
            ctk.CTkLabel(name_row, text=f"  [{rol_text}]",
                         font=_font(10, "bold"), text_color=rol_color
                         ).pack(side="left", padx=4)

            # Active status
            activo = u.get("activo", True)
            if not activo:
                ctk.CTkLabel(name_row, text="  INACTIVO",
                             font=_font(10, "bold"), text_color=DANGER
                             ).pack(side="left", padx=4)

            ctk.CTkLabel(info,
                         text=f"{u.get('email', '')}  |  {u.get('telefono', '')}  |  "
                              f"R:{u.get('region', '-')}  Z:{u.get('zona', '-')}",
                         font=_font(10), text_color=TEXT_SECONDARY
                         ).pack(anchor="w")

            uid = u.get("uid") or u.get("id", "")
            ctk.CTkButton(inner, text="Eliminar", font=_font(11),
                          fg_color=DANGER, hover_color="#B91C1C",
                          height=30, width=80, corner_radius=6,
                          command=lambda _uid=uid, _name=u.get("nombre", ""): self._delete_user(_uid, _name)
                          ).pack(side="right")
            ctk.CTkButton(inner, text="Editar", font=_font(11),
                          fg_color="#0891B2", hover_color="#0E7490",
                          height=30, width=80, corner_radius=6,
                          command=lambda _u=u: self._edit_user(_u)
                          ).pack(side="right", padx=(0, 6))

    def _new_user(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Nuevo Gestor")
        dialog.geometry("420x720")
        dialog.configure(fg_color=BG)
        dialog.transient(self)
        dialog.grab_set()

        frm = ctk.CTkFrame(dialog, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=BORDER)
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="Registrar Nuevo Gestor",
                     font=_font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=20, pady=(16, 12))

        fields = {}
        field_defs = [
            ("nombre", "Nombre completo"),
            ("email", "Correo electrónico"),
            ("password", "Contraseña inicial"),
            ("region", "Región (ej: 01, 02, 03)"),
            ("zona", "Zona (ej: 1211, 2112)"),
            ("seccion", "Sección (letra: A, B, C…)"),
            ("telefono", "Teléfono"),
        ]
        for key, label in field_defs:
            ctk.CTkLabel(frm, text=label, font=_font(11),
                         text_color=TEXT_SECONDARY).pack(padx=20, anchor="w")
            entry = ctk.CTkEntry(frm, font=_font(12), height=34,
                                 corner_radius=8, border_color=BORDER)
            if key == "password":
                entry.configure(show="*")
            entry.pack(fill="x", padx=20, pady=(2, 6))
            fields[key] = entry

        # Role selector
        ctk.CTkLabel(frm, text="Rol del usuario", font=_font(11),
                     text_color=TEXT_SECONDARY).pack(padx=20, anchor="w")
        role_var = ctk.StringVar(value="gestor")
        role_menu = ctk.CTkOptionMenu(
            frm, variable=role_var,
            values=["gestor", "asistente", "supervisor", "admin"],
            font=_font(12), height=34, corner_radius=8,
            fg_color="#F1F5F9", button_color=ACCENT,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_PRIMARY
        )
        role_menu.pack(fill="x", padx=20, pady=(2, 6))

        msg_lbl = ctk.CTkLabel(frm, text="", font=_font(11),
                                text_color=DANGER)
        msg_lbl.pack(padx=20, pady=(0, 4))

        def save():
            vals = {k: e.get().strip() for k, e in fields.items()}
            if not vals["nombre"] or not vals["email"] or not vals["password"] or not vals["seccion"]:
                msg_lbl.configure(text="Nombre, email, contraseña y sección son obligatorios")
                return

            btn_save.configure(state="disabled", text="Creando…")

            def do_create():
                result = self.firebase.create_gestor_user(
                    email=vals["email"],
                    password=vals["password"],
                    nombre=vals["nombre"],
                    seccion=vals["seccion"],
                    telefono=vals.get("telefono", ""),
                    zona=vals.get("zona", ""),
                    region=vals.get("region", ""),
                    rol=role_var.get(),
                )
                self.after(0, lambda: on_result(result))

            def on_result(result):
                btn_save.configure(state="normal", text="Registrar")
                if result["success"]:
                    self._status_lbl.configure(
                        text=f"[OK] Gestor {vals['nombre']} creado exitosamente",
                        text_color=SUCCESS)
                    dialog.destroy()
                    self._refresh_users()
                else:
                    msg_lbl.configure(text=f"Error: {result['error']}")

            threading.Thread(target=do_create, daemon=True).start()

        btn_save = ctk.CTkButton(frm, text="Registrar", font=_font(13, "bold"),
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                  height=40, corner_radius=10, command=save)
        btn_save.pack(fill="x", padx=20, pady=(4, 20))

    def _edit_user(self, user_data):
        """Open an edit dialog for an existing user."""
        uid = user_data.get("uid") or user_data.get("id", "")
        if not uid:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Editar Usuario — {user_data.get('nombre', '')}")
        dialog.geometry("420x720")
        dialog.configure(fg_color=BG)
        dialog.transient(self)
        dialog.grab_set()

        frm = ctk.CTkFrame(dialog, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=BORDER)
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="Editar Usuario",
                     font=_font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=20, pady=(16, 4))
        ctk.CTkLabel(frm, text=f"UID: {uid[:20]}...",
                     font=_font(9), text_color=TEXT_SECONDARY
                     ).pack(padx=20, pady=(0, 8))

        fields = {}
        field_defs = [
            ("nombre", "Nombre completo", user_data.get("nombre", "")),
            ("email", "Correo electronico (solo lectura)", user_data.get("email", "")),
            ("region", "Region (ej: 01, 02, 03)", user_data.get("region", "")),
            ("zona", "Zona (ej: 1211, 2112)", user_data.get("zona", "")),
            ("seccion", "Seccion (letra: A, B, C...)", user_data.get("seccion", "")),
            ("telefono", "Telefono", user_data.get("telefono", "")),
            ("password", "Nueva contrasena (dejar vacio para no cambiar)", ""),
        ]
        for key, label, default in field_defs:
            ctk.CTkLabel(frm, text=label, font=_font(11),
                         text_color=TEXT_SECONDARY).pack(padx=20, anchor="w")
            entry = ctk.CTkEntry(frm, font=_font(12), height=34,
                                 corner_radius=8, border_color=BORDER)
            if key == "password":
                entry.configure(show="*", placeholder_text="Sin cambios")
            elif key == "email":
                entry.configure(state="disabled")
            if default:
                entry.insert(0, default)
            entry.pack(fill="x", padx=20, pady=(2, 6))
            fields[key] = entry

        # Role selector
        ctk.CTkLabel(frm, text="Rol del usuario", font=_font(11),
                     text_color=TEXT_SECONDARY).pack(padx=20, anchor="w")
        role_var = ctk.StringVar(value=user_data.get("rol", "gestor"))
        role_menu = ctk.CTkOptionMenu(
            frm, variable=role_var,
            values=["gestor", "asistente", "supervisor", "admin"],
            font=_font(12), height=34, corner_radius=8,
            fg_color="#F1F5F9", button_color=ACCENT,
            button_hover_color=ACCENT_HOVER, text_color=TEXT_PRIMARY
        )
        role_menu.pack(fill="x", padx=20, pady=(2, 6))

        # Active toggle
        activo_var = ctk.BooleanVar(value=user_data.get("activo", True))
        activo_chk = ctk.CTkCheckBox(frm, text="Cuenta activa",
                                      variable=activo_var, font=_font(12),
                                      text_color=TEXT_PRIMARY,
                                      fg_color=ACCENT, hover_color=ACCENT_HOVER)
        activo_chk.pack(padx=20, pady=(4, 6), anchor="w")

        msg_lbl = ctk.CTkLabel(frm, text="", font=_font(11),
                                text_color=DANGER)
        msg_lbl.pack(padx=20, pady=(0, 4))

        def save():
            updates = {}
            nombre = fields["nombre"].get().strip()
            seccion = fields["seccion"].get().strip().upper()
            telefono = fields["telefono"].get().strip()
            zona = fields["zona"].get().strip()
            region = fields["region"].get().strip()
            password = fields["password"].get().strip()
            rol = role_var.get()
            activo = activo_var.get()

            if not nombre:
                msg_lbl.configure(text="El nombre es obligatorio")
                return

            if nombre != user_data.get("nombre", ""):
                updates["nombre"] = nombre
            if seccion != user_data.get("seccion", ""):
                updates["seccion"] = seccion
            if telefono != user_data.get("telefono", ""):
                updates["telefono"] = telefono
            if zona != user_data.get("zona", ""):
                updates["zona"] = zona
            if region != user_data.get("region", ""):
                updates["region"] = region
            if rol != user_data.get("rol", "gestor"):
                updates["rol"] = rol
            if activo != user_data.get("activo", True):
                updates["activo"] = activo
            if password:
                updates["password"] = password

            if not updates:
                msg_lbl.configure(text="No hay cambios para guardar")
                return

            btn_update.configure(state="disabled", text="Guardando...")

            def do_update():
                result = self.firebase.update_user(uid, updates)
                self.after(0, lambda: on_result(result))

            def on_result(result):
                btn_update.configure(state="normal", text="Guardar Cambios")
                if result["success"]:
                    self._status_lbl.configure(
                        text=f"[OK] {nombre} actualizado exitosamente",
                        text_color=SUCCESS)
                    dialog.destroy()
                    self._refresh_users()
                else:
                    msg_lbl.configure(text=f"Error: {result['error']}")

            threading.Thread(target=do_update, daemon=True).start()

        btn_update = ctk.CTkButton(frm, text="Guardar Cambios", font=_font(13, "bold"),
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    height=40, corner_radius=10, command=save)
        btn_update.pack(fill="x", padx=20, pady=(4, 20))

    def _delete_user(self, uid, name):
        if not messagebox.askyesno("Confirmar",
                                    f"¿Eliminar al gestor {name}?\n"
                                    "Se eliminará su cuenta de acceso."):
            return

        def do_del():
            ok = self.firebase.delete_gestor_user(uid)
            self.after(0, lambda: self._del_done(ok, name))

        threading.Thread(target=do_del, daemon=True).start()

    def _del_done(self, ok, name):
        if ok:
            self._status_lbl.configure(text=f"[OK] {name} eliminado",
                                        text_color=SUCCESS)
        else:
            self._status_lbl.configure(text=f"Error al eliminar {name}",
                                        text_color=DANGER)
        self._refresh_users()


# ═══════════════════════════════════════════════════════════════════
# LOGIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class LoginWindow(ctk.CTk):
    """Login screen — authenticates users before opening the main app."""

    def __init__(self):
        super().__init__()
        self.title("AntCobranzas — Iniciar Sesion")
        self.geometry("440x540")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.auth_service = AuthService()
        self.firebase = FirebaseService()  # For Firestore profile lookup
        self._init_firebase()
        self._build()

        # Center the window
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def _init_firebase(self):
        """Initialize Firebase Admin SDK for profile lookups."""
        from config import SERVICE_ACCOUNT_KEY_PATH
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_path = os.path.join(app_dir, SERVICE_ACCOUNT_KEY_PATH)
        if os.path.exists(key_path):
            try:
                self.firebase.initialize(key_path)
            except Exception:
                pass  # Will work without it (limited profile info)

    def _build(self):
        # Header bar
        hdr = ctk.CTkFrame(self, fg_color=ACCENT, height=80, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="AntCobranzas",
                     font=_font(22, "bold"), text_color=WHITE
                     ).pack(pady=(16, 2))
        ctk.CTkLabel(hdr, text="Sistema de Gestion de Cobranzas",
                     font=_font(11), text_color="#C7D2FE"
                     ).pack()

        # Card
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=16,
                             border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(card, text="Iniciar Sesion",
                     font=_font(18, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=24, pady=(28, 4))
        ctk.CTkLabel(card, text="Ingrese sus credenciales para continuar",
                     font=_font(11), text_color=TEXT_SECONDARY
                     ).pack(padx=24, pady=(0, 16))

        # Email field
        ctk.CTkLabel(card, text="Correo electronico", font=_font(11),
                     text_color=TEXT_SECONDARY).pack(padx=24, anchor="w")
        self._email = ctk.CTkEntry(card, font=_font(13), height=40,
                                    corner_radius=10, border_color=BORDER,
                                    placeholder_text="usuario@ejemplo.com")
        self._email.pack(fill="x", padx=24, pady=(2, 10))

        # Password field
        ctk.CTkLabel(card, text="Contrasena", font=_font(11),
                     text_color=TEXT_SECONDARY).pack(padx=24, anchor="w")
        self._password = ctk.CTkEntry(card, font=_font(13), height=40,
                                       corner_radius=10, border_color=BORDER,
                                       show="*", placeholder_text="********")
        self._password.pack(fill="x", padx=24, pady=(2, 16))

        # Error label
        self._error_lbl = ctk.CTkLabel(card, text="", font=_font(11),
                                        text_color=DANGER, wraplength=340)
        self._error_lbl.pack(padx=24, pady=(0, 4))

        # Login button
        self._btn_login = ctk.CTkButton(
            card, text="Ingresar", font=_font(14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=44, corner_radius=10, command=self._on_login)
        self._btn_login.pack(fill="x", padx=24, pady=(0, 20))

        # Bind Enter key
        self._password.bind("<Return>", lambda e: self._on_login())
        self._email.bind("<Return>", lambda e: self._password.focus())

        # Focus email field
        self.after(100, self._email.focus)

    def _on_login(self):
        email = self._email.get().strip()
        password = self._password.get().strip()

        if not email or not password:
            self._error_lbl.configure(text="Ingrese correo y contrasena")
            return

        self._btn_login.configure(state="disabled", text="Verificando...")
        self._error_lbl.configure(text="")

        def do_login():
            result = self.auth_service.sign_in(email, password, self.firebase)
            self.after(0, lambda: self._on_login_result(result))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_result(self, result):
        self._btn_login.configure(state="normal", text="Ingresar")

        if not result.success:
            self._error_lbl.configure(text=result.error)
            return

        # Login successful — close login window and open main app
        self.destroy()
        app = App(auth_result=result)
        app.mainloop()


def _show_login():
    """Show the login window."""
    login = LoginWindow()
    login.mainloop()


def run_app():
    _show_login()
