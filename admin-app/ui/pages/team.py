"""Team page — User management + Distribution configuration."""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
from typing import TYPE_CHECKING, Any, Callable
from ..theme import *
from ..components import SectionHeader
from services.territorial_utils import (
    count_secciones_in_region,
    count_secciones_in_zona,
    group_secciones_by_hierarchy,
    legacy_fields_from_secciones,
    parse_composite_section_key,
    remove_region,
    remove_seccion,
    remove_zona,
)

if TYPE_CHECKING:
    from ..app import App


class TeamPage:
    """User management and section distribution in a single page."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._current_tab = "users"
        self._gestores: list[dict] = []
        self._assignments: dict[str, str] = {}
        self._gestor_names: dict[str, str] = {}
        self._section_vars: dict[str, ctk.StringVar] = {}
        self._uid_map: dict[str, str | None] = {}

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container

        if not self.app.firebase_connected:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            card = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=12,
                                border_width=1, border_color=BORDER)
            card.pack(fill="x", padx=60, pady=20)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=40, pady=30)
            ctk.CTkLabel(inner, text="📡", font=font(32)).pack()
            ctk.CTkLabel(inner, text="Sin conexión Firebase",
                         font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY).pack(pady=(8, 4))
            ctk.CTkLabel(inner, text="Conecte Firebase para gestionar el equipo.",
                         font=font(FONT_SCALE['base']), text_color=TEXT_SECONDARY).pack()
            return

        # ── Header ────────────────────────────────────────────
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(hdr, text="👥 Gestión de Equipo",
                     font=font(FONT_SCALE['xl'], "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Administra usuarios y distribución de secciones",
                     font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        # ── KPI strip ─────────────────────────────────────────
        self._kpi_strip = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=10,
                                       border_width=1, border_color=BORDER)
        self._kpi_strip.pack(fill="x", padx=16, pady=(0, 12))
        kpi_inner = ctk.CTkFrame(self._kpi_strip, fg_color="transparent")
        kpi_inner.pack(fill="x", padx=16, pady=10)
        kpi_inner.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._kpi_labels: dict[str, ctk.CTkLabel] = {}
        for i, (key, lbl, icon, clr) in enumerate([
            ("total", "Total Usuarios", "👥", ACCENT),
            ("gestores", "Gestores Campo", "📍", SUCCESS),
            ("call", "Call Center", "📞", INFO),
            ("supervisores", "Supervisores", "📈", WARNING),
            ("activos", "Activos", "✅", SUCCESS),
        ]):
            cell = ctk.CTkFrame(kpi_inner, fg_color="transparent")
            cell.grid(row=0, column=i, padx=8, sticky="w")
            ctk.CTkLabel(cell, text=f"{icon} {lbl}",
                         font=font(FONT_SCALE['xs']), text_color=TEXT_MUTED).pack(anchor="w")
            val_lbl = ctk.CTkLabel(cell, text="—",
                                   font=font(FONT_SCALE['2xl'], "bold"), text_color=clr)
            val_lbl.pack(anchor="w", pady=(1, 0))
            self._kpi_labels[key] = val_lbl

        # ── Pill Tabs ─────────────────────────────────────────
        tab_outer = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=10,
                                 border_width=1, border_color=BORDER)
        tab_outer.pack(fill="x", padx=16, pady=(0, 8))
        tab_bar = ctk.CTkFrame(tab_outer, fg_color="transparent")
        tab_bar.pack(fill="x", padx=12, pady=8)

        self._tab_users_btn = ctk.CTkButton(
            tab_bar, text="👤 Usuarios", font=font(FONT_SCALE['sm'], "bold"),
            fg_color=ACCENT, text_color=WHITE, hover_color=ACCENT_HOVER,
            height=32, width=130, corner_radius=8,
            command=lambda: self._switch_tab("users"))
        self._tab_users_btn.pack(side="left", padx=(0, 6))

        self._tab_dist_btn = ctk.CTkButton(
            tab_bar, text="🗺️ Distribución", font=font(FONT_SCALE['sm'], "bold"),
            fg_color="transparent", text_color=TEXT_SECONDARY, hover_color=ACCENT_LIGHT,
            border_width=1, border_color=BORDER,
            height=32, width=140, corner_radius=8,
            command=lambda: self._switch_tab("distribution"))
        self._tab_dist_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            tab_bar, text="📞 Ir a Call Center", font=font(FONT_SCALE['sm'], "bold"),
            fg_color=INFO, text_color=WHITE, hover_color="#2563EB",
            height=32, width=160, corner_radius=8,
            command=lambda: self.app.navigate_to("callcenter"),
        ).pack(side="left", padx=(6, 0))

        # Status hint
        self._status_lbl = ctk.CTkLabel(tab_bar, text="Cargando…",
                                        font=font(FONT_SCALE['xs']), text_color=TEXT_MUTED)
        self._status_lbl.pack(side="right", padx=4)

        # ── Content area ──────────────────────────────────────
        self._content = ctk.CTkFrame(container, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=16)

        self._show_skeleton()
        self._load_users()

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        inactive = {"fg_color": "transparent", "text_color": TEXT_SECONDARY, "border_width": 1}
        active = {"fg_color": ACCENT, "text_color": WHITE, "border_width": 0}
        for btn in (self._tab_users_btn, self._tab_dist_btn):
            btn.configure(**inactive)
        if tab == "users":
            self._tab_users_btn.configure(**active)
            self._render_users()
        else:
            self._tab_dist_btn.configure(**active)
            self._render_distribution()

    def _load_users(self):
        def work():
            try:
                gestores = self.app.firebase.list_gestor_users()
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._on_users_loaded(gestores))
            except Exception as e:
                if self._container and self._container.winfo_exists():
                    self._container.after(0, lambda: self._status_lbl.configure(
                        text=f"Error: {e}", text_color=DANGER))
        threading.Thread(target=work, daemon=True).start()

    def _on_users_loaded(self, gestores):
        self._gestores = [g for g in gestores
                          if g.get("rol") in ("gestor", "asistente", "supervisor", "admin")]
        self._gestor_names = {}
        self._assignments = {}

        for g in self._gestores:
            uid = g.get("uid") or g.get("id", "")
            name = g.get("nombre", g.get("email", "???"))
            self._gestor_names[uid] = name
            secciones = g.get("secciones") or []
            if isinstance(secciones, list):
                for sk in secciones:
                    self._assignments[sk] = uid
            else:
                sec = g.get("seccion", "")
                if sec:
                    self._assignments[sec] = uid

        # Update KPI strip
        total = len(self._gestores)
        gestores_cnt = sum(
            1 for g in self._gestores
            if g.get("rol") == "gestor" and g.get("canal", "campo") != "call"
        )
        call_cnt = sum(
            1 for g in self._gestores
            if g.get("rol") == "gestor" and g.get("canal") == "call"
        )
        supervisores_cnt = sum(1 for g in self._gestores
                               if g.get("rol") in ("supervisor", "admin"))
        activos_cnt = sum(1 for g in self._gestores if g.get("activo", True))
        if hasattr(self, "_kpi_labels"):
            self._kpi_labels["total"].configure(text=str(total))
            self._kpi_labels["gestores"].configure(text=str(gestores_cnt))
            self._kpi_labels["call"].configure(text=str(call_cnt))
            self._kpi_labels["supervisores"].configure(text=str(supervisores_cnt))
            self._kpi_labels["activos"].configure(text=str(activos_cnt))

        self._status_lbl.configure(
            text=f"{total} usuarios cargados",
            text_color=TEXT_MUTED)
        self._render_users()

    def _show_skeleton(self):
        """Show skeleton loading placeholders while data loads."""
        for w in self._content.winfo_children():
            w.destroy()
        for _ in range(4):
            sk = ctk.CTkFrame(self._content, fg_color=CARD_BG, corner_radius=10,
                              border_width=1, border_color=BORDER, height=66)
            sk.pack(fill="x", pady=3)
            sk.pack_propagate(False)
            inner = ctk.CTkFrame(sk, fg_color="transparent")
            inner.pack(fill="x", padx=14, pady=14)
            # Avatar skeleton
            ctk.CTkFrame(inner, fg_color=BORDER, corner_radius=20,
                         width=40, height=40).pack(side="left", padx=(0, 12))
            lines = ctk.CTkFrame(inner, fg_color="transparent")
            lines.pack(side="left")
            ctk.CTkFrame(lines, fg_color=BORDER, corner_radius=4,
                         width=160, height=12).pack(anchor="w", pady=(2, 4))
            ctk.CTkFrame(lines, fg_color="#F1F5F9", corner_radius=4,
                         width=220, height=10).pack(anchor="w")

    # ── Users Tab ──────────────────────────────────────────────
    def _render_users(self):
        for w in self._content.winfo_children():
            w.destroy()

        # Action bar
        action_bar = ctk.CTkFrame(self._content, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(
            action_bar, text="＋ Nuevo Usuario", font=font(FONT_SCALE['sm'], "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=36, width=160, corner_radius=8,
            command=self._new_user
        ).pack(side="left")
        ctk.CTkLabel(action_bar,
                     text=f"{len(self._gestores)} usuario(s)",
                     font=font(FONT_SCALE['xs']), text_color=TEXT_MUTED).pack(side="right", padx=4)

        if not self._gestores:
            empty = ctk.CTkFrame(self._content, fg_color=CARD_BG, corner_radius=10,
                                 border_width=1, border_color=BORDER)
            empty.pack(fill="x", pady=4)
            ctk.CTkLabel(empty, text="👤  No hay usuarios registrados",
                         font=font(FONT_SCALE['base']), text_color=TEXT_MUTED).pack(pady=30)
            return

        for u in sorted(self._gestores, key=lambda x: x.get("nombre", "")):
            self._render_user_card(u)

    _ROLE_META = {
        "admin":       ("#7C3AED", "#F5F3FF", "Admin"),
        "supervisor":  ("#D97706", "#FFFBEB", "Supervisor"),
        "asistente":   ("#0891B2", "#ECFEFF", "Asistente"),
        "gestor":      ("#059669", "#ECFDF5", "Gestor"),
    }

    def _render_user_card(self, u):
        card = ctk.CTkFrame(self._content, fg_color=CARD_BG, corner_radius=10,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=3)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)

        # Avatar with role-colored initials
        rol = u.get("rol", "gestor")
        rol_clr, rol_bg, rol_lbl = self._ROLE_META.get(rol, (ACCENT, ACCENT_LIGHT, rol.capitalize()))
        nombre = u.get("nombre", "") or u.get("email", "?")
        initials = "".join(w[0].upper() for w in nombre.split()[:2]) or "?"

        avatar = ctk.CTkFrame(row, fg_color=rol_bg, corner_radius=20,
                              width=42, height=42)
        avatar.pack(side="left", padx=(0, 12))
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=initials, font=font(FONT_SCALE['base'], "bold"),
                     text_color=rol_clr).place(relx=0.5, rely=0.5, anchor="center")

        # Info block
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(anchor="w")
        ctk.CTkLabel(name_row, text=nombre,
                     font=font(FONT_SCALE['base'], "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        # Role pill
        pill = ctk.CTkFrame(name_row, fg_color=rol_bg, corner_radius=6)
        pill.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(pill, text=rol_lbl,
                     font=font(FONT_SCALE['xs'], "bold"),
                     text_color=rol_clr).pack(padx=6, pady=1)
        if u.get("canal") == "call":
            call_pill = ctk.CTkFrame(name_row, fg_color="#E0F2FE", corner_radius=6)
            call_pill.pack(side="left", padx=(4, 0))
            ctk.CTkLabel(call_pill, text="CALL",
                         font=font(FONT_SCALE['xs'], "bold"),
                         text_color="#0369A1").pack(padx=6, pady=1)
        if not u.get("activo", True):
            pill2 = ctk.CTkFrame(name_row, fg_color=DANGER_LIGHT, corner_radius=6)
            pill2.pack(side="left", padx=(4, 0))
            ctk.CTkLabel(pill2, text="INACTIVO",
                         font=font(FONT_SCALE['xs'], "bold"),
                         text_color=DANGER).pack(padx=6, pady=1)

        # Meta: email + secciones
        secciones = u.get("secciones") or []
        sec_text = ""
        if secciones:
            sec_text = ", ".join(str(s) for s in secciones[:3])
            if len(secciones) > 3:
                sec_text += f"  +{len(secciones)-3} más"
        elif u.get("seccion"):
            sec_text = f"Sec: {u['seccion']}"
        location = "  ·  ".join(filter(None, [
            f"R:{u.get('region','-')}" if u.get("region") else "",
            f"Z:{u.get('zona','-')}" if u.get("zona") else "",
        ]))
        meta = "  ·  ".join(filter(None, [u.get("email", ""), location, sec_text]))
        ctk.CTkLabel(info, text=meta, font=font(FONT_SCALE['xs']),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        # Action buttons
        uid = u.get("uid") or u.get("id", "")
        btn_row = ctk.CTkFrame(row, fg_color="transparent")
        btn_row.pack(side="right")
        ctk.CTkButton(btn_row, text="✏️ Editar",
                      font=font(FONT_SCALE['xs']), fg_color=ACCENT_LIGHT,
                      text_color=ACCENT, hover_color=ACCENT_MUTED,
                      height=28, width=80, corner_radius=6,
                      command=lambda _u=u: self._edit_user(_u)
                      ).pack(side="left", padx=(0, 4))
        show_territorio = (
            rol in ("gestor", "asistente")
            and u.get("canal", "campo") != "call"
        )
        if show_territorio:
            ctk.CTkButton(btn_row, text="🗺️ Territorio",
                          font=font(FONT_SCALE['xs']), fg_color="#EEF2FF",
                          text_color="#4338CA", hover_color="#C7D2FE",
                          height=28, width=96, corner_radius=6,
                          command=lambda _u=u: self._edit_user(_u)
                          ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(btn_row, text="🗑 Eliminar",
                      font=font(FONT_SCALE['xs']), fg_color=DANGER_LIGHT,
                      text_color=DANGER, hover_color="#FCA5A5",
                      height=28, width=84, corner_radius=6,
                      command=lambda _uid=uid, _n=nombre: self._delete_user(_uid, _n)
                      ).pack(side="left")

    def _mount_assigned_territory_panel(
        self,
        parent: ctk.CTkBaseClass,
        selected_keys: list[str],
        on_changed: Callable[[], None],
    ) -> Callable[[], None]:
        """Mount hierarchical Región→Zona→Sección tree. Returns refresh()."""
        ctk.CTkLabel(
            parent,
            text="Territorio asignado (quitar por región, zona o sección)",
            font=font(11, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(padx=16, anchor="w", pady=(10, 0))
        ctk.CTkLabel(
            parent,
            text="Quitar territorio no mueve clientes; solo deja de asignar esa zona/sección al gestor.",
            font=font(9),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="left",
        ).pack(padx=16, anchor="w", pady=(2, 0))

        tree_frame = ctk.CTkFrame(
            parent, fg_color="#F8FAFC", corner_radius=8,
            border_width=1, border_color=BORDER,
        )
        tree_frame.pack(fill="x", padx=16, pady=(6, 0))

        def _confirm_bulk(count: int, label: str) -> bool:
            if count <= 1:
                return True
            return bool(messagebox.askyesno(
                "Quitar territorio",
                f"Se quitarán {count} secciones de {label}.\n¿Continuar?",
            ))

        def _apply_keys(new_keys: list[str]) -> None:
            selected_keys.clear()
            selected_keys.extend(new_keys)
            refresh()
            on_changed()

        def refresh() -> None:
            for w in tree_frame.winfo_children():
                w.destroy()
            hierarchy = group_secciones_by_hierarchy(selected_keys)
            if not hierarchy:
                ctk.CTkLabel(
                    tree_frame,
                    text="  Ningún territorio compuesto asignado",
                    font=font(10),
                    text_color=TEXT_MUTED,
                ).pack(padx=8, pady=8, anchor="w")
                return

            for region, zonas in hierarchy.items():
                region_row = ctk.CTkFrame(tree_frame, fg_color="transparent")
                region_row.pack(fill="x", padx=8, pady=(6, 2))
                ctk.CTkLabel(
                    region_row,
                    text=f"Región {region}",
                    font=font(11, "bold"),
                    text_color=TEXT_PRIMARY,
                ).pack(side="left")
                n_reg = count_secciones_in_region(selected_keys, region)
                ctk.CTkButton(
                    region_row,
                    text="Quitar región",
                    font=font(9),
                    height=24,
                    width=100,
                    corner_radius=6,
                    fg_color=DANGER_LIGHT,
                    text_color=DANGER,
                    hover_color="#FCA5A5",
                    command=lambda r=region, n=n_reg: (
                        _apply_keys(remove_region(selected_keys, r))
                        if _confirm_bulk(n, f"la región {r}") else None
                    ),
                ).pack(side="right")

                for zona, secs in sorted(zonas.items()):
                    zona_row = ctk.CTkFrame(tree_frame, fg_color="transparent")
                    zona_row.pack(fill="x", padx=20, pady=(2, 0))
                    ctk.CTkLabel(
                        zona_row,
                        text=f"Zona {zona}",
                        font=font(10, "bold"),
                        text_color=TEXT_SECONDARY,
                    ).pack(side="left")
                    n_zona = count_secciones_in_zona(selected_keys, region, zona)
                    ctk.CTkButton(
                        zona_row,
                        text="Quitar zona",
                        font=font(9),
                        height=22,
                        width=90,
                        corner_radius=6,
                        fg_color="#FEF3C7",
                        text_color="#B45309",
                        hover_color="#FDE68A",
                        command=lambda r=region, z=zona, n=n_zona: (
                            _apply_keys(remove_zona(selected_keys, r, z))
                            if _confirm_bulk(n, f"la zona {r}/{z}") else None
                        ),
                    ).pack(side="right")

                    secs_row = ctk.CTkFrame(tree_frame, fg_color="transparent")
                    secs_row.pack(fill="x", padx=36, pady=(2, 4))
                    for key in secs:
                        parsed = parse_composite_section_key(key)
                        letter = parsed[2] if parsed else key
                        chip = ctk.CTkFrame(secs_row, fg_color=ACCENT_LIGHT, corner_radius=6)
                        chip.pack(side="left", padx=2, pady=2)
                        ctk.CTkLabel(
                            chip,
                            text=f" {letter} ",
                            font=font(10, "bold"),
                            text_color=ACCENT,
                        ).pack(side="left", padx=(4, 0))
                        ctk.CTkButton(
                            chip,
                            text="✕",
                            font=font(9),
                            width=20,
                            height=20,
                            fg_color="transparent",
                            hover_color=DANGER,
                            text_color=DANGER,
                            corner_radius=4,
                            command=lambda k=key: _apply_keys(
                                remove_seccion(selected_keys, k)
                            ),
                        ).pack(side="left", padx=(0, 2))

        refresh()
        return refresh

    def _new_user(self):
        dialog = ctk.CTkToplevel(self._container)
        dialog.title("Nuevo Usuario")
        dialog.geometry("480x700")
        dialog.configure(fg_color=BG)
        dialog.transient(self._container.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, True)

        # Title
        ctk.CTkLabel(dialog, text="Registrar Nuevo Usuario",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY
                     ).pack(padx=20, pady=(14, 0))

        # Scrollable content area
        scroll = ctk.CTkScrollableFrame(dialog, fg_color=CARD_BG, corner_radius=12,
                                        border_width=1, border_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        # ── Basic fields ──────────────────────────────────────
        fields = {}
        for key, label, pw in [("nombre", "Nombre completo", False),
                                ("email", "Correo electrónico", False),
                                ("password", "Contraseña", True),
                                ("telefono", "Teléfono (opcional)", False)]:
            ctk.CTkLabel(scroll, text=label, font=font(11),
                         text_color=TEXT_SECONDARY).pack(padx=16, anchor="w", pady=(6, 0))
            entry = ctk.CTkEntry(scroll, font=font(12), height=34,
                                 corner_radius=8, border_color=BORDER)
            if pw:
                entry.configure(show="*")
            entry.pack(fill="x", padx=16, pady=(2, 0))
            fields[key] = entry

        # ── Role ─────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Rol", font=font(11),
                     text_color=TEXT_SECONDARY).pack(padx=16, anchor="w", pady=(8, 0))
        role_var = ctk.StringVar(value="gestor")
        role_menu = ctk.CTkOptionMenu(scroll, variable=role_var,
                          values=["gestor", "asistente", "supervisor", "admin"],
                          font=font(12), height=34, corner_radius=8,
                          fg_color="#F1F5F9", button_color=ACCENT,
                          text_color=TEXT_PRIMARY)
        role_menu.pack(fill="x", padx=16, pady=(2, 0))

        # ── Tipo gestor (campo / call center) ─────────────────
        canal_var = ctk.StringVar(value="campo")
        canal_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        canal_wrap.pack(fill="x")
        ctk.CTkLabel(canal_wrap, text="Tipo de gestor", font=font(11),
                     text_color=TEXT_SECONDARY).pack(padx=16, anchor="w", pady=(8, 0))
        canal_menu = ctk.CTkOptionMenu(
            canal_wrap, variable=canal_var,
            values=["campo", "call"],
            font=font(12), height=34, corner_radius=8,
            fg_color="#F1F5F9", button_color=ACCENT, text_color=TEXT_PRIMARY,
        )
        canal_menu.pack(fill="x", padx=16, pady=(2, 0))
        ctk.CTkLabel(
            canal_wrap,
            text="Call Center: gestión telefónica tramo 1 (sin sección territorial).",
            font=font(10), text_color=TEXT_MUTED, wraplength=400, justify="left",
        ).pack(padx=16, anchor="w", pady=(2, 0))

        # ── Cascade Section Picker (Multi-select) ─────────────
        sec_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        sec_wrap.pack(fill="x")

        def _toggle_sec_wrap(*_):
            role = role_var.get()
            if role in ("admin", "supervisor"):
                canal_wrap.pack_forget()
                sec_wrap.pack_forget()
            elif canal_var.get() == "call":
                canal_wrap.pack(fill="x")
                sec_wrap.pack_forget()
            else:
                canal_wrap.pack(fill="x")
                sec_wrap.pack(fill="x")

        role_menu.configure(command=_toggle_sec_wrap)
        canal_menu.configure(command=_toggle_sec_wrap)

        separator = ctk.CTkFrame(sec_wrap, height=1, fg_color=BORDER)
        separator.pack(fill="x", padx=16, pady=(14, 0))

        sec_header = ctk.CTkFrame(sec_wrap, fg_color="transparent")
        sec_header.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(sec_header, text="Secciones asignadas", font=font(12, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        load_cat_btn = ctk.CTkButton(sec_header, text="⟳ Cargar catálogo",
                                     font=font(10), height=26, width=130,
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     corner_radius=6)
        load_cat_btn.pack(side="right")

        sec_status = ctk.CTkLabel(sec_wrap, text="Presiona 'Cargar catálogo' para ver Regiones/Zonas/Secciones.",
                                  font=font(10), text_color=TEXT_MUTED,
                                  wraplength=400, justify="left")
        sec_status.pack(padx=16, anchor="w", pady=(4, 0))

        # Cascade dropdowns
        cascade_frame = ctk.CTkFrame(sec_wrap, fg_color="transparent")
        cascade_frame.pack(fill="x", padx=16, pady=(6, 0))

        _catalog: dict = {}  # Will hold {region: {zonas: {zona: {secciones: [...]}}}}
        region_var = ctk.StringVar(value="")
        zona_var = ctk.StringVar(value="")
        seccion_var = ctk.StringVar(value="")
        selected_keys: list[str] = []  # composite keys like "01_1211_H"

        ctk.CTkLabel(cascade_frame, text="Región", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        region_menu = ctk.CTkOptionMenu(cascade_frame, variable=region_var,
                                        values=["—"], font=font(11), height=30,
                                        width=100, corner_radius=6,
                                        fg_color="#F1F5F9", button_color=ACCENT,
                                        text_color=TEXT_PRIMARY,
                                        command=lambda _: _on_region_change())
        region_menu.grid(row=1, column=0, padx=(0, 6))

        ctk.CTkLabel(cascade_frame, text="Zona", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="w")
        zona_menu = ctk.CTkOptionMenu(cascade_frame, variable=zona_var,
                                      values=["—"], font=font(11), height=30,
                                      width=100, corner_radius=6,
                                      fg_color="#F1F5F9", button_color=ACCENT,
                                      text_color=TEXT_PRIMARY,
                                      command=lambda _: _on_zona_change())
        zona_menu.grid(row=1, column=1, padx=(0, 6))

        ctk.CTkLabel(cascade_frame, text="Sección", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=2, sticky="w")
        seccion_menu = ctk.CTkOptionMenu(cascade_frame, variable=seccion_var,
                                         values=["—"], font=font(11), height=30,
                                         width=80, corner_radius=6,
                                         fg_color="#F1F5F9", button_color=ACCENT,
                                         text_color=TEXT_PRIMARY)
        seccion_menu.grid(row=1, column=2, padx=(0, 6))

        add_sec_btn = ctk.CTkButton(cascade_frame, text="+ Agregar", font=font(10, "bold"),
                                    height=30, width=90, corner_radius=6,
                                    fg_color=SUCCESS, hover_color=SUCCESS_HOVER)
        add_sec_btn.grid(row=1, column=3, padx=(4, 0))

        # Chips display for selected sections
        chips_frame = ctk.CTkFrame(sec_wrap, fg_color="#F8FAFC", corner_radius=8,
                                   border_width=1, border_color=BORDER)
        chips_frame.pack(fill="x", padx=16, pady=(6, 0))
        chips_placeholder = ctk.CTkLabel(chips_frame, text="  Ninguna sección seleccionada",
                                         font=font(10), text_color=TEXT_MUTED)
        chips_placeholder.pack(padx=8, pady=6, anchor="w")

        def _paint_chips():
            for w in chips_frame.winfo_children():
                w.destroy()
            if not selected_keys:
                ctk.CTkLabel(chips_frame, text="  Ninguna sección seleccionada",
                             font=font(10), text_color=TEXT_MUTED).pack(padx=8, pady=6, anchor="w")
                return
            row = ctk.CTkFrame(chips_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=4)
            for key in selected_keys:
                chip = ctk.CTkFrame(row, fg_color=ACCENT_LIGHT, corner_radius=6)
                chip.pack(side="left", padx=2, pady=2)
                parts = key.split("_")
                if len(parts) == 3:
                    lbl = f"R{parts[0]} Z{parts[1]} S{parts[2]}"
                else:
                    lbl = key
                ctk.CTkLabel(chip, text=f" {lbl} ", font=font(10, "bold"),
                             text_color=ACCENT).pack(side="left", padx=(6, 0))
                ctk.CTkButton(chip, text="✕", font=font(9), width=20, height=20,
                              fg_color="transparent", hover_color=DANGER,
                              text_color=DANGER, corner_radius=4,
                              command=lambda k=key: _remove_chip(k)).pack(side="left", padx=(0, 2))

        refresh_territory_tree = self._mount_assigned_territory_panel(
            sec_wrap, selected_keys, _paint_chips,
        )

        def _render_chips():
            _paint_chips()
            refresh_territory_tree()

        def _remove_chip(key):
            if key in selected_keys:
                selected_keys[:] = remove_seccion(selected_keys, key)
                _render_chips()

        def _add_section():
            r = region_var.get()
            z = zona_var.get()
            s = seccion_var.get()
            if r == "—" or z == "—" or s == "—":
                return
            key = f"{r}_{z}_{s}"
            if key not in selected_keys:
                selected_keys.append(key)
                _render_chips()

        add_sec_btn.configure(command=_add_section)

        def _on_region_change():
            r = region_var.get()
            zona_var.set("—")
            seccion_var.set("—")
            seccion_menu.configure(values=["—"])
            if r == "—" or r not in _catalog:
                zona_menu.configure(values=["—"])
                return
            zonas = sorted(_catalog[r].get("zonas", {}).keys())
            zona_menu.configure(values=zonas if zonas else ["—"])
            if zonas:
                zona_var.set(zonas[0])
                _on_zona_change()

        def _on_zona_change():
            r = region_var.get()
            z = zona_var.get()
            seccion_var.set("—")
            if r == "—" or z == "—" or r not in _catalog:
                seccion_menu.configure(values=["—"])
                return
            secs = _catalog[r].get("zonas", {}).get(z, {}).get("secciones", [])
            seccion_menu.configure(values=secs if secs else ["—"])
            if secs:
                seccion_var.set(secs[0])

        def _load_catalog():
            load_cat_btn.configure(state="disabled", text="Cargando…")
            sec_status.configure(text="Consultando catálogo territorial…")

            def work():
                cat = self.app.firebase.get_estructura_territorial()
                dialog.after(0, lambda: _populate_catalog(cat))

            threading.Thread(target=work, daemon=True).start()

        def _populate_catalog(cat):
            load_cat_btn.configure(state="normal", text="⟳ Cargar catálogo")
            _catalog.clear()
            _catalog.update(cat)

            if not cat:
                sec_status.configure(
                    text="Catálogo vacío. Suba un Excel y distribúyalo primero.",
                    text_color=DANGER)
                region_menu.configure(values=["—"])
                return

            regions = sorted(cat.keys())
            total_sec = sum(
                len(zdata.get("secciones", []))
                for rdata in cat.values()
                for zdata in rdata.get("zonas", {}).values()
            )
            sec_status.configure(
                text=f"{len(regions)} regiones, {total_sec} secciones en catálogo:",
                text_color=TEXT_SECONDARY)
            region_menu.configure(values=regions)
            region_var.set(regions[0])
            _on_region_change()

        load_cat_btn.configure(command=_load_catalog)

        # ── Manual entry (fallback) ───────────────────────────
        ctk.CTkLabel(sec_wrap, text="O ingresa manualmente:", font=font(10),
                     text_color=TEXT_MUTED).pack(padx=16, anchor="w", pady=(8, 0))

        manual_row = ctk.CTkFrame(sec_wrap, fg_color="transparent")
        manual_row.pack(fill="x", padx=16, pady=(2, 0))
        manual_fields = {}
        for col, (k, placeholder, w) in enumerate([
                ("region", "Región", 70), ("zona", "Zona", 90), ("seccion", "Sec.", 60)]):
            ctk.CTkLabel(manual_row, text=k.capitalize(), font=font(9),
                         text_color=TEXT_MUTED).grid(row=0, column=col*2, padx=(0 if col==0 else 6, 0), sticky="w")
            e = ctk.CTkEntry(manual_row, font=font(11), height=30, width=w,
                             corner_radius=6, border_color=BORDER,
                             placeholder_text=placeholder)
            e.grid(row=1, column=col*2, padx=(0 if col==0 else 6, 0))
            manual_fields[k] = e

        def _apply_manual():
            r = manual_fields["region"].get().strip()
            z = manual_fields["zona"].get().strip()
            s = manual_fields["seccion"].get().strip().upper()
            if r and z and s:
                key = f"{r}_{z}_{s}"
                if key not in selected_keys:
                    selected_keys.append(key)
                    _render_chips()

        ctk.CTkButton(manual_row, text="+ Agregar", font=font(10),
                      height=30, width=80, corner_radius=6,
                      fg_color=INFO, hover_color="#2563EB",
                      command=_apply_manual).grid(row=1, column=6, padx=(10, 0))

        # ── Error label ───────────────────────────────────────
        msg_lbl = ctk.CTkLabel(scroll, text="", font=font(11), text_color=DANGER,
                               wraplength=400)
        msg_lbl.pack(padx=16, pady=(4, 8))

        # ── Register button (outside scroll, always visible) ──
        btn_save = ctk.CTkButton(dialog, text="Registrar Usuario", font=font(13, "bold"),
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                 height=42, corner_radius=10)
        btn_save.pack(fill="x", padx=16, pady=(8, 14))

        def save():
            vals = {k: e.get().strip() for k, e in fields.items()}
            if not vals["nombre"] or not vals["email"] or not vals["password"]:
                msg_lbl.configure(text="Nombre, email y contraseña son obligatorios")
                return

            is_admin_role = role_var.get() in ("admin", "supervisor")
            is_call = role_var.get() == "gestor" and canal_var.get() == "call"

            if not selected_keys and not is_admin_role and not is_call:
                msg_lbl.configure(text="Selecciona al menos una sección o ingrésala manualmente")
                return

            # Derive region/zona/seccion from first selected key for backward compat
            region, zona, seccion = legacy_fields_from_secciones(selected_keys)
            btn_save.configure(state="disabled", text="Creando…")

            def do_create():
                result = self.app.firebase.create_gestor_user(
                    email=vals["email"], password=vals["password"],
                    nombre=vals["nombre"],
                    seccion=seccion,
                    telefono=vals.get("telefono", ""),
                    zona=zona, region=region, rol=role_var.get(),
                    secciones=selected_keys if selected_keys else None,
                    canal=canal_var.get() if role_var.get() == "gestor" else "campo",
                )
                dialog.after(0, lambda: on_result(result))

            def on_result(result):
                btn_save.configure(state="normal", text="Registrar Usuario")
                if result["success"]:
                    dialog.destroy()
                    self._load_users()
                else:
                    msg_lbl.configure(text=f"Error: {result['error']}")

            threading.Thread(target=do_create, daemon=True).start()

        btn_save.configure(command=save)

        # Auto-load catalog on open
        dialog.after(400, _load_catalog)

    def _edit_user(self, user_data):
        uid = user_data.get("uid") or user_data.get("id", "")
        if not uid:
            return

        dialog = ctk.CTkToplevel(self._container)
        dialog.title(f"Editar — {user_data.get('nombre', '')}")
        dialog.geometry("480x720")
        dialog.configure(fg_color=BG)
        dialog.transient(self._container.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, True)

        # Title
        ctk.CTkLabel(dialog, text="Editar Usuario",
                     font=font(15, "bold"), text_color=TEXT_PRIMARY).pack(padx=20, pady=(14, 0))
        ctk.CTkLabel(dialog, text=f"UID: {uid[:24]}{'…' if len(uid)>24 else ''}",
                     font=font(9), text_color=TEXT_MUTED).pack(padx=20)

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(dialog, fg_color=CARD_BG, corner_radius=12,
                                        border_width=1, border_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=16, pady=(8, 0))

        # ── Basic fields ──────────────────────────────────────
        fields = {}
        for key, label, default, readonly in [
            ("nombre", "Nombre", user_data.get("nombre", ""), False),
            ("email", "Email (solo lectura)", user_data.get("email", ""), True),
            ("telefono", "Teléfono", user_data.get("telefono", ""), False),
            ("password", "Nueva contraseña (vacío = sin cambio)", "", False),
        ]:
            ctk.CTkLabel(scroll, text=label, font=font(11),
                         text_color=TEXT_SECONDARY).pack(padx=16, anchor="w", pady=(6, 0))
            entry = ctk.CTkEntry(scroll, font=font(12), height=34,
                                 corner_radius=8, border_color=BORDER)
            if key == "password":
                entry.configure(show="*", placeholder_text="Sin cambios")
            elif readonly:
                entry.configure(state="disabled")
            if default:
                entry.insert(0, default)
            entry.pack(fill="x", padx=16, pady=(2, 0))
            fields[key] = entry

        # ── Role + Active ─────────────────────────────────────
        ctk.CTkLabel(scroll, text="Rol", font=font(11),
                     text_color=TEXT_SECONDARY).pack(padx=16, anchor="w", pady=(8, 0))
        role_var = ctk.StringVar(value=user_data.get("rol", "gestor"))
        ctk.CTkOptionMenu(scroll, variable=role_var,
                          values=["gestor", "asistente", "supervisor", "admin"],
                          font=font(12), height=34, corner_radius=8,
                          fg_color="#F1F5F9", button_color=ACCENT,
                          text_color=TEXT_PRIMARY).pack(fill="x", padx=16, pady=(2, 0))

        activo_var = ctk.BooleanVar(value=user_data.get("activo", True))
        ctk.CTkCheckBox(scroll, text="Cuenta activa", variable=activo_var,
                        font=font(12), fg_color=ACCENT).pack(padx=16, pady=(8, 0), anchor="w")

        # ── Cascade Section Picker (Multi-select) ─────────────
        separator = ctk.CTkFrame(scroll, height=1, fg_color=BORDER)
        separator.pack(fill="x", padx=16, pady=(14, 0))

        # Determine currently assigned composite keys
        existing_secciones = user_data.get("secciones") or []
        current_keys: list[str] = []
        if isinstance(existing_secciones, list):
            current_keys = [k for k in existing_secciones if isinstance(k, str)]
        if not current_keys and user_data.get("region") and user_data.get("zona") and user_data.get("seccion"):
            current_keys = [f"{user_data['region']}_{user_data['zona']}_{user_data['seccion'].upper()}"]

        sec_header = ctk.CTkFrame(scroll, fg_color="transparent")
        sec_header.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(sec_header, text="Secciones asignadas", font=font(12, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        load_cat_btn = ctk.CTkButton(sec_header, text="⟳ Cargar catálogo",
                                     font=font(10), height=26, width=130,
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     corner_radius=6)
        load_cat_btn.pack(side="right")

        sec_status = ctk.CTkLabel(scroll, text="Presiona 'Cargar catálogo' para ver Regiones/Zonas/Secciones.",
                                  font=font(10), text_color=TEXT_MUTED,
                                  wraplength=400, justify="left")
        sec_status.pack(padx=16, anchor="w", pady=(4, 0))

        # Cascade dropdowns
        cascade_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        cascade_frame.pack(fill="x", padx=16, pady=(6, 0))

        _catalog: dict = {}
        region_var2 = ctk.StringVar(value="")
        zona_var2 = ctk.StringVar(value="")
        seccion_var2 = ctk.StringVar(value="")
        selected_keys: list[str] = list(current_keys)

        ctk.CTkLabel(cascade_frame, text="Región", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        region_menu = ctk.CTkOptionMenu(cascade_frame, variable=region_var2,
                                        values=["—"], font=font(11), height=30,
                                        width=100, corner_radius=6,
                                        fg_color="#F1F5F9", button_color=ACCENT,
                                        text_color=TEXT_PRIMARY,
                                        command=lambda _: _on_region_change())
        region_menu.grid(row=1, column=0, padx=(0, 6))

        ctk.CTkLabel(cascade_frame, text="Zona", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="w")
        zona_menu = ctk.CTkOptionMenu(cascade_frame, variable=zona_var2,
                                      values=["—"], font=font(11), height=30,
                                      width=100, corner_radius=6,
                                      fg_color="#F1F5F9", button_color=ACCENT,
                                      text_color=TEXT_PRIMARY,
                                      command=lambda _: _on_zona_change())
        zona_menu.grid(row=1, column=1, padx=(0, 6))

        ctk.CTkLabel(cascade_frame, text="Sección", font=font(10),
                     text_color=TEXT_MUTED).grid(row=0, column=2, sticky="w")
        seccion_menu = ctk.CTkOptionMenu(cascade_frame, variable=seccion_var2,
                                         values=["—"], font=font(11), height=30,
                                         width=80, corner_radius=6,
                                         fg_color="#F1F5F9", button_color=ACCENT,
                                         text_color=TEXT_PRIMARY)
        seccion_menu.grid(row=1, column=2, padx=(0, 6))

        add_sec_btn = ctk.CTkButton(cascade_frame, text="+ Agregar", font=font(10, "bold"),
                                    height=30, width=90, corner_radius=6,
                                    fg_color=SUCCESS, hover_color=SUCCESS_HOVER)
        add_sec_btn.grid(row=1, column=3, padx=(4, 0))

        # Chips display
        chips_frame = ctk.CTkFrame(scroll, fg_color="#F8FAFC", corner_radius=8,
                                   border_width=1, border_color=BORDER)
        chips_frame.pack(fill="x", padx=16, pady=(6, 0))

        def _paint_chips():
            for w in chips_frame.winfo_children():
                w.destroy()
            if not selected_keys:
                ctk.CTkLabel(chips_frame, text="  Ninguna sección seleccionada",
                             font=font(10), text_color=TEXT_MUTED).pack(padx=8, pady=6, anchor="w")
                return
            row = ctk.CTkFrame(chips_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=4)
            for key in selected_keys:
                chip = ctk.CTkFrame(row, fg_color=ACCENT_LIGHT, corner_radius=6)
                chip.pack(side="left", padx=2, pady=2)
                parts = key.split("_")
                if len(parts) == 3:
                    lbl = f"R{parts[0]} Z{parts[1]} S{parts[2]}"
                else:
                    lbl = key
                ctk.CTkLabel(chip, text=f" {lbl} ", font=font(10, "bold"),
                             text_color=ACCENT).pack(side="left", padx=(6, 0))
                ctk.CTkButton(chip, text="✕", font=font(9), width=20, height=20,
                              fg_color="transparent", hover_color=DANGER,
                              text_color=DANGER, corner_radius=4,
                              command=lambda k=key: _remove_chip(k)).pack(side="left", padx=(0, 2))

        is_call_user = (
            user_data.get("rol") == "gestor" and user_data.get("canal") == "call"
        )
        refresh_territory_tree = (lambda: None)
        if not is_call_user:
            refresh_territory_tree = self._mount_assigned_territory_panel(
                scroll, selected_keys, _paint_chips,
            )

        def _render_chips():
            _paint_chips()
            refresh_territory_tree()

        def _remove_chip(key):
            if key in selected_keys:
                selected_keys[:] = remove_seccion(selected_keys, key)
                _render_chips()

        def _add_section():
            r = region_var2.get()
            z = zona_var2.get()
            s = seccion_var2.get()
            if r == "—" or z == "—" or s == "—":
                return
            key = f"{r}_{z}_{s}"
            if key not in selected_keys:
                selected_keys.append(key)
                _render_chips()

        add_sec_btn.configure(command=_add_section)

        def _on_region_change():
            r = region_var2.get()
            zona_var2.set("—")
            seccion_var2.set("—")
            seccion_menu.configure(values=["—"])
            if r == "—" or r not in _catalog:
                zona_menu.configure(values=["—"])
                return
            zonas = sorted(_catalog[r].get("zonas", {}).keys())
            zona_menu.configure(values=zonas if zonas else ["—"])
            if zonas:
                zona_var2.set(zonas[0])
                _on_zona_change()

        def _on_zona_change():
            r = region_var2.get()
            z = zona_var2.get()
            seccion_var2.set("—")
            if r == "—" or z == "—" or r not in _catalog:
                seccion_menu.configure(values=["—"])
                return
            secs = _catalog[r].get("zonas", {}).get(z, {}).get("secciones", [])
            seccion_menu.configure(values=secs if secs else ["—"])
            if secs:
                seccion_var2.set(secs[0])

        def _load_catalog():
            load_cat_btn.configure(state="disabled", text="Cargando…")

            def work():
                cat = self.app.firebase.get_estructura_territorial()
                dialog.after(0, lambda: _populate_catalog(cat))

            threading.Thread(target=work, daemon=True).start()

        def _populate_catalog(cat):
            load_cat_btn.configure(state="normal", text="⟳ Cargar catálogo")
            _catalog.clear()
            _catalog.update(cat)

            if not cat:
                sec_status.configure(
                    text="Catálogo vacío. Suba un Excel y distribúyalo primero.",
                    text_color=DANGER)
                region_menu.configure(values=["—"])
                return

            regions = sorted(cat.keys())
            total_sec = sum(
                len(zdata.get("secciones", []))
                for rdata in cat.values()
                for zdata in rdata.get("zonas", {}).values()
            )
            sec_status.configure(
                text=f"{len(regions)} regiones, {total_sec} secciones en catálogo:",
                text_color=TEXT_SECONDARY)
            region_menu.configure(values=regions)
            region_var2.set(regions[0])
            _on_region_change()

        load_cat_btn.configure(command=_load_catalog)

        # Render initial chips from existing data
        _render_chips()

        # ── Manual fallback ───────────────────────────────────
        ctk.CTkLabel(scroll, text="O agrega manualmente (Región_Zona_Sección):",
                     font=font(10), text_color=TEXT_MUTED).pack(padx=16, anchor="w", pady=(8, 0))
        manual_row = ctk.CTkFrame(scroll, fg_color="transparent")
        manual_row.pack(fill="x", padx=16, pady=(2, 0))
        manual_fields = {}
        r_val = user_data.get("region", "")
        z_val = user_data.get("zona", "")
        s_val = user_data.get("seccion", "").upper()
        for col, (k, placeholder, default, w) in enumerate([
                ("region", "Región", r_val, 70),
                ("zona", "Zona", z_val, 90),
                ("seccion", "Sec.", s_val, 60)]):
            ctk.CTkLabel(manual_row, text=k.capitalize(), font=font(9),
                         text_color=TEXT_MUTED).grid(row=0, column=col*2, padx=(0 if col==0 else 6, 0), sticky="w")
            e = ctk.CTkEntry(manual_row, font=font(11), height=30, width=w,
                             corner_radius=6, border_color=BORDER)
            if default:
                e.insert(0, default)
            e.grid(row=1, column=col*2, padx=(0 if col==0 else 6, 0))
            manual_fields[k] = e

        def _apply_manual():
            r = manual_fields["region"].get().strip()
            z = manual_fields["zona"].get().strip()
            s = manual_fields["seccion"].get().strip().upper()
            if r and z and s:
                key = f"{r}_{z}_{s}"
                if key not in selected_keys:
                    selected_keys.append(key)
                    _render_chips()

        ctk.CTkButton(manual_row, text="+ Agregar", font=font(10),
                      height=30, width=80, corner_radius=6,
                      fg_color=INFO, hover_color="#2563EB",
                      command=_apply_manual).grid(row=1, column=6, padx=(10, 0))

        msg_lbl = ctk.CTkLabel(scroll, text="", font=font(11), text_color=DANGER,
                               wraplength=400)
        msg_lbl.pack(padx=16, pady=(4, 8))

        # ── Save button (always visible, outside scroll) ───────
        btn_update = ctk.CTkButton(dialog, text="Guardar Cambios", font=font(13, "bold"),
                                   fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                   height=42, corner_radius=10)
        btn_update.pack(fill="x", padx=16, pady=(8, 14))

        def save():
            updates = {}
            for key in ("nombre", "telefono"):
                val = fields[key].get().strip()
                if val != user_data.get(key, ""):
                    updates[key] = val
            if role_var.get() != user_data.get("rol", "gestor"):
                updates["rol"] = role_var.get()
            if activo_var.get() != user_data.get("activo", True):
                updates["activo"] = activo_var.get()
            pw = fields["password"].get().strip()
            if pw:
                updates["password"] = pw

            # Section updates from multi-select
            if sorted(selected_keys) != sorted(current_keys):
                rol = role_var.get()
                is_call = (
                    rol == "gestor" and user_data.get("canal", "campo") == "call"
                )
                needs_sections = (
                    rol == "asistente"
                    or (rol == "gestor" and not is_call)
                )
                if needs_sections and not selected_keys:
                    msg_lbl.configure(
                        text="Gestores de campo y asistentes requieren al menos una sección."
                    )
                    return
                updates["secciones"] = sorted(selected_keys)
                region, zona, seccion = legacy_fields_from_secciones(selected_keys)
                updates["region"] = region
                updates["zona"] = zona
                updates["seccion"] = seccion

            if not updates:
                msg_lbl.configure(text="No hay cambios")
                return

            btn_update.configure(state="disabled", text="Guardando…")

            def do_update():
                result = self.app.firebase.update_user(uid, updates)
                dialog.after(0, lambda: on_result(result))

            def on_result(result):
                btn_update.configure(state="normal", text="Guardar Cambios")
                if result["success"]:
                    dialog.destroy()
                    self._load_users()
                else:
                    msg_lbl.configure(text=f"Error: {result['error']}")

            threading.Thread(target=do_update, daemon=True).start()

        btn_update.configure(command=save)
        dialog.after(400, _load_catalog)

    def _delete_user(self, uid, name):
        if not messagebox.askyesno("Confirmar",
                                   f"¿Eliminar al usuario {name}?"):
            return

        def do_del():
            ok = self.app.firebase.delete_gestor_user(uid)
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._load_users())
        threading.Thread(target=do_del, daemon=True).start()

    # ── Distribution Tab ──────────────────────────────────────
    def _render_distribution(self):
        for w in self._content.winfo_children():
            w.destroy()

        if not self.app.parsed_data:
            card = ctk.CTkFrame(self._content, fg_color=CARD_BG, corner_radius=10,
                                border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=20, padx=20)
            ctk.CTkLabel(card, text="📂  Sin datos de campaña",
                         font=font(FONT_SCALE['base'], "bold"), text_color=TEXT_PRIMARY
                         ).pack(pady=(20, 4))
            ctk.CTkLabel(card, text="Cargue un archivo Excel primero para configurar la distribución.",
                         font=font(FONT_SCALE['sm']), text_color=TEXT_SECONDARY
                         ).pack(pady=(0, 20))
            return

        from services.excel_parser import get_hierarchy, make_seccion_key as _mk_key

        # Save button
        save_btn = ctk.CTkButton(
            self._content, text="💾 Guardar Asignaciones", font=font(FONT_SCALE['sm'], "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            height=36, width=200, corner_radius=8,
            command=lambda: self._save_assignments(save_btn))
        save_btn.pack(anchor="w", pady=(0, 12))

        hierarchy = get_hierarchy(self.app.parsed_data["all_clients"])

        gestor_options = ["Sin asignar"]
        gestor_uid_map: dict[str, str | None] = {"Sin asignar": None}
        for g in sorted(self._gestores, key=lambda x: x.get("nombre", "")):
            if g.get("canal") == "call":
                continue
            uid = g.get("uid") or g.get("id", "")
            label = f"{g.get('nombre', '?')}  ({g.get('email', '')})"
            gestor_options.append(label)
            gestor_uid_map[label] = uid

        uid_to_label = {v: k for k, v in gestor_uid_map.items() if v}
        self._section_vars = {}
        self._uid_map = gestor_uid_map

        # Collect all items to render (region headers, zone headers, section rows)
        render_queue: list[tuple] = []  # ("region"|"zona"|"sec", ...)
        for region_key, region_data in sorted(hierarchy["regions"].items()):
            render_queue.append(("region", region_key))
            for zona_key, zona_data in sorted(region_data["zonas"].items()):
                render_queue.append(("zona", region_key, zona_key))
                for sec_key, sec_data in sorted(zona_data["secciones"].items()):
                    composite = _mk_key(region_key, zona_key, sec_key)
                    render_queue.append(("sec", region_key, zona_key, sec_key,
                                         sec_data, composite))

        # Show loading hint
        loading_lbl = ctk.CTkLabel(self._content,
                                   text=f"Cargando {len(render_queue)} elementos…",
                                   font=font(FONT_SCALE['sm']), text_color=TEXT_MUTED)
        loading_lbl.pack(pady=8)

        self._dist_batch(render_queue, 0, gestor_options, uid_to_label, loading_lbl)

    # ── Batch render for distribution ─────────────────────────
    def _dist_batch(self, queue, idx, gestor_options, uid_to_label, loading_lbl):
        if not self._content.winfo_exists():
            return
        # Destroy loading label on first frame
        if idx == 0 and loading_lbl.winfo_exists():
            loading_lbl.destroy()

        batch = 8
        end = min(idx + batch, len(queue))
        for i in range(idx, end):
            item = queue[i]
            kind = item[0]
            if kind == "region":
                region_key = item[1]
                r_frame = ctk.CTkFrame(self._content, fg_color=ACCENT_LIGHT,
                                       corner_radius=8, border_width=1,
                                       border_color=ACCENT_MUTED)
                r_frame.pack(fill="x", pady=(8, 2))
                r_inner = ctk.CTkFrame(r_frame, fg_color="transparent")
                r_inner.pack(fill="x", padx=14, pady=6)
                ctk.CTkLabel(r_inner, text=f"🗺️  Región {region_key}",
                             font=font(FONT_SCALE['base'], "bold"),
                             text_color=ACCENT).pack(side="left")

            elif kind == "zona":
                _, region_key, zona_key = item
                z_frame = ctk.CTkFrame(self._content, fg_color="#F0FDFA",
                                       corner_radius=8, border_width=1,
                                       border_color="#99F6E4")
                z_frame.pack(fill="x", pady=(2, 1), padx=(20, 0))
                z_inner = ctk.CTkFrame(z_frame, fg_color="transparent")
                z_inner.pack(fill="x", padx=12, pady=5)
                ctk.CTkLabel(z_inner, text=f"Zona {zona_key}",
                             font=font(FONT_SCALE['sm'], "bold"),
                             text_color="#0D9488").pack(side="left")

            elif kind == "sec":
                _, region_key, zona_key, sec_key, sec_data, composite = item
                s_card = ctk.CTkFrame(self._content, fg_color=CARD_BG,
                                      corner_radius=6, border_width=1,
                                      border_color=BORDER)
                s_card.pack(fill="x", pady=1, padx=(40, 0))
                s_row = ctk.CTkFrame(s_card, fg_color="transparent")
                s_row.pack(fill="x", padx=10, pady=5)

                badge = ctk.CTkFrame(s_row, fg_color=ACCENT_LIGHT,
                                     corner_radius=4, width=26, height=26)
                badge.pack(side="left", padx=(0, 8))
                badge.pack_propagate(False)
                ctk.CTkLabel(badge, text=str(sec_key), font=font(FONT_SCALE['xs'], "bold"),
                             text_color=ACCENT).place(relx=0.5, rely=0.5, anchor="center")

                ctk.CTkLabel(s_row,
                             text=f"Sección {sec_key}  ·  "
                                  f"{sec_data['num_clientes']} clientes",
                             font=font(FONT_SCALE['sm']), text_color=TEXT_PRIMARY
                             ).pack(side="left")

                current_uid = self._assignments.get(composite)
                current_label = uid_to_label.get(current_uid, "Sin asignar")  # type: ignore
                var = ctk.StringVar(value=current_label)
                self._section_vars[composite] = var

                ctk.CTkOptionMenu(
                    s_row, variable=var, values=gestor_options,
                    font=font(FONT_SCALE['xs']), height=28, width=220, corner_radius=6,
                    fg_color="#F1F5F9", button_color=ACCENT,
                    text_color=TEXT_PRIMARY
                ).pack(side="right")

        if end < len(queue):
            self._content.after(1, lambda: self._dist_batch(
                queue, end, gestor_options, uid_to_label, loading_lbl))

    def _save_assignments(self, save_btn):
        save_btn.configure(state="disabled", text="Guardando…")

        # Only sections visible in Distribución (current Excel) are in scope.
        excel_keys = set(self._section_vars.keys())
        uid_to_keys: dict[str, list[str]] = {}
        for sec_key, var in self._section_vars.items():
            uid = self._uid_map.get(var.get())
            if uid:
                uid_to_keys.setdefault(uid, []).append(sec_key)

        def work():
            updated = 0
            # Merge scoped to Excel: keep sections outside excel_keys; never wipe
            # call gestors or users whose territory is entirely outside this Excel.
            for g in self._gestores:
                if g.get("canal") == "call":
                    continue
                uid = g.get("uid") or g.get("id", "")
                if not uid:
                    continue

                current = g.get("secciones") or []
                if not isinstance(current, list):
                    legacy = g.get("seccion", "")
                    current = [legacy] if legacy else []

                kept = [sk for sk in current if sk not in excel_keys]
                assigned = uid_to_keys.get(uid, [])
                keys_sorted = sorted(set(kept) | set(assigned))

                if keys_sorted == sorted(set(current)):
                    continue

                if keys_sorted:
                    r, z, s = legacy_fields_from_secciones(keys_sorted)
                    payload = {
                        "secciones": keys_sorted,
                        "seccion": s,
                        "region": r,
                        "zona": z,
                    }
                else:
                    payload = {
                        "secciones": [],
                        "seccion": "",
                        "region": "",
                        "zona": "",
                    }
                try:
                    self.app.firebase.update_user(uid, payload)
                    updated += 1
                except Exception:
                    pass

            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._save_done(save_btn, updated))

        threading.Thread(target=work, daemon=True).start()

    def _save_done(self, save_btn, updated):
        save_btn.configure(state="normal", text="Guardar Asignaciones")
        self._status_lbl.configure(
            text=f"Guardadas {updated} asignaciones", text_color=SUCCESS)
        self._load_users()
