"""
Reusable UI components — AntCobranzas Premium Design System.
Enhanced with gradients, shadows, and modern styling.
"""
from __future__ import annotations
import customtkinter as ctk
from .theme import *


class KPICard(ctk.CTkFrame):
    """Clean KPI card with label, large value and optional accent color."""

    def __init__(self, parent, label: str, value: str, accent=None, **kw):
        accent = accent or ACCENT
        super().__init__(parent, corner_radius=12, fg_color=CARD_BG,
                         border_width=1, border_color=BORDER, **kw)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=16, pady=14, fill="both", expand=True)

        ctk.CTkLabel(inner, text=label, font=font(FONT_SCALE['sm']),
                     text_color=TEXT_SECONDARY).pack(anchor="w")

        self._val = ctk.CTkLabel(inner, text=value, font=font(FONT_SCALE['3xl'], "bold"),
                                 text_color=accent)
        self._val.pack(anchor="w", pady=(6, 0))

    def set(self, v: str):
        self._val.configure(text=v)


class SectionHeader(ctk.CTkFrame):
    """Enhanced section header with visual separator and better typography."""

    def __init__(self, parent, title: str, subtitle: str = "", icon: str = "", **kw):
        super().__init__(parent, fg_color="transparent", **kw)

        # Title with icon support
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(anchor="w", pady=(0, 4))

        if icon:
            icon_label = ctk.CTkLabel(title_frame, text=icon, font=font(FONT_SCALE['xl']),
                                      text_color=ACCENT)
            icon_label.pack(side="left", padx=(0, 8))

        title_text = ctk.CTkLabel(title_frame, text=title, font=font(FONT_SCALE['xl'], "bold"),
                                  text_color=TEXT_PRIMARY)
        title_text.pack(side="left")

        # Visual separator line
        separator = ctk.CTkFrame(self, fg_color=ACCENT_LIGHT, height=2, corner_radius=1)
        separator.pack(fill="x", pady=(4, 8))

        # Subtitle if provided
        if subtitle:
            subtitle_label = ctk.CTkLabel(self, text=subtitle, font=font(FONT_SCALE['base']),
                                          text_color=TEXT_SECONDARY, wraplength=600)
            subtitle_label.pack(anchor="w", pady=(0, 4))


class ActionButton(ctk.CTkButton):
    """Premium action button with gradient effects and enhanced hover states."""

    def __init__(self, parent, text: str, color=None, icon: str = "",
                 width: int = 180, height: int = BUTTON_HEIGHT, **kw):
        color = color or ACCENT
        hover = _darken(color)

        # Enhanced button with icon support
        label = f"{icon}  {text}" if icon else text

        super().__init__(parent, text=label, font=font(FONT_SCALE['base'], "bold"),
                         fg_color=color, hover_color=hover,
                         height=height, width=width, corner_radius=BUTTON_CORNER_RADIUS,
                         border_width=0, **kw)

        # Add subtle animation on click
        self.bind("<Button-1>", lambda e: self._animate_click())

    def _animate_click(self):
        """Quick scale animation on click."""
        original_color = self.cget("fg_color")
        self.configure(fg_color=_darken(original_color))
        self.after(100, lambda: self.configure(fg_color=original_color))


class EmptyState(ctk.CTkFrame):
    """Enhanced empty state with better visual hierarchy and call-to-action."""

    def __init__(self, parent, title: str, message: str, action_text: str = "",
                 action_command=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)

        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=60, padx=60)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=CARD_PADDING*2, pady=CARD_PADDING*2)

        # Icon placeholder (using emoji for now)
        icon_label = ctk.CTkLabel(content, text="📊", font=font(FONT_SCALE['4xl']))
        icon_label.pack(pady=(0, 16))

        # Enhanced title
        title_label = ctk.CTkLabel(content, text=title, font=font(FONT_SCALE['2xl'], "bold"),
                                   text_color=TEXT_PRIMARY)
        title_label.pack()

        # Enhanced message
        message_label = ctk.CTkLabel(content, text=message, font=font(FONT_SCALE['base']),
                                     text_color=TEXT_SECONDARY, wraplength=500)
        message_label.pack(pady=(12, 24))

        # Action button if provided
        if action_text and action_command:
            ActionButton(content, action_text, command=action_command).pack()


