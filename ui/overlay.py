"""
Overlay UI
==========
Real-time visual overlay using OpenCV.
Draws detection boxes, bot state, FPS, and more on the captured frame.
Runs in its own thread.
"""

import time
import threading
import cv2
import numpy as np
from utils.logger import get_logger

logger = get_logger("overlay")


# Color palette (BGR format for OpenCV)
COLORS = {
    "enemy":         (0, 0, 255),       # Red
    "elite":         (0, 128, 255),     # Orange
    "boss":          (0, 0, 200),       # Dark Red
    "loot":          (0, 255, 255),     # Yellow
    "portal":        (255, 0, 255),     # Magenta
    "npc":           (0, 255, 0),       # Green
    "dead_screen":   (100, 100, 255),   # Light Red
    "hp_bar":        (0, 200, 0),       # Dark Green
    "inventory_full": (0, 165, 255),    # Orange
    "default":       (200, 200, 200),   # Gray
}

STATE_COLORS = {
    "IDLE":    (200, 200, 200),  # Gray
    "MOVING":  (255, 200, 0),    # Cyan
    "COMBAT":  (0, 0, 255),      # Red
    "LOOTING": (0, 255, 255),    # Yellow
    "HEALING": (0, 255, 0),      # Green
    "DEAD":    (0, 0, 150),      # Dark Red
    "SELLING": (255, 165, 0),    # Blue-ish
    "STUCK":   (0, 100, 255),    # Orange
    "PAUSED":  (128, 128, 128),  # Gray
}


