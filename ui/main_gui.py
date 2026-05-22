"""
Main GUI Window - Advanced Dashboard Layout
===========================================
A premium dark-themed, layout-accurate replica of a high-end gaming dashboard.
Features a left sidebar navigation, top status cards, a center hero banner,
live interactive charts (donut and bar charts), a target tracker,
and a right sidebar user profile & alert notifications.
"""

import tkinter as tk
from tkinter import scrolledtext
from tkinter import messagebox
import threading
import time
import math
import logging
import random
import glob
import os
import json
from PIL import Image, ImageTk


COLORS = {
    "bg_dark":        "#08080a",  # Deep dashboard background
    "bg_sidebar":     "#0e0e11",  # Sidebar dark background
    "bg_card":        "#141417",  # Premium rounded card color
    "bg_card_inner":  "#1b1b20",  # Nested card/input color
    "border":         "#22222a",  # Subtle card border
    "border_focus":   "#d44040",  # Active red border
    "text_primary":   "#f0f0f5",  # White
    "text_secondary": "#9fa0a6",  # Cool gray
    "text_dim":       "#5a5b63",  # Muted gray
    "red_primary":    "#c0392b",  # Drakensang Red
    "red_hover":      "#e74c3c",  # Vibrant Red
    "red_dark":       "#8b1a1a",  # Dark Red
    "red_glow":       "#ff3333",  # Neon Red
    "gold":           "#c8a84e",  # Premium Gold
    "success":        "#2ecc71",  # Green
    "warning":        "#f1c40f",  # Yellow
    "error":          "#e74c3c",  
    "info":           "#3498db",  # Blue
}

# Logger handler to route logs to the UI log view
class TextWidgetHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        try:
            self.text_widget.after(0, self._append, msg, record.levelno)
        except Exception:
            pass

    def _append(self, msg, level):
        self.text_widget.config(state=tk.NORMAL)
        tag = "info"
        if level >= logging.ERROR:
            tag = "error"
        elif level >= logging.WARNING:
            tag = "warning"
        elif level <= logging.DEBUG:
            tag = "debug"
        self.text_widget.insert(tk.END, msg + "\n", tag)
        self.text_widget.see(tk.END)
        
        # Limit buffer to 400 lines
        lines = int(self.text_widget.index('end-1c').split('.')[0])
        if lines > 400:
            self.text_widget.delete("1.0", "100.0")
        self.text_widget.config(state=tk.DISABLED)


class ModernCard(tk.Canvas):
    """A beautiful custom card widget with rounded corners and optional borders."""
    def __init__(self, parent, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], highlightthickness=0, **kwargs)
        self.bg_color = bg
        self.border_color = border_color
        self.radius = radius
        
        # Internal container for child widgets
        self.container = tk.Frame(self, bg=bg)
        self.container_id = self.create_window(0, 0, window=self.container, anchor="nw")
        
        self.bind("<Configure>", self._on_resize)

    def configure(self, **kwargs):
        # Extract custom arguments if passed
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
        if "border_color" in kwargs:
            self.border_color = kwargs.pop("border_color")
        
        # Pass remaining standard canvas configuration arguments to super
        super().configure(**kwargs)
        self._on_resize()

    def config(self, **kwargs):
        self.configure(**kwargs)
        
    def _on_resize(self, event=None):
        w = event.width if event else self.winfo_width()
        h = event.height if event else self.winfo_height()
        r = self.radius
        
        # Keep container frame background synchronized
        self.container.config(bg=self.bg_color)
        
        self.delete("bg")
        # Draw soft rounded corners
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=self.bg_color, outline=self.border_color, tags="bg")
        self.create_arc(w-r*2-1, 0, w-1, r*2, start=0, extent=90, fill=self.bg_color, outline=self.border_color, tags="bg")
        self.create_arc(0, h-r*2-1, r*2, h-1, start=180, extent=90, fill=self.bg_color, outline=self.border_color, tags="bg")
        self.create_arc(w-r*2-1, h-r*2-1, w-1, h-1, start=270, extent=90, fill=self.bg_color, outline=self.border_color, tags="bg")
        
        # Draw central filled boxes to cover the center area
        self.create_rectangle(r, 0, w-r, h, fill=self.bg_color, outline="", tags="bg")
        self.create_rectangle(0, r, w, h-r, fill=self.bg_color, outline="", tags="bg")
        
        # Draw border outline lines
        self.create_line(r, 0, w-r, 0, fill=self.border_color, tags="bg")
        self.create_line(r, h-1, w-r, h-1, fill=self.border_color, tags="bg")
        self.create_line(0, r, 0, h-r, fill=self.border_color, tags="bg")
        self.create_line(w-1, r, w-1, h-r, fill=self.border_color, tags="bg")
        
        # Position container frame slightly inside the rounded boundaries
        pad = 8
        self.coords(self.container_id, pad, pad)
        self.itemconfigure(self.container_id, width=max(1, w - pad*2), height=max(1, h - pad*2))