class StatusBadge(ctk.CTkFrame):
    """Enhanced status badge with better colors and animations."""

    def __init__(self, parent, text: str, color: str = ACCENT, size: str = "normal", **kw):
        height = 28 if size == "normal" else 24
        corner_radius = 8 if size == "normal" else 6

        super().__init__(parent, fg_color=color, corner_radius=corner_radius,
                         height=height, **kw)
        self.pack_propagate(False)

        font_size = FONT_SCALE['sm'] if size == "normal" else FONT_SCALE['xs']
        ctk.CTkLabel(self, text=text, font=font(font_size, "bold"),
                     text_color=WHITE).pack(padx=12, pady=4)


class ProgressCard(ctk.CTkFrame):
    """New component for progress visualization with enhanced styling."""

    def __init__(self, parent, title: str, current: int, total: int, color=None, **kw):
        color = color or ACCENT
        super().__init__(parent, corner_radius=CARD_CORNER_RADIUS, fg_color=CARD_BG,
                         border_width=1, border_color=BORDER, **kw)

        # Shadow
        shadow = ctk.CTkFrame(self, fg_color=CARD_SHADOW, corner_radius=CARD_CORNER_RADIUS)
        shadow.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

        inner = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=CARD_CORNER_RADIUS-2)
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)

        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.pack(padx=CARD_PADDING, pady=CARD_PADDING, fill="x")

        # Title
        ctk.CTkLabel(content, text=title, font=font(FONT_SCALE['base'], "bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", pady=(0, 8))

        # Progress percentage
        percentage = (current / total * 100) if total > 0 else 0
        pct_text = f"{percentage:.1f}%"

        # Progress bar with enhanced styling
        pb_frame = ctk.CTkFrame(content, fg_color="transparent")
        pb_frame.pack(fill="x", pady=(4, 8))

        self._progress = ctk.CTkProgressBar(pb_frame, width=300, height=8,
                                            progress_color=color, fg_color=BORDER,
                                            corner_radius=4)
        self._progress.pack(fill="x")
        self._progress.set(current / total if total > 0 else 0)

        # Stats
        stats_frame = ctk.CTkFrame(content, fg_color="transparent")
        stats_frame.pack(fill="x")

        ctk.CTkLabel(stats_frame, text=f"{current}/{total}", font=font(FONT_SCALE['sm']),
                     text_color=TEXT_SECONDARY).pack(side="left")
        ctk.CTkLabel(stats_frame, text=pct_text, font=font(FONT_SCALE['sm'], "bold"),
                     text_color=color).pack(side="right")


def tune_scrollable(frame: ctk.CTkScrollableFrame) -> None:
    """Apply smooth wheel-scroll tuning to any CTkScrollableFrame."""
    canvas = frame._parent_canvas
    # yscrollincrement=20 → each CTk "unit" scroll = 20 px → 3 units/notch = 60 px/notch
    # (matches the Windows default of ~3 text lines per notch).
    # highlightthickness=0 eliminates the focus-rectangle border repaint on every frame.
    canvas.configure(highlightthickness=0, yscrollincrement=20)
    canvas.bind("<MouseWheel>", lambda _e: canvas.update_idletasks(), add=True)


def scroll_to_top(frame: ctk.CTkScrollableFrame) -> None:
    """Reset a scrollable frame viewport to the top."""
    frame._parent_canvas.yview_moveto(0)
    frame._parent_canvas.update_idletasks()


class SmoothScrollableFrame(ctk.CTkScrollableFrame):
    """Scrollable frame with smooth wheel scrolling (for tab content, dialogs, etc.)."""

    def __init__(self, parent, **kw):
        defaults = {
            "fg_color": BG,
            "scrollbar_button_color": BORDER,
            "scrollbar_button_hover_color": ACCENT,
            "corner_radius": 0,
        }
        defaults.update(kw)
        super().__init__(parent, **defaults)
        tune_scrollable(self)

    def scroll_to_top(self):
        scroll_to_top(self)


class PageFrame(SmoothScrollableFrame):
    """Main content area — smooth scroll + clear helper."""

    def clear(self):
        for w in self.winfo_children():
            w.destroy()
        scroll_to_top(self)


# ── Enhanced Helpers ──────────────────────────────────────────────

def _darken(hex_color: str) -> str:
    """Enhanced color darkening with better algorithm."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.85
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


def _lighten(hex_color: str) -> str:
    """Lighten a hex color."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 1.15
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


class CampanaBancoFilterBar(ctk.CTkFrame):
    """
    Barra de filtro por número de campaña del banco (Excel col. E).
    Oculta si solo hay una campaña banco en la cartera.
    """

    def __init__(
        self,
        parent,
        available: list[str],
        selected: str | None = None,
        on_change=None,
        **kw,
    ):
        from services.campana_banco_utils import (
            SIN_CAMPANA_KEY,
            display_label_for_key,
            filter_bar_visible,
        )

        super().__init__(parent, fg_color="transparent", **kw)
        self._on_change = on_change
        self._selected = selected
        self._buttons: dict[str | None, ctk.CTkButton] = {}

        if not filter_bar_visible(available):
            return

        ctk.CTkLabel(
            self,
            text="Nº campaña banco:",
            font=font(FONT_SCALE["sm"], "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="left", fill="x", expand=True)

        options: list[tuple[str | None, str]] = [(None, "Todas")]
        for key in available:
            options.append((key, display_label_for_key(key)))

        for value, label in options:
            btn = ctk.CTkButton(
                row,
                text=label,
                height=28,
                font=font(FONT_SCALE["xs"]),
                fg_color=ACCENT if value == selected else BORDER,
                hover_color=ACCENT_HOVER if value == selected else ACCENT_LIGHT,
                text_color=WHITE if value == selected else TEXT_PRIMARY,
                corner_radius=14,
                command=lambda v=value: self._select(v),
            )
            btn.pack(side="left", padx=(0, 6), pady=2)
            self._buttons[value] = btn

    def _select(self, value: str | None):
        self._selected = value
        for v, btn in self._buttons.items():
            active = v == value
            btn.configure(
                fg_color=ACCENT if active else BORDER,
                hover_color=ACCENT_HOVER if active else ACCENT_LIGHT,
                text_color=WHITE if active else TEXT_PRIMARY,
            )
        if self._on_change:
            self._on_change(value)

    def get_selected(self) -> str | None:
        return self._selected


class CampaignTimelineCard(ctk.CTkFrame):
    """Tarjeta de línea de tiempo para una campaña banco."""

    def __init__(
        self,
        parent,
        timeline: dict,
        *,
        on_edit_dates=None,
        **kw,
    ):
        super().__init__(
            parent,
            fg_color=CARD_BG,
            corner_radius=CARD_CORNER_RADIUS,
            border_width=1,
            border_color=BORDER,
            **kw,
        )
        self._timeline = timeline
        self._on_edit_dates = on_edit_dates

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=CARD_PADDING, pady=CARD_PADDING)

        header_row = ctk.CTkFrame(content, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 8))
        header_row.grid_columnconfigure(0, weight=1)

        title_col = ctk.CTkFrame(header_row, fg_color="transparent")
        title_col.grid(row=0, column=0, sticky="w")

        label = timeline.get("label", "—")
        ctk.CTkLabel(
            title_col,
            text=f"📋 Campaña banco: {label}",
            font=font(FONT_SCALE["base"], "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        fi = timeline.get("fecha_inicio")
        ff = timeline.get("fecha_fin")
        fecha_txt = (
            f"{fi.strftime('%d/%m/%Y')} → {ff.strftime('%d/%m/%Y')}"
            if fi and ff else "—"
        )
        origen = "editadas manualmente" if timeline.get("es_manual") else "detectadas del Excel"
        ctk.CTkLabel(
            title_col,
            text=f"{fecha_txt}  ·  Fechas {origen}",
            font=font(FONT_SCALE["xs"]),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        dia = timeline.get("dia_actual", 1)
        duracion = timeline.get("duracion", 59)
        restantes = timeline.get("dias_restantes", 0)
        tramo_label = timeline.get("tramo_label", "N/A")
        cuentas = timeline.get("cuentas", 0)
        ctk.CTkLabel(
            title_col,
            text=(
                f"Día {dia} / {duracion}  ·  {tramo_label}  ·  "
                f"{restantes} días restantes  ·  {cuentas} cuentas"
            ),
            font=font(FONT_SCALE["sm"]),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        if on_edit_dates:
            ctk.CTkButton(
                header_row,
                text="✏️ Editar fechas",
                fg_color="transparent",
                border_width=1,
                border_color=ACCENT,
                text_color=ACCENT,
                hover_color=ACCENT_LIGHT,
                width=110,
                height=28,
                font=font(11),
                command=on_edit_dates,
            ).grid(row=0, column=1, sticky="e")

        from services.database import TramoEnum

        tramo = timeline.get("tramo")
        progress = dia / duracion if duracion else 0.0
        carta_days = timeline.get("carta_days") or [1, 9, 11, 35, 44]
        carta_labels = ["E1-1", "E1-2", "E2-1", "E2-2", "E3-1"]
        carta_colors = [ACCENT, ACCENT, WARNING, WARNING, DANGER]
        label_levels = [0, 1, 0, 1, 0]
        bounds = timeline.get("tramo_boundaries") or {
            1: (1, 10), 2: (11, 43), 3: (44, 59),
        }

        import tkinter as tk

        timeline_canvas = tk.Canvas(
            content, height=72, bg=CARD_BG, highlightthickness=0
        )
        timeline_canvas.pack(fill="x", pady=(4, 4))

        def _draw(event=None):
            timeline_canvas.delete("all")
            w = timeline_canvas.winfo_width()
            if w < 20:
                timeline_canvas.after(60, _draw)
                return
            bar_y, bar_h = 58, 8
            timeline_canvas.create_rectangle(
                0, bar_y - bar_h // 2, w, bar_y + bar_h // 2,
                fill=BORDER, outline="",
            )
            fill_w = max(bar_h, int(w * min(1.0, progress)))
            timeline_canvas.create_rectangle(
                0, bar_y - bar_h // 2, fill_w, bar_y + bar_h // 2,
                fill=ACCENT, outline="",
            )
            if duracion > 0:
                day_x = max(
                    bar_h,
                    min(w - bar_h, int(w * (dia - 0.5) / duracion)),
                )
                timeline_canvas.create_oval(
                    day_x - 6, bar_y - 6, day_x + 6, bar_y + 6,
                    fill=ACCENT, outline=CARD_BG, width=2,
                )
            for i2, (day, lbl2, color, level) in enumerate(
                zip(carta_days, carta_labels, carta_colors, label_levels)
            ):
                if duracion <= 0:
                    continue
                x = max(18, min(w - 18, int(w * (day - 0.5) / duracion)))
                lbl_y = 8 if level == 0 else 24
                timeline_canvas.create_line(
                    x, lbl_y + 12, x, bar_y - bar_h // 2 - 2,
                    fill=color, width=1, dash=(3, 2),
                )
                timeline_canvas.create_text(
                    x, lbl_y, text=lbl2,
                    fill=color, font=("Segoe UI", 9, "bold"), anchor="center",
                )
                dot_r = 4
                timeline_canvas.create_oval(
                    x - dot_r, bar_y - dot_r, x + dot_r, bar_y + dot_r,
                    fill=color, outline=CARD_BG, width=1,
                )

        timeline_canvas.bind("<Configure>", _draw)
        timeline_canvas.after(60, _draw)

        seg_frame = ctk.CTkFrame(content, fg_color="transparent")
        seg_frame.pack(fill="x", pady=(4, 0))
        seg_frame.grid_columnconfigure((0, 1, 2), weight=1)

        segments = [
            ("Tramo 1", bounds.get(1, (1, 10)), tramo == TramoEnum.TRAMO_1),
            ("Tramo 2", bounds.get(2, (11, 43)), tramo == TramoEnum.TRAMO_2),
            ("Tramo 3", bounds.get(3, (44, 59)), tramo == TramoEnum.TRAMO_3),
        ]
        for i3, (name, (s, e), active) in enumerate(segments):
            color = ACCENT if active else TEXT_MUTED
            wt = "bold" if active else "normal"
            ctk.CTkLabel(
                seg_frame,
                text=f"{name}  ·  Días {s}-{e}",
                font=font(FONT_SCALE["base"], wt),
                text_color=color,
            ).grid(row=0, column=i3, sticky="w", padx=8)
