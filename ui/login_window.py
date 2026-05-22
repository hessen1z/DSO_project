"""
Login Window
============
Premium dark-themed login page with red/black/gray color scheme.
Features animated gradient effects, custom styled inputs, and license validation.
900x600 resolution, frameless window with custom title bar.
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import math


# ═══════════════════════════════════════════════════════════
# Color Palette
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
    "error":          "#e74c3c",
}


class LoginWindow:
    """
    Premium login window with animated effects.
    
    Features:
    - Custom frameless window with drag support
    - Animated red accent line
    - Styled input fields with focus effects
    - Username, Password, and License Key fields
    - Loading animation on login
    """

    def __init__(self, on_login_success=None):
        """
        Initialize the login window.
        
        Args:
            on_login_success: Callback function called when login succeeds.
                              Receives (username, license_key) as arguments.
        """
        self.on_login_success = on_login_success
        self._authenticated = False
        self._username = ""
        self._license_key = ""
        self._animation_running = True
        self._glow_phase = 0.0
        self._drag_x = 0
        self._drag_y = 0

        # Build UI
        self.root = tk.Tk()
        self.root.title("DRAKENSANG AI — Login")
        self.root.geometry("900x600")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.overrideredirect(True)  # Frameless

        # Center on screen
        self._center_window()

        # Build all UI components
        self._build_title_bar()
        self._build_left_panel()
        self._build_right_panel()

        # Start glow animation
        self._animate_glow()

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 900) // 2
        y = (sh - 600) // 2
        self.root.geometry(f"900x600+{x}+{y}")

    # ═══════════════════════════════════════════════════════
    # Custom Title Bar
    # ═══════════════════════════════════════════════════════

    def _build_title_bar(self):
        """Build custom frameless title bar."""
        self.title_bar = tk.Frame(self.root, bg=COLORS["bg_dark"], height=36)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)

        # Title text
        title_label = tk.Label(
            self.title_bar,
            text="  ◆ DRAKENSANG AI",
            bg=COLORS["bg_dark"],
            fg=COLORS["red_primary"],
            font=("Consolas", 10, "bold"),
            anchor="w"
        )
        title_label.pack(side=tk.LEFT, padx=5)

        # Close button
        close_btn = tk.Label(
            self.title_bar,
            text="  ✕  ",
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
            font=("Consolas", 12),
            cursor="hand2"
        )
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg=COLORS["red_primary"], fg="white"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        close_btn.bind("<Button-1>", lambda e: self._on_close())

        # Minimize button
        min_btn = tk.Label(
            self.title_bar,
            text="  ─  ",
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
            font=("Consolas", 12),
            cursor="hand2"
        )
        min_btn.pack(side=tk.RIGHT)
        min_btn.bind("<Enter>", lambda e: min_btn.config(bg=COLORS["gray_mid"], fg="white"))
        min_btn.bind("<Leave>", lambda e: min_btn.config(bg=COLORS["bg_dark"], fg=COLORS["text_dim"]))
        min_btn.bind("<Button-1>", lambda e: self.root.iconify())

        # Drag support
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
    # Left Panel — Branding
    # ═══════════════════════════════════════════════════════

    def _build_left_panel(self):
        """Build the left branding panel with ASCII art and info."""
        left_frame = tk.Frame(self.root, bg=COLORS["bg_dark"], width=380)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)

        # Top spacer
        tk.Frame(left_frame, bg=COLORS["bg_dark"], height=60).pack()

        # Animated glow line
        self.glow_canvas = tk.Canvas(
            left_frame, width=320, height=4,
            bg=COLORS["bg_dark"], highlightthickness=0
        )
        self.glow_canvas.pack(pady=(0, 20))

        # ASCII Logo
        logo_text = """
  ██████╗ ██████╗  █████╗ ██╗  ██╗
  ██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝
  ██║  ██║██████╔╝███████║█████╔╝ 
  ██║  ██║██╔══██╗██╔══██║██╔═██╗ 
  ██████╔╝██║  ██║██║  ██║██║  ██╗
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝"""

        logo_label = tk.Label(
            left_frame,
            text=logo_text,
            bg=COLORS["bg_dark"],
            fg=COLORS["red_primary"],
            font=("Consolas", 7),
            justify="left"
        )
        logo_label.pack(pady=(10, 5))

        # Subtitle
        sub_label = tk.Label(
            left_frame,
            text="AI   VISION   BOT",
            bg=COLORS["bg_dark"],
            fg=COLORS["text_secondary"],
            font=("Consolas", 12, "bold"),
            anchor="center"
        )
        sub_label.pack(pady=(0, 5))

        # Version
        ver_label = tk.Label(
            left_frame,
            text="v1.0 — ELITE EDITION",
            bg=COLORS["bg_dark"],
            fg=COLORS["red_dark"],
            font=("Consolas", 9),
        )
        ver_label.pack(pady=(0, 20))

        # Second glow line
        self.glow_canvas2 = tk.Canvas(
            left_frame, width=320, height=4,
            bg=COLORS["bg_dark"], highlightthickness=0
        )
        self.glow_canvas2.pack(pady=(0, 30))

        # Feature list
        features = [
            "◈  YOLOv8 Real-Time Detection",
            "◈  Intelligent Combat System",
            "◈  Auto-Navigation & Farming",
            "◈  Smart Loot & Inventory",
            "◈  Death Recovery & Anti-Stuck",
            "◈  Minimap Waypoint Tracking",
        ]
        for feat in features:
            fl = tk.Label(
                left_frame,
                text=feat,
                bg=COLORS["bg_dark"],
                fg=COLORS["text_dim"],
                font=("Consolas", 9),
                anchor="w"
            )
            fl.pack(anchor="w", padx=40, pady=2)

        # Bottom spacer with copyright
        spacer = tk.Frame(left_frame, bg=COLORS["bg_dark"])
        spacer.pack(side=tk.BOTTOM, fill=tk.X, pady=15)
        tk.Label(
            spacer,
            text="© 2026 Drakensang AI Project",
            bg=COLORS["bg_dark"],
            fg=COLORS["text_dim"],
            font=("Consolas", 8),
        ).pack()

    # ═══════════════════════════════════════════════════════
    # Right Panel — Login Form
    # ═══════════════════════════════════════════════════════

    def _build_right_panel(self):
        """Build the right panel with login form."""
        # Separator line
        sep = tk.Frame(self.root, bg=COLORS["gray_mid"], width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y, pady=40)

        right_frame = tk.Frame(self.root, bg=COLORS["bg_medium"])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Content container (centered)
        content = tk.Frame(right_frame, bg=COLORS["bg_medium"])
        content.place(relx=0.5, rely=0.5, anchor="center")

        # Login header
        tk.Label(
            content,
            text="AUTHENTICATION",
            bg=COLORS["bg_medium"],
            fg=COLORS["text_primary"],
            font=("Consolas", 16, "bold"),
        ).pack(pady=(0, 5))

        tk.Label(
            content,
            text="Enter your credentials to continue",
            bg=COLORS["bg_medium"],
            fg=COLORS["text_dim"],
            font=("Consolas", 9),
        ).pack(pady=(0, 30))

        # ── Username Field ──
        self._build_input_field(content, "USERNAME", "user_entry", show_char=None)

        # ── Password Field ──
        self._build_input_field(content, "PASSWORD", "pass_entry", show_char="●")

        # ── License Key Field ──
        self._build_input_field(content, "LICENSE KEY", "key_entry", show_char=None)

        # Status label
        self.status_label = tk.Label(
            content,
            text="",
            bg=COLORS["bg_medium"],
            fg=COLORS["error"],
            font=("Consolas", 9),
        )
        self.status_label.pack(pady=(15, 5))

        # Login button
        self.login_btn = tk.Canvas(
            content, width=340, height=45,
            bg=COLORS["bg_medium"], highlightthickness=0,
            cursor="hand2"
        )
        self.login_btn.pack(pady=(5, 10))
        self._draw_login_button(COLORS["red_primary"])
        self.login_btn.bind("<Enter>", lambda e: self._draw_login_button(COLORS["red_hover"]))
        self.login_btn.bind("<Leave>", lambda e: self._draw_login_button(COLORS["red_primary"]))
        self.login_btn.bind("<Button-1>", lambda e: self._on_login_click())

        # Forgot key link
        tk.Label(
            content,
            text="Need a license? Contact admin",
            bg=COLORS["bg_medium"],
            fg=COLORS["text_dim"],
            font=("Consolas", 8),
            cursor="hand2"
        ).pack(pady=(0, 0))

    def _build_input_field(self, parent, label_text, attr_name, show_char=None):
        """Build a styled input field with label."""
        # Label
        tk.Label(
            parent,
            text=label_text,
            bg=COLORS["bg_medium"],
            fg=COLORS["text_secondary"],
            font=("Consolas", 9, "bold"),
            anchor="w"
        ).pack(anchor="w", padx=30, pady=(10, 3))

        # Entry container with border effect
        entry_frame = tk.Frame(
            parent,
            bg=COLORS["border"],
            padx=1, pady=1
        )
        entry_frame.pack(padx=30, fill=tk.X)

        entry = tk.Entry(
            entry_frame,
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["red_primary"],
            font=("Consolas", 11),
            relief="flat",
            bd=8,
        )
        if show_char:
            entry.config(show=show_char)

        entry.pack(fill=tk.X)

        # Focus effects
        def on_focus_in(e):
            entry_frame.config(bg=COLORS["border_focus"])
            entry.config(bg=COLORS["bg_input_focus"])

        def on_focus_out(e):
            entry_frame.config(bg=COLORS["border"])
            entry.config(bg=COLORS["bg_input"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        # Bind Enter key to login
        entry.bind("<Return>", lambda e: self._on_login_click())

        setattr(self, attr_name, entry)

    def _draw_login_button(self, color, text="LOGIN ▸"):
        """Draw the login button on canvas."""
        self.login_btn.delete("all")
        # Rounded rectangle background
        self.login_btn.create_rectangle(
            2, 2, 338, 43,
            fill=color, outline=color, width=0
        )
        # Button text
        self.login_btn.create_text(
            170, 22,
            text=text,
            fill="white",
            font=("Consolas", 12, "bold")
        )

    # ═══════════════════════════════════════════════════════
    # Animation
    # ═══════════════════════════════════════════════════════

    def _animate_glow(self):
        """Animate the red glow lines."""
        if not self._animation_running:
            return

        self._glow_phase += 0.05
        if self._glow_phase > 2 * math.pi:
            self._glow_phase -= 2 * math.pi

        # Calculate glow intensity
        intensity = (math.sin(self._glow_phase) + 1) / 2  # 0.0 to 1.0

        # Interpolate color
        r = int(60 + intensity * 132)  # 60 to 192
        g = int(10 + intensity * 10)
        b = int(10 + intensity * 10)
        glow_color = f"#{r:02x}{g:02x}{b:02x}"

        # Draw gradient line on both canvases
        for canvas in [self.glow_canvas, self.glow_canvas2]:
            canvas.delete("all")
            w = 320
            segments = 40
            seg_w = w / segments
            for i in range(segments):
                # Create wave effect
                local_phase = self._glow_phase + (i / segments) * math.pi * 2
                local_intensity = (math.sin(local_phase) + 1) / 2
                lr = int(40 + local_intensity * 152)
                lg = int(5 + local_intensity * 15)
                lb = int(5 + local_intensity * 15)
                seg_color = f"#{lr:02x}{lg:02x}{lb:02x}"
                canvas.create_rectangle(
                    i * seg_w, 0, (i + 1) * seg_w, 4,
                    fill=seg_color, outline=seg_color
                )

        self.root.after(30, self._animate_glow)

    # ═══════════════════════════════════════════════════════
    # Login Logic
    # ═══════════════════════════════════════════════════════

    def _on_login_click(self):
        """Handle login button click."""
        username = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()
        license_key = self.key_entry.get().strip()

        # Validation
        if not username:
            self._show_status("⚠ Username is required", COLORS["error"])
            return
            
        # Admin bypass for "احسين", "حسين", or "hessen"
        is_admin_bypass = username.lower() in ["احسين", "حسين", "hessen"]

        if not is_admin_bypass:
            if not password:
                self._show_status("⚠ Password is required", COLORS["error"])
                return
            if not license_key:
                self._show_status("⚠ License key is required", COLORS["error"])
                return

        # Disable button and show loading
        self.login_btn.unbind("<Button-1>")
        self.login_btn.unbind("<Enter>")
        self.login_btn.unbind("<Leave>")
        self._show_status("Authenticating...", COLORS["text_secondary"])
        self._draw_login_button(COLORS["red_dark"], text="VERIFYING...")

        # Simulate authentication delay
        def authenticate():
            time.sleep(1.2)

            is_valid = False
            if is_admin_bypass:
                is_valid = True
            else:
                # Valid credentials check: user must type correct password/key if not bypassing
                # Default is: password="admin", license="admin"
                if password == "admin" and license_key == "admin":
                    is_valid = True

            if is_valid:
                self._authenticated = True
                self._username = username
                self._license_key = license_key if not is_admin_bypass else "BYPASS_KEY"
                self.root.after(0, self._on_auth_success)
            else:
                self.root.after(0, self._on_auth_failed)

        threading.Thread(target=authenticate, daemon=True).start()

    def _on_auth_success(self):
        """Handle successful authentication."""
        self._show_status("✓ Authentication successful!", COLORS["success"])
        self._draw_login_button(COLORS["success"], text="✓ WELCOME")

        # Close login and launch main GUI after short delay
        self.root.after(800, self._launch_main)

    def _on_auth_failed(self):
        """Handle failed authentication."""
        self._show_status("⚠ Invalid Password or License Key", COLORS["error"])
        self._draw_login_button(COLORS["red_primary"])
        # Re-bind events to allow user to try again
        self.login_btn.bind("<Enter>", lambda e: self._draw_login_button(COLORS["red_hover"]))
        self.login_btn.bind("<Leave>", lambda e: self._draw_login_button(COLORS["red_primary"]))
        self.login_btn.bind("<Button-1>", lambda e: self._on_login_click())

    def _launch_main(self):
        """Close login window and trigger main GUI."""
        self._animation_running = False
        self.root.destroy()
        if self.on_login_success:
            self.on_login_success(self._username, self._license_key)

    def _show_status(self, text, color):
        """Update the status label."""
        self.status_label.config(text=text, fg=color)

    def _on_close(self):
        """Handle window close."""
        self._animation_running = False
        self.root.destroy()

    # ═══════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════

    def run(self):
        """Start the login window main loop."""
        self.root.mainloop()
        return self._authenticated

    @property
    def authenticated(self):
        return self._authenticated

    @property
    def username(self):
        return self._username

    @property
    def license_key(self):
        return self._license_key
