"""GPS Tracking page — gestor field locations and routes."""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import math
from typing import TYPE_CHECKING
from ..theme import *
from ..components import KPICard, SectionHeader

if TYPE_CHECKING:
    from ..app import App

_SEC_COLORS = [
    "#6366F1", "#0D9488", "#D97706", "#DC2626", "#7C3AED",
    "#059669", "#E11D48", "#0891B2", "#B45309", "#3B82F6",
]
_TREE_BATCH = 80


class TrackingPage:
    """GPS tracking dashboard — gestor locations, routes and distances."""

    def __init__(self, app: App):
        self.app = app
        self._container = None
        self._auto_refresh = False
        self._after_id = None
        self._gestores: list = []
        self._selected_uid = None
        self._color_map: dict = {}
        self._detail_area = None
        self._kpi_widgets: list[KPICard] = []
        self._gestor_list = None
        self._refresh_btn = None
        self._status_lbl = None
        self._trail_tree = None

    def render(self, container: ctk.CTkScrollableFrame):
        for w in container.winfo_children():
            w.destroy()
        self._container = container
        self._auto_refresh = True
        self._after_id = None
        self._kpi_widgets = []

        if not self.app.firebase_connected:
            ctk.CTkFrame(container, fg_color="transparent", height=40).pack()
            ctk.CTkLabel(container, text="Conecte Firebase para ver el tracking GPS.",
                         font=font(14), text_color=TEXT_SECONDARY).pack(pady=20)
            return

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(8, 12))
        SectionHeader(hdr, "GPS Tracking",
                      "Ubicación de gestores en campo").pack(side="left")

        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(
            btn_frame, text="Ver Mapa Web", font=font(11, "bold"),
            fg_color=SUCCESS, hover_color=SUCCESS_HOVER,
            height=32, width=130, corner_radius=8,
            command=self._open_web_map
        ).pack(side="left", padx=(0, 6))

        self._refresh_btn = ctk.CTkButton(
            btn_frame, text="Actualizar", font=font(11, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=32, width=110, corner_radius=8,
            command=self._refresh)
        self._refresh_btn.pack(side="left")

        self._status_lbl = ctk.CTkLabel(container, text="Cargando GPS…",
                                        font=font(11), text_color=TEXT_SECONDARY)
        self._status_lbl.pack(padx=8, pady=4)

        # Two-panel layout
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=4)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        # Left: gestor list
        left = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER, width=280)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Gestores", font=font(13, "bold"),
                     text_color=TEXT_PRIMARY).pack(padx=12, pady=(12, 4), anchor="w")

        self._gestor_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._gestor_list.pack(fill="both", expand=True, padx=4, pady=4)

        # Right: detail
        right = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=12,
                             border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")

        kpi_frame = ctk.CTkFrame(right, fg_color="transparent", height=80)
        kpi_frame.pack(fill="x", padx=12, pady=(12, 4))
        kpi_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Create KPI placeholders once
        kpi_defs = [
            ("Gestor", "—", ACCENT),
            ("Sección", "—", "#0D9488"),
            ("Km Recorridos", "—", WARNING),
            ("Puntos", "—", INFO),
        ]
        self._kpi_widgets = []
        for i, (lbl, val, clr) in enumerate(kpi_defs):
            kw = KPICard(kpi_frame, lbl, val, clr)
            kw.grid(row=0, column=i, padx=3, sticky="nsew")
            self._kpi_widgets.append(kw)

        self._detail_area = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._detail_area.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkLabel(self._detail_area,
                     text="Seleccione un gestor para ver su recorrido",
                     font=font(13), text_color=TEXT_SECONDARY).pack(pady=40)

        self._refresh()

    def stop(self):
        self._auto_refresh = False
        if self._after_id and self._container and self._container.winfo_exists():
            try:
                self._container.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None

    def _open_web_map(self):
        import webbrowser
        webbrowser.open("https://clase-001.web.app")

    def _refresh(self):
        if not self._auto_refresh:
            return
        self._refresh_btn.configure(state="disabled", text="Cargando…")

        def work():
            gestores = self.app.firebase.get_tracking_summary()
            if self._container and self._container.winfo_exists():
                self._container.after(0, lambda: self._on_data(gestores))

        threading.Thread(target=work, daemon=True).start()

    def _on_data(self, gestores):
        self._gestores = gestores
        try:
            if self._refresh_btn.winfo_exists():
                self._refresh_btn.configure(state="normal", text="Actualizar")
        except Exception:
            pass

        secciones = sorted(set(g.get("seccion", "?") for g in gestores))
        self._color_map = {s: _SEC_COLORS[i % len(_SEC_COLORS)]
                           for i, s in enumerate(secciones)}

        # Rebuild gestor list only if contents changed
        new_uids = sorted(g.get("uid", "") for g in gestores)
        old_uids = getattr(self, "_prev_uids", None)
        if new_uids != old_uids:
            self._prev_uids = new_uids
            self._rebuild_gestor_list(gestores)
        # else: keep existing list intact — no flicker

        if not gestores:
            self._status_lbl.configure(
                text="Sin datos de tracking disponibles", text_color=TEXT_SECONDARY)
        else:
            self._status_lbl.configure(
                text=f"{len(gestores)} gestores con GPS", text_color=SUCCESS)

        if self._auto_refresh and self._container and self._container.winfo_exists():
            self._after_id = self._container.after(30000, self._refresh)

    def _rebuild_gestor_list(self, gestores):
        for w in self._gestor_list.winfo_children():
            w.destroy()

        if not gestores:
            ctk.CTkLabel(self._gestor_list, text="Sin datos GPS",
                         font=font(11), text_color=TEXT_SECONDARY).pack(pady=20)
            return

        for g in sorted(gestores, key=lambda x: x.get("seccion", "")):
            uid = g.get("uid", "")
            nombre = g.get("gestor_nombre", "") or uid[:8]
            seccion = g.get("seccion", "?")
            color = self._color_map.get(seccion, ACCENT)

            card = ctk.CTkFrame(self._gestor_list, fg_color="transparent",
                                cursor="hand2")
            card.pack(fill="x", pady=2)

            badge = ctk.CTkFrame(card, fg_color=color, corner_radius=5,
                                 width=26, height=26)
            badge.pack(side="left", padx=(4, 8))
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=seccion[:2], font=font(10, "bold"),
                         text_color=WHITE).place(relx=0.5, rely=0.5, anchor="center")

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=nombre, font=font(11, "bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="w")

            for widget in [card, info]:
                widget.bind("<Button-1>",
                            lambda e, _uid=uid: self._select_gestor(_uid))

    def _select_gestor(self, uid):
        self._selected_uid = uid
        for w in self._detail_area.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail_area, text="Cargando recorrido…",
                     font=font(12), text_color=TEXT_SECONDARY).pack(pady=20)

        def work():
            points = self.app.firebase.get_tracking_points(uid, limit=300)
            # Pre-compute distances and row data on worker thread
            prepared = self._prepare_trail(uid, points)
            if self._container and self._container.winfo_exists():
                self._container.after(
                    0, lambda: self._render_trail(uid, points, prepared))

        threading.Thread(target=work, daemon=True).start()

    def _prepare_trail(self, uid, points) -> dict:
        """Heavy computation off the main thread."""
        total_km = 0.0
        rows = []
        prev_lat, prev_lng = None, None

        for pt in points:
            try:
                lat = float(pt.get("lat", 0))
                lng = float(pt.get("lng", 0))
            except (TypeError, ValueError):
                lat, lng = 0.0, 0.0

            dist_m = ""
            if prev_lat is not None and lat != 0 and lng != 0:
                d = _haversine_km(prev_lat, prev_lng, lat, lng)
                total_km += d
                dist_m = f"{d * 1000:.0f}"

            if lat != 0 and lng != 0:
                prev_lat, prev_lng = lat, lng

            rows.append((
                pt.get("timestamp_str", pt.get("fecha", "")),
                f"{lat:.5f}" if lat else "",
                f"{lng:.5f}" if lng else "",
                pt.get("tipo", "visita"),
                pt.get("cliente_nombre", ""),
                dist_m,
            ))

        auto_pts = sum(1 for p in points if p.get("tipo") == "auto")
        visit_pts = sum(1 for p in points if p.get("tipo") != "auto")

        return {
            "total_km": total_km,
            "auto_pts": auto_pts,
            "visit_pts": visit_pts,
            "rows": rows,
        }

    def _render_trail(self, uid, points, prepared: dict):
        for w in self._detail_area.winfo_children():
            w.destroy()

        gestor = next((g for g in self._gestores if g.get("uid") == uid), {})
        nombre = gestor.get("gestor_nombre", "") or uid[:12]
        seccion = gestor.get("seccion", "?")

        # Update KPIs in-place
        self._kpi_widgets[0].set(nombre)
        self._kpi_widgets[1].set(seccion)
        self._kpi_widgets[2].set(f"{prepared['total_km']:.2f}")
        self._kpi_widgets[3].set(
            f"{prepared['auto_pts']} auto / {prepared['visit_pts']} visita")

        if not points:
            ctk.CTkLabel(self._detail_area, text="Sin puntos de tracking",
                         font=font(13), text_color=TEXT_SECONDARY).pack(pady=30)
            return

        # Route canvas
        map_frame = ctk.CTkFrame(self._detail_area, fg_color="#F1F5F9",
                                 corner_radius=12, border_width=1,
                                 border_color=BORDER, height=250)
        map_frame.pack(fill="x", pady=(4, 8))
        map_frame.pack_propagate(False)

        canvas = tk.Canvas(map_frame, bg="#F1F5F9", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self._container.after(100, lambda: self._draw_route(canvas, points))

        # Google Maps link
        if points:
            last = points[-1]
            lat, lng = last.get("lat", 0), last.get("lng", 0)
            ctk.CTkButton(
                self._detail_area, text="Abrir en Google Maps",
                font=font(11), fg_color="#0D9488", hover_color="#0F766E",
                height=30, corner_radius=8,
                command=lambda: self._open_gmaps(lat, lng)
            ).pack(anchor="w", pady=(0, 8))

        # Points table
        ctk.CTkLabel(self._detail_area, text="Historial de Puntos",
                     font=font(13, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", pady=(8, 4))

        tf = ctk.CTkFrame(self._detail_area, fg_color=CARD_BG,
                          corner_radius=10, border_width=1, border_color=BORDER)
        tf.pack(fill="x", pady=4)

        cols = ("hora", "lat", "lng", "tipo", "cliente", "km")
        style_name = apply_treeview_style("Track.Treeview")
        self._trail_tree = ttk.Treeview(
            tf, columns=cols, show="headings",
            style=style_name, height=min(len(points) + 1, 12))
        for c, h, w in [("hora", "Hora", 130), ("lat", "Lat", 90),
                         ("lng", "Lng", 90), ("tipo", "Tipo", 60),
                         ("cliente", "Cliente", 160), ("km", "Dist(m)", 70)]:
            self._trail_tree.heading(c, text=h)
            self._trail_tree.column(c, width=w, minwidth=50)
        self._trail_tree.pack(fill="x", padx=2, pady=2)

        # Insert rows in batches
        self._insert_batch(prepared["rows"], 0)

    def _insert_batch(self, rows, start):
        if not self._trail_tree or not self._trail_tree.winfo_exists():
            return
        end = min(start + _TREE_BATCH, len(rows))
        for i in range(start, end):
            self._trail_tree.insert("", "end", values=rows[i])
        if end < len(rows):
            self._container.after(1, lambda: self._insert_batch(rows, end))

    def _draw_route(self, canvas, points):
        canvas.update_idletasks()
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        coords = []
        for p in points:
            try:
                lat, lng = float(p["lat"]), float(p["lng"])
                if lat != 0 and lng != 0:
                    coords.append((lat, lng, p.get("tipo", "auto")))
            except (KeyError, TypeError, ValueError):
                continue

        if not coords:
            canvas.create_text(cw // 2, ch // 2, text="Sin coordenadas",
                               font=(FONT_FAMILY, 11), fill=TEXT_SECONDARY)
            return

        lats = [c[0] for c in coords]
        lngs = [c[1] for c in coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lng, max_lng = min(lngs), max(lngs)
        pad = 25
        lat_range = max_lat - min_lat or 0.001
        lng_range = max_lng - min_lng or 0.001

        def to_xy(lat, lng):
            x = pad + (lng - min_lng) / lng_range * (cw - 2 * pad)
            y = pad + (max_lat - lat) / lat_range * (ch - 2 * pad)
            return x, y

        if len(coords) >= 2:
            line_pts = []
            for lat, lng, _ in coords:
                x, y = to_xy(lat, lng)
                line_pts.extend([x, y])
            canvas.create_line(line_pts, fill=ACCENT, width=2, smooth=True)

        for i, (lat, lng, tipo) in enumerate(coords):
            x, y = to_xy(lat, lng)
            r = 3 if tipo == "auto" else 5
            color = "#7C3AED" if tipo == "auto" else SUCCESS
            if i == 0:
                color, r = SUCCESS, 6
            elif i == len(coords) - 1:
                color, r = DANGER, 6
            canvas.create_oval(x - r, y - r, x + r, y + r,
                               fill=color, outline=WHITE, width=1)

    @staticmethod
    def _open_gmaps(lat, lng):
        import webbrowser
        webbrowser.open(f"https://www.google.com/maps?q={lat},{lng}")


# ── Module-level helper (avoids method-call overhead in loops) ──
def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = (math.sin(dLat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dLng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
