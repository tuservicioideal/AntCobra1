"""
AntCobranzas Premium Design System
Enhanced visual design with gradients, shadows, and modern aesthetics.
"""
import customtkinter as ctk

# ── Appearance ───────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Remove DPI scaling to prevent Tkinter errors
# ctk.set_widget_scaling(1.0)  # Commented out to avoid command errors
# ctk.deactivate_automatic_dpi_awareness()  # Commented out to avoid issues

# ── Enhanced Color Palette ────────────────────────────────────────
# Sidebar (premium dark with gradients)
SIDEBAR_BG       = "#0F172A"
SIDEBAR_HOVER    = "#1E293B"
SIDEBAR_ACTIVE   = "#334155"
SIDEBAR_TEXT     = "#CBD5E1"
SIDEBAR_TEXT_ACT = "#FFFFFF"
SIDEBAR_DIVIDER  = "#334155"
SIDEBAR_GRADIENT_START = "#0F172A"
SIDEBAR_GRADIENT_END   = "#1E293B"

# Content area (enhanced)
BG               = "#F8FAFC"
CARD_BG          = "#FFFFFF"
CARD_SHADOW      = "#E2E8F0"
BORDER           = "#E2E8F0"
BORDER_FOCUS     = "#CBD5E1"
CARD_GRADIENT_START = "#FFFFFF"
CARD_GRADIENT_END   = "#F8FAFC"

# Enhanced Typography
TEXT_PRIMARY     = "#0F172A"
TEXT_SECONDARY   = "#475569"
TEXT_MUTED       = "#94A3B8"
TEXT_ACCENT      = "#1E293B"

# Premium Accent Colors
ACCENT           = "#3B82F6"
ACCENT_HOVER     = "#2563EB"
ACCENT_LIGHT     = "#EFF6FF"
ACCENT_MUTED     = "#DBEAFE"
ACCENT_GRADIENT_START = "#3B82F6"
ACCENT_GRADIENT_END   = "#1D4ED8"

# Enhanced Semantic Colors
SUCCESS          = "#10B981"
SUCCESS_HOVER    = "#059669"
SUCCESS_LIGHT    = "#ECFDF5"
SUCCESS_GRADIENT_START = "#10B981"
SUCCESS_GRADIENT_END   = "#047857"

WARNING          = "#F59E0B"
WARNING_HOVER    = "#D97706"
WARNING_LIGHT    = "#FFFBEB"
WARNING_GRADIENT_START = "#F59E0B"
WARNING_GRADIENT_END   = "#D97706"

DANGER           = "#EF4444"
DANGER_HOVER     = "#DC2626"
DANGER_LIGHT     = "#FEF2F2"
DANGER_GRADIENT_START = "#EF4444"
DANGER_GRADIENT_END   = "#DC2626"

INFO             = "#06B6D4"
INFO_LIGHT       = "#ECFEFF"
INFO_GRADIENT_START = "#06B6D4"
INFO_GRADIENT_END   = "#0891B2"

WHITE            = "#FFFFFF"
BLACK            = "#000000"

# ── Enhanced Typography ───────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

def font(size: int = 14, weight: str = "normal", family: str = FONT_FAMILY) -> ctk.CTkFont:
    """Enhanced font function with better defaults."""
    return ctk.CTkFont(family=family, size=size, weight=weight)

# Font scale for better readability
FONT_SCALE = {
    'xs': 10,   # Small labels
    'sm': 12,   # Body text
    'base': 14, # Default
    'lg': 16,   # Large text
    'xl': 18,   # Headings
    '2xl': 20,  # Big headings
    '3xl': 24,  # Hero text
    '4xl': 32,  # Display
}

# ── Enhanced Sidebar Config ───────────────────────────────────────
SIDEBAR_WIDTH = 220
SIDEBAR_ITEM_H = 36   # compact: all nav items visible without scrolling

# ── Enhanced Component Styles ─────────────────────────────────────
# Button styles
BUTTON_HEIGHT = 40
BUTTON_CORNER_RADIUS = 10

# Card styles
CARD_CORNER_RADIUS = 16
CARD_PADDING = 20

# Input styles
INPUT_HEIGHT = 40
INPUT_CORNER_RADIUS = 8

# ── Treeview Enhanced Styles ──────────────────────────────────────
def apply_treeview_style(style_name: str = "App.Treeview"):
    """Enhanced treeview with better styling."""
    from tkinter import ttk
    style = ttk.Style()
    style.theme_use("clam")

    # Configure the treeview
    style.configure(style_name,
                    background=CARD_BG,
                    foreground=TEXT_PRIMARY,
                    fieldbackground=CARD_BG,
                    font=(FONT_FAMILY, FONT_SCALE['sm']),
                    rowheight=36,  # Increased row height
                    borderwidth=0,
                    relief="flat")

    # Enhanced heading style
    style.configure(f"{style_name}.Heading",
                    background=ACCENT_LIGHT,
                    foreground=ACCENT,
                    font=(FONT_FAMILY, FONT_SCALE['sm'], "bold"),
                    borderwidth=0,
                    relief="flat",
                    padding=(10, 5))

    # Enhanced selection style
    style.map(style_name,
              background=[("selected", ACCENT_LIGHT)],
              foreground=[("selected", ACCENT)])

    # Add subtle border
    style.layout(style_name, [
        ('Treeview.field', {
            'border': '1',
            'children': [
                ('Treeview.padding', {
                    'children': [
                        ('Treeview.treearea', {'sticky': 'nswe'})
                    ],
                    'sticky': 'nswe'
                })
            ],
            'sticky': 'nswe'
        })
    ])

    return style_name

# ── Animation Helpers ─────────────────────────────────────────────
def animate_color_change(widget, start_color: str, end_color: str, duration: int = 300):
    """Simple color transition animation."""
    steps = 20
    step_duration = duration // steps

    def interpolate_color(color1, color2, factor):
        """Interpolate between two hex colors."""
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)

        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"

    def animate_step(step=0):
        if step <= steps:
            factor = step / steps
            current_color = interpolate_color(start_color, end_color, factor)
            widget.configure(fg_color=current_color)
            widget.after(step_duration, animate_step, step + 1)

    animate_step()

# ── Gradient Helper (for future use) ──────────────────────────────
def create_gradient_canvas(parent, width: int, height: int, start_color: str, end_color: str):
    """Create a canvas with gradient background (for advanced effects)."""
    from tkinter import Canvas

    canvas = Canvas(parent, width=width, height=height, highlightthickness=0)

    # Create gradient effect using rectangles
    for i in range(height):
        factor = i / height
        r1, g1, b1 = int(start_color[1:3], 16), int(start_color[3:5], 16), int(start_color[5:7], 16)
        r2, g2, b2 = int(end_color[1:3], 16), int(end_color[3:5], 16), int(end_color[5:7], 16)

        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        color = f"#{r:02x}{g:02x}{b:02x}"
        canvas.create_rectangle(0, i, width, i+1, fill=color, outline="")

    return canvas
