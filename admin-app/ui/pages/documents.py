"""Documents page — letter generation (Word template mode) and final campaign report."""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import shutil
from typing import TYPE_CHECKING
from ..theme import *
from ..components import SectionHeader, ActionButton

if TYPE_CHECKING:
    from ..app import App

# Folder where uploaded Word templates are stored
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "templates"
)

CARTA_NOMBRES = {
    1: "E1-1 — Invitación a Reingreso (Día 1)",
    2: "E1-2 — No Pierdas Ser Empresaria (Día 9)",
    3: "E2-1 — Requerimiento de Pago (Día 11)",
    4: "E2-2 — Insistencia de Pago (Día 35)",
    5: "E3-1 — Exigimos Pago / Pre Judicial (Día 44)",
}

_TAG_HELP = (
    "Etiquetas disponibles en sus plantillas Word (formato exacto, MAYÚSCULAS):\n"
    "{{NOMBRE}}  {{DNI}}  {{DIRECCION}}  {{CODIGO}}  {{ZONA}}  {{SECCION}}\n"
    "{{CAMPANA}}  {{DEUDA}}  {{CODIGO_PAGO}}  {{FECHA}}  {{FECHA_VENCIMIENTO}}\n"
    "{{GESTOR_NOMBRE}}  {{GESTOR_CELULAR}}\n\n"
    "Reglas: escriba cada tag como texto continuo (sin cambiar fuente a mitad del tag).\n"
    "No use {NOMBRE} ni campos Word nativos (Combinar correspondencia).\n"
    "Fase actual: solo se genera Word (.docx). PDF/JPG temporalmente deshabilitados."
)