class Overlay:
    """
    Real-time OpenCV overlay for visualizing bot state.

    Features:
    - Detection bounding boxes with class labels
    - Current FSM state display
    - FPS counters (capture + detection)
    - HP bar indicator
    - Statistics panel
    - Waypoint visualization
    """

    def __init__(self, config: dict, capture_system=None, detector=None,
                 game_state=None, waypoint_system=None):
        """
        Initialize the overlay.

        Args:
            config: Overlay configuration dict
            capture_system: Reference to ScreenCapture
            detector: Reference to YOLODetector
            game_state: Reference to GameState
            waypoint_system: Reference to WaypointSystem
        """
        self.config = config
        self.capture = capture_system
        self.detector = detector
        self.state = game_state
        self.waypoints = waypoint_system

        # Config
        self.enabled = config.get("enabled", True)
        self.show_boxes = config.get("show_boxes", True)
        self.show_state = config.get("show_state", True)
        self.show_fps = config.get("show_fps", True)
        self.show_waypoints = config.get("show_waypoints", True)
        self.box_thickness = config.get("box_thickness", 2)
        self.font_scale = config.get("font_scale", 0.6)
        self.opacity = config.get("opacity", 0.7)

        # Window
        self._window_name = "Drakensang AI Bot - Overlay"
        self._running = False
        self._thread = None
        self._visible = False
        self.gui_active = False

        # Tkinter window references for safe GUI thread rendering
        self._overlay_window = None
        self._canvas = None
        self._photo_image = None

        logger.info(f"Overlay initialized | Enabled: {self.enabled}")

    def _draw_detections(self, frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw detection bounding boxes and labels."""
        if not self.show_boxes:
            return frame

        for det in detections:
            color = COLORS.get(det.class_name, COLORS["default"])
            x1, y1, x2, y2 = det.bbox

            # Draw box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.box_thickness)

            # Draw label with background
            label = f"{det.class_name} {det.confidence:.0%}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, 1
            )

            # Label background
            cv2.rectangle(frame, (x1, y1 - label_h - 10), (x1 + label_w + 5, y1), color, -1)

            # Label text
            cv2.putText(frame, label, (x1 + 2, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, (255, 255, 255), 1)

            # Draw center point
            cv2.circle(frame, (det.center_x, det.center_y), 4, color, -1)

        return frame

    def _draw_state_panel(self, frame: np.ndarray) -> np.ndarray:
        """Draw the bot state information panel."""
        if not self.show_state or not self.state:
            return frame

        summary = self.state.get_state_summary()
        bot_state = summary.get("bot_state", "UNKNOWN")
        state_color = STATE_COLORS.get(bot_state, (200, 200, 200))

        # Panel background
        panel_h = 220
        panel_w = 280
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (panel_w, panel_h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, self.opacity, frame, 1 - self.opacity, 0, frame)

        # Panel border
        cv2.rectangle(frame, (10, 10), (panel_w, panel_h), state_color, 2)

        # Title
        cv2.putText(frame, "DRAKENSANG AI BOT", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

        # Bot state
        cv2.putText(frame, f"State: {bot_state}", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, state_color, 2)

        # Duration
        duration = summary.get("state_duration", 0)
        cv2.putText(frame, f"Duration: {duration:.1f}s", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        # Enemies
        enemies = summary.get("enemies", 0) + summary.get("elites", 0) + summary.get("bosses", 0)
        cv2.putText(frame, f"Enemies: {enemies}", (20, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # Loot
        loot = summary.get("loot", 0)
        cv2.putText(frame, f"Loot: {loot}", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # HP
        hp = summary.get("hp", 100)
        hp_color = (0, 255, 0) if hp > 60 else (0, 255, 255) if hp > 30 else (0, 0, 255)
        cv2.putText(frame, f"HP: {hp:.0f}%", (20, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, hp_color, 1)

        # HP bar
        bar_x, bar_y = 80, 130
        bar_w = 180
        bar_h = 12
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
        fill_w = int(bar_w * hp / 100)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), hp_color, -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (200, 200, 200), 1)

        # Stats
        y_offset = 160
        stats_lines = [
            f"Kills: {summary.get('enemies_killed', 0)}",
            f"Loot: {summary.get('loot_picked', 0)}",
            f"Potions: {summary.get('potions_used', 0)}",
            f"Deaths: {summary.get('deaths', 0)}",
            f"Time: {summary.get('session_time_str', '00:00:00')}",
        ]

        for line in stats_lines:
            cv2.putText(frame, line, (20, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)
            y_offset += 15

        return frame

    def _draw_fps(self, frame: np.ndarray) -> np.ndarray:
        """Draw FPS counters."""
        if not self.show_fps:
            return frame

        h, w = frame.shape[:2]
        fps_x = w - 200

        # Capture FPS
        cap_fps = self.capture.fps if self.capture else 0
        cv2.putText(frame, f"Capture: {cap_fps:.1f} FPS", (fps_x, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        # Detection FPS
        det_fps = self.detector.fps if self.detector else 0
        cv2.putText(frame, f"Detect: {det_fps:.1f} FPS", (fps_x, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

        return frame

    def _draw_waypoints(self, frame: np.ndarray) -> np.ndarray:
        """Draw waypoint path on the overlay."""
        if not self.show_waypoints or not self.waypoints:
            return frame

        wps = self.waypoints.waypoints
        if len(wps) < 2:
            return frame

        # Draw waypoint path
        for i in range(len(wps)):
            wp = wps[i]
            x, y = wp.get("x", 0), wp.get("y", 0)

            # Draw waypoint marker
            is_current = (i == self.waypoints.current_index)
            color = (0, 255, 0) if is_current else (100, 100, 100)
            radius = 8 if is_current else 5

            cv2.circle(frame, (x, y), radius, color, -1)
            cv2.putText(frame, str(i), (x + 10, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

            # Draw line to next waypoint
            next_i = (i + 1) % len(wps)
            next_wp = wps[next_i]
            cv2.line(frame, (x, y), (next_wp.get("x", 0), next_wp.get("y", 0)),
                     (60, 60, 60), 1)

        return frame

    def _draw_target_indicator(self, frame: np.ndarray) -> np.ndarray:
        """Draw indicator on current target."""
        if not self.state:
            return frame

        target = self.state.current_target
        if target is None:
            return frame

        # Draw crosshair on target
        cx, cy = target.center_x, target.center_y
        size = 20
        color = (0, 255, 255)  # Yellow

        cv2.line(frame, (cx - size, cy), (cx + size, cy), color, 2)
        cv2.line(frame, (cx, cy - size), (cx, cy + size), color, 2)
        cv2.circle(frame, (cx, cy), size, color, 1)

        # Label
        cv2.putText(frame, "TARGET", (cx - 25, cy - size - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return frame

    def _overlay_loop(self):
        """Main overlay rendering loop."""
        logger.info("Overlay thread started")
        window_created = False

        while self._running:
            try:
                if not self._visible:
                    if window_created:
                        try:
                            cv2.destroyWindow(self._window_name)
                        except Exception:
                            pass
                        window_created = False
                    time.sleep(0.1)
                    continue

                if not window_created:
                    cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(self._window_name, 960, 540)
                    window_created = True

                # Get current frame
                frame = self.capture.frame if self.capture else None
                if frame is None:
                    time.sleep(0.05)
                    continue

                # Resize for overlay display (half resolution for performance)
                h, w = frame.shape[:2]
                display = cv2.resize(frame, (w // 2, h // 2))

                # Get detections (scale boxes to half resolution)
                if self.detector:
                    detections = self.detector.detections
                    # Scale detection coordinates
                    scaled_detections = []
                    for det in detections:
                        from detection.yolo_detector import Detection
                        scaled = Detection(
                            class_name=det.class_name,
                            confidence=det.confidence,
                            bbox=(det.bbox[0]//2, det.bbox[1]//2, det.bbox[2]//2, det.bbox[3]//2),
                            class_id=det.class_id
                        )
                        scaled_detections.append(scaled)
                    display = self._draw_detections(display, scaled_detections)

                # Draw overlays
                display = self._draw_state_panel(display)
                display = self._draw_fps(display)
                display = self._draw_target_indicator(display)

                # Show frame
                cv2.imshow(self._window_name, display)

                # Handle key press (1ms wait)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("Overlay closed by user (Q)")
                    self._visible = False

            except Exception as e:
                logger.error(f"Overlay error: {e}")
                time.sleep(0.1)

        if window_created:
            try:
                cv2.destroyWindow(self._window_name)
            except Exception:
                pass
        logger.info("Overlay thread stopped")

    def start(self):
        """Start the overlay. Bypasses thread creation if running in GUI mode."""
        if not self.enabled:
            logger.info("Overlay disabled in config")
            return

        if self._running:
            return

        self._running = True
        if self.gui_active:
            logger.info("Overlay starting in GUI mode (main-thread updates only)")
        else:
            self._thread = threading.Thread(target=self._overlay_loop, daemon=True, name="OverlayThread")
            self._thread.start()
            logger.info("Overlay thread started")

    def stop(self):
        """Stop the overlay."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        
        # Clean up any residual Tkinter window
        if hasattr(self, "_overlay_window") and self._overlay_window:
            try:
                self._overlay_window.destroy()
            except Exception:
                pass
            self._overlay_window = None
            self._canvas = None
            self._photo_image = None

        # Clean up any residual cv2 window
        if getattr(self, "_window_created", False) or hasattr(self, "_overlay_loop"):
            try:
                cv2.destroyWindow(self._window_name)
            except Exception:
                pass
            self._window_created = False
            
        logger.info("Overlay stopped")

    def update_once(self):
        """Process and draw overlay once. Designed to be called safely on the main GUI thread."""
        if not self._running:
            return

        try:
            # GUI active mode - render inside a beautiful Tkinter Toplevel window using PIL
            if self.gui_active:
                if not self._visible:
                    if self._overlay_window:
                        try:
                            self._overlay_window.destroy()
                        except Exception:
                            pass
                        self._overlay_window = None
                        self._canvas = None
                        self._photo_image = None
                    return

                # Create Toplevel overlay window if not exists
                if not self._overlay_window:
                    import tkinter as tk
                    self._overlay_window = tk.Toplevel()
                    self._overlay_window.title("DRAKENSANG AI — Live Vision Feed")
                    self._overlay_window.geometry("960x540")
                    self._overlay_window.resizable(False, False)
                    self._overlay_window.configure(bg="#0c0d12")
                    
                    # Styled top bar or label
                    self._overlay_window.overrideredirect(False)
                    
                    # Clean handle for close button
                    def on_close():
                        self._visible = False
                        if self._overlay_window:
                            try:
                                self._overlay_window.destroy()
                            except Exception:
                                pass
                            self._overlay_window = None
                            self._canvas = None
                            self._photo_image = None
                    self._overlay_window.protocol("WM_DELETE_WINDOW", on_close)

                    self._canvas = tk.Canvas(self._overlay_window, width=960, height=540, bg="#0c0d12", highlightthickness=0)
                    self._canvas.pack(fill=tk.BOTH, expand=True)

                # Get frame
                frame = self.capture.frame if self.capture else None
                if frame is None:
                    return

                # Process display BGR image
                h, w = frame.shape[:2]
                display = cv2.resize(frame, (w // 2, h // 2))

                # Scale and draw detections
                if self.detector:
                    detections = self.detector.detections
                    scaled_detections = []
                    for det in detections:
                        from detection.yolo_detector import Detection
                        scaled = Detection(
                            class_name=det.class_name,
                            confidence=det.confidence,
                            bbox=(det.bbox[0]//2, det.bbox[1]//2, det.bbox[2]//2, det.bbox[3]//2),
                            class_id=det.class_id
                        )
                        scaled_detections.append(scaled)
                    display = self._draw_detections(display, scaled_detections)

                display = self._draw_state_panel(display)
                display = self._draw_fps(display)
                display = self._draw_target_indicator(display)

                # Convert display BGR numpy array to PIL ImageTk.PhotoImage
                from PIL import Image, ImageTk
                rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                
                # Create photo image and render on canvas
                self._photo_image = ImageTk.PhotoImage(image=pil_img)
                self._canvas.delete("all")
                self._canvas.create_image(0, 0, anchor="nw", image=self._photo_image)
                return

            # Non-GUI mode - fallback to cv2.imshow
            if not self._visible:
                if getattr(self, "_window_created", False):
                    try:
                        cv2.destroyWindow(self._window_name)
                    except Exception:
                        pass
                    self._window_created = False
                return

            if not getattr(self, "_window_created", False):
                cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self._window_name, 960, 540)
                self._window_created = True

            # Get current frame
            frame = self.capture.frame if self.capture else None
            if frame is None:
                return

            # Resize for overlay display (half resolution for performance)
            h, w = frame.shape[:2]
            display = cv2.resize(frame, (w // 2, h // 2))

            # Get detections (scale boxes to half resolution)
            if self.detector:
                detections = self.detector.detections
                scaled_detections = []
                for det in detections:
                    from detection.yolo_detector import Detection
                    scaled = Detection(
                        class_name=det.class_name,
                        confidence=det.confidence,
                        bbox=(det.bbox[0]//2, det.bbox[1]//2, det.bbox[2]//2, det.bbox[3]//2),
                        class_id=det.class_id
                    )
                    scaled_detections.append(scaled)
                display = self._draw_detections(display, scaled_detections)

            # Draw overlays
            display = self._draw_state_panel(display)
            display = self._draw_fps(display)
            display = self._draw_target_indicator(display)

            # Show frame
            cv2.imshow(self._window_name, display)

            # Handle key press (1ms wait)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                logger.info("Overlay closed by user (Q)")
                self._visible = False

        except Exception as e:
            logger.error(f"Overlay single update error: {e}")

    def toggle(self):
        """Toggle overlay visibility."""
        self._visible = not self._visible
        logger.info(f"Overlay {'visible' if self._visible else 'hidden'}")

    @property
    def visible(self) -> bool:
        return self._visible
