"""Settings page — campaign configuration, tramo timing & letter scheduling."""
from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import threading
from typing import TYPE_CHECKING

from ..theme import *
from ..components import SectionHeader, ActionButton

if TYPE_CHECKING:
    from ..app import App

from services.database import db_service, ConfigCampana, PlantillaCarta
from services.tramo_engine import load_config
from services.template_engine import TAGS, CARTA_NOMBRES


class _DateTimePickerDialog(tk.Toplevel):
    """Simple date/time picker dialog with spinboxes."""

    MONTHS = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    def __init__(self, parent, initial: datetime | None = None):
        super().__init__(parent)
        self.title("Seleccionar fecha y hora")
        self.resizable(False, False)
        self.grab_set()
        self.result: datetime | None = None

        now = initial or datetime.now()

        # ── Center over parent ──
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - 180}+{py - 120}")

        frm = tk.Frame(self, padx=16, pady=12)
        frm.pack()

        # Date row
        tk.Label(frm, text="Fecha:", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        date_frm = tk.Frame(frm)
        date_frm.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self._day = ttk.Spinbox(date_frm, from_=1, to=31, width=4, font=("", 11))
        self._day.set(now.day)
        self._day.pack(side="left")

        tk.Label(date_frm, text="/").pack(side="left", padx=2)

        self._month = ttk.Combobox(
            date_frm, values=self.MONTHS, width=10, font=("", 11), state="readonly"
        )
        self._month.current(now.month - 1)
        self._month.pack(side="left")

        tk.Label(date_frm, text="/").pack(side="left", padx=2)

        self._year = ttk.Spinbox(date_frm, from_=2020, to=2099, width=6, font=("", 11))
        self._year.set(now.year)
        self._year.pack(side="left")

        # Time row
        tk.Label(frm, text="Hora:", font=("", 11, "bold")).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        time_frm = tk.Frame(frm)
        time_frm.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        self._hour = ttk.Spinbox(time_frm, from_=0, to=23, width=4, font=("", 11), format="%02.0f")
        self._hour.set(f"{now.hour:02d}")
        self._hour.pack(side="left")

        tk.Label(time_frm, text=":").pack(side="left", padx=2)

        self._minute = ttk.Spinbox(time_frm, from_=0, to=59, width=4, font=("", 11), format="%02.0f")
        self._minute.set(f"{now.minute:02d}")
        self._minute.pack(side="left")

        # Buttons
        btn_frm = tk.Frame(frm)
        btn_frm.grid(row=2, column=0, columnspan=2, pady=(12, 0))

        tk.Button(btn_frm, text="Confirmar", width=12, bg="#2563eb", fg="white",
                  font=("", 11, "bold"), command=self._confirm).pack(side="left", padx=4)
        tk.Button(btn_frm, text="Sin programar", width=12,
                  font=("", 11), command=self._clear).pack(side="left", padx=4)
        tk.Button(btn_frm, text="Cancelar", width=10,
                  font=("", 11), command=self.destroy).pack(side="left", padx=4)

    def _confirm(self):
        try:
            day = int(self._day.get())
            month = self.MONTHS.index(self._month.get()) + 1
            year = int(self._year.get())
            hour = int(self._hour.get())
            minute = int(self._minute.get())
            self.result = datetime(year, month, day, hour, minute)
        except (ValueError, IndexError) as exc:
            messagebox.showerror("Error", f"Fecha/hora inválida:\n{exc}", parent=self)
            return
        self.destroy()

    def _clear(self):
        self.result = None
        self.destroy()


def _try_parse(text: str, fmt: str) -> bool:
    try:
        datetime.strptime(text, fmt)
        return True
    except ValueError:
        return False


class SettingsPage:
    """Admin-only page to configure campaign parameters."""

    def __init__(self, app: "App"):
        self.app = app
        self._vars: dict[str, tk.Variable] = {}

    # ── Public interface ─────────────────────────────────────

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()

        SectionHeader(
            container,
            "Configuración",
            "Parámetros de empresa, tramos, programación de cartas y plantillas",
        ).pack(padx=8, pady=(8, 12), anchor="w")

        # Load current config from DB
        cfg = self._load_cfg()

        # ── 0. Empresa / Gestor ──────────────────────────────
        self._card_gestor_empresa(container, cfg)

        # ── 1. Duración ─────────────────────────────────────
        self._card_duracion(container, cfg)

        # ── 2. Tramos ───────────────────────────────────────
        self._card_tramos(container, cfg)

        # ── 3. Cartas ───────────────────────────────────────
        self._card_cartas(container, cfg)

        # ── 4. Umbrales ─────────────────────────────────────
        self._card_umbrales(container, cfg)

        # ── 4b. Comisión del responsable ────────────────────
        self._card_comision_jefe(container, cfg)

        # ── 5. Automatización ───────────────────────────────
        self._card_automatizacion(container, cfg)

        # ── 6. Plantillas de Cartas ──────────────────────────
        self._card_plantillas(container)

        # ── 7. Zona de peligro (borrados y reinicio de pruebas) ──
        self._card_zona_peligro(container)

        # ── Save button ─────────────────────────────────────
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(4, 20))

        ActionButton(
            btn_frame,
            text="Guardar configuración",
            color=SUCCESS,
            width=220,
            command=self._on_save,
        ).pack(side="left")

        self._status_label = ctk.CTkLabel(
            btn_frame, text="", font=font(12), text_color=TEXT_SECONDARY
        )
        self._status_label.pack(side="left", padx=16)

    def stop(self):
        pass

    # ── Cards ────────────────────────────────────────────────

    def _make_card(self, parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill="x", padx=8, pady=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(
            inner, text=title, font=font(15, "bold"), text_color=TEXT_PRIMARY
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                inner, text=subtitle, font=font(11), text_color=TEXT_SECONDARY
            ).pack(anchor="w", pady=(2, 8))
        return inner

    def _int_entry(self, parent, label: str, key: str, value: int, width: int = 70):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=font(12), text_color=TEXT_PRIMARY, width=200, anchor="w").pack(side="left")
        var = tk.IntVar(value=value)
        self._vars[key] = var
        ctk.CTkEntry(row, textvariable=var, width=width, font=font(12)).pack(side="left", padx=(4, 0))

    def _float_entry(self, parent, label: str, key: str, value: float, width: int = 90):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=font(12), text_color=TEXT_PRIMARY, width=200, anchor="w").pack(side="left")
        var = tk.DoubleVar(value=value)
        self._vars[key] = var
        ctk.CTkEntry(row, textvariable=var, width=width, font=font(12)).pack(side="left", padx=(4, 0))

    def _datetime_entry(self, parent, label: str, key: str, value: datetime | None, width: int = 170):
        """Date/time entry as a string field (YYYY-MM-DD HH:MM)."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, font=font(12), text_color=TEXT_PRIMARY, width=200, anchor="w").pack(side="left")
        text = value.strftime("%Y-%m-%d %H:%M") if value else ""
        var = tk.StringVar(value=text)
        self._vars[key] = var
        ctk.CTkEntry(row, textvariable=var, width=width, font=font(12),
                      placeholder_text="YYYY-MM-DD HH:MM").pack(side="left", padx=(4, 0))

    # ── Section builders ─────────────────────────────────────

    def _card_gestor_empresa(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "🏢  Empresa y Gestor de Cobranza",
            "Datos fijos que aparecerán en el encabezado y firma de todas las cartas. "
            "Estos datos son estáticos (no cambian por cliente).",
        )

        fields = [
            ("Nombre de la empresa:",    "nombre_empresa",    cfg.nombre_empresa or "",    350),
            ("RUC:",                      "ruc_empresa",       cfg.ruc_empresa or "",       150),
            ("Dirección de la empresa:",  "direccion_empresa", cfg.direccion_empresa or "", 400),
            ("Nombre del gestor:",        "nombre_gestor",     cfg.nombre_gestor or "",     300),
            ("Cargo del gestor:",         "cargo_gestor",      cfg.cargo_gestor or "",      250),
            ("Teléfono del gestor:",      "telefono_gestor",   cfg.telefono_gestor or "",   180),
            ("Correo del gestor:",        "correo_gestor",     cfg.correo_gestor or "",     280),
        ]

        for label_text, key, value, width in fields:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row, text=label_text, font=font(12), text_color=TEXT_PRIMARY,
                width=200, anchor="w"
            ).pack(side="left")
            var = tk.StringVar(value=value)
            self._vars[key] = var
            ctk.CTkEntry(
                row, textvariable=var, width=width, font=font(12),
                placeholder_text=label_text.rstrip(":")
            ).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(
            inner,
            text="⚠️  Los campos en blanco no aparecerán en las cartas generadas.",
            font=font(11), text_color=WARNING,
        ).pack(anchor="w", pady=(8, 0))

    def _card_duracion(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Duración de Campaña",
            "Ciclo por cuenta: 59 días de gestión desde fecha de asignación del Excel.",
        )
        self._int_entry(inner, "Duración gestión (días):", "duracion_dias", cfg.duracion_dias)
        self._int_entry(inner, "Cierre automático (día):", "dias_cierre",
                        getattr(cfg, "dias_cierre", 60) or 60)
        self._int_entry(inner, "Retorno al banco (día):", "dias_retorno_banco",
                        getattr(cfg, "dias_retorno_banco", 70) or 70)
        self._int_entry(inner, "Ventana ingreso Excel (días):", "ventana_ingreso_dias",
                        getattr(cfg, "ventana_ingreso_dias", 21) or 21)

    def _card_tramos(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Tramos de Cobranza",
            "Rangos de días para cada fase. Los tramos deben ser consecutivos y cubrir toda la duración.",
        )
        for i, (label, k_ini, k_fin, v_ini, v_fin) in enumerate([
            ("Etapa 1 — Recuperación inicial (10 d)", "tramo1_inicio", "tramo1_fin", cfg.tramo1_inicio, cfg.tramo1_fin),
            ("Etapa 2 — Seguimiento medio (33 d)", "tramo2_inicio", "tramo2_fin", cfg.tramo2_inicio, cfg.tramo2_fin),
            ("Etapa 3 — Cierre de gestión (16 d)", "tramo3_inicio", "tramo3_fin", cfg.tramo3_inicio, cfg.tramo3_fin),
        ]):
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=font(12, "bold"), text_color=TEXT_PRIMARY, width=230, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text="Día", font=font(11), text_color=TEXT_SECONDARY).pack(side="left", padx=(4, 2))
            var_ini = tk.IntVar(value=v_ini)
            self._vars[k_ini] = var_ini
            ctk.CTkEntry(row, textvariable=var_ini, width=55, font=font(12)).pack(side="left")
            ctk.CTkLabel(row, text="a", font=font(11), text_color=TEXT_SECONDARY).pack(side="left", padx=4)
            var_fin = tk.IntVar(value=v_fin)
            self._vars[k_fin] = var_fin
            ctk.CTkEntry(row, textvariable=var_fin, width=55, font=font(12)).pack(side="left")

    def _card_cartas(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Programación de Cartas (5 Etapas)",
            "Día de campaña en que corresponde cada carta, fecha/hora de generación y modo de envío.",
        )
        cartas = [
            ("E1-1 — Invitación a Reingreso",       "carta1_dia", cfg.carta1_dia, "carta1_programada", cfg.carta1_programada, "auto_envio_carta1", cfg.auto_envio_carta1, "formato_carta1", cfg.formato_carta1),
            ("E1-2 — No Pierdas Ser Empresaria",    "carta2_dia", cfg.carta2_dia, "carta2_programada", cfg.carta2_programada, "auto_envio_carta2", cfg.auto_envio_carta2, "formato_carta2", cfg.formato_carta2),
            ("E2-1 — Requerimiento de Pago",        "carta3_dia", cfg.carta3_dia, "carta3_programada", cfg.carta3_programada, "auto_envio_carta3", cfg.auto_envio_carta3, "formato_carta3", cfg.formato_carta3),
            ("E2-2 — Insistimos en el Pago",        "carta4_dia", cfg.carta4_dia, "carta4_programada", cfg.carta4_programada, "auto_envio_carta4", cfg.auto_envio_carta4, "formato_carta4", cfg.formato_carta4),
            ("E3-1 — Exigimos Pago / Pre Judicial", "carta5_dia", cfg.carta5_dia, "carta5_programada", cfg.carta5_programada, "auto_envio_carta5", cfg.auto_envio_carta5, "formato_carta5", cfg.formato_carta5),
        ]
        for label, k_dia, v_dia, k_prog, v_prog, k_auto, v_auto, k_fmt, v_fmt in cartas:
            # ── Row 1: label + day + date picker ──────────────
            grp = ctk.CTkFrame(inner, fg_color="transparent")
            grp.pack(fill="x", pady=(6, 0))
            ctk.CTkLabel(grp, text=label, font=font(12, "bold"), text_color=TEXT_PRIMARY, width=200, anchor="w").pack(side="left")

            ctk.CTkLabel(grp, text="Día:", font=font(11), text_color=TEXT_SECONDARY).pack(side="left", padx=(4, 2))
            var_dia = tk.IntVar(value=v_dia)
            self._vars[k_dia] = var_dia
            ctk.CTkEntry(grp, textvariable=var_dia, width=55, font=font(12)).pack(side="left")

            ctk.CTkLabel(grp, text="Programar:", font=font(11), text_color=TEXT_SECONDARY).pack(side="left", padx=(12, 4))

            # StringVar stores the selected datetime as text
            dt_text = v_prog.strftime("%d/%m/%Y %H:%M") if v_prog else ""
            var_prog = tk.StringVar(value=dt_text)
            self._vars[k_prog] = var_prog

            lbl_val = ctk.CTkLabel(
                grp,
                textvariable=var_prog,
                font=font(11),
                text_color=TEXT_PRIMARY,
                width=130,
                anchor="w",
            )
            lbl_val.pack(side="left")

            def _open_picker_btn(kp=k_prog):
                current_text = self._vars[kp].get().strip()
                initial = None
                if current_text:
                    try:
                        initial = datetime.strptime(current_text, "%d/%m/%Y %H:%M")
                    except ValueError:
                        pass
                dlg = _DateTimePickerDialog(self.app, initial)
                self.app.wait_window(dlg)
                if hasattr(dlg, "result"):
                    if dlg.result is not None:
                        self._vars[kp].set(dlg.result.strftime("%d/%m/%Y %H:%M"))
                    else:
                        self._vars[kp].set("")

            ctk.CTkButton(
                grp,
                text="📅 Seleccionar",
                width=120,
                height=26,
                font=font(11),
                command=_open_picker_btn,
            ).pack(side="left", padx=(4, 0))

            # ── Row 2: auto-send toggle + format ──────────────
            auto_row = ctk.CTkFrame(inner, fg_color="transparent")
            auto_row.pack(fill="x", padx=(208, 0), pady=(2, 4))

            var_auto = tk.BooleanVar(value=bool(v_auto))
            self._vars[k_auto] = var_auto
            ctk.CTkCheckBox(
                auto_row,
                text="Envío automático a gestores",
                variable=var_auto,
                font=font(11),
                text_color=TEXT_SECONDARY,
                fg_color=SUCCESS,
                hover_color=SUCCESS_HOVER,
                checkmark_color=WHITE,
            ).pack(side="left")

            # Formato fijado a Word (.docx) — PDF/JPG temporalmente deshabilitados
            self._vars[k_fmt] = tk.StringVar(value="Word")

            # Thin separator between letters
            ctk.CTkFrame(inner, fg_color=BORDER, height=1).pack(fill="x", pady=(2, 0))

    def _card_umbrales(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Umbrales de Saldo",
            "Montos mínimos que determinan si un cliente sigue en cobranza y si recibe carta física.",
        )
        self._float_entry(inner, "Mínimo para gestión (S/):", "umbral_minimo_gestion", cfg.umbral_minimo_gestion)
        self._float_entry(inner, "Mínimo carta física (S/):", "umbral_carta_fisica", cfg.umbral_carta_fisica)

    def _card_comision_jefe(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Comisión del responsable",
            "Porcentaje sobre la recuperación según datos del banco (Excel). "
            "Se muestra como ganancia estimada en estadísticas del APK y escritorio.",
        )
        self._float_entry(
            inner,
            "Porcentaje de comisión (%):",
            "porcentaje_comision_jefe",
            getattr(cfg, "porcentaje_comision_jefe", 15.0) or 15.0,
        )

    def _card_automatizacion(self, parent, cfg: ConfigCampana):
        inner = self._make_card(
            parent,
            "Automatización",
            "Opciones para evaluar tramos y generar cartas de forma automática.",
        )
        var = tk.BooleanVar(value=cfg.auto_evaluar_tramos)
        self._vars["auto_evaluar_tramos"] = var
        ctk.CTkCheckBox(
            inner,
            text="Evaluar tramos automáticamente al abrir la aplicación",
            variable=var,
            font=font(12),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=2)

    # ── Plantillas de Cartas ───────────────────────────────

    def _card_plantillas(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill="x", padx=8, pady=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(inner, text="📄  Plantillas de Cartas",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Edita el contenido de cada carta. Usa {{ETIQUETA}} para datos variables. "
                 "Primera línea = título. **negrita** *cursiva* [ROJO]rojo[/ROJO] "
                 "[CENTRO]centrado[/CENTRO] [FIRMA]firma[/FIRMA] [NOTA]pie[/NOTA]  \u2022 viñeta",
            font=font(11), text_color=TEXT_SECONDARY, wraplength=720, justify="left",
        ).pack(anchor="w", pady=(2, 10))

        # ─ Tab selector ─────────────────────────────────────────
        tab_row = ctk.CTkFrame(inner, fg_color="transparent")
        tab_row.pack(fill="x", pady=(0, 8))

        self._plantilla_tab = tk.IntVar(value=1)
        self._tab_buttons: dict[int, ctk.CTkButton] = {}
        short_labels = {1: "E1-1", 2: "E1-2", 3: "E2-1", 4: "E2-2", 5: "E3-1"}

        # Content area (recreated on tab switch)
        self._plantilla_content_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self._plantilla_content_frame.pack(fill="x")

        def _switch_tab(n: int):
            self._plantilla_tab.set(n)
            for k, btn in self._tab_buttons.items():
                btn.configure(
                    fg_color=ACCENT if k == n else "#E2E8F0",
                    text_color=WHITE if k == n else TEXT_PRIMARY,
                )
            self._render_plantilla_tab(n)

        for n in range(1, 6):
            btn = ctk.CTkButton(
                tab_row, text=short_labels[n], font=font(11, "bold"),
                fg_color=ACCENT if n == 1 else "#E2E8F0",
                text_color=WHITE if n == 1 else TEXT_PRIMARY,
                hover_color=ACCENT_HOVER,
                height=30, width=80, corner_radius=8,
                command=lambda k=n: _switch_tab(k),
            )
            btn.pack(side="left", padx=3)
            self._tab_buttons[n] = btn

        # Load first tab
        self._render_plantilla_tab(1)

    def _render_plantilla_tab(self, numero_carta: int):
        """Render the editor for a single carta template."""
        frame = self._plantilla_content_frame
        for w in frame.winfo_children():
            w.destroy()

        # Load template from DB
        with db_service.session() as session:
            plantilla = PlantillaCarta.get_or_create(session, numero_carta)
            contenido = plantilla.contenido or ""
            nombre = plantilla.nombre or CARTA_NOMBRES.get(numero_carta, f"Carta {numero_carta}")

        # Two-column layout: editor (left) + tags ref (right)
        cols = ctk.CTkFrame(frame, fg_color="transparent")
        cols.pack(fill="x")
        cols.grid_columnconfigure(0, weight=3)
        cols.grid_columnconfigure(1, weight=1)

        # Left: text editor
        left = ctk.CTkFrame(cols, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(left, text=nombre, font=font(12, "bold"),
                     text_color=ACCENT).pack(anchor="w", pady=(0, 4))

        self._plantilla_textbox = ctk.CTkTextbox(
            left, height=320, font=("Consolas", 11),
            wrap="word", fg_color=WHITE, text_color=TEXT_PRIMARY,
            border_width=1, border_color=BORDER,
        )
        self._plantilla_textbox.pack(fill="x")
        self._plantilla_textbox.insert("1.0", contenido)

        # Buttons row
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", pady=(6, 0))

        self._plantilla_status = ctk.CTkLabel(
            btn_row, text="", font=font(11), text_color=TEXT_SECONDARY)
        self._plantilla_status.pack(side="right", padx=8)

        ctk.CTkButton(
            btn_row, text="Restaurar por defecto", font=font(11),
            fg_color="#E2E8F0", text_color=TEXT_PRIMARY,
            hover_color=BORDER, height=30, corner_radius=8,
            command=lambda n=numero_carta: self._restore_default(n),
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            btn_row, text="💾  Guardar plantilla", font=font(11, "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            height=30, corner_radius=8,
            command=lambda n=numero_carta: self._save_plantilla(n),
        ).pack(side="left")

        # Right: tag reference
        right = ctk.CTkFrame(cols, fg_color="#F8FAFC",
                              corner_radius=8, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        rfr = ctk.CTkFrame(right, fg_color="transparent")
        rfr.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(rfr, text="Etiquetas disponibles",
                     font=font(11, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w", pady=(0, 6))
        for tag, desc in TAGS.items():
            tag_frm = ctk.CTkFrame(rfr, fg_color="transparent")
            tag_frm.pack(fill="x", pady=1)
            ctk.CTkLabel(
                tag_frm, text=f"{{{{{tag}}}}}",
                font=("Consolas", 9), text_color=ACCENT,
                anchor="w", width=160,
            ).pack(side="left")

        ctk.CTkLabel(rfr, text="Formato:",
                     font=font(10, "bold"), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(8, 2))
        fmt_lines = [
            ("**texto**",              "negrita"),
            ("*texto*",                "cursiva"),
            ("[ROJO]t[/ROJO]",         "rojo"),
            ("[CENTRO]t[/CENTRO]",     "centrado"),
            ("[FIRMA]t[/FIRMA]",       "firma"),
            ("[NOTA]t[/NOTA]",         "pie peq"),
            ("\u2022 texto",           "viñeta"),
        ]
        for code, label in fmt_lines:
            fr = ctk.CTkFrame(rfr, fg_color="transparent")
            fr.pack(fill="x", pady=1)
            ctk.CTkLabel(fr, text=code, font=("Consolas", 9),
                         text_color=INFO, anchor="w", width=130).pack(side="left")
            ctk.CTkLabel(fr, text=label, font=font(9),
                         text_color=TEXT_SECONDARY, anchor="w").pack(side="left", padx=(4, 0))

    def _card_zona_peligro(self, parent):
        """Zona de peligro unificada: reinicio de pruebas y limpieza de datos."""
        card = ctk.CTkFrame(
            parent, fg_color="#1C1012", corner_radius=12,
            border_width=1, border_color="#7F1D1D",
        )
        card.pack(fill="x", padx=8, pady=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(
            inner, text="⚠  Zona de peligro",
            font=font(15, "bold"), text_color="#EF4444",
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Acciones destructivas e irreversibles. Úselas solo cuando sea necesario.",
            font=font(11), text_color="#FCA5A5",
        ).pack(anchor="w", pady=(2, 14))

        # ── Reiniciar entorno de pruebas ──
        reset_frame = ctk.CTkFrame(inner, fg_color="#2A1518", corner_radius=8,
                                   border_width=1, border_color="#991B1B")
        reset_frame.pack(fill="x", pady=(0, 12))
        reset_inner = ctk.CTkFrame(reset_frame, fg_color="transparent")
        reset_inner.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(
            reset_inner, text="🧪 Reiniciar entorno de pruebas",
            font=font(13, "bold"), text_color=WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            reset_inner,
            text=(
                "Elimina la campaña activa en SQLite y en Firebase (cartera_activa). "
                "Útil para volver a cargar Excel y probar reparto, wizard y APK sin datos viejos. "
                "No borra usuarios del equipo."
            ),
            font=font(11), text_color="#FCA5A5",
            wraplength=720, justify="left",
        ).pack(anchor="w", pady=(4, 10))
        ctk.CTkButton(
            reset_inner,
            text="Eliminar campaña y datos de prueba",
            font=font(12, "bold"),
            fg_color=DANGER, hover_color=DANGER_HOVER,
            height=36, width=300,
            corner_radius=8,
            command=self.app._on_delete_campaign,
        ).pack(anchor="w")

        ctk.CTkFrame(inner, fg_color="#7F1D1D", height=1).pack(fill="x", pady=(0, 12))

        # ── Limpieza de datos ──
        ctk.CTkLabel(
            inner, text="Limpieza de datos",
            font=font(13, "bold"), text_color=WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Herramientas avanzadas para limpiar información antigua o eliminar "
                 "todo el contenido de Firebase y la base local.",
            font=font(11), text_color="#FCA5A5",
            wraplength=720, justify="left",
        ).pack(anchor="w", pady=(2, 10))

        row_days = ctk.CTkFrame(inner, fg_color="transparent")
        row_days.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(
            row_days,
            text="Antigüedad para limpieza inteligente (días):",
            font=font(12),
            text_color="#FECACA",
            width=270,
            anchor="w",
        ).pack(side="left")
        self._cleanup_days = tk.IntVar(value=90)
        ctk.CTkEntry(row_days, textvariable=self._cleanup_days, width=80, font=font(12)).pack(side="left")

        ctk.CTkButton(
            inner,
            text="Limpiar datos antiguos",
            font=font(12, "bold"),
            fg_color="#B45309",
            hover_color="#92400E",
            height=34,
            corner_radius=8,
            command=self._on_cleanup_old_data,
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            inner,
            text="Elimina campañas no activas antiguas en local y en Firebase (mantiene cartera_activa).",
            font=font(10),
            text_color="#FCA5A5",
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(
            inner,
            text="Eliminar todo (Firebase + base local)",
            font=font(12, "bold"),
            fg_color=DANGER,
            hover_color=DANGER_HOVER,
            height=36,
            corner_radius=8,
            command=self._on_delete_all_data,
        ).pack(anchor="w")

        ctk.CTkButton(
            inner,
            text="Eliminar solo base local",
            font=font(12, "bold"),
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            height=36,
            corner_radius=8,
            command=self._on_delete_local_data,
        ).pack(anchor="w", pady=(8, 0))

    def _on_cleanup_old_data(self):
        dias = self._get_int_var("_cleanup_days", default=90)
        if dias < 1:
            messagebox.showwarning("Validación", "Los días deben ser mayores a 0.")
            return

        if not messagebox.askyesno(
            "Limpieza Inteligente",
            f"Se limpiarán datos antiguos (>{dias} días):\n\n"
            f"• Firebase: campañas antiguas, excepto cartera_activa\n"
            f"• Local: campañas no activas y logs antiguos\n\n"
            f"¿Desea continuar?",
            icon="warning",
        ):
            return

        self.app.set_status("Ejecutando limpieza inteligente…", 0.3)

        def work():
            try:
                fb_res = None
                if self.app.firebase_connected:
                    fb_res = self.app.firebase.cleanup_old_data(days_to_keep=dias)
                local_res = self.app.campaign_mgr.cleanup_old_local_data(days_to_keep=dias)
                self.app.after(0, lambda: self._cleanup_old_done(dias, local_res, fb_res))
            except Exception as exc:
                self.app.after(0, lambda: messagebox.showerror("Error", f"No se pudo limpiar datos antiguos:\n{exc}"))
                self.app.after(0, lambda: self.app.set_status("Error en limpieza inteligente", 0))

        threading.Thread(target=work, daemon=True).start()

    def _cleanup_old_done(self, dias: int, local_res: dict, fb_res: dict | None):
        self.app._invalidate_pages()
        self.app._update_campaign_bar()
        self.app.set_status("Limpieza inteligente completada", 1)

        fb_msg = "Firebase no conectado"
        if fb_res is not None:
            fb_msg = (
                f"Firebase: {len(fb_res.get('deleted_campaigns', []))} campaña(s) eliminada(s), "
                f"{len(fb_res.get('kept_campaigns', []))} conservada(s)"
            )

        messagebox.showinfo(
            "Limpieza completada",
            f"Limpieza de datos antiguos (> {dias} días) finalizada.\n\n"
            f"Local: {local_res.get('deleted_campaigns', 0)} campaña(s), "
            f"{local_res.get('deleted_sync_logs', 0)} log(s)\n"
            f"{fb_msg}",
        )

    def _on_delete_all_data(self):
        ok = messagebox.askyesno(
            "Eliminar TODO",
            "Se eliminarán TODOS los datos actuales:\n\n"
            "• Firebase: cartera_activa\n"
            "• Base local: campañas, clientes, historial y logs\n\n"
            "Esta acción NO se puede deshacer.\n\n¿Continuar?",
            icon="warning",
        )
        if not ok:
            return

        dialog = ctk.CTkInputDialog(
            text="Escriba ELIMINAR TODO para confirmar:",
            title="Confirmación final",
        )
        typed = (dialog.get_input() or "").strip().upper()
        if typed != "ELIMINAR TODO":
            messagebox.showinfo("Cancelado", "Operación cancelada: confirmación no válida.")
            return

        self.app.set_status("Eliminando todos los datos…", 0.2)

        def work():
            try:
                fb = self.app.firebase if self.app.firebase_connected else None
                result = self.app.campaign_mgr.delete_all_campaign_data(firebase_service=fb)
                self.app.after(0, lambda: self._delete_all_done(result))
            except Exception as exc:
                self.app.after(0, lambda: messagebox.showerror("Error", f"No se pudo eliminar todo:\n{exc}"))
                self.app.after(0, lambda: self.app.set_status("Error eliminando datos", 0))

        threading.Thread(target=work, daemon=True).start()

    def _delete_all_done(self, result: dict):
        self.app.active_campaign = None
        self.app.parsed_data = None
        self.app._invalidate_pages()
        self.app._update_campaign_bar()
        self.app.set_status("Eliminación total completada", 1)

        fb = result.get("firebase") or {}
        if fb.get("error"):
            fb_text = f"Firebase: error ({fb.get('error')})"
        elif fb.get("campaign_deleted"):
            fb_text = f"Firebase: {fb.get('deleted_clients', 0)} clientes eliminados"
        else:
            fb_text = "Firebase: sin cambios"

        messagebox.showinfo(
            "Eliminación total",
            f"Proceso finalizado.\n\n"
            f"Local: {result.get('local_campaigns_deleted', 0)} campaña(s), "
            f"{result.get('local_clients_deleted', 0)} cliente(s), "
            f"{result.get('local_sync_logs_deleted', 0)} log(s)\n"
            f"{fb_text}",
        )

    def _on_delete_local_data(self):
        ok = messagebox.askyesno(
            "Eliminar base local",
            "Se eliminarán TODOS los datos de la base local:\n\n"
            "• Campañas, clientes, historial y logs locales\n"
            "• No se tocará Firebase\n\n"
            "Esta acción NO se puede deshacer.\n\n¿Continuar?",
            icon="warning",
        )
        if not ok:
            return

        dialog = ctk.CTkInputDialog(
            text="Escriba ELIMINAR LOCAL para confirmar:",
            title="Confirmación final",
        )
        typed = (dialog.get_input() or "").strip().upper()
        if typed != "ELIMINAR LOCAL":
            messagebox.showinfo("Cancelado", "Operación cancelada: confirmación no válida.")
            return

        self.app.set_status("Eliminando base local…", 0.2)

        def work():
            try:
                result = self.app.campaign_mgr.delete_all_local_data()
                self.app.after(0, lambda: self._delete_local_done(result))
            except Exception as exc:
                self.app.after(0, lambda: messagebox.showerror("Error", f"No se pudo eliminar la base local:\n{exc}"))
                self.app.after(0, lambda: self.app.set_status("Error eliminando base local", 0))

        threading.Thread(target=work, daemon=True).start()

    def _delete_local_done(self, result: dict):
        self.app.active_campaign = None
        self.app.parsed_data = None
        self.app._invalidate_pages()
        self.app._update_campaign_bar()
        self.app.set_status("Base local eliminada", 1)

        messagebox.showinfo(
            "Base local eliminada",
            f"Proceso finalizado.\n\n"
            f"Local: {result.get('local_campaigns_deleted', 0)} campaña(s), "
            f"{result.get('local_clients_deleted', 0)} cliente(s), "
            f"{result.get('local_sync_logs_deleted', 0)} log(s)\n"
            f"Firebase: sin cambios",
        )

    def _get_int_var(self, attr: str, default: int = 0) -> int:
        try:
            var = getattr(self, attr)
            return int(var.get())
        except Exception:
            return default

    def _save_plantilla(self, numero_carta: int):
        """Persist the current textbox content to the DB."""
        contenido = self._plantilla_textbox.get("1.0", "end-1c")
        try:
            with db_service.session() as session:
                plantilla = PlantillaCarta.get_or_create(session, numero_carta)
                plantilla.contenido = contenido
                plantilla.fecha_actualizacion = datetime.now()
                session.commit()
            self._plantilla_status.configure(
                text=f"✓ Guardada — {datetime.now().strftime('%H:%M:%S')}",
                text_color=SUCCESS,
            )
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar la plantilla:\n{exc}")

    def _restore_default(self, numero_carta: int):
        """Reset template to the built-in default content."""
        from services.template_engine import DEFAULT_TEMPLATES
        default = DEFAULT_TEMPLATES.get(numero_carta, "")
        self._plantilla_textbox.delete("1.0", "end")
        self._plantilla_textbox.insert("1.0", default)
        self._plantilla_status.configure(text="Restaurado (no guardado)", text_color=WARNING)

    # ── Save logic ───────────────────────────────────────────

    def _on_save(self):
        errors = self._validate()
        if errors:
            messagebox.showerror("Validación", "\n".join(errors))
            return

        try:
            with db_service.session() as session:
                cfg = ConfigCampana.get_or_create(session)

                cfg.duracion_dias = self._get_int("duracion_dias")
                cfg.dias_cierre = self._get_int("dias_cierre")
                cfg.dias_retorno_banco = self._get_int("dias_retorno_banco")
                cfg.ventana_ingreso_dias = self._get_int("ventana_ingreso_dias")

                cfg.tramo1_inicio = self._get_int("tramo1_inicio")
                cfg.tramo1_fin = self._get_int("tramo1_fin")
                cfg.tramo2_inicio = self._get_int("tramo2_inicio")
                cfg.tramo2_fin = self._get_int("tramo2_fin")
                cfg.tramo3_inicio = self._get_int("tramo3_inicio")
                cfg.tramo3_fin = self._get_int("tramo3_fin")

                cfg.carta1_dia = self._get_int("carta1_dia")
                cfg.carta2_dia = self._get_int("carta2_dia")
                cfg.carta3_dia = self._get_int("carta3_dia")
                cfg.carta4_dia = self._get_int("carta4_dia")
                cfg.carta5_dia = self._get_int("carta5_dia")

                cfg.carta1_programada = self._get_datetime("carta1_programada")
                cfg.carta2_programada = self._get_datetime("carta2_programada")
                cfg.carta3_programada = self._get_datetime("carta3_programada")
                cfg.carta4_programada = self._get_datetime("carta4_programada")
                cfg.carta5_programada = self._get_datetime("carta5_programada")

                cfg.nombre_empresa   = self._get_str("nombre_empresa") or None
                cfg.ruc_empresa      = self._get_str("ruc_empresa") or None
                cfg.direccion_empresa = self._get_str("direccion_empresa") or None
                cfg.nombre_gestor    = self._get_str("nombre_gestor") or None
                cfg.cargo_gestor     = self._get_str("cargo_gestor") or None
                cfg.telefono_gestor  = self._get_str("telefono_gestor") or None
                cfg.correo_gestor    = self._get_str("correo_gestor") or None

                cfg.umbral_minimo_gestion = self._get_float("umbral_minimo_gestion")
                cfg.umbral_carta_fisica   = self._get_float("umbral_carta_fisica")
                cfg.porcentaje_comision_jefe = self._get_float("porcentaje_comision_jefe")

                cfg.auto_evaluar_tramos = bool(self._vars["auto_evaluar_tramos"].get())

                for i in range(1, 6):
                    setattr(cfg, f"auto_envio_carta{i}",
                            bool(self._vars.get(f"auto_envio_carta{i}", tk.BooleanVar()).get()))
                    setattr(cfg, f"formato_carta{i}",
                            self._get_str(f"formato_carta{i}") or "Word")

                cfg.fecha_actualizacion = datetime.now()
                session.commit()

            # Refresh the tramo engine globals from the new config
            load_config()

            # Sync to Firestore if connected
            self._sync_to_firestore()

            self._status_label.configure(
                text=f"✓ Guardado — {datetime.now().strftime('%H:%M:%S')}",
                text_color=SUCCESS,
            )
            self.app.set_status("Configuración guardada")

        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar:\n{exc}")

    def _sync_to_firestore(self):
        """Push config to Firestore ``configuracion/campana`` doc."""
        fb = self.app.firebase
        if not fb or not fb._initialized:
            return
        try:
            with db_service.session() as session:
                cfg = ConfigCampana.get_or_create(session)
                data = cfg.to_dict()
            fb.sync_campaign_config(data)
        except Exception:
            pass  # Non-critical — offline is fine

    # ── Validation ───────────────────────────────────────────

    def _validate(self) -> list[str]:
        errors: list[str] = []
        dur = self._get_int("duracion_dias")
        if dur < 1:
            errors.append("La duración debe ser al menos 1 día.")

        # Tramo continuity
        t1s, t1e = self._get_int("tramo1_inicio"), self._get_int("tramo1_fin")
        t2s, t2e = self._get_int("tramo2_inicio"), self._get_int("tramo2_fin")
        t3s, t3e = self._get_int("tramo3_inicio"), self._get_int("tramo3_fin")

        for label, s, e in [("Tramo 1", t1s, t1e), ("Tramo 2", t2s, t2e), ("Tramo 3", t3s, t3e)]:
            if s > e:
                errors.append(f"{label}: el día de inicio ({s}) no puede ser mayor al fin ({e}).")

        if t2s != t1e + 1:
            errors.append(f"Tramo 2 debe comenzar en día {t1e + 1} (justo después de Tramo 1).")
        if t3s != t2e + 1:
            errors.append(f"Tramo 3 debe comenzar en día {t2e + 1} (justo después de Tramo 2).")
        if t3e != dur:
            errors.append(f"Tramo 3 debe terminar en día {dur} (duración de gestión).")
        if t1s != 1:
            errors.append("Tramo 1 debe comenzar en día 1.")

        dias_cierre = self._get_int("dias_cierre")
        dias_retorno = self._get_int("dias_retorno_banco")
        if dias_cierre <= dur:
            errors.append(f"El día de cierre ({dias_cierre}) debe ser mayor a la duración ({dur}).")
        if dias_retorno <= dias_cierre:
            errors.append(
                f"El día de retorno ({dias_retorno}) debe ser mayor al día de cierre ({dias_cierre})."
            )

        # Carta days within range
        for n in (1, 2, 3, 4, 5):
            d = self._get_int(f"carta{n}_dia")
            if d < 1 or d > dur:
                errors.append(f"E-{n}: día {d} fuera de rango (1–{dur}).")

        # Programada format
        for n in (1, 2, 3, 4, 5):
            val = self._vars.get(f"carta{n}_programada", tk.StringVar()).get().strip()
            if val:
                valid = any(
                    _try_parse(val, fmt)
                    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M")
                )
                if not valid:
                    errors.append(f"Carta {n} programada: formato inválido.")

        # Thresholds
        if self._get_float("umbral_minimo_gestion") < 0:
            errors.append("El umbral mínimo de gestión no puede ser negativo.")
        if self._get_float("umbral_carta_fisica") < 0:
            errors.append("El umbral de carta física no puede ser negativo.")

        pct = self._get_float("porcentaje_comision_jefe")
        if pct < 0 or pct > 100:
            errors.append("El porcentaje de comisión debe estar entre 0 y 100.")

        return errors

    # ── Helpers ──────────────────────────────────────────────

    def _load_cfg(self) -> ConfigCampana:
        with db_service.session() as session:
            return ConfigCampana.get_or_create(session)

    def _get_str(self, key: str) -> str:
        try:
            return str(self._vars[key].get()).strip()
        except KeyError:
            return ""

    def _get_int(self, key: str) -> int:
        try:
            return int(self._vars[key].get())
        except (ValueError, KeyError):
            return 0

    def _get_float(self, key: str) -> float:
        try:
            return float(self._vars[key].get())
        except (ValueError, KeyError):
            return 0.0

    def _get_datetime(self, key: str) -> datetime | None:
        val = self._vars[key].get().strip()
        if not val:
            return None
        for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None
