"""
Main GUI Window
================
Premium dark-themed main control panel with red/black/gray color scheme.
Provides full bot control, status monitoring, and configuration.
900x600 resolution, frameless window with custom title bar.
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import math
import logging


# ═══════════════════════════════════════════════════════════
# Color Palette (shared with login)
# ═══════════════════════════════════════════════════════════
COLORS = {
    "bg_dark":        "#0a0a0a",
    "bg_medium":      "#141414",
    "bg_card":        "#1a1a1a",
    "bg_input":       "#1e1e1e",
    "bg_input_focus": "#252525",
    "border":         "#2a2a2a",
    "border_focus":   "#c0392b",
    "text_primary":   "#e8e8e8",
    "text_secondary": "#888888",
    "text_dim":       "#555555",
    "red_primary":    "#c0392b",
    "red_hover":      "#e74c3c",
    "red_dark":       "#8b1a1a",
    "red_glow":       "#ff2d2d",
    "gray_light":     "#3a3a3a",
    "gray_mid":       "#2d2d2d",
    "accent":         "#d44040",
    "success":        "#27ae60",
    "success_dark":   "#1e8449",
    "warning":        "#f39c12",
    "error":          "#e74c3c",
    "info":           "#3498db",
}


class TextWidgetHandler(logging.Handler):
    """Logging handler that writes to a tkinter Text widget."""

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

        # Color based on level
        tag = "info"
        if level >= logging.ERROR:
            tag = "error"
        elif level >= logging.WARNING:
            tag = "warning"
        elif level <= logging.DEBUG:
            tag = "debug"

        self.text_widget.insert(tk.END, msg + "\n", tag)
        self.text_widget.see(tk.END)

        # Limit lines
        lines = int(self.text_widget.index('end-1c').split('.')[0])
        if lines > 500:
            self.text_widget.delete("1.0", "100.0")

        self.text_widget.config(state=tk.DISABLED)


class MainGUI:
    """
    Main bot control panel GUI.
    
    Features:
    - Real-time status dashboard
    - Bot start/stop controls
    - Live log viewer with colored output
    - System stats display
    - Configuration quick-access
    - Hotkey reference panel
    """

    def __init__(self, bot_instance, username="User", license_key="", authenticated=False):
        """
        Initialize the main GUI.
        
        Args:
            bot_instance: Reference to the DrakensangBot instance
            username: Logged-in username
            license_key: Active license key
            authenticated: True if successfully logged in
        """
        if not authenticated:
            raise PermissionError("Access Denied: MainGUI must be started through the login page.")

        self.bot = bot_instance
        self.username = username
        self.license_key = license_key
        self._running = True
        self._drag_x = 0
        self._drag_y = 0
        self._glow_phase = 0.0

        # Build UI
        self.root = tk.Tk()
        self.root.title("DRAKENSANG AI — Control Panel")
        self.root.geometry("900x600")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.overrideredirect(True)

        self._center_window()
        self._build_title_bar()
        self._build_main_content()

        # Start update loops
        self._update_stats()
        self._animate_accent()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 900) // 2
        y = (sh - 600) // 2
        self.root.geometry(f"900x600+{x}+{y}")

    # ═══════════════════════════════════════════════════════
    # Title Bar
    # ═══════════════════════════════════════════════════════

    def _build_title_bar(self):
        self.title_bar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=36)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)

        title_label = tk.Label(
            self.title_bar,
            text="  ◆ DRAKENSANG AI — CONTROL PANEL",
            bg=COLORS["bg_dark"],
            fg=COLORS["red_primary"],
            font=("Consolas", 10, "bold"),
            anchor="w"
        )
        title_label.pack(side=tk.LEFT, padx=5)

        # User badge
        user_badge = tk.Label(
            self.title_bar,
            text=f"  ● {self.username}  ",
            bg=COLORS["bg_dark"],
            fg=COLORS["success"],
            font=("Consolas", 9),
        )
        user_badge.pack(side=tk.LEFT, padx=20)

        # Close button
        close_btn = tk.Label(
            self.title_bar, text="  ✕  ",
            bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=("Consolas", 12), cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg=COLORS["red_primary"], fg="white"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        close_btn.bind("<Button-1>", lambda e: self._on_close())

        # Minimize button
        min_btn = tk.Label(
            self.title_bar, text="  ─  ",
            bg=COLORS["bg_dark"], fg=COLORS["text_dim"],
            font=("Consolas", 12), cursor="hand2"
        )
        min_btn.pack(side=tk.RIGHT)
        min_btn.bind("<Enter>", lambda e: min_btn.config(bg=COLORS["gray_mid"], fg="white"))
        min_btn.bind("<Leave>", lambda e: min_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        min_btn.bind("<Button-1>", lambda e: self.root.iconify())

        # Drag
        self.title_bar.bind("<Button-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)
        title_label.bind("<Button-1>", self._start_drag)
        title_label.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ═══════════════════════════════════════════════════════
    # Main Content
    # ═══════════════════════════════════════════════════════

    def _build_main_content(self):
        # Accent line under title bar
        self.accent_canvas = tk.Canvas(
            self.root, width=900, height=3,
            bg=COLORS["bg_dark"], highlightthickness=0
        )
        self.accent_canvas.pack(fill=tk.X)

        # Main container
        main = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ── Top Row: Status Cards ──
        top_row = tk.Frame(main, bg=COLORS["bg_dark"])
        top_row.pack(fill=tk.X, pady=(5, 8))

        self._build_status_card(top_row, "BOT STATUS", "status_val", "OFFLINE", COLORS["error"])
        self._build_status_card(top_row, "ENEMIES KILLED", "kills_val", "0", COLORS["red_primary"])
        self._build_status_card(top_row, "LOOT PICKED", "loot_val", "0", COLORS["warning"])
        self._build_status_card(top_row, "SESSION TIME", "time_val", "00:00:00", COLORS["info"])
        self._build_status_card(top_row, "HP", "hp_val", "100%", COLORS["success"])

        # ── Middle Row: Controls + Log ──
        mid_row = tk.Frame(main, bg=COLORS["bg_dark"])
        mid_row.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Left: Control Panel
        self._build_control_panel(mid_row)

        # Right: Log Viewer
        self._build_log_viewer(mid_row)

        # ── Bottom Row: Hotkey Reference ──
        self._build_hotkey_bar(main)

    def _build_status_card(self, parent, title, attr_name, default_val, color):
        """Build a small status card widget."""
        card = tk.Frame(parent, bg=COLORS["bg_card"], padx=12, pady=8,
                        highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        tk.Label(
            card, text=title,
            bg=COLORS["bg_card"], fg=COLORS["text_dim"],
            font=("Consolas", 7, "bold")
        ).pack(anchor="w")

        val_label = tk.Label(
            card, text=default_val,
            bg=COLORS["bg_card"], fg=color,
            font=("Consolas", 14, "bold")
        )
        val_label.pack(anchor="w", pady=(2, 0))

        setattr(self, attr_name, val_label)

    def _build_control_panel(self, parent):
        """Build the left control panel with buttons."""
        ctrl_frame = tk.Frame(parent, bg=COLORS["bg_card"], width=260,
                              highlightbackground=COLORS["border"], highlightthickness=1)
        ctrl_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        ctrl_frame.pack_propagate(False)

        # Header
        tk.Label(
            ctrl_frame, text="  ◈ CONTROLS",
            bg=COLORS["bg_card"], fg=COLORS["red_primary"],
            font=("Consolas", 11, "bold"), anchor="w"
        ).pack(fill=tk.X, pady=(12, 15), padx=10)

        # Start/Stop Button
        self.start_btn_canvas = tk.Canvas(
            ctrl_frame, width=230, height=42,
            bg=COLORS["bg_card"], highlightthickness=0, cursor="hand2"
        )
        self.start_btn_canvas.pack(pady=(0, 8))
        self._draw_start_button(False)
        self.start_btn_canvas.bind("<Button-1>", lambda e: self._toggle_bot())

        # Overlay Toggle
        self._build_ctrl_button(ctrl_frame, "◈  TOGGLE OVERLAY", self._toggle_overlay)

        # Record Waypoint
        self._build_ctrl_button(ctrl_frame, "◈  RECORD WAYPOINT", self._record_waypoint)

        # Capture Screenshot
        self._build_ctrl_button(ctrl_frame, "◈  CAPTURE SCREENSHOT", self._capture_screenshot)

        # Auto Dataset Toggle
        self._build_ctrl_button(ctrl_frame, "◈  AUTO DATASET", self._toggle_auto_capture)

        # Separator
        tk.Frame(ctrl_frame, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=15, pady=12)

        # Stats section
        tk.Label(
            ctrl_frame, text="  ◈ STATISTICS",
            bg=COLORS["bg_card"], fg=COLORS["red_primary"],
            font=("Consolas", 10, "bold"), anchor="w"
        ).pack(fill=tk.X, padx=10, pady=(0, 8))

        stats_items = [
            ("Potions Used:", "potions_stat", "0"),
            ("Deaths:", "deaths_stat", "0"),
            ("State:", "state_stat", "IDLE"),
            ("Detection FPS:", "det_fps_stat", "0"),
        ]
        for label_text, attr_name, default in stats_items:
            row = tk.Frame(ctrl_frame, bg=COLORS["bg_card"])
            row.pack(fill=tk.X, padx=15, pady=2)
            tk.Label(
                row, text=label_text,
                bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                font=("Consolas", 9), anchor="w"
            ).pack(side=tk.LEFT)
            val = tk.Label(
                row, text=default,
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=("Consolas", 9, "bold"), anchor="e"
            )
            val.pack(side=tk.RIGHT)
            setattr(self, attr_name, val)

    def _build_ctrl_button(self, parent, text, command):
        """Build a styled control button."""
        btn_frame = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
        btn_frame.pack(padx=15, pady=3, fill=tk.X)

        btn = tk.Label(
            btn_frame, text=text,
            bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
            font=("Consolas", 9), pady=6, padx=10,
            cursor="hand2", anchor="w"
        )
        btn.pack(fill=tk.X)

        btn.bind("<Enter>", lambda e: (
            btn.config(bg=COLORS["gray_mid"], fg=COLORS["text_primary"]),
            btn_frame.config(bg=COLORS["red_primary"])
        ))
        btn.bind("<Leave>", lambda e: (
            btn.config(bg=COLORS["bg_input"], fg=COLORS["text_secondary"]),
            btn_frame.config(bg=COLORS["border"])
        ))
        btn.bind("<Button-1>", lambda e: command())

    def _draw_start_button(self, is_active):
        """Draw the start/stop toggle button."""
        self.start_btn_canvas.delete("all")
        if is_active:
            color = COLORS["error"]
            text = "■  STOP BOT"
        else:
            color = COLORS["success"]
            text = "▶  START BOT"

        self.start_btn_canvas.create_rectangle(
            2, 2, 228, 40, fill=color, outline=color
        )
        self.start_btn_canvas.create_text(
            115, 21, text=text,
            fill="white", font=("Consolas", 11, "bold")
        )

    def _build_log_viewer(self, parent):
        """Build the log viewer panel."""
        log_frame = tk.Frame(parent, bg=COLORS["bg_card"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(log_frame, bg=COLORS["bg_card"])
        header.pack(fill=tk.X, padx=10, pady=(10, 5))

        tk.Label(
            header, text="◈ LIVE LOG",
            bg=COLORS["bg_card"], fg=COLORS["red_primary"],
            font=("Consolas", 11, "bold"), anchor="w"
        ).pack(side=tk.LEFT)

        # Clear button
        clear_btn = tk.Label(
            header, text="  CLEAR  ",
            bg=COLORS["bg_input"], fg=COLORS["text_dim"],
            font=("Consolas", 8), cursor="hand2"
        )
        clear_btn.pack(side=tk.RIGHT)
        clear_btn.bind("<Button-1>", lambda e: self._clear_log())
        clear_btn.bind("<Enter>", lambda e: clear_btn.config(fg=COLORS["text_primary"]))
        clear_btn.bind("<Leave>", lambda e: clear_btn.config(fg=COLORS["text_dim"]))

        # Log text widget
        self.log_text = tk.Text(
            log_frame,
            bg="#0d0d0d",
            fg=COLORS["text_secondary"],
            font=("Consolas", 9),
            relief="flat",
            bd=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
            insertbackground=COLORS["red_primary"],
            selectbackground=COLORS["red_dark"],
            selectforeground="white",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Configure log tags for colored output
        self.log_text.tag_configure("info", foreground=COLORS["text_secondary"])
        self.log_text.tag_configure("warning", foreground=COLORS["warning"])
        self.log_text.tag_configure("error", foreground=COLORS["error"])
        self.log_text.tag_configure("debug", foreground=COLORS["text_dim"])

        # Attach logging handler
        self.log_handler = TextWidgetHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s | %(name)-12s | %(message)s",
            datefmt="%H:%M:%S"
        ))

        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)

        # Initial log message
        self._append_log("═══ DRAKENSANG AI CONTROL PANEL INITIALIZED ═══", "info")
        self._append_log(f"Welcome, {self.username}! Bot is ready.", "info")
        self._append_log("Press START or F9 to begin.", "info")

    def _append_log(self, message, tag="info"):
        """Manually append a message to the log."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        self._append_log("Log cleared.", "info")

    def _build_hotkey_bar(self, parent):
        """Build the bottom hotkey reference bar."""
        bar = tk.Frame(parent, bg=COLORS["bg_card"], height=32,
                       highlightbackground=COLORS["border"], highlightthickness=1)
        bar.pack(fill=tk.X, pady=(0, 5))
        bar.pack_propagate(False)

        hotkeys = [
            ("F9", "Start/Stop"),
            ("F10", "Waypoint"),
            ("F11", "Screenshot"),
            ("F7", "Auto-Cap"),
            ("F12", "Overlay"),
            ("F8", "EXIT"),
        ]

        for key, desc in hotkeys:
            item = tk.Frame(bar, bg=COLORS["bg_card"])
            item.pack(side=tk.LEFT, padx=8, pady=4)

            key_label = tk.Label(
                item, text=f" {key} ",
                bg=COLORS["red_dark"], fg="white",
                font=("Consolas", 8, "bold"),
            )
            key_label.pack(side=tk.LEFT, padx=(0, 4))

            tk.Label(
                item, text=desc,
                bg=COLORS["bg_card"], fg=COLORS["text_dim"],
                font=("Consolas", 8),
            ).pack(side=tk.LEFT)

    # ═══════════════════════════════════════════════════════
    # Accent Animation
    # ═══════════════════════════════════════════════════════

    def _animate_accent(self):
        if not self._running:
            return

        self._glow_phase += 0.04
        if self._glow_phase > 2 * math.pi:
            self._glow_phase -= 2 * math.pi

        self.accent_canvas.delete("all")
        w = 900
        segments = 60
        seg_w = w / segments
        for i in range(segments):
            phase = self._glow_phase + (i / segments) * math.pi * 2
            intensity = (math.sin(phase) + 1) / 2
            r = int(40 + intensity * 152)
            g = int(5 + intensity * 15)
            b = int(5 + intensity * 15)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.accent_canvas.create_rectangle(
                i * seg_w, 0, (i + 1) * seg_w, 3,
                fill=color, outline=color
            )

        self.root.after(30, self._animate_accent)

    # ═══════════════════════════════════════════════════════
    # Bot Control Actions
    # ═══════════════════════════════════════════════════════

    def _toggle_bot(self):
        try:
            self.bot.toggle_bot()
            is_active = self.bot._bot_active
            self._draw_start_button(is_active)
            if is_active:
                self._append_log("═══ BOT STARTED ═══", "warning")
                self.status_val.config(text="ONLINE", fg=COLORS["success"])
            else:
                self._append_log("═══ BOT STOPPED ═══", "warning")
                self.status_val.config(text="OFFLINE", fg=COLORS["error"])
        except Exception as e:
            self._append_log(f"Error toggling bot: {e}", "error")

    def _toggle_overlay(self):
        try:
            self.bot.overlay.toggle()
            self._append_log("Overlay toggled", "info")
        except Exception as e:
            self._append_log(f"Error toggling overlay: {e}", "error")

    def _record_waypoint(self):
        try:
            self.bot.navigation.record_mouse_position()
            self._append_log("Waypoint recorded at mouse position", "info")
        except Exception as e:
            self._append_log(f"Error recording waypoint: {e}", "error")

    def _capture_screenshot(self):
        try:
            threading.Thread(target=self.bot.capture_training_image, daemon=True).start()
            self._append_log("Screenshot captured for training", "info")
        except Exception as e:
            self._append_log(f"Error capturing screenshot: {e}", "error")

    def _toggle_auto_capture(self):
        try:
            self.bot.toggle_auto_capture()
            status = "ON" if self.bot._auto_capture else "OFF"
            self._append_log(f"Auto dataset capture: {status}", "info")
        except Exception as e:
            self._append_log(f"Error toggling auto capture: {e}", "error")

    # ═══════════════════════════════════════════════════════
    # Stats Update Loop
    # ═══════════════════════════════════════════════════════

    def _update_stats(self):
        if not self._running:
            return

        try:
            if hasattr(self.bot, 'game_state') and self.bot.game_state:
                summary = self.bot.game_state.get_state_summary()

                # Update cards
                kills = summary.get('enemies_killed', 0)
                self.kills_val.config(text=str(kills))

                loot = summary.get('loot_picked', 0)
                self.loot_val.config(text=str(loot))

                session_time = summary.get('session_time_str', '00:00:00')
                self.time_val.config(text=session_time)

                hp = summary.get('hp', 100)
                hp_color = COLORS["success"] if hp > 60 else COLORS["warning"] if hp > 30 else COLORS["error"]
                self.hp_val.config(text=f"{hp:.0f}%", fg=hp_color)

                # Update stats
                self.potions_stat.config(text=str(summary.get('potions_used', 0)))
                self.deaths_stat.config(text=str(summary.get('deaths', 0)))

                bot_state = summary.get('bot_state', 'IDLE')
                state_colors = {
                    "IDLE": COLORS["text_dim"],
                    "COMBAT": COLORS["error"],
                    "MOVING": COLORS["info"],
                    "LOOTING": COLORS["warning"],
                    "HEALING": COLORS["success"],
                    "DEAD": COLORS["error"],
                    "PAUSED": COLORS["text_dim"],
                }
                self.state_stat.config(
                    text=bot_state,
                    fg=state_colors.get(bot_state, COLORS["text_secondary"])
                )

                # Bot status card
                if self.bot._bot_active:
                    self.status_val.config(text="ONLINE", fg=COLORS["success"])
                else:
                    self.status_val.config(text="OFFLINE", fg=COLORS["error"])

            # Detection FPS
            if hasattr(self.bot, 'detector') and self.bot.detector:
                det_fps = getattr(self.bot.detector, 'fps', 0)
                self.det_fps_stat.config(text=f"{det_fps:.1f}")

        except Exception:
            pass

        self.root.after(500, self._update_stats)

    # ═══════════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════════

    def _on_close(self):
        self._running = False
        try:
            self.bot.emergency_stop()
        except Exception:
            pass

        # Remove log handler
        try:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)
        except Exception:
            pass

        self.root.destroy()

    def run(self):
        """Start the main GUI main loop."""
        self.root.mainloop()