class MainGUI:
    def __init__(self, bot_instance, username="User", license_key="", authenticated=False):
        if not authenticated:
            raise PermissionError("Access Denied: MainGUI must be started through the login page.")

        self.bot = bot_instance
        self.username = username
        self.license_key = license_key
        
        self._running = True
        self._drag_x = 0
        self._drag_y = 0
        self._glow_phase = 0.0
        self._active_page = "dashboard"
        self._notifications = []
        
        # State distribution data for doughnut chart (default/mock)
        self.state_data = {
            "Combat": 40,
            "Navigate": 30,
            "Loot": 15,
            "Heal": 10,
            "Idle": 5
        }

        # Initialize Tkinter Window
        self.root = tk.Tk()
        self.root.title("DRAKENSANG AI — Control Panel")
        self.root.geometry("1150x700")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.overrideredirect(True)

        self._center_window()
        self._build_layout()
        
        # Start core loops
        self._update_stats_loop()
        self._animate_accent()
        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Bind Map event to restore overrideredirect and rounded corners when restored from taskbar
        self.root.bind("<Map>", self._on_window_map)

        # Apply rounded corners after full UI is built and rendered
        self.root.after(100, self._apply_system_rounded_corners)

    def _apply_system_rounded_corners(self):
        try:
            import ctypes
            self.root.update_idletasks()
            # wm_frame() returns the real OS-level top-level window handle
            hwnd = int(self.root.wm_frame(), 16)
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, 1152, 702, 22, 22)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def _on_window_map(self, event):
        self.root.overrideredirect(True)
        self._apply_system_rounded_corners()

    def _minimize_window(self):
        self.root.overrideredirect(False)
        self.root.iconify()

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 1150) // 2
        y = (sh - 700) // 2
        self.root.geometry(f"1150x700+{x}+{y}")

    def _build_layout(self):
        # 1. Custom Frameless Title Bar
        self._build_title_bar()

        # 2. Dynamic Red-Glowing Accent Separator
        self.accent_canvas = tk.Canvas(self.root, width=1150, height=2, bg=COLORS["bg_dark"], highlightthickness=0)
        self.accent_canvas.pack(fill=tk.X)

        # 3. Main Workspace Container
        self.workspace = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.workspace.pack(fill=tk.BOTH, expand=True)

        # 4. Left Sidebar Navigation Panel
        self._build_sidebar()

        # 5. Right Sidebar (User Profile + Notifications + Live Detections)
        self._build_right_sidebar()

        # 6. Central Dashboard / Page Content Panel
        self.main_content = tk.Frame(self.workspace, bg=COLORS["bg_dark"])
        self.main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 10), pady=10)

        # Initialize page frame dictionary
        self.pages = {}
        
        # Build pages
        self._build_dashboard_page()
        self._build_controls_page()
        self._build_waypoints_page()
        self._build_combos_page()
        self._build_macros_page()
        self._build_offsets_page()

        # Show default page
        self.show_page("dashboard")

    # ═══════════════════════════════════════════════════════
    # Title Bar Window Control
    # ═══════════════════════════════════════════════════════
    def _build_title_bar(self):
        tb = tk.Frame(self.root, bg=COLORS["bg_dark"], height=32)
        tb.pack(fill=tk.X)
        tb.pack_propagate(False)

        title_label = tk.Label(
            tb, text="  ◆  DRAKENSANG AI  —  CONTROL PANEL",
            bg=COLORS["bg_dark"], fg=COLORS["red_primary"],
            font=("Segoe UI", 9, "bold")
        )
        title_label.pack(side=tk.LEFT, padx=5)

        # Exit & Minimize buttons
        close_btn = tk.Label(
            tb, text="  ✕  ", bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=("Consolas", 11), cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg=COLORS["red_primary"], fg="white"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        close_btn.bind("<Button-1>", lambda e: self._on_close())

        min_btn = tk.Label(
            tb, text="  ─  ", bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=("Consolas", 11), cursor="hand2"
        )
        min_btn.pack(side=tk.RIGHT)
        min_btn.bind("<Enter>", lambda e: min_btn.config(bg=COLORS["bg_card_inner"], fg="white"))
        min_btn.bind("<Leave>", lambda e: min_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        min_btn.bind("<Button-1>", lambda e: self._minimize_window())

        # Bind window drag event
        for widget in [tb, title_label]:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ═══════════════════════════════════════════════════════
    # Left Sidebar Navigation
    # ═══════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = tk.Frame(self.workspace, bg=COLORS["bg_sidebar"], width=180)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Logo branding
        logo_frame = tk.Frame(self.sidebar, bg=COLORS["bg_sidebar"])
        logo_frame.pack(fill=tk.X, pady=(20, 25))

        tk.Label(
            logo_frame, text="DRAKENSANG",
            bg=COLORS["bg_sidebar"], fg=COLORS["text_primary"],
            font=("Segoe UI", 12, "bold")
        ).pack()
        tk.Label(
            logo_frame, text="E L I T E   A I",
            bg=COLORS["bg_sidebar"], fg=COLORS["red_primary"],
            font=("Segoe UI", 8, "bold")
        ).pack(pady=(2, 0))

        # Search Bar Mock (from reference)
        search_card = ModernCard(self.sidebar, bg=COLORS["bg_card_inner"], border_color=COLORS["border"], radius=8, height=32)
        search_card.pack(fill=tk.X, padx=12, pady=(0, 20))
        
        search_label = tk.Label(
            search_card.container, text="🔍  Search parameters...",
            bg=COLORS["bg_card_inner"], fg=COLORS["text_dim"],
            font=("Segoe UI", 8), anchor="w"
        )
        search_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Nav Buttons list
        self.nav_items = [
            ("Home", "🏠  Home", "dashboard"),
            ("Controls", "⚔️  Bot Controls", "controls"),
            ("Waypoints", "📍  Waypoint Editor", "waypoints"),
            ("Combos", "🎯  Combo Editor", "combos"),
            ("Macros", "🎮  Macro Profiles", "macros"),
            ("Offsets", "🔧  Offsets", "offsets")
        ]
        
        self.nav_buttons = {}
        for key, text, page_id in self.nav_items:
            btn = tk.Label(
                self.sidebar, text=f"    {text}",
                bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"],
                font=("Segoe UI", 9, "bold"), anchor="w",
                cursor="hand2", height=2
            )
            btn.pack(fill=tk.X, padx=6, pady=2)
            
            # Hover animations
            btn.bind("<Enter>", lambda e, k=key: self._on_nav_hover(k, True))
            btn.bind("<Leave>", lambda e, k=key: self._on_nav_hover(k, False))
            btn.bind("<Button-1>", lambda e, pid=page_id: self.show_page(pid))
            
            self.nav_buttons[key] = btn

        # Bottom actions
        logout_spacer = tk.Frame(self.sidebar, bg=COLORS["bg_sidebar"])
        logout_spacer.pack(fill=tk.BOTH, expand=True)

        self.btn_exit = tk.Label(
            self.sidebar, text="    🚪  Exit Application",
            bg=COLORS["bg_sidebar"], fg=COLORS["text_dim"],
            font=("Segoe UI", 9, "bold"), anchor="w",
            cursor="hand2", height=2
        )
        self.btn_exit.pack(fill=tk.X, padx=6, pady=10)
        self.btn_exit.bind("<Enter>", lambda e: self.btn_exit.config(fg=COLORS["red_hover"]))
        self.btn_exit.bind("<Leave>", lambda e: self.btn_exit.config(fg=COLORS["text_dim"]))
        self.btn_exit.bind("<Button-1>", lambda e: self._on_close())

    def _on_nav_hover(self, key, is_entering):
        btn = self.nav_buttons[key]
        is_active = key.lower() == self._active_page.lower()
        if is_active:
            return
            
        if is_entering:
            btn.config(bg=COLORS["bg_card"], fg=COLORS["text_primary"])
        else:
            btn.config(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])

    def show_page(self, page_id):
        self._active_page = page_id
        
        # Hide all pages
        for pid, frame in self.pages.items():
            frame.pack_forget()

        # Show active page
        self.pages[page_id].pack(fill=tk.BOTH, expand=True)

        # Update Nav buttons styles
        for key, text, pid in self.nav_items:
            btn = self.nav_buttons[key]
            if pid == page_id:
                btn.config(bg=COLORS["bg_card"], fg=COLORS["gold"])
            else:
                btn.config(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])

    # ═══════════════════════════════════════════════════════
    # Right Sidebar (User Profile & Notifications)
    # ═══════════════════════════════════════════════════════
    def _build_right_sidebar(self):
        rs = tk.Frame(self.workspace, bg=COLORS["bg_sidebar"], width=215)
        rs.pack(side=tk.RIGHT, fill=tk.Y)
        rs.pack_propagate(False)

        # Profile Card (replica of Top Right gamer card)
        profile_card = ModernCard(rs, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=12, height=95)
        profile_card.pack(fill=tk.X, padx=10, pady=(15, 10))

        c = profile_card.container
        
        # Top line: avatar shield shape + gamer username
        top_row = tk.Frame(c, bg=COLORS["bg_card"])
        top_row.pack(fill=tk.X, pady=(2, 4))
        
        # Avatar representation
        self.avatar_canvas = tk.Canvas(top_row, width=32, height=32, bg=COLORS["bg_card"], highlightthickness=0)
        self.avatar_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self._draw_avatar_shield()

        user_info = tk.Frame(top_row, bg=COLORS["bg_card"])
        user_info.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(user_info, text=self.username, bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(user_info, text="Elite License Holder", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 7, "bold")).pack(anchor="w")

        # XP/Progress Bar
        progress_info = tk.Frame(c, bg=COLORS["bg_card"])
        progress_info.pack(fill=tk.X, pady=(4, 2))
        
        tk.Label(progress_info, text="Active Session Status", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
        self.session_percentage_lbl = tk.Label(progress_info, text="100%", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 7, "bold"))
        self.session_percentage_lbl.pack(side=tk.RIGHT)

        # Canvas progress bar
        self.profile_pb = tk.Canvas(c, height=6, bg=COLORS["bg_card_inner"], highlightthickness=0)
        self.profile_pb.pack(fill=tk.X, pady=2)
        self._draw_profile_pb(1.0) # Full load initially

        # Connection status label
        self.status_sub_lbl = tk.Label(c, text="● Connected & Secure", bg=COLORS["bg_card"], fg=COLORS["success"], font=("Segoe UI", 7, "bold"), anchor="w")
        self.status_sub_lbl.pack(fill=tk.X, pady=(2, 0))

        # Alert Notifications List
        tk.Label(rs, text="LIVE NOTIFICATIONS", bg=COLORS["bg_sidebar"], fg=COLORS["text_dim"], font=("Segoe UI", 7, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(10, 2))
        
        self.notify_box = tk.Frame(rs, bg=COLORS["bg_sidebar"])
        self.notify_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Populate initially
        self._add_notification("System initialized", "Success")
        self._add_notification("Awaiting Start Command", "Info")

        # Detected Targets panel
        tk.Label(rs, text="DETECTED TARGETS (YOLO)", bg=COLORS["bg_sidebar"], fg=COLORS["text_dim"], font=("Segoe UI", 7, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(10, 2))
        
        self.targets_card = ModernCard(rs, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=10, height=130)
        self.targets_card.pack(fill=tk.X, padx=10, pady=(0, 15))
        
        self.targets_list_frame = tk.Frame(self.targets_card.container, bg=COLORS["bg_card"])
        self.targets_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._update_detected_targets([])

    def _draw_avatar_shield(self):
        # Draw a stylish gold/red emblem
        self.avatar_canvas.delete("all")
        self.avatar_canvas.create_polygon(16, 2, 28, 8, 28, 24, 16, 30, 4, 24, 4, 8, fill=COLORS["red_dark"], outline=COLORS["gold"], width=1.5)
        self.avatar_canvas.create_text(16, 16, text="AI", fill=COLORS["text_primary"], font=("Consolas", 9, "bold"))

    def _draw_profile_pb(self, ratio):
        self.profile_pb.delete("all")
        self.profile_pb.update()
        w = self.profile_pb.winfo_width()
        h = 6
        if w < 10: w = 200
        # draw background
        self.profile_pb.create_rectangle(0, 0, w, h, fill=COLORS["bg_card_inner"], outline="")
        # draw fill
        fill_w = int(w * ratio)
        self.profile_pb.create_rectangle(0, 0, fill_w, h, fill=COLORS["gold"], outline="")

    def _add_notification(self, text, category="Info"):
        # Max notifications: 4
        if len(self._notifications) >= 4:
            self._notifications.pop(0)
        self._notifications.append((text, category, time.strftime("%H:%M")))
        
        # Redraw notification box
        for w in self.notify_box.winfo_children():
            w.destroy()
            
        colors_cat = {
            "Success": COLORS["success"],
            "Warning": COLORS["warning"],
            "Error": COLORS["error"],
            "Info": COLORS["info"]
        }
        
        for msg, cat, t in reversed(self._notifications):
            card = ModernCard(self.notify_box, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=8, height=45)
            card.pack(fill=tk.X, pady=3)
            
            lbl_msg = tk.Label(card.container, text=msg, bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 7, "bold"), anchor="w")
            lbl_msg.pack(fill=tk.X, padx=5, pady=(2, 0))
            
            lbl_time = tk.Label(card.container, text=f"{t}  •  {cat}", bg=COLORS["bg_card"], fg=colors_cat.get(cat, COLORS["text_dim"]), font=("Segoe UI", 6, "bold"), anchor="w")
            lbl_time.pack(fill=tk.X, padx=5, pady=(0, 2))

    def _update_detected_targets(self, targets):
        for w in self.targets_list_frame.winfo_children():
            w.destroy()
            
        if not targets:
            tk.Label(self.targets_list_frame, text="No entities detected", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 8)).pack(pady=30)
            return

        for name, hp_pct, color in targets:
            row = tk.Frame(self.targets_list_frame, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, pady=2)
            
            # Indicator dot
            dot = tk.Canvas(row, width=8, height=8, bg=COLORS["bg_card"], highlightthickness=0)
            dot.pack(side=tk.LEFT, padx=(2, 6))
            dot.create_oval(0, 0, 8, 8, fill=color, outline="")
            
            # Name
            tk.Label(row, text=name, bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 7, "bold")).pack(side=tk.LEFT)
            # HP representation
            tk.Label(row, text=f"{hp_pct}% HP", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 7)).pack(side=tk.RIGHT, padx=2)

    # ═══════════════════════════════════════════════════════
    # PAGE 1: Home/Dashboard View
    # ═══════════════════════════════════════════════════════
    # PAGE 1: Home/Dashboard View
    # ═══════════════════════════════════════════════════════
    def _build_dashboard_page(self):
        import math
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["dashboard"] = page

        # TOP ROW: Real-time state dashboard cards (horizontal metrics blocks)
        metrics_frame = tk.Frame(page, bg=COLORS["bg_dark"])
        metrics_frame.pack(fill=tk.X, pady=(0, 10))

        # Metrics cards configuration
        metrics_data = [
            ("BOT STATUS", "OFFLINE", COLORS["error"]),
            ("CLASS", "Custom", COLORS["gold"]),
            ("ENEMIES KILLED", "0", COLORS["red_primary"]),
            ("LOOT PICKED", "0", COLORS["success"]),
            ("SESSION TIME", "00:00:00", COLORS["info"]),
            ("PLAYER HP", "100%", COLORS["success"]),
        ]

        self.blocks = {}
        for name, value, col in metrics_data:
            card = ModernCard(metrics_frame, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=10, height=65)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
            c = card.container
            
            tk.Label(c, text=name, bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 7, "bold")).pack(pady=(4, 1))
            lbl_val = tk.Label(c, text=value, bg=COLORS["bg_card"], fg=col, font=("Segoe UI", 10, "bold"))
            lbl_val.pack(pady=(0, 4))
            self.blocks[name] = lbl_val

        # MAIN CONTENT ROW: Split into Left Column (Console) and Right Column (Radar + Settings)
        main_split = tk.Frame(page, bg=COLORS["bg_dark"])
        main_split.pack(fill=tk.BOTH, expand=True)

        # -------------------------------------------------------------
        # LEFT COLUMN: System Telemetry & Console
        # -------------------------------------------------------------
        left_col = tk.Frame(main_split, bg=COLORS["bg_dark"])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        console_card = ModernCard(left_col, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        console_card.pack(fill=tk.BOTH, expand=True)
        cc = console_card.container

        # Console Header bar
        header_bar = tk.Frame(cc, bg=COLORS["bg_card"])
        header_bar.pack(fill=tk.X, padx=15, pady=(12, 6))

        tk.Label(header_bar, text="📋  SYSTEM TELEMETRY CONSOLE", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        # Quick Actions inside Header
        actions_frame = tk.Frame(header_bar, bg=COLORS["bg_card"])
        actions_frame.pack(side=tk.RIGHT)

        # Attach process action
        def attach_process():
            import pygetwindow as gw
            import psutil

            GAME_WINDOW_TITLES = ["Drakensang Online", "Bigpoint", "drakensang"]
            GAME_EXE_NAMES     = ["drakensang.exe", "dso.exe", "bigpoint.exe"]

            self._append_log("Searching for Drakensang Online process...", "warning")

            # ── 1. Try to find via window title ──────────────────────
            found_window = None
            for title_fragment in GAME_WINDOW_TITLES:
                matches = [w for w in gw.getAllWindows()
                           if title_fragment.lower() in w.title.lower() and w.title.strip()]
                if matches:
                    found_window = matches[0]
                    break

            # ── 2. Try psutil process search if no window found ──────
            found_pid  = None
            found_name = None
            if not found_window:
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        pname = proc.info["name"].lower()
                        if any(exe in pname for exe in GAME_EXE_NAMES):
                            found_pid  = proc.info["pid"]
                            found_name = proc.info["name"]
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            # ── 3. Report results ────────────────────────────────────
            if found_window:
                pid_info = ""
                try:
                    for proc in psutil.process_iter(["pid", "name"]):
                        if proc.info["name"].lower() in [exe.lower() for exe in GAME_EXE_NAMES]:
                            pid_info = f"PID: {proc.info['pid']}"
                            break
                except Exception:
                    pid_info = "PID: N/A"

                self._append_log(
                    f"✅ Found game window: \"{found_window.title}\" — {pid_info}", "success"
                )
                self._add_notification("Game attached!", "Success")

                # Focus the window
                try:
                    found_window.activate()
                except Exception:
                    pass

            elif found_pid:
                self._append_log(
                    f"✅ Found game process: {found_name} (PID: {found_pid}) — no visible window", "success"
                )
                self._add_notification("Game process found!", "Success")

            else:
                self._append_log(
                    "❌ Drakensang Online not found. Please launch the game client first.", "error"
                )
                self._add_notification("Game not running!", "Error")
                from tkinter import messagebox
                messagebox.showwarning(
                    "Game Not Found",
                    "Drakensang Online is not running.\n\n"
                    "Please open the game client and then click Attach Process again."
                )

        btn_attach = tk.Label(
            actions_frame, text=" 🔗 Attach Process ", bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), cursor="hand2", height=2
        )
        btn_attach.pack(side=tk.LEFT, padx=3)
        btn_attach.bind("<Button-1>", lambda e: attach_process())
        btn_attach.bind("<Enter>", lambda e: btn_attach.config(bg=COLORS["info"], fg="white"))
        btn_attach.bind("<Leave>", lambda e: btn_attach.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"]))

        # Clear Console action
        btn_clear = tk.Label(
            actions_frame, text=" ✕ Clear Log ", bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 8, "bold"), cursor="hand2", height=2
        )
        btn_clear.pack(side=tk.LEFT, padx=3)
        btn_clear.bind("<Button-1>", lambda e: self._clear_log())
        btn_clear.bind("<Enter>", lambda e: btn_clear.config(bg=COLORS["red_primary"], fg="white"))
        btn_clear.bind("<Leave>", lambda e: btn_clear.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"]))

        # Scrolled Text Box for logs
        self.log_text = tk.Text(
            cc, bg="#08080b", fg=COLORS["text_secondary"],
            font=("Consolas", 9), relief="flat", bd=8, wrap=tk.WORD, state=tk.DISABLED,
            insertbackground=COLORS["red_primary"], selectbackground=COLORS["red_dark"]
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # Setup message coloring tags
        self.log_text.tag_configure("info", foreground=COLORS["text_secondary"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("error", foreground=COLORS["error"])
        self.log_text.tag_configure("success", foreground=COLORS["success"])
        self.log_text.tag_configure("debug", foreground=COLORS["text_dim"])

        # Setup standard logger
        import logging
        self.log_handler = TextWidgetHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S"
        ))

        # Add to logger root
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)

        self._append_log("System bound to Live Telemetry Log stream.", "success")

        # -------------------------------------------------------------
        # RIGHT COLUMN: Radar & Quick Settings
        # -------------------------------------------------------------
        right_col = tk.Frame(main_split, bg=COLORS["bg_dark"], width=300)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        right_col.pack_propagate(False)

        # 0. Start Button panel card
        self.start_btn_card = ModernCard(right_col, bg=COLORS["success"], border_color=COLORS["success"], radius=15, height=55)
        self.start_btn_card.pack(fill=tk.X, pady=(0, 5))
        sbc = self.start_btn_card.container
        
        self.start_btn_lbl = tk.Label(
            sbc, text="▶ START BOT", bg=COLORS["success"], fg="white",
            font=("Segoe UI", 11, "bold"), cursor="hand2"
        )
        self.start_btn_lbl.pack(fill=tk.BOTH, expand=True)
        self.start_btn_lbl.bind("<Button-1>", lambda e: self._toggle_bot())

        # 1. Radar panel card
        radar_card = ModernCard(right_col, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15, height=265)
        radar_card.pack(fill=tk.X, pady=(0, 5))
        rc = radar_card.container

        tk.Label(rc, text="◈  TACTICAL RADAR", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

        # Radar Canvas
        self.radar_canvas = tk.Canvas(rc, width=220, height=200, bg="#0d0e12", highlightthickness=0)
        self.radar_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 10))
        self.radar_sweep_angle = 0
        
        # Start sweep animation
        self._animate_radar()

        # 2. Quick Settings panel card
        settings_card = ModernCard(right_col, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        settings_card.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        sc = settings_card.container

        tk.Label(sc, text="◈  QUICK CONFIGURATION", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 8))

        # Load values from config
        config = getattr(self.bot, "config", {})
        combat_cfg = config.get("combat", {})
        nav_cfg = config.get("navigation", {})
        hum_cfg = config.get("humanizer", {})

        # Attack Range Setting
        range_frame = tk.Frame(sc, bg=COLORS["bg_card"])
        range_frame.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(range_frame, text="Attack Range (px):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.val_attack_range = tk.Entry(range_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3, font=("Segoe UI", 8, "bold"))
        self.val_attack_range.pack(side=tk.RIGHT)
        self.val_attack_range.insert(0, str(combat_cfg.get("attack_range", 150)))

        # Move Delay Setting
        move_frame = tk.Frame(sc, bg=COLORS["bg_card"])
        move_frame.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(move_frame, text="Move Delay (s):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.val_move_delay = tk.Entry(move_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3, font=("Segoe UI", 8, "bold"))
        self.val_move_delay.pack(side=tk.RIGHT)
        self.val_move_delay.insert(0, str(nav_cfg.get("move_delay", 0.5)))

        # Skill Delay Setting
        skill_frame = tk.Frame(sc, bg=COLORS["bg_card"])
        skill_frame.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(skill_frame, text="Humanizer Min Delay (s):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.val_skill_delay = tk.Entry(skill_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3, font=("Segoe UI", 8, "bold"))
        self.val_skill_delay.pack(side=tk.RIGHT)
        self.val_skill_delay.insert(0, str(hum_cfg.get("min_delay", 0.05)))

        # Auto Loot Setting
        loot_frame = tk.Frame(sc, bg=COLORS["bg_card"])
        loot_frame.pack(fill=tk.X, padx=12, pady=6)
        
        self.val_auto_loot_var = tk.BooleanVar(value=True)
        chk_loot = tk.Checkbutton(
            loot_frame, text="Enable Auto Loot Collection",
            variable=self.val_auto_loot_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), bd=0
        )
        chk_loot.pack(side=tk.LEFT)

        def apply_quick_settings():
            try:
                import json
                rng = int(self.val_attack_range.get())
                mv = float(self.val_move_delay.get())
                sk = float(self.val_skill_delay.get())
                
                # Apply in memory
                if hasattr(self.bot, 'combat') and self.bot.combat:
                    self.bot.combat.attack_range = rng
                if hasattr(self.bot, 'navigation') and self.bot.navigation:
                    self.bot.navigation.move_delay = mv
                if hasattr(self.bot, 'humanizer') and self.bot.humanizer:
                    self.bot.humanizer.min_delay = sk

                # Save to config file settings.json
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    
                    cfg["combat"]["attack_range"] = rng
                    cfg["navigation"]["move_delay"] = mv
                    cfg["humanizer"]["min_delay"] = sk

                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)

                self._append_log("Quick Settings applied successfully and saved!", "success")
                self._add_notification("Quick Settings Saved", "Success")
            except Exception as e:
                self._append_log(f"Failed to apply settings: {e}", "error")

        # Apply settings button
        btn_apply = tk.Label(
            sc, text=" 💾  APPLY CONFIGURATION ", bg=COLORS["red_primary"], fg="white",
            font=("Segoe UI", 8, "bold"), cursor="hand2", height=2
        )
        btn_apply.pack(fill=tk.X, padx=12, pady=10)
        btn_apply.bind("<Button-1>", lambda e: apply_quick_settings())

    def _animate_radar(self):
        if not self._running:
            return

        import math
        canvas = self.radar_canvas
        canvas.delete("all")
        
        # Get dimensions
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10 or h < 10:
            w, h = 220, 200
        
        cx, cy = w / 2, h / 2
        r_max = min(cx, cy) - 10
        
        # 1. Draw outer circle
        canvas.create_oval(cx - r_max, cy - r_max, cx + r_max, cy + r_max, outline="#1b3024", width=1.5)
        # Concentric circles
        canvas.create_oval(cx - r_max * 0.7, cy - r_max * 0.7, cx + r_max * 0.7, cy + r_max * 0.7, outline="#1b3024", width=1, dash=(3, 3))
        canvas.create_oval(cx - r_max * 0.4, cy - r_max * 0.4, cx + r_max * 0.4, cy + r_max * 0.4, outline="#1b3024", width=1, dash=(3, 3))
        
        # 2. Draw cross axes
        canvas.create_line(cx - r_max, cy, cx + r_max, cy, fill="#1b3024", width=1)
        canvas.create_line(cx, cy - r_max, cx, cy + r_max, fill="#1b3024", width=1)
        
        # 3. Draw player dot (Center blue dot)
        canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=COLORS["info"], outline="")
        
        # 4. Sweep line
        self.radar_sweep_angle = (self.radar_sweep_angle + 3) % 360
        rad = math.radians(self.radar_sweep_angle)
        sx = cx + r_max * math.cos(rad)
        sy = cy + r_max * math.sin(rad)
        
        # Draw sweeping gradient line
        canvas.create_line(cx, cy, sx, sy, fill="#32a852", width=1.5)
        
        # 5. Plot active detected targets
        raw_detections = []
        if hasattr(self.bot, 'detector') and self.bot.detector:
            raw_detections = getattr(self.bot.detector, 'detections', [])
        
        if raw_detections:
            for det in raw_detections:
                label = det.get('label', 'enemy')
                bbox = det.get('bbox', None)
                if bbox:
                    # Map bbox center relative to screen center
                    x, y, bw, bh = bbox
                    dcx = x + bw/2
                    dcy = y + bh/2
                    rx = (dcx - 320) / 320.0
                    ry = (dcy - 240) / 240.0
                    
                    px = cx + rx * r_max * 0.9
                    py = cy + ry * r_max * 0.9
                    
                    col = COLORS["error"] if "enemy" in label.lower() or "mob" in label.lower() else COLORS["success"] if "loot" in label.lower() else COLORS["gold"]
                    canvas.create_oval(px - 3, py - 3, px + 3, py + 3, fill=col, outline="")

        self.root.after(30, self._animate_radar)

    # ═══════════════════════════════════════════════════════
    # PAGE 2: Bot Controls Config View
    # ═══════════════════════════════════════════════════════
    def _build_controls_page(self):
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["controls"] = page

        # Detailed Bot configuration and actions
        grid = tk.Frame(page, bg=COLORS["bg_dark"])
        grid.pack(fill=tk.BOTH, expand=True)

        # 1. Action Panel
        action_card = ModernCard(grid, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=12)
        action_card.grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="nsew")
        
        ac = action_card.container
        tk.Label(ac, text="◈ INTERACTION HUB", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 8), padx=8)

        # --- Class Profile Selector ---
        class_frame = tk.Frame(ac, bg=COLORS["bg_card"])
        class_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(
            class_frame, text="⚔  CLASS PROFILE", bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")
        ).pack(side=tk.LEFT)

        # Build dropdown values from class_profiles
        try:
            from combat.class_profiles import get_all_display_names
            profile_map = get_all_display_names()
        except Exception:
            profile_map = {"custom": "Custom"}

        self._class_profile_keys = list(profile_map.keys())
        self._class_display_names = list(profile_map.values())

        # Determine current selection
        current_class = "Custom"
        if hasattr(self.bot, 'combat') and self.bot.combat:
            active = getattr(self.bot.combat, 'active_class', 'custom')
            current_class = profile_map.get(active, "Custom")

        self._class_var = tk.StringVar(value=current_class)
        class_dropdown = tk.OptionMenu(
            class_frame, self._class_var, *self._class_display_names,
            command=self._on_class_changed
        )
        class_dropdown.config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), highlightthickness=0,
            activebackground=COLORS["red_primary"], activeforeground="white",
            relief="flat", bd=0, cursor="hand2"
        )
        class_dropdown["menu"].config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8), activebackground=COLORS["red_primary"],
            activeforeground="white", bd=0
        )
        class_dropdown.pack(side=tk.RIGHT)

        # --- Map Profile Selector ---
        map_frame = tk.Frame(ac, bg=COLORS["bg_card"])
        map_frame.pack(fill=tk.X, padx=12, pady=(8, 6))

        tk.Label(
            map_frame, text="📍  ACTIVE MAP PATH", bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")
        ).pack(side=tk.LEFT)

        # Scan available maps
        available_maps = self._scan_available_maps()
        current_map_name = "default"
        if hasattr(self.bot, 'navigation') and self.bot.navigation:
            current_map_name = self.bot.navigation.active_map_name
        
        self._map_var = tk.StringVar(value=current_map_name)
        map_dropdown = tk.OptionMenu(
            map_frame, self._map_var, *available_maps,
            command=self._on_controls_map_changed
        )
        map_dropdown.config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), highlightthickness=0,
            activebackground=COLORS["red_primary"], activeforeground="white",
            relief="flat", bd=0, cursor="hand2"
        )
        map_dropdown["menu"].config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8), activebackground=COLORS["red_primary"],
            activeforeground="white", bd=0
        )
        map_dropdown.pack(side=tk.RIGHT)

        # Action buttons
        self._build_btn(ac, "🔊 TOGGLE GAME OVERLAY", self._toggle_overlay)
        self._build_btn(ac, "📍 RECORD MAP WAYPOINT", self._record_waypoint)
        self._build_btn(ac, "📸 CAPTURE TRAINING SCREENSHOT", self._capture_screenshot)
        self._build_btn(ac, "💾 TOGGLE AUTO DATASET CAPTURE", self._toggle_auto_capture)

        # 2. General Stats Card
        stats_card = ModernCard(grid, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=12)
        stats_card.grid(row=0, column=1, padx=(5, 0), pady=(0, 5), sticky="nsew")
        
        sc = stats_card.container
        tk.Label(sc, text="◈ PERFORMANCE STATISTICS", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 8), padx=8)

        stats_layout = [
            ("Bot Session State", "state_stat", "IDLE"),
            ("Active Class", "class_stat", "Custom"),
            ("Enemies Killed", "kills_stat", "0"),
            ("Loot Items Picked", "loot_stat", "0"),
            ("Potions Consumed", "potions_stat", "0"),
            ("Character Deaths", "deaths_stat", "0"),
            ("Danger Score", "danger_stat", "0"),
            ("Detection Inference FPS", "fps_stat", "0.0")
        ]
        
        for lbl, attr, val in stats_layout:
            row = tk.Frame(sc, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=12, pady=3)
            
            tk.Label(row, text=lbl, bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
            v = tk.Label(row, text=val, bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 8, "bold"))
            v.pack(side=tk.RIGHT)
            setattr(self, attr, v)

        # 3. Status Display Card (Top Indicators replica)
        status_card = ModernCard(grid, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=12)
        status_card.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="nsew")
        
        s_container = status_card.container
        tk.Label(s_container, text="◈ REAL-TIME STATE DASHBOARD", bg=COLORS["bg_card"], fg=COLORS["gold"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 8), padx=8)

        # Horizontal Row of Status Indicator blocks
        blocks_frame = tk.Frame(s_container, bg=COLORS["bg_card"])
        blocks_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.blocks = {}
        indicators = [
            ("BOT STATUS", "OFFLINE", COLORS["error"]),
            ("CLASS", "Custom", COLORS["gold"]),
            ("ENEMIES KILLED", "0", COLORS["red_primary"]),
            ("LOOT PICKED", "0", COLORS["warning"]),
            ("SESSION TIME", "00:00:00", COLORS["info"]),
            ("PLAYER HP", "100%", COLORS["success"]),
        ]
        
        for title, val, color in indicators:
            block = tk.Frame(blocks_frame, bg=COLORS["bg_card_inner"], bd=1, relief="solid", highlightbackground=COLORS["border"])
            block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=5)
            
            tk.Label(block, text=title, bg=COLORS["bg_card_inner"], fg=COLORS["text_dim"], font=("Segoe UI", 6, "bold")).pack(pady=(6, 1))
            lbl_val = tk.Label(block, text=val, bg=COLORS["bg_card_inner"], fg=color, font=("Segoe UI", 11, "bold"))
            lbl_val.pack(pady=(0, 6))
            
            self.blocks[title] = lbl_val

        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=3)
        grid.rowconfigure(1, weight=2)

    def _build_btn(self, parent, text, cmd):
        card = ModernCard(parent, bg=COLORS["bg_card_inner"], border_color=COLORS["border"], radius=8, height=36)
        card.pack(padx=12, pady=4, fill=tk.X)
        card.pack_propagate(False)
        
        lbl = tk.Label(
            card.container, text=text, bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        lbl.pack(fill=tk.BOTH, expand=True)
        
        def on_enter(e):
            card.bg_color = COLORS["bg_card"]
            card.border_color = COLORS["red_primary"]
            lbl.config(bg=COLORS["bg_card"], fg=COLORS["text_primary"])
            card._on_resize()
            
        def on_leave(e):
            card.bg_color = COLORS["bg_card_inner"]
            card.border_color = COLORS["border"]
            lbl.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"])
            card._on_resize()
            
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", lambda e: cmd())

    # ═══════════════════════════════════════════════════════
    # PAGE: Interactive Map Waypoint Editor
    # ═══════════════════════════════════════════════════════
    def _build_waypoints_page(self):
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["waypoints"] = page

        # Horizontal layout: Left Map Canvas, Right Control panel
        container = tk.Frame(page, bg=COLORS["bg_dark"])
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Left Map Card
        map_card = ModernCard(container, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        map_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        mc = map_card.container
        
        # Header for Editor
        tk.Label(
            mc, text="◈ INTERACTIVE MAP PATH EDITOR", 
            bg=COLORS["bg_card"], fg=COLORS["gold"], 
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(5, 5), padx=5)

        # Canvas container with a sleek border
        canvas_border = tk.Frame(mc, bg=COLORS["border"], bd=1)
        canvas_border.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tkinter Canvas
        self.editor_canvas = tk.Canvas(
            canvas_border, width=520, height=390, 
            bg="#0b0b0e", highlightthickness=0, cursor="crosshair"
        )
        self.editor_canvas.pack(fill=tk.BOTH, expand=True)
        self.editor_canvas.bind("<Button-1>", self._on_canvas_click)

        # 2. Right Control Panel Card
        ctrl_card = ModernCard(container, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15, width=220)
        ctrl_card.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ctrl_card.pack_propagate(False)

        cc = ctrl_card.container

        # Header for Controls
        tk.Label(
            cc, text="◈ CONTROLS", 
            bg=COLORS["bg_card"], fg=COLORS["gold"], 
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", pady=(5, 5))

        # --- Active Map Dropdown ---
        tk.Label(
            cc, text="SELECT BACKGROUND MAP", 
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"], 
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", pady=(0, 2))

        self.editor_maps_list = self._scan_available_maps()
        self.active_map_file_var = tk.StringVar(value=self.editor_maps_list[0] if self.editor_maps_list else "None")
        
        self.map_dropdown = tk.OptionMenu(
            cc, self.active_map_file_var, *(self.editor_maps_list if self.editor_maps_list else ["None"]),
            command=self._on_editor_map_changed
        )
        self.map_dropdown.config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), highlightthickness=0,
            activebackground=COLORS["red_primary"], activeforeground="white",
            relief="flat", bd=0, cursor="hand2"
        )
        self.map_dropdown["menu"].config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8), activebackground=COLORS["red_primary"],
            activeforeground="white", bd=0
        )
        self.map_dropdown.pack(fill=tk.X, pady=(0, 8))

        # --- Path Type Dropdown ---
        tk.Label(
            cc, text="ROUTE PATH TYPE", 
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"], 
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", pady=(0, 2))

        self.path_types = ["⚔️ Farming Loop", "☠️ Boss Rush", "🛡️ Safe Route", "💰 Loot Run"]
        self.path_type_var = tk.StringVar(value=self.path_types[0])
        self.path_type_dropdown = tk.OptionMenu(
            cc, self.path_type_var, *self.path_types,
            command=lambda v: self._redraw_editor_waypoints()
        )
        self.path_type_dropdown.config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8, "bold"), highlightthickness=0,
            activebackground=COLORS["red_primary"], activeforeground="white",
            relief="flat", bd=0, cursor="hand2"
        )
        self.path_type_dropdown["menu"].config(
            bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            font=("Segoe UI", 8), activebackground=COLORS["red_primary"],
            activeforeground="white", bd=0
        )
        self.path_type_dropdown.pack(fill=tk.X, pady=(0, 8))

        # --- Map File Name Input (for creating new paths) ---
        tk.Label(
            cc, text="ACTIVE MAP PATH NAME", 
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"], 
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", pady=(0, 2))

        self.map_name_entry = tk.Entry(
            cc, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            insertbackground=COLORS["red_primary"], font=("Segoe UI", 8),
            bd=0, relief="flat", highlightthickness=1, highlightcolor=COLORS["red_primary"],
            highlightbackground=COLORS["border"]
        )
        self.map_name_entry.pack(fill=tk.X, ipady=3, pady=(0, 8))
        self.map_name_entry.insert(0, "q5 map")

        # --- Screen Boundaries Config ---
        tk.Label(
            cc, text="SCREEN RESOLUTION CALIBRATION", 
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"], 
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", pady=(0, 2))

        res_frame = tk.Frame(cc, bg=COLORS["bg_card"])
        res_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Label(res_frame, text="W:", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.screen_w_entry = tk.Entry(
            res_frame, width=5, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            insertbackground=COLORS["red_primary"], font=("Segoe UI", 8),
            bd=0, relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.screen_w_entry.pack(side=tk.LEFT, padx=(2, 4), ipady=1)
        self.screen_w_entry.insert(0, "1920")

        tk.Label(res_frame, text="H:", bg=COLORS["bg_card"], fg=COLORS["text_dim"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.screen_h_entry = tk.Entry(
            res_frame, width=5, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"],
            insertbackground=COLORS["red_primary"], font=("Segoe UI", 8),
            bd=0, relief="flat", highlightthickness=1, highlightbackground=COLORS["border"]
        )
        self.screen_h_entry.pack(side=tk.LEFT, padx=(2, 0), ipady=1)
        self.screen_h_entry.insert(0, "1080")

        # --- Live Navigation Info Card ---
        tk.Label(
            cc, text="LIVE NAVIGATION METRICS", 
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"], 
            font=("Segoe UI", 7, "bold")
        ).pack(anchor="w", pady=(2, 2))

        self.metrics_frame = tk.Frame(cc, bg=COLORS["bg_card_inner"], padx=5, pady=4, bd=1, relief="solid", highlightbackground=COLORS["border"])
        self.metrics_frame.pack(fill=tk.X, pady=(0, 8))

        self.node_lbl = tk.Label(self.metrics_frame, text="Active Node: None", bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold"), anchor="w")
        self.node_lbl.pack(fill=tk.X)

        self.dist_lbl = tk.Label(self.metrics_frame, text="Distance: -- px", bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold"), anchor="w")
        self.dist_lbl.pack(fill=tk.X)

        self.progress_lbl = tk.Label(self.metrics_frame, text="Path Progress: 0%", bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold"), anchor="w")
        self.progress_lbl.pack(fill=tk.X)

        # --- Buttons ---
        self._build_btn_compact(cc, "💾 SAVE PATH WAYPOINTS", self._save_editor_path)
        self._build_btn_compact(cc, "🔄 RELOAD / LOAD PATH", self._load_editor_path)
        self._build_btn_compact(cc, "🗑️ CLEAR CURRENT CANVAS", self._clear_editor_canvas)

        # Instructions / Help box
        help_box = tk.Label(
            cc, text="💡 Click map to add waypoints.\n- Plotted dots connect in a loop.\n- Toggle in-game TAB map for live dot.",
            bg=COLORS["bg_card_inner"], fg=COLORS["text_dim"],
            font=("Segoe UI", 7), justify=tk.LEFT, anchor="w",
            padx=4, pady=3, bd=1, relief="solid", highlightbackground=COLORS["border"]
        )
        help_box.pack(fill=tk.X, side=tk.BOTTOM, pady=3)

        # State fields
        self.editor_waypoints = []
        self.editor_photo_image = None
        self._map_img_w = 648  # Actual loaded map image width
        self._map_img_h = 489  # Actual loaded map image height
        
        # Load Q5 by default if exists
        self.root.after(100, lambda: self._on_editor_map_changed("q5 map"))

    def _build_btn_compact(self, parent, text, cmd):
        card = ModernCard(parent, bg=COLORS["bg_card_inner"], border_color=COLORS["border"], radius=6, height=28)
        card.pack(pady=3, fill=tk.X)
        card.pack_propagate(False)
        
        lbl = tk.Label(
            card.container, text=text, bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 7, "bold"), cursor="hand2"
        )
        lbl.pack(fill=tk.BOTH, expand=True)
        
        def on_enter(e):
            card.bg_color = COLORS["bg_card"]
            card.border_color = COLORS["red_primary"]
            lbl.config(bg=COLORS["bg_card"], fg=COLORS["text_primary"])
            card._on_resize()
            
        def on_leave(e):
            card.bg_color = COLORS["bg_card_inner"]
            card.border_color = COLORS["border"]
            lbl.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"])
            card._on_resize()
            
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", lambda e: cmd())

    def _scan_available_maps(self):
        """Scan assests/ for PNG image files (real in-game map screenshots)."""
        assests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assests")
        os.makedirs(assests_dir, exist_ok=True)
        pattern = os.path.join(assests_dir, "*.png")
        files = glob.glob(pattern)
        names = []
        for f in files:
            base = os.path.basename(f)
            name, _ = os.path.splitext(base)
            names.append(name)
        if not names:
            names = ["q5 map"]  # Fallback
        return names

    def _on_editor_map_changed(self, selected_name):
        """Handle when the background map selection changes in the editor."""
        self.map_name_entry.delete(0, tk.END)
        self.map_name_entry.insert(0, selected_name)
        
        # Load background image from assests/ directory
        assests_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assests")
        img_path = os.path.join(assests_dir, f"{selected_name}.png")
        if os.path.exists(img_path):
            try:
                # Load with PIL, store original dimensions, and resize to fit canvas
                pil_img = Image.open(img_path).convert("RGBA")
                self._map_img_w, self._map_img_h = pil_img.size
                pil_resized = pil_img.resize((520, 390), Image.Resampling.LANCZOS)
                self.editor_photo_image = ImageTk.PhotoImage(pil_resized)
                
                # Draw on canvas
                self.editor_canvas.delete("all")
                self.editor_canvas.create_image(0, 0, anchor="nw", image=self.editor_photo_image)
                self._append_log(f"Editor background map set to: {selected_name}.png (from assests/)", "info")
            except Exception as e:
                self._append_log(f"Failed to load map image {img_path}: {e}", "error")
        else:
            self.editor_canvas.delete("all")
            self.editor_canvas.create_text(260, 195, text=f"Map image {selected_name}.png not found in assests/.", fill=COLORS["text_dim"])
            self._append_log(f"Map image not found: {img_path}", "warning")

        # Load existing waypoints if JSON file exists
        self._load_editor_path()

    def _on_canvas_click(self, event):
        """Handle canvas left clicks to place waypoints."""
        cx, cy = event.x, event.y
        
        # Boundaries validation
        if cx < 0 or cx > 520 or cy < 0 or cy > 390:
            return
            
        # Get canvas scaling factors (canvas is 520x390, image is _map_img_w x _map_img_h)
        scale_x = 520.0 / self._map_img_w
        scale_y = 390.0 / self._map_img_h
        ix = cx / scale_x
        iy = cy / scale_y
        
        # Get screen calibration variables
        try:
            W = int(self.screen_w_entry.get())
            H = int(self.screen_h_entry.get())
        except ValueError:
            W, H = 1920, 1080
            
        # Calculate transparent map overlay boundaries on the 1920x1080 (or WxH) screen
        MW = W * 0.625
        MH = H * 0.833
        Left = (W - MW) / 2
        Top = (H - MH) / 2
        
        # Map back to full-screen in-game overlay coordinates
        mx = int(Left + (ix / self._map_img_w) * MW)
        my = int(Top + (iy / self._map_img_h) * MH)
        
        # Store waypoint
        wp = {"x": mx, "y": my, "mx": mx, "my": my}
        self.editor_waypoints.append(wp)
        
        # Redraw
        self._redraw_editor_waypoints()
        self._append_log(f"Placed waypoint #{len(self.editor_waypoints)} at screen ({mx}, {my})", "info")

    def _redraw_editor_waypoints(self):
        """Redraw waypoints, danger zones, and sequential dashed lines on the editor canvas."""
        # Clear existing elements
        self.editor_canvas.delete("wp")
        self.editor_canvas.delete("wp_danger")
        
        # 1. Draw Danger / Heat Zones (Holographic sci-fi circles)
        map_name = self.map_name_entry.get().strip().lower()
        if "q5" in map_name:
            # Danger Zone (Boss room on Q5)
            self.editor_canvas.create_oval(
                442 - 40, 247 - 40, 442 + 40, 247 + 40,
                outline="#ff3333", width=1.5, dash=(4, 4), tags="wp_danger"
            )
            self.editor_canvas.create_text(
                442, 247, text="☠️ BOSS ZONE", fill="#ff5555",
                font=("Segoe UI", 7, "bold"), tags="wp_danger"
            )
            
            # Mob Density Zone
            self.editor_canvas.create_oval(
                312 - 30, 65 - 30, 312 + 30, 65 + 30,
                outline="#ffcc00", width=1.5, dash=(4, 4), tags="wp_danger"
            )
            self.editor_canvas.create_text(
                312, 65, text="⚠️ MOB ELITES", fill="#ffdd33",
                font=("Segoe UI", 7, "bold"), tags="wp_danger"
            )
        else:
            # Decorative default zone
            self.editor_canvas.create_oval(
                260 - 35, 195 - 35, 260 + 35, 195 + 35,
                outline="#ff8800", width=1, dash=(3, 3), tags="wp_danger"
            )
            self.editor_canvas.create_text(
                260, 195, text="⚡ PATROL ZONE", fill="#ffaa44",
                font=("Segoe UI", 7, "bold"), tags="wp_danger"
            )

        if not self.editor_waypoints:
            return

        try:
            W = int(self.screen_w_entry.get())
            H = int(self.screen_h_entry.get())
        except ValueError:
            W, H = 1920, 1080

        MW = W * 0.625
        MH = H * 0.833
        Left = (W - MW) / 2
        Top = (H - MH) / 2

        coords = []
        for i, wp in enumerate(self.editor_waypoints):
            # Scale overlay coordinate back to canvas coordinates
            mx = wp.get("mx", wp.get("x", 960))
            my = wp.get("my", wp.get("y", 540))
            
            ix = ((mx - Left) / MW) * self._map_img_w
            iy = ((my - Top) / MH) * self._map_img_h
            cx = ix * (520.0 / self._map_img_w)
            cy = iy * (390.0 / self._map_img_h)
            coords.append((cx, cy))

            # Fetch active target from bot
            is_active_target = False
            if hasattr(self, 'bot') and self.bot._bot_active:
                if hasattr(self.bot, 'navigation') and self.bot.navigation:
                    if self.bot.navigation.current_index == i:
                        is_active_target = True

            # Draw glowing green/red/gold dot for waypoint
            if is_active_target:
                color = COLORS["gold"]
                outline_color = "#ffffff"
                dot_size = 8
            else:
                color = COLORS["success"] if i == 0 else COLORS["error"]
                outline_color = COLORS["gold"]
                dot_size = 6
                
            self.editor_canvas.create_oval(
                cx - dot_size, cy - dot_size, cx + dot_size, cy + dot_size,
                fill=color, outline=outline_color, width=1.5 if is_active_target else 1, tags="wp"
            )
            
            # Label
            self.editor_canvas.create_text(cx, cy - 14, text=str(i + 1), fill=COLORS["text_primary"], font=("Segoe UI", 8, "bold"), tags="wp")

        # Determine connecting line colors based on path type
        path_type = self.path_type_var.get() if hasattr(self, 'path_type_var') else "⚔️ Farming Loop"
        if "Boss" in path_type:
            base_line_color = "#ff3333"
        elif "Safe" in path_type:
            base_line_color = "#33ff33"
        elif "Loot" in path_type:
            base_line_color = "#ffcc00"
        else:
            base_line_color = "#00ffff" # Cyan default

        # Draw connecting lines
        for i in range(len(coords)):
            c1 = coords[i]
            c2 = coords[(i + 1) % len(coords)] # Loop back to first point
            
            is_loop_back = (i == len(coords) - 1)
            line_color = COLORS["gold"] if is_loop_back else base_line_color
            line_dash = (3, 3) if is_loop_back else None
            
            if len(coords) > 1:
                self.editor_canvas.create_line(c1[0], c1[1], c2[0], c2[1], fill=line_color, dash=line_dash, width=1.5, tags="wp")

    def _save_editor_path(self):
        """Save the editor waypoints to the JSON file."""
        map_name = self.map_name_entry.get().strip()
        if not map_name:
            messagebox.showerror("Error", "Please specify a map path name first!")
            return

        if not self.editor_waypoints:
            messagebox.showerror("Error", "No waypoints placed on canvas to save!")
            return

        try:
            # Update the bot navigation waypoints list
            if hasattr(self.bot, 'navigation') and self.bot.navigation:
                self.bot.navigation.waypoints = self.editor_waypoints.copy()
                self.bot.navigation.active_map_name = map_name
                self.bot.navigation._save_waypoints()
                
                # Append log
                self._append_log(f"Navigation System: Saved {len(self.editor_waypoints)} waypoints to maps/{map_name}.json", "warning")
                self._add_notification(f"Saved {map_name} path", "Success")
                messagebox.showinfo("Success", f"Waypoints saved successfully to maps/{map_name}.json!")
            else:
                self._append_log("Bot navigation system is not active.", "error")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save waypoints: {e}")

    def _load_editor_path(self):
        """Load waypoints from the JSON map file if exists."""
        map_name = self.map_name_entry.get().strip()
        if not map_name:
            return

        map_file = os.path.join("config", "maps", f"{map_name}.json")
        if os.path.exists(map_file):
            try:
                # Load waypoints into editor
                import json
                with open(map_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    self.editor_waypoints = data
                elif isinstance(data, dict) and "waypoints" in data:
                    self.editor_waypoints = data["waypoints"]
                    
                self._redraw_editor_waypoints()
                self._append_log(f"Loaded {len(self.editor_waypoints)} waypoints from maps/{map_name}.json", "info")
                
                # Update bot too
                if hasattr(self.bot, 'navigation') and self.bot.navigation:
                    self.bot.navigation.waypoints = self.editor_waypoints.copy()
                    self.bot.navigation.active_map_name = map_name
                    self.bot.navigation._current_waypoint_index = 0
            except Exception as e:
                self._append_log(f"Failed to load map path JSON: {e}", "error")
        else:
            self.editor_waypoints = []
            self.editor_canvas.delete("wp")
            self._append_log(f"No existing waypoints JSON found for map '{map_name}'. Let's place some!", "info")

    def _clear_editor_canvas(self):
        """Wipe the current active list of waypoints and redraw."""
        self.editor_waypoints = []
        self._redraw_editor_waypoints()
        self._append_log("Waypoint Editor canvas wiped.", "info")

    def _update_waypoint_canvas_animation(self):
        """Perform real-time waypoint canvas animations (energy flow and player dot)."""
        if not hasattr(self, 'editor_canvas') or not self.editor_canvas:
            return

        # Clear existing dynamic/animated elements
        self.editor_canvas.delete("wp_dynamic")

        # 1. Update Energy Flow Particles along the lines
        if self.editor_waypoints and len(self.editor_waypoints) > 1:
            try:
                W = int(self.screen_w_entry.get())
                H = int(self.screen_h_entry.get())
            except ValueError:
                W, H = 1920, 1080

            MW = W * 0.625
            MH = H * 0.833
            Left = (W - MW) / 2
            Top = (H - MH) / 2

            # Calculate all canvas coordinates
            coords = []
            for wp in self.editor_waypoints:
                mx = wp.get("mx", wp.get("x", 960))
                my = wp.get("my", wp.get("y", 540))
                ix = ((mx - Left) / MW) * self._map_img_w
                iy = ((my - Top) / MH) * self._map_img_h
                coords.append((ix * (520.0 / self._map_img_w), iy * (390.0 / self._map_img_h)))

            # Increment animation offset
            if not hasattr(self, 'path_flow_offset'):
                self.path_flow_offset = 0.0
            self.path_flow_offset += 0.02
            if self.path_flow_offset > 1.0:
                self.path_flow_offset = 0.0

            # Draw a flowing packet on each segment
            path_type = self.path_type_var.get() if hasattr(self, 'path_type_var') else "⚔️ Farming Loop"
            flow_color = "#ffffff" # default white glow
            if "Boss" in path_type:
                flow_color = "#ff8888"
            elif "Safe" in path_type:
                flow_color = "#88ff88"
            elif "Loot" in path_type:
                flow_color = "#ffee88"
            else:
                flow_color = "#88ffff"

            for i in range(len(coords)):
                c1 = coords[i]
                c2 = coords[(i + 1) % len(coords)]
                
                # Interpolate particle position
                px = c1[0] + (c2[0] - c1[0]) * self.path_flow_offset
                py = c1[1] + (c2[1] - c1[1]) * self.path_flow_offset
                
                # Draw particle
                self.editor_canvas.create_oval(
                    px - 3, py - 3, px + 3, py + 3,
                    fill=flow_color, outline="#ffffff", width=1, tags="wp_dynamic"
                )

        # 2. Draw Live Player Position (Live Sync) and direction arrow
        bot_active = self.bot._bot_active if hasattr(self.bot, '_bot_active') else False
        player_pos = None
        if bot_active and hasattr(self.bot, 'navigation') and self.bot.navigation:
            player_pos = self.bot.navigation.player_minimap_pos

        if player_pos is not None:
            px, py = player_pos
            try:
                W = int(self.screen_w_entry.get())
                H = int(self.screen_h_entry.get())
            except ValueError:
                W, H = 1920, 1080

            MW = W * 0.625
            MH = H * 0.833
            Left = (W - MW) / 2
            Top = (H - MH) / 2

            # Map player pos to canvas
            ix = ((px - Left) / MW) * self._map_img_w
            iy = ((py - Top) / MH) * self._map_img_h
            pcx = ix * (520.0 / self._map_img_w)
            pcy = iy * (390.0 / self._map_img_h)

            # Pulsing green dot
            pulse_rad = 6 + 3 * math.sin(self._glow_phase * 2)
            self.editor_canvas.create_oval(
                pcx - pulse_rad, pcy - pulse_rad, pcx + pulse_rad, pcy + pulse_rad,
                fill="", outline="#33ff33", width=1.5, tags="wp_dynamic"
            )
            self.editor_canvas.create_oval(
                pcx - 3, pcy - 3, pcx + 3, pcy + 3,
                fill="#33ff33", outline="#ffffff", width=1, tags="wp_dynamic"
            )
            
            # Text label
            self.editor_canvas.create_text(
                pcx, pcy + 15, text="YOU", fill="#33ff33",
                font=("Segoe UI", 7, "bold"), tags="wp_dynamic"
            )

            # Draw line and direction arrow to current target waypoint
            curr_idx = self.bot.navigation.current_index
            if 0 <= curr_idx < len(self.editor_waypoints):
                target_wp = self.editor_waypoints[curr_idx]
                tmx = target_wp.get("mx", target_wp.get("x", 960))
                tmy = target_wp.get("my", target_wp.get("y", 540))
                
                tix = ((tmx - Left) / MW) * self._map_img_w
                tiy = ((tmy - Top) / MH) * self._map_img_h
                tcx = tix * (520.0 / self._map_img_w)
                tcy = tiy * (390.0 / self._map_img_h)
                
                # Draw connecting arrow line
                self.editor_canvas.create_line(
                    pcx, pcy, tcx, tcy, fill="#ffcc00",
                    dash=(2, 2), arrow=tk.LAST, width=1.5, tags="wp_dynamic"
                )

                # Update live labels!
                # Calculate distance
                dist = math.sqrt((tmx - px) ** 2 + (tmy - py) ** 2)
                self.node_lbl.config(text=f"Active Node: #{curr_idx + 1} / {len(self.editor_waypoints)}")
                self.dist_lbl.config(text=f"Distance: {dist:.1f} px", fg="#ffcc00" if dist > 30 else "#33ff33")
                
                progress = int((curr_idx / len(self.editor_waypoints)) * 100)
                self.progress_lbl.config(text=f"Path Progress: {progress}%")
        else:
            # Clear or show none when bot not running/minimap not tracked
            self.node_lbl.config(text="Active Node: None")
            self.dist_lbl.config(text="Distance: -- px", fg=COLORS["text_secondary"])
            self.progress_lbl.config(text="Path Progress: 0%")

    def _on_controls_map_changed(self, selected_map):
        """Sync map changes from the controls page to the waypoint system."""
        try:
            map_file = os.path.join("config", "maps", f"{selected_map}.json")
            if os.path.exists(map_file):
                if hasattr(self.bot, 'navigation') and self.bot.navigation:
                    self.bot.navigation.load_waypoints_from_file(map_file)
                    self._append_log(f"Bot active path switched to map: {selected_map}", "warning")
                    self._add_notification(f"Path: {selected_map}", "Success")
                    # Update editor dropdown if it exists
                    if hasattr(self, 'active_map_file_var'):
                        self.active_map_file_var.set(selected_map)
                        self._on_editor_map_changed(selected_map)
            else:
                self._append_log(f"No JSON waypoint file found for map: {selected_map}", "warning")
        except Exception as e:
            self._append_log(f"Failed to load map path: {e}", "error")

    # Redundant Logs Page removed (Integrated into Home dashboard)

    def _append_log(self, message, tag="info"):
        if not hasattr(self, 'log_text') or not self.log_text:
            return
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            self.log_text.config(state=tk.DISABLED)
            self._append_log("System console cleared.", "info")

    def _build_combos_page(self):
        from tkinter import ttk
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["combos"] = page

        # Split into Left Panel (List & Controls) and Right Panel (Status & Tips)
        left_panel = tk.Frame(page, bg=COLORS["bg_dark"])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_panel = tk.Frame(page, bg=COLORS["bg_dark"], width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_panel.pack_propagate(False)

        # -------------------------------------------------------------
        # LEFT PANEL: Dynamic Combo List Builder
        # -------------------------------------------------------------
        combo_card = ModernCard(left_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        combo_card.pack(fill=tk.BOTH, expand=True)
        c = combo_card.container

        # Header
        header = tk.Frame(c, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        tk.Label(
            header, text="🎯  DYNAMIC COMBAT COMBO ENGINE",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        # Enable/Disable Switch Frame
        enable_frame = tk.Frame(c, bg=COLORS["bg_card"])
        enable_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        # Checkbox state
        self._combo_enabled_var = tk.BooleanVar(value=True)
        if hasattr(self.bot, "combat") and self.bot.combat:
            self._combo_enabled_var.set(self.bot.combat.combo_enabled)

        def toggle_combo_engine():
            enabled = self._combo_enabled_var.get()
            if hasattr(self.bot, "combat") and self.bot.combat:
                self.bot.combat.combo_enabled = enabled
            self._append_log(f"Combat Combo Engine toggled: {'ENABLED' if enabled else 'DISABLED'}", "info")
            self._add_notification(f"Combo Engine: {'ON' if enabled else 'OFF'}", "Success" if enabled else "Info")

        chk_btn = tk.Checkbutton(
            enable_frame, text="Enable Combo Engine Logic",
            variable=self._combo_enabled_var,
            command=toggle_combo_engine,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["text_primary"],
            font=("Segoe UI", 9, "bold"), bd=0
        )
        chk_btn.pack(side=tk.LEFT)

        # Styled Table (Treeview) for Combo List
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Combo.Treeview",
            background=COLORS["bg_card_inner"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card_inner"],
            rowheight=26,
            bd=0,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Combo.Treeview.Heading",
            background=COLORS["bg_sidebar"],
            foreground=COLORS["text_secondary"],
            font=("Segoe UI", 9, "bold"),
            borderwidth=0
        )
        style.map(
            "Combo.Treeview",
            background=[("selected", COLORS["red_primary"])],
            foreground=[("selected", "white")]
        )

        tree_frame = tk.Frame(c, bg=COLORS["bg_card_inner"], bd=1, relief="solid", highlightthickness=0)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.combo_tree = ttk.Treeview(
            tree_frame, columns=("step", "key", "cooldown"),
            show="headings", style="Combo.Treeview"
        )
        self.combo_tree.heading("step", text="Step #", anchor="center")
        self.combo_tree.heading("key", text="Hotkey / Skill Button", anchor="center")
        self.combo_tree.heading("cooldown", text="Cooldown Delay (Seconds)", anchor="center")

        self.combo_tree.column("step", width=80, anchor="center")
        self.combo_tree.column("key", width=180, anchor="center")
        self.combo_tree.column("cooldown", width=180, anchor="center")
        self.combo_tree.pack(fill=tk.BOTH, expand=True)

        # Populate current combo
        self._populate_combo_tree()

        # Add / Insert Step Panel
        insert_frame = tk.Frame(c, bg=COLORS["bg_card"])
        insert_frame.pack(fill=tk.X, padx=15, pady=(10, 5))

        # Skill key entry
        tk.Label(insert_frame, text="Key:", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        self.combo_key_entry = tk.Entry(insert_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=4, insertbackground=COLORS["red_primary"], font=("Segoe UI", 9, "bold"))
        self.combo_key_entry.grid(row=0, column=1, padx=5)
        self.combo_key_entry.insert(0, "q")

        # Cooldown entry
        tk.Label(insert_frame, text="Cooldown (s):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8, "bold")).grid(row=0, column=2, padx=5, sticky="w")
        self.combo_cd_entry = tk.Entry(insert_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=4, insertbackground=COLORS["red_primary"], font=("Segoe UI", 9, "bold"))
        self.combo_cd_entry.grid(row=0, column=3, padx=5)
        self.combo_cd_entry.insert(0, "1.5")

        def add_combo_step():
            key = self.combo_key_entry.get().strip()
            cd_str = self.combo_cd_entry.get().strip()
            if not key:
                self._add_notification("Skill key cannot be empty!", "Error")
                return
            try:
                cooldown = float(cd_str)
                if cooldown < 0:
                    raise ValueError
            except ValueError:
                self._add_notification("Cooldown must be a positive number!", "Error")
                return

            # Append to tree
            count = len(self.combo_tree.get_children()) + 1
            self.combo_tree.insert("", "end", values=(f"#{count}", key, f"{cooldown}s"))
            self._add_notification(f"Added: Step #{count} -> [{key}]", "Success")

        # Add button
        btn_add = tk.Label(insert_frame, text="  ＋ ADD STEP  ", bg=COLORS["success"], fg="white", font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_add.grid(row=0, column=4, padx=10)
        btn_add.bind("<Button-1>", lambda e: add_combo_step())

        # Action Buttons Panel
        btn_frame = tk.Frame(c, bg=COLORS["bg_card"])
        btn_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

        def remove_selected():
            sel = self.combo_tree.selection()
            if not sel:
                self._add_notification("Please select a step to remove", "Info")
                return
            for item in sel:
                self.combo_tree.delete(item)
            self._renumber_combo_steps()
            self._add_notification("Removed step from combo sequence", "Warning")

        def move_up():
            sel = self.combo_tree.selection()
            if not sel:
                return
            for item in sel:
                idx = self.combo_tree.index(item)
                if idx > 0:
                    self.combo_tree.move(item, "", idx - 1)
            self._renumber_combo_steps()

        def move_down():
            sel = self.combo_tree.selection()
            if not sel:
                return
            for item in sel:
                idx = self.combo_tree.index(item)
                self.combo_tree.move(item, "", idx + 1)
            self._renumber_combo_steps()

        def save_combo():
            sequence = []
            cooldowns = []
            for child in self.combo_tree.get_children():
                values = self.combo_tree.item(child)["values"]
                sequence.append(str(values[1]))
                cooldowns.append(float(str(values[2]).replace("s", "")))

            # Update in memory
            if hasattr(self.bot, "combat") and self.bot.combat:
                self.bot.combat.combo_sequence = sequence
                self.bot.combat.combo_cooldowns = cooldowns
                self.bot.combat._combo_step = 0
                self.bot.combat._combo_last_used = {k: 0 for k in sequence}
            
            # Save to config file settings.json
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    
                    if "combat" not in cfg:
                        cfg["combat"] = {}
                    cfg["combat"]["combo_sequence"] = sequence
                    cfg["combat"]["combo_cooldowns"] = cooldowns
                    cfg["combat"]["combo_enabled"] = self._combo_enabled_var.get()

                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                
                self._append_log(f"Saved custom combo to settings.json: {sequence}", "warning")
                self._add_notification("Combo Sequence Saved & Applied!", "Success")
            except Exception as e:
                self._append_log(f"Failed to save settings: {e}", "error")

        def reset_defaults():
            # Get current active class profile from combat system
            if hasattr(self.bot, "combat") and self.bot.combat:
                from combat.class_profiles import get_profile
                profile = get_profile(self.bot.combat.active_class)
                seq = profile.get("combo_sequence", ["2", "3", "1", "1", "1"])
                cds = profile.get("combo_cooldowns", [0.0, 5.0, 8.0, 2.0, 2.0])
                
                # Clear tree
                for child in self.combo_tree.get_children():
                    self.combo_tree.delete(child)
                
                for idx, (key, cd) in enumerate(zip(seq, cds)):
                    self.combo_tree.insert("", "end", values=(f"#{idx+1}", key, f"{cd}s"))
                
                self._add_notification(f"Reset combo to {profile.get('display_name')} defaults!", "Info")

        # Render action buttons
        btn_up = tk.Label(btn_frame, text="  ▲ MOVE UP  ", bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_up.pack(side=tk.LEFT, padx=5)
        btn_up.bind("<Button-1>", lambda e: move_up())

        btn_down = tk.Label(btn_frame, text="  ▼ MOVE DOWN  ", bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_down.pack(side=tk.LEFT, padx=5)
        btn_down.bind("<Button-1>", lambda e: move_down())

        btn_del = tk.Label(btn_frame, text="  ✕ REMOVE STEP  ", bg=COLORS["red_dark"], fg="white", font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_del.pack(side=tk.LEFT, padx=5)
        btn_del.bind("<Button-1>", lambda e: remove_selected())

        btn_reset = tk.Label(btn_frame, text="  🔄 RESET TO DEFAULT  ", bg=COLORS["bg_card_inner"], fg=COLORS["text_secondary"], font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_reset.pack(side=tk.LEFT, padx=5)
        btn_reset.bind("<Button-1>", lambda e: reset_defaults())

        btn_save = tk.Label(btn_frame, text="  💾 SAVE & APPLY  ", bg=COLORS["red_primary"], fg="white", font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_save.pack(side=tk.RIGHT, padx=5)
        btn_save.bind("<Button-1>", lambda e: save_combo())


        # -------------------------------------------------------------
        # RIGHT PANEL: Info, Guide & Monitoring Stats
        # -------------------------------------------------------------
        info_card = ModernCard(right_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        info_card.pack(fill=tk.BOTH, expand=True)
        rc = info_card.container

        tk.Label(
            rc, text="◈ ENGINE GUIDE",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 10))

        guide_text = (
            "Drakensang AI supports fully custom combat skill rotations (Combos).\n\n"
            "How it works:\n"
            "1. When COMBAT activates, the FSM triggers the Combo Engine.\n"
            "2. The bot cycles through the steps in order (1, 2, 3...).\n"
            "3. If a step's cooldown is still active, it skips to the next ready skill.\n"
            "4. If all skills are on cooldown, it falls back to your Basic Attack key.\n\n"
            "Tips:\n"
            "- Start with CC/Stun keys first (e.g. key '3' for Ranger).\n"
            "- Put buffs next, then heavy damage bursers.\n"
            "- Always set appropriate cooldowns (in seconds) to avoid spamming skills that are not ready."
        )

        tb = tk.Label(
            rc, text=guide_text,
            bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
            font=("Segoe UI", 8), justify="left", wraplength=250
        )
        tb.pack(anchor="w", padx=10, pady=5)

        # Divider
        tk.Frame(rc, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=10, pady=15)

        # Real-time rotation monitoring details card
        tk.Label(
            rc, text="◈ REAL-TIME STATUS",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(0, 5))

        self.combo_status_class = tk.Label(rc, text="Class Profile: Loading...", bg=COLORS["bg_card"], fg=COLORS["text_primary"], font=("Segoe UI", 9, "bold"))
        self.combo_status_class.pack(anchor="w", padx=10, pady=2)

        self.combo_status_step = tk.Label(rc, text="Current Step: Step #0", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 9))
        self.combo_status_step.pack(anchor="w", padx=10, pady=2)

        self.combo_status_skill = tk.Label(rc, text="Next Ready Skill: --", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 9))
        self.combo_status_skill.pack(anchor="w", padx=10, pady=2)

        self._update_combo_monitoring_loop()

    def _build_macros_page(self):
        from tkinter import ttk
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["macros"] = page

        # Split into Left Panel (List & Input) and Right Panel (Settings & Profiles)
        left_panel = tk.Frame(page, bg=COLORS["bg_dark"])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_panel = tk.Frame(page, bg=COLORS["bg_dark"], width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_panel.pack_propagate(False)

        # -------------------------------------------------------------
        # LEFT PANEL: 10 Skill Macro Slots Treeview
        # -------------------------------------------------------------
        macro_card = ModernCard(left_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        macro_card.pack(fill=tk.BOTH, expand=True)
        mc = macro_card.container

        # Header
        header = tk.Frame(mc, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        tk.Label(
            header, text="🎮  SMART MACRO PROFILE EDITOR (10 SLOTS)",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.LEFT)

        # Treeview frame
        tree_frame = tk.Frame(mc, bg=COLORS["bg_card_inner"], bd=1, relief="solid", highlightthickness=0)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.macro_tree = ttk.Treeview(
            tree_frame, columns=("slot", "label", "key", "condition", "intent", "cooldown", "range", "delay"),
            show="headings", style="Combo.Treeview"
        )
        self.macro_tree.heading("slot", text="Slot", anchor="center")
        self.macro_tree.heading("label", text="Skill Name / Label", anchor="center")
        self.macro_tree.heading("key", text="Hotkey", anchor="center")
        self.macro_tree.heading("condition", text="Condition", anchor="center")
        self.macro_tree.heading("intent", text="Skill Intent", anchor="center")
        self.macro_tree.heading("cooldown", text="Cooldown", anchor="center")
        self.macro_tree.heading("range", text="Range (px)", anchor="center")
        self.macro_tree.heading("delay", text="Pre-cast Delay", anchor="center")

        self.macro_tree.column("slot", width=45, anchor="center")
        self.macro_tree.column("label", width=110, anchor="w")
        self.macro_tree.column("key", width=55, anchor="center")
        self.macro_tree.column("condition", width=95, anchor="center")
        self.macro_tree.column("intent", width=95, anchor="center")
        self.macro_tree.column("cooldown", width=75, anchor="center")
        self.macro_tree.column("range", width=75, anchor="center")
        self.macro_tree.column("delay", width=75, anchor="center")
        self.macro_tree.pack(fill=tk.BOTH, expand=True)

        # Slot Editor inputs below the tree
        editor_frame = tk.LabelFrame(
            mc, text=" EDIT SELECTED SLOT ", bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 8, "bold"), labelanchor="nw", bd=1, relief="solid",
            highlightbackground=COLORS["border"], padx=10, pady=5
        )
        editor_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

        # Inputs layout:
        # Row 0: Label, Hotkey, Condition, Intent
        tk.Label(editor_frame, text="Name/Label:", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w", pady=2)
        self.mac_label_entry = tk.Entry(editor_frame, width=12, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3)
        self.mac_label_entry.grid(row=0, column=1, padx=3, pady=2)

        tk.Label(editor_frame, text="Hotkey:", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w", pady=2)
        self.mac_key_entry = tk.Entry(editor_frame, width=6, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3)
        self.mac_key_entry.grid(row=0, column=3, padx=3, pady=2)

        tk.Label(editor_frame, text="Condition:", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=0, column=4, sticky="w", pady=2)
        self.mac_cond_var = tk.StringVar(value="always")
        mac_cond_dropdown = tk.OptionMenu(
            editor_frame, self.mac_cond_var, "always", "enemy_in_range", "low_hp", "surrounded", "boss_detected", "off_cooldown"
        )
        mac_cond_dropdown.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", font=("Segoe UI", 8, "bold"), bd=0)
        mac_cond_dropdown.grid(row=0, column=5, padx=3, pady=2)

        tk.Label(editor_frame, text="Intent:", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=0, column=6, sticky="w", pady=2)
        self.mac_intent_var = tk.StringVar(value="single_dps")
        mac_intent_dropdown = tk.OptionMenu(
            editor_frame, self.mac_intent_var, "single_dps", "aoe_burst", "cc", "buff", "escape", "heal"
        )
        mac_intent_dropdown.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", font=("Segoe UI", 8, "bold"), bd=0)
        mac_intent_dropdown.grid(row=0, column=7, padx=3, pady=2)

        # Row 1: Cooldown, Range, Delay
        tk.Label(editor_frame, text="CD (s):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=1, column=0, sticky="w", pady=2)
        self.mac_cooldown_entry = tk.Entry(editor_frame, width=12, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3)
        self.mac_cooldown_entry.grid(row=1, column=1, padx=3, pady=2)

        tk.Label(editor_frame, text="Range (px):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=1, column=2, sticky="w", pady=2)
        self.mac_range_entry = tk.Entry(editor_frame, width=6, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3)
        self.mac_range_entry.grid(row=1, column=3, padx=3, pady=2)

        tk.Label(editor_frame, text="Delay (s):", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 8)).grid(row=1, column=4, sticky="w", pady=2)
        self.mac_delay_entry = tk.Entry(editor_frame, width=8, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=3)
        self.mac_delay_entry.grid(row=1, column=5, padx=3, pady=2)

        # Update button inside Slot Editor
        def update_selected_slot():
            sel = self.macro_tree.selection()
            if not sel:
                self._add_notification("Please select a slot in the tree to edit!", "Info")
                return
            item = sel[0]
            values = self.macro_tree.item(item)["values"]
            
            lbl = self.mac_label_entry.get().strip()
            key = self.mac_key_entry.get().strip()
            cond = self.mac_cond_var.get()
            intent = self.mac_intent_var.get()
            
            try:
                cd = float(self.mac_cooldown_entry.get())
                rng = int(self.mac_range_entry.get())
                del_val = float(self.mac_delay_entry.get())
            except ValueError:
                self._add_notification("Invalid number values entered!", "Error")
                return
                
            self.macro_tree.item(item, values=(values[0], lbl, key, cond, intent, f"{cd}s", f"{rng}px", f"{del_val}s"))
            self._add_notification(f"Updated Slot {values[0]}", "Success")

        btn_update_slot = tk.Label(editor_frame, text=" UPDATE SLOT ", bg=COLORS["success"], fg="white", font=("Segoe UI", 8, "bold"), cursor="hand2", height=2)
        btn_update_slot.grid(row=0, column=8, rowspan=2, padx=10, sticky="nsew")
        btn_update_slot.bind("<Button-1>", lambda e: update_selected_slot())

        # Select row binding to populate inputs
        def on_tree_select(event):
            sel = self.macro_tree.selection()
            if not sel:
                return
            values = self.macro_tree.item(sel[0])["values"]
            self.mac_label_entry.delete(0, tk.END)
            self.mac_label_entry.insert(0, str(values[1]))
            self.mac_key_entry.delete(0, tk.END)
            self.mac_key_entry.insert(0, str(values[2]))
            self.mac_cond_var.set(str(values[3]))
            self.mac_intent_var.set(str(values[4]))
            self.mac_cooldown_entry.delete(0, tk.END)
            self.mac_cooldown_entry.insert(0, str(values[5]).replace("s", ""))
            self.mac_range_entry.delete(0, tk.END)
            self.mac_range_entry.insert(0, str(values[6]).replace("px", ""))
            self.mac_delay_entry.delete(0, tk.END)
            self.mac_delay_entry.insert(0, str(values[7]).replace("s", ""))

        self.macro_tree.bind("<<TreeviewSelect>>", on_tree_select)

        # -------------------------------------------------------------
        # RIGHT PANEL: Profile Selection and Global Options
        # -------------------------------------------------------------
        profile_card = ModernCard(right_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        profile_card.pack(fill=tk.BOTH, expand=True)
        pc_c = profile_card.container

        tk.Label(
            pc_c, text="◈ PROFILE CONFIG",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 10))

        # Profile Select Menu
        tk.Label(pc_c, text="ACTIVE MACRO PROFILE", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10)
        
        self.macro_profiles_list = ["Default", "Custom", "Ranger", "Mage", "Dragonknight", "Steam"]
        self.active_macro_profile_var = tk.StringVar(value="Default")
        
        def on_macro_profile_changed(profile_name):
            self._load_macro_slots_into_gui(profile_name)

        macro_profile_menu = tk.OptionMenu(
            pc_c, self.active_macro_profile_var, *self.macro_profiles_list, command=on_macro_profile_changed
        )
        macro_profile_menu.config(bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", font=("Segoe UI", 8, "bold"), bd=0)
        macro_profile_menu.pack(fill=tk.X, padx=10, pady=(2, 10))

        # Checkboxes for parameters
        self.macro_enabled_var = tk.BooleanVar(value=True)
        chk_mac_enabled = tk.Checkbutton(
            pc_c, text="Enable Smart Macro Evaluator", variable=self.macro_enabled_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"], selectcolor=COLORS["bg_card_inner"], font=("Segoe UI", 8, "bold"), bd=0
        )
        chk_mac_enabled.pack(anchor="w", padx=10, pady=3)

        self.prioritize_elites_var = tk.BooleanVar(value=True)
        chk_elites = tk.Checkbutton(
            pc_c, text="Prioritize Elite/Mini-Bosses", variable=self.prioritize_elites_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"], selectcolor=COLORS["bg_card_inner"], font=("Segoe UI", 8, "bold"), bd=0
        )
        chk_elites.pack(anchor="w", padx=10, pady=3)

        self.auto_dodge_var = tk.BooleanVar(value=True)
        chk_dodge = tk.Checkbutton(
            pc_c, text="Auto Dodge Boss Red AoE", variable=self.auto_dodge_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"], selectcolor=COLORS["bg_card_inner"], font=("Segoe UI", 8, "bold"), bd=0
        )
        chk_dodge.pack(anchor="w", padx=10, pady=3)

        self.mana_conservation_var = tk.BooleanVar(value=False)
        chk_mana = tk.Checkbutton(
            pc_c, text="Enable Mana Conservation Mode", variable=self.mana_conservation_var,
            bg=COLORS["bg_card"], fg=COLORS["text_primary"], selectcolor=COLORS["bg_card_inner"], font=("Segoe UI", 8, "bold"), bd=0
        )
        chk_mana.pack(anchor="w", padx=10, pady=3)

        # Save and reset actions
        def save_macro_profile():
            profile_name = self.active_macro_profile_var.get().strip()
            slots = []
            for child in self.macro_tree.get_children():
                values = self.macro_tree.item(child)["values"]
                slots.append({
                    "label": str(values[1]),
                    "key": str(values[2]),
                    "condition": str(values[3]),
                    "intent": str(values[4]),
                    "cooldown": float(str(values[5]).replace("s", "")),
                    "range": int(str(values[6]).replace("px", "")),
                    "delay": float(str(values[7]).replace("s", ""))
                })
            
            profile_data = {
                "profile_name": profile_name,
                "active_class": profile_name.lower(),
                "prioritize_elites": self.prioritize_elites_var.get(),
                "auto_dodge_boss_aoe": self.auto_dodge_var.get(),
                "mana_conservation": self.mana_conservation_var.get(),
                "slots": slots
            }
            
            # Save to config/macro_profiles/{name}.json
            try:
                os.makedirs(os.path.join("config", "macro_profiles"), exist_ok=True)
                filepath = os.path.join("config", "macro_profiles", f"{profile_name.lower().strip()}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(profile_data, f, indent=4)
                
                # Apply in memory
                if hasattr(self.bot, "combat") and self.bot.combat:
                    self.bot.combat.macro_enabled = self.macro_enabled_var.get()
                    self.bot.combat.active_macro_profile = profile_name
                    self.bot.combat.macro_slots = slots
                    self.bot.combat.prioritize_elites = self.prioritize_elites_var.get()
                    self.bot.combat.auto_dodge_boss_aoe = self.auto_dodge_var.get()
                    self.bot.combat.mana_conservation = self.mana_conservation_var.get()
                    self.bot.combat._macro_last_used = {slot["key"]: 0 for slot in slots}

                # Save main settings too
                config_path = os.path.join("config", "settings.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    cfg["combat"]["macro_enabled"] = self.macro_enabled_var.get()
                    cfg["combat"]["macro_profile_name"] = profile_name
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                
                self._append_log(f"Macro Profile '{profile_name}' saved and applied successfully!", "success")
                self._add_notification(f"Macro Saved: {profile_name}", "Success")
                messagebox.showinfo("Success", f"Macro Profile '{profile_name}' saved successfully!")
            except Exception as e:
                self._append_log(f"Failed to save macro profile: {e}", "error")

        def reset_macro_profile():
            profile_name = self.active_macro_profile_var.get()
            self._load_macro_slots_into_gui(profile_name)
            self._add_notification(f"Reset {profile_name} presets", "Info")

        # Action Buttons
        self._build_btn_compact(pc_c, "💾 SAVE PROFILE", save_macro_profile)
        self._build_btn_compact(pc_c, "🔄 RESET PRESETS", reset_macro_profile)

        # Load default by default
        self._load_macro_slots_into_gui("Default")

    def _load_macro_slots_into_gui(self, name: str):
        # Clear tree
        for child in self.macro_tree.get_children():
            self.macro_tree.delete(child)
            
        slots = []
        prioritize_elites = True
        auto_dodge = True
        mana_consv = False

        # Attempt to read from file first
        filename = f"{name.lower().strip()}.json"
        path = os.path.join("config", "macro_profiles", filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    slots = data.get("slots", [])
                    prioritize_elites = data.get("prioritize_elites", True)
                    auto_dodge = data.get("auto_dodge_boss_aoe", True)
                    mana_consv = data.get("mana_conservation", False)
            except Exception:
                pass

        # If not found, try to load class preset from knowledge layer
        if not slots:
            from knowledge.knowledge_loader import get_class_knowledge
            kw_data = get_class_knowledge(name)
            if kw_data:
                slots = kw_data.get("default_macro_slots", [])
                
        # Fallback to default.json
        if not slots:
            default_path = os.path.join("config", "macro_profiles", "default.json")
            if os.path.exists(default_path):
                try:
                    with open(default_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        slots = data.get("slots", [])
                except Exception:
                    pass

        # Load into treeview
        for idx, slot in enumerate(slots):
            label = slot.get("label", f"Skill {idx+1}")
            key = slot.get("key", "")
            cond = slot.get("condition", "always")
            intent = slot.get("intent", "single_dps")
            cd = slot.get("cooldown", 0.0)
            rng = slot.get("range", 9999)
            delay = slot.get("delay", 0.1)
            
            self.macro_tree.insert("", "end", values=(idx+1, label, key, cond, intent, f"{cd}s", f"{rng}px", f"{delay}s"))

        self.prioritize_elites_var.set(prioritize_elites)
        self.auto_dodge_var.set(auto_dodge)
        self.mana_conservation_var.set(mana_consv)

    def _build_offsets_page(self):
        from tkinter import ttk
        page = tk.Frame(self.main_content, bg=COLORS["bg_dark"])
        self.pages["offsets"] = page

        # Split into Left Panel (Offset List) and Right Panel (Actions & Editor)
        left_panel = tk.Frame(page, bg=COLORS["bg_dark"])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_panel = tk.Frame(page, bg=COLORS["bg_dark"], width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))
        right_panel.pack_propagate(False)

        # -------------------------------------------------------------
        # LEFT PANEL: Memory Offsets Treeview Table
        # -------------------------------------------------------------
        offsets_card = ModernCard(left_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        offsets_card.pack(fill=tk.BOTH, expand=True)
        oc_c = offsets_card.container

        # Header
        tk.Label(
            oc_c, text="🔧  MEMORY OFFSETS & BASE ADDRESSES",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Styled Table (Treeview) for Offsets
        tree_frame = tk.Frame(oc_c, bg=COLORS["bg_card_inner"], bd=1, relief="solid", highlightthickness=0)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        self.offsets_tree = ttk.Treeview(
            tree_frame, columns=("name", "offset", "description"),
            show="headings", style="Combo.Treeview"
        )
        self.offsets_tree.heading("name", text="Offset Name", anchor="w")
        self.offsets_tree.heading("offset", text="Memory Hex Value", anchor="center")
        self.offsets_tree.heading("description", text="Description / Function", anchor="w")

        self.offsets_tree.column("name", width=180, anchor="w")
        self.offsets_tree.column("offset", width=150, anchor="center")
        self.offsets_tree.column("description", width=250, anchor="w")
        self.offsets_tree.pack(fill=tk.BOTH, expand=True)

        self._populate_offsets_tree()

        # -------------------------------------------------------------
        # RIGHT PANEL: Edit & Save Panel
        # -------------------------------------------------------------
        edit_card = ModernCard(right_panel, bg=COLORS["bg_card"], border_color=COLORS["border"], radius=15)
        edit_card.pack(fill=tk.BOTH, expand=True)
        ec_c = edit_card.container

        tk.Label(
            ec_c, text="◈ EDIT OFFSET",
            bg=COLORS["bg_card"], fg=COLORS["gold"],
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 10))

        # Editing Inputs
        tk.Label(ec_c, text="OFFSET NAME", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(5, 1))
        self.offset_name_lbl = tk.Label(ec_c, text="Select a row to edit...", bg=COLORS["bg_card_inner"], fg=COLORS["text_dim"], font=("Segoe UI", 9, "bold"), anchor="w", height=2)
        self.offset_name_lbl.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(ec_c, text="HEX VALUE (e.g. 0x1C)", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(5, 1))
        self.offset_value_entry = tk.Entry(ec_c, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=4, insertbackground=COLORS["red_primary"], font=("Segoe UI", 9, "bold"))
        self.offset_value_entry.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(ec_c, text="DESCRIPTION", bg=COLORS["bg_card"], fg=COLORS["text_secondary"], font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=10, pady=(5, 1))
        self.offset_desc_entry = tk.Entry(ec_c, bg=COLORS["bg_card_inner"], fg=COLORS["text_primary"], relief="flat", bd=4, insertbackground=COLORS["red_primary"], font=("Segoe UI", 9))
        self.offset_desc_entry.pack(fill=tk.X, padx=10, pady=(0, 20))

        # Select row binding to populate inputs
        def on_offset_select(event):
            sel = self.offsets_tree.selection()
            if not sel:
                return
            values = self.offsets_tree.item(sel[0])["values"]
            self.offset_name_lbl.config(text=str(values[0]), fg=COLORS["text_primary"])
            self.offset_value_entry.delete(0, tk.END)
            self.offset_value_entry.insert(0, str(values[1]))
            self.offset_desc_entry.delete(0, tk.END)
            self.offset_desc_entry.insert(0, str(values[2]))

        self.offsets_tree.bind("<<TreeviewSelect>>", on_offset_select)

        # Action functions
        def save_offset_value():
            name = self.offset_name_lbl.cget("text")
            if name == "Select a row to edit...":
                self._add_notification("Please select an offset row first!", "Error")
                return
                
            val = self.offset_value_entry.get().strip()
            desc = self.offset_desc_entry.get().strip()
            
            # Simple hex validator
            if not val.lower().startswith("0x"):
                self._add_notification("Hex must start with 0x!", "Error")
                return
                
            # Update Treeview
            sel = self.offsets_tree.selection()
            if sel:
                self.offsets_tree.item(sel[0], values=(name, val, desc))
                
            # Save all offsets from Treeview to config/offsets.json
            self._save_offsets_file()
            self._append_log(f"Offset '{name}' updated to {val}", "success")
            self._add_notification(f"Saved offset {name}", "Success")

        def reset_offsets_to_default():
            self._write_default_offsets_json()
            self._populate_offsets_tree()
            self._add_notification("Reset offsets to default", "Warning")

        self._build_btn_compact(ec_c, "💾 SAVE OFFSET", save_offset_value)
        self._build_btn_compact(ec_c, "🔄 RESET OFFSETS", reset_offsets_to_default)

    def _populate_offsets_tree(self):
        # Clear tree
        for child in self.offsets_tree.get_children():
            self.offsets_tree.delete(child)

        # Load from config/offsets.json
        filepath = os.path.join("config", "offsets.json")
        if not os.path.exists(filepath):
            self._write_default_offsets_json()

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for name, offset_data in data.items():
                val = offset_data.get("val", "0x0")
                desc = offset_data.get("desc", "")
                self.offsets_tree.insert("", "end", values=(name, val, desc))
        except Exception as e:
            self._append_log(f"Failed to populate offsets table: {e}", "error")

    def _write_default_offsets_json(self):
        default_offsets = {
            "Base Address": {"val": "0x00D70000", "desc": "Process game base pointer address"},
            "Player HP Offset": {"val": "0x1C", "desc": "Current Player Health Point offset"},
            "Player Max HP Offset": {"val": "0x20", "desc": "Max Player Health Point offset"},
            "Player Mana Offset": {"val": "0x24", "desc": "Current Player Resource (Mana/Rage/Steam) offset"},
            "Target Base Address": {"val": "0x00D78000", "desc": "Base address pointer for active combat targets"},
            "Entity Count Offset": {"val": "0x38", "desc": "Counts the number of active entities in drawing range"},
            "Minimap Coordinates": {"val": "0x40", "desc": "Character X/Y coordinates on the minimap overlay"},
            "Gold Counter Offset": {"val": "0x5A", "desc": "Player total gold count representation offset"}
        }
        try:
            os.makedirs("config", exist_ok=True)
            filepath = os.path.join("config", "offsets.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(default_offsets, f, indent=4)
        except Exception:
            pass

    def _save_offsets_file(self):
        offsets_data = {}
        for child in self.offsets_tree.get_children():
            values = self.offsets_tree.item(child)["values"]
            offsets_data[str(values[0])] = {
                "val": str(values[1]),
                "desc": str(values[2])
            }
            
        try:
            filepath = os.path.join("config", "offsets.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(offsets_data, f, indent=4)
        except Exception as e:
            self._append_log(f"Failed to save offsets to file: {e}", "error")

    def _populate_combo_tree(self):
        seq = ["2", "3", "1", "1", "1"]
        cds = [0.0, 5.0, 8.0, 2.0, 2.0]

        if hasattr(self.bot, "combat") and self.bot.combat:
            seq = self.bot.combat.combo_sequence
            cds = self.bot.combat.combo_cooldowns

        for child in self.combo_tree.get_children():
            self.combo_tree.delete(child)

        for idx, (key, cd) in enumerate(zip(seq, cds)):
            self.combo_tree.insert("", "end", values=(f"#{idx+1}", key, f"{cd}s"))

    def _renumber_combo_steps(self):
        for idx, child in enumerate(self.combo_tree.get_children()):
            val = list(self.combo_tree.item(child)["values"])
            val[0] = f"#{idx+1}"
            self.combo_tree.item(child, values=val)

    def _update_combo_monitoring_loop(self):
        if not self._running:
            return
        
        try:
            if hasattr(self.bot, "combat") and self.bot.combat:
                status = self.bot.combat.get_status()
                cls_name = status.get("active_class", "custom").upper()
                step_idx = status.get("combo_step", 0) + 1
                next_skill = status.get("combo_skill", "--")

                if hasattr(self, "combo_status_class") and self.combo_status_class:
                    self.combo_status_class.config(text=f"Class Profile: {cls_name}")
                if hasattr(self, "combo_status_step") and self.combo_status_step:
                    self.combo_status_step.config(text=f"Current Step: Step #{step_idx}")
                if hasattr(self, "combo_status_skill") and self.combo_status_skill:
                    self.combo_status_skill.config(text=f"Next Ready Skill: [{next_skill}]")
        except Exception:
            pass

        self.root.after(500, self._update_combo_monitoring_loop)

    # ═══════════════════════════════════════════════════════
    # Header Animation
    # ═══════════════════════════════════════════════════════
    def _animate_accent(self):
        if not self._running:
            return

        self._glow_phase += 0.05
        if self._glow_phase > 2 * math.pi:
            self._glow_phase -= 2 * math.pi

        self.accent_canvas.delete("all")
        w = 1150
        segments = 70
        seg_w = w / segments
        for i in range(segments):
            phase = self._glow_phase + (i / segments) * math.pi * 2
            intensity = (math.sin(phase) + 1) / 2
            r = int(50 + intensity * 150)
            g = int(10 + intensity * 10)
            b = int(10 + intensity * 10)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.accent_canvas.create_rectangle(
                i * seg_w, 0, (i + 1) * seg_w, 2,
                fill=color, outline=color
            )

        # Update waypoint page animations if active
        if self._active_page == "waypoints":
            self._update_waypoint_canvas_animation()

        self.root.after(30, self._animate_accent)

    # ═══════════════════════════════════════════════════════
    # Core Bot Handler Callbacks
    # ═══════════════════════════════════════════════════════
    def _toggle_bot(self):
        """Toggle bot on/off in a background thread to prevent GUI freeze."""
        import threading

        # Prevent double-clicks while toggling
        if hasattr(self, '_bot_toggling') and self._bot_toggling:
            return
        self._bot_toggling = True

        # Immediately show a "working" state on the button
        self.start_btn_lbl.config(text="⏳ WORKING...", cursor="watch")
        self._append_log("⏳ Sending bot toggle command...", "warning")

        def _do_toggle():
            try:
                self.bot.toggle_bot()
                is_active = self.bot._bot_active

                # Schedule GUI updates back on the main thread
                self.root.after(0, lambda: self._on_toggle_complete(is_active))
            except Exception as e:
                self.root.after(0, lambda: self._on_toggle_error(str(e)))

        t = threading.Thread(target=_do_toggle, daemon=True, name="BotToggleThread")
        t.start()

    def _on_toggle_complete(self, is_active):
        """Called on main thread after bot toggle finishes."""
        self._bot_toggling = False
        self._update_start_button_state(is_active)

        if is_active:
            self._append_log("🟢 Drakensang AI is now ONLINE & RUNNING!", "success")
            self._add_notification("Start bot command executed", "Success")
        else:
            self._append_log("🔴 Drakensang AI is now OFFLINE!", "error")
            self._add_notification("Stop bot command executed", "Warning")

    def _on_toggle_error(self, error_msg):
        """Called on main thread if bot toggle fails."""
        self._bot_toggling = False
        self._update_start_button_state(False)
        self._append_log(f"Error toggling bot: {error_msg}", "error")

    def _update_start_button_state(self, is_active):
        if is_active:
            self.start_btn_card.config(bg=COLORS["error"], border_color=COLORS["error"])
            self.start_btn_lbl.config(text="■ STOP BOT", bg=COLORS["error"])
        else:
            self.start_btn_card.config(bg=COLORS["success"], border_color=COLORS["success"])
            self.start_btn_lbl.config(text="▶ START BOT", bg=COLORS["success"])

    def _on_class_changed(self, selected_display_name):
        """Handle class profile dropdown change."""
        try:
            # Find the profile key from display name
            idx = self._class_display_names.index(selected_display_name)
            class_key = self._class_profile_keys[idx]

            if hasattr(self.bot, 'combat') and self.bot.combat:
                self.bot.combat.switch_class(class_key)
                self._append_log(f"Combat profile switched to: {selected_display_name}", "warning")
                self._add_notification(f"Class: {selected_display_name}", "Success")
            else:
                self._append_log("Combat system not initialized yet", "warning")
        except Exception as e:
            self._append_log(f"Failed to switch class: {e}", "error")

    def _toggle_overlay(self):
        try:
            self.bot.overlay.toggle()
            self._append_log("Command sent: Toggle HUD Overlay", "info")
            self._add_notification("Overlay toggled", "Info")
        except Exception as e:
            self._append_log(f"Failed to toggle overlay: {e}", "error")

    def _record_waypoint(self):
        try:
            self.bot.navigation.record_mouse_position()
            self._append_log("Navigation system: Waypoint recorded successfully", "info")
            self._add_notification("Waypoint saved", "Success")
        except Exception as e:
            self._append_log(f"Failed to record waypoint: {e}", "error")

    def _capture_screenshot(self):
        try:
            threading.Thread(target=self.bot.capture_training_image, daemon=True).start()
            self._append_log("Dataset manager: Capturing screen matrix frame...", "info")
            self._add_notification("Screenshot saved", "Success")
        except Exception as e:
            self._append_log(f"Failed to capture frame: {e}", "error")

    def _toggle_auto_capture(self):
        try:
            self.bot.toggle_auto_capture()
            status = "ON" if self.bot._auto_capture else "OFF"
            self._append_log(f"Dataset manager: Auto Capture set to {status}", "info")
            self._add_notification(f"Auto capturing: {status}", "Info")
        except Exception as e:
            self._append_log(f"Failed to toggle auto capture: {e}", "error")

    # ═══════════════════════════════════════════════════════
    # Update Stats Loop
    # ═══════════════════════════════════════════════════════
    def _update_stats_loop(self):
        if not self._running:
            return

        try:
            # Safe metrics retrieval from DrakensangBot instance
            if hasattr(self.bot, 'game_state') and self.bot.game_state:
                summary = self.bot.game_state.get_state_summary()
                
                # Fetch statistics
                kills = summary.get('enemies_killed', 0)
                loot = summary.get('loot_picked', 0)
                potions = summary.get('potions_used', 0)
                deaths = summary.get('deaths', 0)
                session_time = summary.get('session_time_str', '00:00:00')
                hp = summary.get('hp', 100)
                bot_state = summary.get('bot_state', 'IDLE')
                
                # Calculate active ratios for donut chart
                # If bot is running, simulate partition variations
                if self.bot._bot_active:
                    self.state_data["Combat"] = random.randint(35, 45)
                    self.state_data["Navigate"] = random.randint(25, 35)
                    self.state_data["Loot"] = random.randint(10, 20)
                    self.state_data["Heal"] = random.randint(5, 12)
                    self.state_data["Idle"] = 100 - (self.state_data["Combat"] + self.state_data["Navigate"] + self.state_data["Loot"] + self.state_data["Heal"])
                    self._draw_donut_chart()
                    self._build_donut_legend()

                # Update XP/HP ratio bar mockup
                self._draw_profile_pb(hp / 100.0)
                self.session_percentage_lbl.config(text=f"{hp:.0f}%")
                
                # Update text components
                self.kills_stat.config(text=str(kills))
                self.loot_stat.config(text=str(loot))
                self.potions_stat.config(text=str(potions))
                self.deaths_stat.config(text=str(deaths))
                self.state_stat.config(text=bot_state)

                # Update combat intelligence stats
                if hasattr(self.bot, 'combat') and self.bot.combat:
                    combat_status = self.bot.combat.get_status()
                    class_name = combat_status.get('active_class', 'custom').capitalize()
                    danger = combat_status.get('danger_score', 0)
                    
                    self.class_stat.config(text=class_name)
                    
                    danger_color = COLORS["success"] if danger < 30 else COLORS["warning"] if danger < 60 else COLORS["error"]
                    self.danger_stat.config(text=f"{danger}", fg=danger_color)
                    
                    # Update CLASS block in dashboard
                    if "CLASS" in self.blocks:
                        self.blocks["CLASS"].config(text=class_name[:6])

                # Update live indicator block labels
                self.blocks["ENEMIES KILLED"].config(text=str(kills))
                self.blocks["LOOT PICKED"].config(text=str(loot))
                self.blocks["SESSION TIME"].config(text=session_time)
                
                hp_color = COLORS["success"] if hp > 65 else COLORS["warning"] if hp > 30 else COLORS["error"]
                self.blocks["PLAYER HP"].config(text=f"{hp:.0f}%", fg=hp_color)

                bot_active = self.bot._bot_active
                status_text = "ONLINE" if bot_active else "OFFLINE"
                status_color = COLORS["success"] if bot_active else COLORS["error"]
                
                self.blocks["BOT STATUS"].config(text=status_text, fg=status_color)
                self.status_sub_lbl.config(text=f"● Bot State: {status_text}", fg=status_color)
                self._update_start_button_state(bot_active)

            # Query live detector objects
            if hasattr(self.bot, 'detector') and self.bot.detector:
                det_fps = getattr(self.bot.detector, 'fps', 0.0)
                self.fps_stat.config(text=f"{det_fps:.1f}")

                # Update detected targets from detector
                raw_detections = getattr(self.bot.detector, 'detections', [])
                formatted_targets = []
                for det in raw_detections[:4]: # Max 4 items
                    label = det.get('label', 'Entity')
                    conf = int(det.get('confidence', 0.9) * 100)
                    # Assign a status color
                    color = COLORS["error"] if "enemy" in label.lower() or "mob" in label.lower() else COLORS["success"] if "loot" in label.lower() else COLORS["info"]
                    formatted_targets.append((label.capitalize(), conf, color))
                
                self._update_detected_targets(formatted_targets)

        except Exception as e:
            pass

        self.root.after(500, self._update_stats_loop)

    # ═══════════════════════════════════════════════════════
    # Lifecycle Cleanup
    # ═══════════════════════════════════════════════════════
    def _on_close(self):
        self._running = False
        try:
            self.bot.emergency_stop()
        except Exception:
            pass

        # Cleanup root logger handler
        try:
            logging.getLogger().removeHandler(self.log_handler)
        except Exception:
            pass

        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Fallback dry-run mock tester class
    class MockBot:
        def __init__(self):
            self._bot_active = False
            self._auto_capture = False
            self.game_state = MockGameState()
            self.detector = MockDetector()
            self.overlay = MockOverlay()
            self.navigation = MockNavigation()
            self.combat = MockCombat()

        def toggle_bot(self):
            self._bot_active = not self._bot_active

        def toggle_auto_capture(self):
            self._auto_capture = not self._auto_capture

        def emergency_stop(self):
            pass

        def capture_training_image(self):
            time.sleep(0.5)

    class MockGameState:
        def __init__(self):
            self.stats = {
                'enemies_killed': 142,
                'loot_picked': 235,
                'potions_used': 12,
                'deaths': 1,
                'session_time_str': '01:45:22'
            }

        def get_state_summary(self):
            return {
                'enemies_killed': self.stats['enemies_killed'],
                'loot_picked': self.stats['loot_picked'],
                'potions_used': self.stats['potions_used'],
                'deaths': self.stats['deaths'],
                'session_time_str': self.stats['session_time_str'],
                'hp': 82.0,
                'bot_state': 'COMBAT'
            }

    class MockDetector:
        def __init__(self):
            self.fps = 24.5
            self.detections = [
                {'label': 'mob', 'confidence': 0.85},
                {'label': 'loot_gold', 'confidence': 0.95},
                {'label': 'player', 'confidence': 0.99}
            ]

    class MockOverlay:
        def toggle(self):
            pass

    class MockCombat:
        def __init__(self):
            self.active_class = "custom"

        def get_status(self):
            return {
                "active_class": self.active_class,
                "attack_count": 42,
                "combo_step": 2,
                "combo_skill": "3",
                "retreating": False,
                "kiting": True,
                "danger_score": 15.0,
                "has_target": True,
                "target_class": "enemy"
            }

        def switch_class(self, class_name):
            self.active_class = class_name

    class MockNavigation:
        def record_mouse_position(self):
            pass

    gui = MainGUI(
        bot_instance=MockBot(),
        username="TesterPro2026",
        license_key="MOCK_LICENSE_KEY",
        authenticated=True
    )
    gui.run()