class DocumentsPage:
    """Generate collection letters and Day-60 final report."""

    def __init__(self, app: App):
        self.app = app
        self._tpl_name_labels: dict[int, ctk.CTkLabel] = {}

    # ── Render ───────────────────────────────────────────────────────────────

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._tpl_name_labels.clear()

        SectionHeader(
            container, "Documentos",
            "Plantillas Word de cobranza e informes"
        ).pack(padx=8, pady=(8, 12), anchor="w")

        self._render_word_templates_card(container)
        self._render_letters_card(container)

        ctk.CTkFrame(container, fg_color=BORDER, height=1).pack(
            fill="x", padx=8, pady=4)

        self._render_report_card(container)

        self._status = ctk.CTkLabel(container, text="",
                                    font=font(11), text_color=TEXT_SECONDARY)
        self._status.pack(padx=8, pady=8)

    # ── Word Templates Card ──────────────────────────────────────────────────

    def _render_word_templates_card(self, container):
        card = ctk.CTkFrame(container, fg_color=CARD_BG,
                            corner_radius=12, border_width=1,
                            border_color=BORDER)
        card.pack(fill="x", padx=8, pady=(0, 12))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(inner, text="Plantillas Word",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text=(
                "Suba un archivo .docx por tipo de carta. "
                "Las etiquetas {{TAG}} se rellenan automáticamente al generar. "
                "Las marcas de agua e imágenes del Word se conservan."
            ),
            font=font(12), text_color=TEXT_SECONDARY,
            wraplength=680, justify="left",
        ).pack(anchor="w", pady=(2, 10))

        help_frame = ctk.CTkFrame(inner, fg_color="#1E293B", corner_radius=8)
        help_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            help_frame, text=_TAG_HELP,
            font=("Consolas", 10), text_color="#94A3B8",
            justify="left",
        ).pack(padx=12, pady=8, anchor="w")

        for nc in range(1, 6):
            self._render_template_row(inner, nc)

    def _render_template_row(self, parent, nc: int):
        row = ctk.CTkFrame(parent, fg_color="#1E293B", corner_radius=8)
        row.pack(fill="x", pady=3)

        ctk.CTkLabel(
            row, text=CARTA_NOMBRES[nc],
            font=font(11, "bold"), text_color="#F1F5F9",
            width=320, anchor="w",
        ).pack(side="left", padx=(12, 8), pady=8)

        tpl_path = self._get_word_template_path(nc)
        has_tpl = bool(tpl_path and os.path.isfile(tpl_path))
        name_text = os.path.basename(tpl_path) if has_tpl else "Sin plantilla"
        name_color = "#34D399" if has_tpl else "#64748B"

        lbl = ctk.CTkLabel(
            row, text=name_text,
            font=font(11), text_color=name_color,
            anchor="w",
        )
        lbl.pack(side="left", padx=(0, 12), expand=True, fill="x")
        self._tpl_name_labels[nc] = lbl

        if has_tpl:
            ctk.CTkButton(
                row, text="✕ Quitar", font=font(11),
                fg_color="#7F1D1D", hover_color="#991B1B",
                height=30, width=80, corner_radius=6,
                command=lambda n=nc: self._on_remove_word_template(n),
            ).pack(side="right", padx=(4, 12), pady=6)

        ctk.CTkButton(
            row, text="⬆ Subir .docx", font=font(11),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=30, width=110, corner_radius=6,
            command=lambda n=nc: self._on_upload_word_template(n),
        ).pack(side="right", padx=(0, 4), pady=6)

    # ── Letters Generation Card ──────────────────────────────────────────────

    def _render_letters_card(self, container):
        letters_card = ctk.CTkFrame(container, fg_color=CARD_BG,
                                    corner_radius=12, border_width=1,
                                    border_color=BORDER)
        letters_card.pack(fill="x", padx=8, pady=(0, 12))

        lc_inner = ctk.CTkFrame(letters_card, fg_color="transparent")
        lc_inner.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(lc_inner, text="Generar Cartas",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w")
        ctk.CTkLabel(
            lc_inner,
            text=(
                "Si hay una plantilla Word cargada para el tipo seleccionado se usa "
                "automáticamente (salida DOCX personalizado). "
                "De lo contrario se usa la plantilla de texto."
            ),
            font=font(12), text_color=TEXT_SECONDARY,
            wraplength=680, justify="left",
        ).pack(anchor="w", pady=(2, 12))

        self._carta_var = tk.IntVar(value=1)
        for val, label in CARTA_NOMBRES.items():
            ctk.CTkRadioButton(
                lc_inner, text=label,
                variable=self._carta_var, value=val,
                font=font(11), text_color=TEXT_PRIMARY,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=self._on_carta_changed,
            ).pack(anchor="w", padx=4, pady=2)

        self._use_tramo = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            lc_inner,
            text="Solo clientes pendientes (motor de tramos)",
            variable=self._use_tramo,
            font=font(11), text_color=TEXT_PRIMARY,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).pack(anchor="w", padx=4, pady=(8, 4))

        # Mode info label
        self._mode_label = ctk.CTkLabel(
            lc_inner, text="", font=font(11), text_color="#94A3B8"
        )
        self._mode_label.pack(anchor="w", padx=4, pady=(2, 4))
        self._refresh_mode_label()

        ctk.CTkLabel(
            lc_inner,
            text="Fase actual: solo Word (.docx). PDF e imagen (JPG) están temporalmente deshabilitados.",
            font=font(11),
            text_color="#94A3B8",
            wraplength=680,
            justify="left",
        ).pack(anchor="w", padx=4, pady=(0, 8))

        self._upload_firebase = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            lc_inner,
            text="Enviar a Firebase (gestores pueden descargar)",
            variable=self._upload_firebase,
            font=font(11), text_color=TEXT_PRIMARY,
            fg_color="#7C3AED", hover_color="#6D28D9",
        ).pack(anchor="w", padx=4, pady=(2, 8))

        can_generate = self.app.parsed_data is not None
        btn_row = ctk.CTkFrame(lc_inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(4, 0))

        self._btn_gen = ctk.CTkButton(
            btn_row, text="Generar Cartas", font=font(13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=40, width=200, corner_radius=10,
            command=lambda: self._on_generate_letters(make_zip=False),
            state="normal" if can_generate else "disabled")
        self._btn_gen.pack(side="left", padx=(0, 8))

        self._btn_zip = ctk.CTkButton(
            btn_row, text="📦  Generar Todo en ZIP", font=font(12, "bold"),
            fg_color="#059669", hover_color="#047857",
            height=40, width=200, corner_radius=10,
            command=lambda: self._on_generate_letters(make_zip=True),
            state="normal" if can_generate else "disabled")
        self._btn_zip.pack(side="left")

        if not can_generate:
            ctk.CTkLabel(
                lc_inner,
                text="Cargue un archivo Excel desde la página Campaña para habilitar.",
                font=font(11), text_color=WARNING,
            ).pack(anchor="w", pady=(4, 0))

    # ── Final Report Card ────────────────────────────────────────────────────

    def _render_report_card(self, container):
        report_card = ctk.CTkFrame(container, fg_color=CARD_BG,
                                   corner_radius=12, border_width=1,
                                   border_color=BORDER)
        report_card.pack(fill="x", padx=8, pady=(8, 12))

        rc_inner = ctk.CTkFrame(report_card, fg_color="transparent")
        rc_inner.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(rc_inner, text="Informe Final de Campaña",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w")
        ctk.CTkLabel(
            rc_inner,
            text="Genera el informe ejecutivo de cierre con estadísticas completas, "
                 "avance por sección y alertas registradas.",
            font=font(12), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 12))

        can_report = (self.app.active_campaign is not None
                      and self.app.firebase_connected)
        self._btn_report = ctk.CTkButton(
            rc_inner, text="Generar Informe Final", font=font(13, "bold"),
            fg_color="#7C3AED", hover_color="#6D28D9",
            height=40, width=220, corner_radius=10,
            command=self._on_final_report,
            state="normal" if can_report else "disabled")
        self._btn_report.pack(anchor="w")

        if not can_report:
            missing = []
            if not self.app.active_campaign:
                missing.append("Campaña activa")
            if not self.app.firebase_connected:
                missing.append("Firebase conectado")
            ctk.CTkLabel(rc_inner,
                         text=f"Requiere: {', '.join(missing)}",
                         font=font(11), text_color=WARNING,
                         ).pack(anchor="w", pady=(4, 0))

    def stop(self):
        pass

    # ── Word Template helpers ────────────────────────────────────────────────

    def _get_word_template_path(self, nc: int) -> str | None:
        try:
            from services.database import db_service, PlantillaCarta
            with db_service.session() as sess:
                p = PlantillaCarta.get_or_create(sess, nc)
                return p.word_template_path or None
        except Exception:
            return None

    def _on_upload_word_template(self, nc: int):
        path = filedialog.askopenfilename(
            title=f"Subir plantilla Word — Carta {nc}",
            filetypes=[("Documentos Word", "*.docx"), ("Todos", "*.*")],
        )
        if not path:
            return

        os.makedirs(_TEMPLATES_DIR, exist_ok=True)
        dest = os.path.join(_TEMPLATES_DIR, f"plantilla_carta_{nc}.docx")
        try:
            shutil.copy2(path, dest)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo copiar el archivo:\n{e}")
            return

        try:
            from services.database import db_service, PlantillaCarta
            with db_service.session() as sess:
                p = PlantillaCarta.get_or_create(sess, nc)
                p.word_template_path = dest
                sess.commit()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar en la base de datos:\n{e}")
            return

        lbl = self._tpl_name_labels.get(nc)
        if lbl:
            lbl.configure(text=os.path.basename(dest), text_color="#34D399")

        self._refresh_mode_label()
        scan_msg = ""
        try:
            from services.word_template_engine import scan_template_tags
            scan = scan_template_tags(dest)
            parts = []
            if scan["supported"]:
                parts.append(
                    "Etiquetas reconocidas: "
                    + ", ".join(f"{{{{{t}}}}}" for t in scan["supported"])
                )
            if scan["unknown"]:
                parts.append(
                    "Etiquetas no soportadas: "
                    + ", ".join(f"{{{{{t}}}}}" for t in scan["unknown"])
                )
            if scan["fragments"]:
                parts.append(
                    "Word partió algunos tags en el XML; el motor los reparará al generar."
                )
            if parts:
                scan_msg = "\n\n" + "\n".join(parts)
        except Exception as e:
            scan_msg = f"\n\nNo se pudo analizar la plantilla: {e}"

        sync_msg = ""
        if self.app.firebase_connected:
            try:
                self.app.firebase.upload_letter_template(nc, dest)
                sync_msg = "\n\nPlantilla sincronizada a Firebase (gestores APK)."
            except Exception as e:
                sync_msg = f"\n\n⚠ No se pudo sincronizar a Firebase: {e}"

        messagebox.showinfo(
            "Plantilla cargada",
            f"Plantilla para Carta {nc} actualizada:\n{os.path.basename(dest)}\n\n"
            "Las cartas se generarán en DOCX personalizado usando este Word."
            f"{scan_msg}{sync_msg}",
        )

    def _on_remove_word_template(self, nc: int):
        if not messagebox.askyesno(
            "Quitar plantilla",
            f"¿Quitar la plantilla Word de la Carta {nc}?\n"
            "Se usará la plantilla de texto en su lugar.",
        ):
            return

        try:
            from services.database import db_service, PlantillaCarta
            with db_service.session() as sess:
                p = PlantillaCarta.get_or_create(sess, nc)
                p.word_template_path = None
                sess.commit()
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar la base de datos:\n{e}")
            return

        lbl = self._tpl_name_labels.get(nc)
        if lbl:
            lbl.configure(text="Sin plantilla", text_color="#64748B")

        self._refresh_mode_label()
        if self.app.firebase_connected:
            try:
                self.app.firebase.remove_letter_template(nc)
            except Exception:
                pass

    def _on_carta_changed(self):
        self._refresh_mode_label()

    def _refresh_mode_label(self):
        if not hasattr(self, "_mode_label"):
            return
        nc = getattr(self, "_carta_var", None)
        if nc is None:
            return
        tpl = self._get_word_template_path(nc.get())
        if tpl and os.path.isfile(tpl):
            self._mode_label.configure(
                text=f"✓ Modo Word — se usará '{os.path.basename(tpl)}' → salida DOCX personalizado",
                text_color="#34D399",
            )
        else:
            self._mode_label.configure(
                text="ℹ Modo texto — suba una plantilla .docx para usar modo Word",
                text_color="#94A3B8",
            )

    # ── Letter Generation ────────────────────────────────────────────────────

    def _on_generate_letters(self, make_zip: bool = False):
        if not self.app.parsed_data:
            messagebox.showwarning("Cartas", "Cargue un archivo Excel primero.")
            return

        numero_carta = self._carta_var.get()
        word_tpl = self._get_word_template_path(numero_carta)
        use_word = bool(word_tpl and os.path.isfile(word_tpl))
        formats = ["docx"]

        output_dir = filedialog.askdirectory(
            title="Seleccionar carpeta para guardar las cartas")
        if not output_dir:
            return

        use_tramo  = self._use_tramo.get()
        upload_fb  = self._upload_firebase.get()

        gestores_info: dict = {}
        gestores_phones: dict = {}
        if self.app.firebase_connected:
            try:
                users = self.app.firebase.list_gestor_users()
                for u in users:
                    name = u.get("nombre", "")
                    phone = str(
                        u.get("telefono") or u.get("telefono_movil") or ""
                    ).strip()
                    if not name and not phone:
                        continue
                    for sk in (u.get("secciones") or []):
                        if name:
                            gestores_info[sk] = name
                        if phone:
                            gestores_phones[sk] = phone
                    sec = u.get("seccion", "")
                    if sec:
                        if name:
                            gestores_info[sec] = name
                        if phone:
                            gestores_phones[sec] = phone
            except Exception:
                pass

        from services.database import db_service, ConfigCampana, PlantillaCarta
        gestor_config: dict = {}
        template_text = ""
        try:
            with db_service.session() as _sess:
                _cfg = ConfigCampana.get_or_create(_sess)
                gestor_config = {
                    k: v for k, v in _cfg.to_dict().items()
                    if k in ("nombre_empresa", "ruc_empresa", "nombre_gestor",
                             "cargo_gestor", "telefono_gestor", "correo_gestor",
                             "direccion_empresa")
                }
                _p = PlantillaCarta.get_or_create(_sess, numero_carta)
                template_text = _p.contenido or ""
        except Exception:
            pass

        campaign_info: dict = {}
        campaign_id = ""
        if self.app.active_campaign:
            campaign_id = str(self.app.active_campaign.id)
            campaign_info = {
                "id": campaign_id,
                "nombre": getattr(self.app.active_campaign, "nombre", ""),
            }

        self._btn_gen.configure(state="disabled", text="Generando…")
        self._btn_zip.configure(state="disabled")
        self._status.configure(
            text=f"Generando Carta N° {numero_carta}…",
            text_color=TEXT_SECONDARY,
        )

        def work():
            try:
                from services.campaign_manager import CampaignManager

                if use_tramo and campaign_id:
                    cm = CampaignManager()
                    by_seccion = cm.group_pending_letters_by_section(
                        campaign_id,
                        numero_carta=numero_carta,
                    )
                    if not by_seccion:
                        self.app.after(0, lambda: self._letters_err(
                            f"No hay cartas N° {numero_carta} pendientes "
                            f"según el motor de tramos."))
                        return
                else:
                    by_seccion = self.app.parsed_data["by_seccion"]

                zip_path = None

                if use_word:
                    from services.letter_exporter import (
                        export_all_letters_from_word, build_zip,
                    )
                    result = export_all_letters_from_word(
                        by_seccion=by_seccion,
                        numero_carta=numero_carta,
                        template_path=word_tpl,
                        output_dir=output_dir,
                        gestores_info=gestores_info,
                        gestores_phones=gestores_phones,
                        campaign_id=campaign_id,
                        gestor_config=gestor_config,
                        campaign_info=campaign_info,
                        formats=["docx"],
                    )
                else:
                    from services.letter_exporter import (
                        export_all_letters, build_zip,
                    )
                    result = export_all_letters(
                        by_seccion=by_seccion,
                        numero_carta=numero_carta,
                        output_dir=output_dir,
                        formats=formats,
                        gestores_info=gestores_info,
                        campaign_id=campaign_id,
                        gestor_config=gestor_config,
                        template_text=template_text,
                        campaign_info=campaign_info,
                    )

                if make_zip and result["files"]:
                    import os as _os
                    zip_name = f"cartas_E{numero_carta}_{campaign_id or 'sin_campaña'}.zip"
                    zip_path = build_zip(
                        result["files"],
                        _os.path.join(output_dir, zip_name),
                    )

                if upload_fb and self.app.firebase_connected:
                    self._upload_to_firebase(result, numero_carta, campaign_id)

                self.app.after(0, lambda: self._letters_ok(result, zip_path))
            except Exception as e:
                self.app.after(0, lambda: self._letters_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _upload_to_firebase(self, result: dict, numero_carta: int, campaign_id: str):
        import re
        fb = self.app.firebase
        if not fb or not fb._initialized:
            return
        seccion_to_uid: dict[str, str] = {}
        try:
            for user in fb.list_gestor_users():
                uid = str(user.get("uid") or user.get("id") or "")
                if not uid:
                    continue
                for sk in (user.get("secciones") or []):
                    seccion_to_uid[str(sk)] = uid
        except Exception:
            seccion_to_uid = {}

        for path in result.get("files", []):
            if not str(path).lower().endswith(".docx"):
                continue
            try:
                fname = os.path.basename(path)
                sec_match = re.search(r"_Sec([A-Za-z0-9_]+)_", fname)
                cli_match = re.search(r"Cli([^_]+)_", fname)
                seccion_letter = sec_match.group(1) if sec_match else ""
                seccion_key = seccion_letter

                # Try to map section letter to full composite section key.
                candidates = [k for k in seccion_to_uid.keys() if k.endswith(f"_{seccion_letter}")]
                if len(candidates) == 1:
                    seccion_key = candidates[0]

                gestor_uid = seccion_to_uid.get(seccion_key, "")
                cliente_id = cli_match.group(1) if cli_match else ""

                fb.upload_generated_letter(
                    file_path=path,
                    campaign_id=campaign_id or "cartera_activa",
                    numero_carta=numero_carta,
                    seccion_key=seccion_key or "SIN_SECCION",
                    gestor_uid=gestor_uid or "SIN_GESTOR",
                    cliente_id=cliente_id,
                )
            except Exception:
                pass

    def _letters_ok(self, result: dict, zip_path: str | None = None):
        self._btn_gen.configure(state="normal", text="Generar Cartas")
        self._btn_zip.configure(state="normal")
        n_files   = result["total_files"]
        n_letters = result["total_letters"]
        out       = result["output_dir"]
        errors    = result.get("errors", [])
        errs_txt  = (
            f"\n\n⚠ Errores ({len(errors)}):\n" + "\n".join(errors[:5])
            if errors else ""
        )
        zip_txt = f"\n\nZIP: {zip_path}" if zip_path else ""
        self._status.configure(
            text=f"{n_files} archivos · {n_letters} cartas",
            text_color=SUCCESS)
        messagebox.showinfo(
            "Cartas Generadas",
            f"Se generaron {n_files} archivos con {n_letters} cartas."
            f"{zip_txt}{errs_txt}\n\nUbicación:\n{out}")
        os.startfile(out)

    def _letters_err(self, msg: str):
        self._btn_gen.configure(state="normal", text="Generar Cartas")
        self._btn_zip.configure(state="disabled")
        self._status.configure(text=f"Error: {msg}", text_color=DANGER)
        messagebox.showerror("Error", f"Error al generar cartas:\n{msg}")

    # ── Final Report ─────────────────────────────────────────────────────────

    def _on_final_report(self):
        if not self.app.firebase_connected:
            messagebox.showwarning("Firebase", "Conecte Firebase primero.")
            return
        if not self.app.active_campaign:
            messagebox.showwarning("Campaña", "No hay campaña activa.")
            return

        output_dir = filedialog.askdirectory(
            title="Seleccionar carpeta para guardar el informe")
        if not output_dir:
            return

        campaign = self.app.active_campaign
        self._btn_report.configure(state="disabled", text="Generando…")
        self._status.configure(text="Generando informe final…",
                               text_color=TEXT_SECONDARY)

        from services.word_generator import generate_final_report

        def work():
            try:
                resumen = self.app.firebase.get_campaign_status(campaign.id)
                alertas = []
                try:
                    alertas = self.app.firebase.get_alerts(estado="", limit=500)
                except Exception:
                    pass

                secciones_stats = []
                try:
                    by_sec = self.app.campaign_mgr.get_clients_by_section(campaign.id)
                    gestores = {}
                    try:
                        users = self.app.firebase.list_gestor_users()
                        for u in users:
                            secs = u.get("secciones") or []
                            if isinstance(secs, list):
                                for sk in secs:
                                    gestores[sk] = u.get("nombre", "")
                            s = u.get("seccion", "")
                            if s and s not in gestores:
                                gestores[s] = u.get("nombre", "")
                    except Exception:
                        pass

                    for sec, clients in sorted(by_sec.items()):
                        sec_data = {
                            "seccion": sec,
                            "gestor": gestores.get(sec, ""),
                            "total": len(clients),
                        }
                        counts = {
                            "visitados": 0, "pagados": 0,
                            "morosos": 0, "no_ubica": 0,
                            "suplantacion": 0, "pago_no_registrado": 0,
                        }
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
                self.app.after(0, lambda: self._report_ok(path))
            except Exception as e:
                self.app.after(0, lambda: self._report_err(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _report_ok(self, path):
        self._btn_report.configure(state="normal", text="Generar Informe Final")
        self._status.configure(text="Informe final generado", text_color=SUCCESS)
        messagebox.showinfo(
            "Informe Final",
            f"El informe fue generado exitosamente.\n\n{path}")
        os.startfile(os.path.dirname(path))

    def _report_err(self, msg):
        self._btn_report.configure(state="normal", text="Generar Informe Final")
        self._status.configure(text=f"Error: {msg}", text_color=DANGER)
        messagebox.showerror("Error", f"Error al generar informe:\n{msg}")
