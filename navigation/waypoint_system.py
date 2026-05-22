"""
Waypoint Navigation System
==========================
Click-to-move navigation using predefined waypoints.

Features:
- Circular waypoint routes for farming loops
- Recording mode (press hotkey to save current mouse position as waypoint)
- Minimap Green-Dot Tracker: detects the bright green player dot on the
  DSO overlay map (Tab key) to track player position and navigate by
  clicking directly on the overlay map ahead of the player
- Layer 1: Recorded waypoints → bot clicks them in order on the map overlay
- Layer 2: Path correction if player dot drifts from the expected node
"""

import time
import json
import os
import math
import threading
import cv2
import numpy as np
from state.game_state import GameState
from input.humanizer import Humanizer
from input.action_lock import ActionLock
from utils.logger import get_logger

logger = get_logger("navigation")


class WaypointSystem:
    """
    Waypoint-based navigation with minimap green-dot tracking.

    Minimap navigation overview:
        1. Bot grabs the latest screen frame.
        2. Crops the minimap region (configurable, defaults to top-right corner).
        3. Converts to HSV and masks for bright green pixels (the player dot).
        4. Finds the centroid of the green blob → player's minimap coordinate.
        5. Finds the next waypoint node on the minimap.
        6. Clicks slightly ahead of the player toward the next node.

    Classic waypoint navigation (no minimap):
        Bot right-clicks screen waypoints in order at a configurable delay.
    """

    # Default minimap region as fraction of screen (top-right corner in DSO)
    _DEFAULT_MINIMAP_FRAC = {"left": 0.77, "top": 0.0, "right": 1.0, "bottom": 0.22}

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict,
                 action_lock: ActionLock = None):
        self.state = game_state
        self.input = humanizer
        self.action_lock = action_lock or ActionLock(enabled=False)

        # --- Classic waypoint config ---
        self.waypoints = config.get("waypoints", [])
        self.move_click = config.get("move_click_key", "right")
        self.reached_threshold = config.get("waypoint_reached_threshold", 30)
        self.move_delay = config.get("move_delay", 0.5)

        # --- Minimap config ---
        mm_cfg = config.get("minimap", {})
        self.minimap_enabled = mm_cfg.get("enabled", False)
        self._minimap_region_cfg = mm_cfg.get("region", None)  # {left,top,width,height} in pixels
        self._green_lower = np.array(mm_cfg.get("green_dot_lower_hsv", [40, 70, 70]))
        self._green_upper = np.array(mm_cfg.get("green_dot_upper_hsv", [80, 255, 255]))
        self._min_dot_area = mm_cfg.get("min_dot_area", 5)
        self._max_dot_area = mm_cfg.get("max_dot_area", 400)
        self._minimap_waypoint_offset = mm_cfg.get("waypoint_click_offset", 20)

        # --- Navigation state ---
        self._current_waypoint_index = 0
        self._last_move_time = 0
        self._recording = False
        self._recorded_waypoints = []

        # --- Minimap state ---
        self._player_minimap_pos = None   # (x, y) in minimap pixel space
        self._minimap_lock = threading.Lock()
        self._last_minimap_frame = None   # Last minimap crop (for overlay debug)
        self._screen_w = 1920
        self._screen_h = 1080

        # Config file path for saving waypoints
        self._config_path = os.path.join("config", "settings.json")
        self.active_map_name = "default"

        logger.info(
            f"WaypointSystem initialized | Waypoints: {len(self.waypoints)} | "
            f"Minimap: {self.minimap_enabled}"
        )

    # =========================================================
    # Properties
    # =========================================================

    @property
    def current_waypoint(self) -> dict:
        """Get the current target waypoint."""
        if not self.waypoints:
            return None
        return self.waypoints[self._current_waypoint_index]

    @property
    def current_index(self) -> int:
        return self._current_waypoint_index

    @property
    def total_waypoints(self) -> int:
        return len(self.waypoints)

    @property
    def player_minimap_pos(self):
        """Last known player position on minimap (x, y) in minimap pixel coords."""
        with self._minimap_lock:
            return self._player_minimap_pos

    # =========================================================
    # Main Execute
    # =========================================================

    def execute(self):
        """
        Execute one navigation tick.
        Called by the decision engine when in MOVING state.
        All movement clicks are serialized through the action lock.
        """
        if not self.waypoints:
            logger.debug("No waypoints configured — standing idle")
            return

        # Rate-limit movement clicks
        now = time.time()
        if now - self._last_move_time < self.move_delay:
            return

        waypoint = self.current_waypoint
        if waypoint is None:
            return

        with self.action_lock.acquire("navigation") as acquired:
            if not acquired:
                logger.debug("Navigation skipped — action lock unavailable")
                return

            # Choose navigation mode
            if self.minimap_enabled:
                self._execute_minimap_navigation(waypoint)
            else:
                self._execute_classic_navigation(waypoint)

        self._last_move_time = now

    # =========================================================
    # Classic Navigation (right-click screen waypoints)
    # =========================================================

    def _execute_classic_navigation(self, waypoint: dict):
        """Click on the waypoint screen coordinate to move the character."""
        target_x = waypoint.get("x", 960)
        target_y = waypoint.get("y", 540)

        if self.move_click == "right":
            self.input.right_click(target_x, target_y)
        else:
            self.input.click(target_x, target_y)

        logger.debug(
            f"Classic nav → waypoint {self._current_waypoint_index}: ({target_x}, {target_y})"
        )
        self._advance_waypoint()

    # =========================================================
    # Minimap Navigation (green-dot tracking)
    # =========================================================

    def update_minimap_frame(self, frame: np.ndarray):
        """
        Process a screen frame to detect the player's green dot on the minimap.
        Should be called each time a new frame is captured.

        Args:
            frame: Full-screen BGR numpy array from ScreenCapture
        """
        if frame is None or not self.minimap_enabled:
            return

        try:
            h, w = frame.shape[:2]
            self._screen_w = w
            self._screen_h = h

            # Crop the minimap region
            mm_crop, mm_offset = self._crop_minimap(frame, w, h)
            if mm_crop is None:
                return

            # Store last crop for overlay debugging
            with self._minimap_lock:
                self._last_minimap_frame = mm_crop.copy()

            # Detect player green dot
            dot_pos = self._detect_green_dot(mm_crop)

            if dot_pos is not None:
                # Convert minimap-local coords to full-screen coords
                screen_x = mm_offset[0] + dot_pos[0]
                screen_y = mm_offset[1] + dot_pos[1]
                with self._minimap_lock:
                    self._player_minimap_pos = (screen_x, screen_y)
                logger.debug(f"Player minimap dot at screen ({screen_x}, {screen_y})")
            else:
                logger.debug("Green dot not found on minimap this frame")

        except Exception as e:
            logger.error(f"Minimap update error: {e}")

    def _crop_minimap(self, frame: np.ndarray, w: int, h: int):
        """
        Crop the minimap region from the full frame.

        Returns:
            (crop_array, (offset_x, offset_y)) or (None, None)
        """
        if self._minimap_region_cfg:
            # User specified an exact pixel region {left, top, width, height}
            r = self._minimap_region_cfg
            x1 = int(r.get("left", 0))
            y1 = int(r.get("top", 0))
            x2 = int(x1 + r.get("width", 200))
            y2 = int(y1 + r.get("height", 200))
        else:
            # Default: top-right corner of screen (DSO minimap location)
            frac = self._DEFAULT_MINIMAP_FRAC
            x1 = int(frac["left"] * w)
            y1 = int(frac["top"] * h)
            x2 = int(frac["right"] * w)
            y2 = int(frac["bottom"] * h)

        # Safety clamp
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None, None

        return frame[y1:y2, x1:x2].copy(), (x1, y1)

    def _detect_green_dot(self, mm_crop: np.ndarray):
        """
        Detect the bright green player dot in a minimap crop.

        Returns:
            (cx, cy) center of the green blob in crop-local coordinates, or None
        """
        hsv = cv2.cvtColor(mm_crop, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._green_lower, self._green_upper)

        # Clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_area = 0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self._min_dot_area <= area <= self._max_dot_area:
                if area > best_area:
                    best_area = area
                    best = cnt

        if best is None:
            return None

        # Return centroid
        M = cv2.moments(best)
        if M["m00"] == 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)

    def _execute_minimap_navigation(self, waypoint: dict):
        """
        Navigate using minimap click-to-move.

        Strategy:
            1. Get the player's current minimap screen position.
            2. Get the next waypoint's minimap position.
            3. Click slightly ahead of the player toward the waypoint on the map.
            4. If player is close enough to the waypoint, advance to next.
        """
        player_pos = self.player_minimap_pos

        # Waypoint stores minimap screen coords (mx, my)
        wp_mx = waypoint.get("mx")
        wp_my = waypoint.get("my")

        # Fallback to classic screen coords if no minimap coords defined
        if wp_mx is None or wp_my is None:
            self._execute_classic_navigation(waypoint)
            return

        # If we can see the player dot, check distance to next waypoint
        if player_pos is not None:
            px, py = player_pos
            dist = math.sqrt((wp_mx - px) ** 2 + (wp_my - py) ** 2)

            # Advance waypoint if player dot is close enough
            if dist < self.reached_threshold:
                logger.info(
                    f"Minimap waypoint {self._current_waypoint_index} reached (dist={dist:.0f}px)"
                )
                self._advance_waypoint()
                return

            # Click toward the next waypoint on the minimap (slightly ahead)
            click_x, click_y = self._get_click_ahead(px, py, wp_mx, wp_my)
        else:
            # No dot detected — click directly on the waypoint
            click_x, click_y = wp_mx, wp_my

        logger.debug(
            f"Minimap nav → clicking ({click_x}, {click_y}) "
            f"toward waypoint {self._current_waypoint_index}"
        )
        self.input.right_click(click_x, click_y)

    def _get_click_ahead(self, px: int, py: int, tx: int, ty: int) -> tuple:
        """
        Calculate a click point slightly ahead of the player toward the target.

        Args:
            px, py: Player minimap screen position
            tx, ty: Target waypoint minimap screen position

        Returns:
            (click_x, click_y) screen coordinate to click
        """
        dx = tx - px
        dy = ty - py
        dist = math.sqrt(dx * dx + dy * dy) or 1.0

        # Step offset pixels toward target (clamped to dist)
        step = min(self._minimap_waypoint_offset, dist)
        click_x = int(px + (dx / dist) * step)
        click_y = int(py + (dy / dist) * step)

        return click_x, click_y

    def _advance_waypoint(self):
        """Advance to the next waypoint in the loop."""
        if not self.waypoints:
            return
        self._current_waypoint_index = (self._current_waypoint_index + 1) % len(self.waypoints)
        logger.debug(f"Advanced to waypoint {self._current_waypoint_index}/{len(self.waypoints)}")

    # =========================================================
    # Waypoint Recording Mode
    # =========================================================

    def go_to_waypoint(self, index: int):
        """Jump to a specific waypoint."""
        if 0 <= index < len(self.waypoints):
            self._current_waypoint_index = index
            logger.info(f"Jumped to waypoint {index}")
        else:
            logger.warning(f"Invalid waypoint index: {index}")

    def go_to_first(self):
        """Return to the first waypoint."""
        self._current_waypoint_index = 0
        logger.info("Returning to first waypoint")

    def start_recording(self):
        """Start recording waypoints."""
        self._recording = True
        self._recorded_waypoints = []
        logger.info("Waypoint recording started — press record key to add points")

    def stop_recording(self):
        """Stop recording and save waypoints."""
        self._recording = False
        if self._recorded_waypoints:
            self.waypoints = self._recorded_waypoints.copy()
            self._current_waypoint_index = 0
            self._save_waypoints()
            logger.info(f"Recording stopped — {len(self.waypoints)} waypoints saved")
        else:
            logger.warning("Recording stopped — no waypoints recorded")

    def record_point(self, x: int, y: int, mx: int = None, my: int = None):
        """
        Record a waypoint at the given screen position.
        Optionally also records the player's minimap position at the same moment.

        Args:
            x, y: Screen click coordinates
            mx, my: Minimap screen coordinates (optional)
        """
        if self._recording:
            point = {"x": x, "y": y}
            if mx is not None and my is not None:
                point["mx"] = mx
                point["my"] = my
            self._recorded_waypoints.append(point)
            logger.info(
                f"Recorded waypoint #{len(self._recorded_waypoints)}: "
                f"screen=({x},{y})"
                + (f" minimap=({mx},{my})" if mx else "")
            )

    def record_mouse_position(self):
        """
        Record a waypoint at the current mouse position.
        Also captures the minimap dot position at this moment.
        """
        import pyautogui
        pos = pyautogui.position()
        mm_pos = self.player_minimap_pos
        mx, my = mm_pos if mm_pos else (None, None)
        self.record_point(pos.x, pos.y, mx, my)

    def _save_waypoints(self):
        """Save waypoints to the config file or active map file."""
        try:
            if self.active_map_name == "default":
                if os.path.exists(self._config_path):
                    with open(self._config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                else:
                    config = {}

                if "navigation" not in config:
                    config["navigation"] = {}
                config["navigation"]["waypoints"] = self.waypoints

                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4)
                logger.info(f"Waypoints saved to {self._config_path}")
            else:
                os.makedirs(os.path.join("config", "maps"), exist_ok=True)
                map_file = os.path.join("config", "maps", f"{self.active_map_name}.json")
                with open(map_file, "w", encoding="utf-8") as f:
                    json.dump({"waypoints": self.waypoints}, f, indent=4)
                logger.info(f"Waypoints saved to map file {map_file}")
        except Exception as e:
            logger.error(f"Failed to save waypoints: {e}")

    def load_waypoints_from_file(self, filepath: str):
        """Load waypoints from a JSON file and update active map name."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                self.waypoints = data
            elif isinstance(data, dict) and "waypoints" in data:
                self.waypoints = data["waypoints"]

            self._current_waypoint_index = 0
            
            # Extract map name from filename
            base = os.path.basename(filepath)
            name, _ = os.path.splitext(base)
            self.active_map_name = name
            
            logger.info(f"Loaded {len(self.waypoints)} waypoints for map '{name}' from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load waypoints: {e}")

    @property
    def is_recording(self) -> bool:
        return self._recording

    def get_status(self) -> dict:
        """Get navigation status for logging/overlay."""
        wp = self.current_waypoint
        mm = self.player_minimap_pos
        return {
            "current_index": self._current_waypoint_index,
            "total_waypoints": len(self.waypoints),
            "target": f"({wp['x']}, {wp['y']})" if wp else "none",
            "recording": self._recording,
            "recorded_count": len(self._recorded_waypoints),
            "minimap_enabled": self.minimap_enabled,
            "player_dot": f"({mm[0]}, {mm[1]})" if mm else "not detected",
        }
