"""
Waypoint Navigation System
==========================
Click-to-move navigation using predefined waypoints.
Supports circular routes, recording mode, and configurable speed.
"""

import time
import json
import os
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("navigation")


class WaypointSystem:
    """
    Waypoint-based navigation system.

    The bot clicks on screen positions to move the character
    along a predefined path. Supports circular loops for farming routes.
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict):
        """
        Initialize the waypoint system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Navigation configuration dict
        """
        self.state = game_state
        self.input = humanizer

        # Config
        self.waypoints = config.get("waypoints", [])
        self.move_click = config.get("move_click_key", "right")
        self.reached_threshold = config.get("waypoint_reached_threshold", 30)
        self.move_delay = config.get("move_delay", 0.5)

        # Navigation state
        self._current_waypoint_index = 0
        self._last_move_time = 0
        self._recording = False
        self._recorded_waypoints = []

        # Config file path for saving waypoints
        self._config_path = os.path.join("config", "settings.json")

        logger.info(f"WaypointSystem initialized | Waypoints: {len(self.waypoints)}")

    @property
    def current_waypoint(self) -> dict:
        """Get the current target waypoint."""
        if not self.waypoints:
            return None
        return self.waypoints[self._current_waypoint_index]

    @property
    def current_index(self) -> int:
        """Get current waypoint index."""
        return self._current_waypoint_index

    @property
    def total_waypoints(self) -> int:
        """Get total number of waypoints."""
        return len(self.waypoints)

    def execute(self):
        """
        Execute one navigation tick.
        Called by the decision engine when in MOVING state.
        """
        if not self.waypoints:
            logger.debug("No waypoints configured — standing idle")
            return

        # Rate limit movement clicks
        now = time.time()
        if now - self._last_move_time < self.move_delay:
            return

        # Get current waypoint
        waypoint = self.current_waypoint
        if waypoint is None:
            return

        target_x = waypoint.get("x", 960)
        target_y = waypoint.get("y", 540)

        # Click to move towards waypoint
        if self.move_click == "right":
            self.input.right_click(target_x, target_y)
        else:
            self.input.click(target_x, target_y)

        self._last_move_time = now
        logger.debug(f"Moving to waypoint {self._current_waypoint_index}: ({target_x}, {target_y})")

        # Advance to next waypoint after a delay
        # (In a real bot, you'd check if you arrived based on position/detection)
        # For now, we advance based on time
        self._advance_waypoint()

    def _advance_waypoint(self):
        """Move to the next waypoint in the loop."""
        if not self.waypoints:
            return

        self._current_waypoint_index = (self._current_waypoint_index + 1) % len(self.waypoints)
        logger.debug(f"Advanced to waypoint {self._current_waypoint_index}/{len(self.waypoints)}")

    def go_to_waypoint(self, index: int):
        """
        Jump to a specific waypoint.

        Args:
            index: Waypoint index to go to
        """
        if 0 <= index < len(self.waypoints):
            self._current_waypoint_index = index
            logger.info(f"Jumped to waypoint {index}")
        else:
            logger.warning(f"Invalid waypoint index: {index}")

    def go_to_first(self):
        """Return to the first waypoint."""
        self._current_waypoint_index = 0
        logger.info("Returning to first waypoint")

    # =========================================================
    # Recording Mode
    # =========================================================

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

    def record_point(self, x: int, y: int):
        """
        Record a waypoint at the given position.

        Args:
            x: Screen X position
            y: Screen Y position
        """
        if self._recording:
            point = {"x": x, "y": y}
            self._recorded_waypoints.append(point)
            logger.info(f"Recorded waypoint #{len(self._recorded_waypoints)}: ({x}, {y})")

    def record_mouse_position(self):
        """Record a waypoint at the current mouse position."""
        import pyautogui
        pos = pyautogui.position()
        self.record_point(pos.x, pos.y)

    def _save_waypoints(self):
        """Save waypoints to the config file."""
        try:
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
        except Exception as e:
            logger.error(f"Failed to save waypoints: {e}")

    def load_waypoints_from_file(self, filepath: str):
        """
        Load waypoints from a JSON file.

        Args:
            filepath: Path to JSON file with waypoints list
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                self.waypoints = data
            elif isinstance(data, dict) and "waypoints" in data:
                self.waypoints = data["waypoints"]

            self._current_waypoint_index = 0
            logger.info(f"Loaded {len(self.waypoints)} waypoints from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load waypoints: {e}")

    @property
    def is_recording(self) -> bool:
        return self._recording

    def get_status(self) -> dict:
        """Get navigation status for logging/overlay."""
        wp = self.current_waypoint
        return {
            "current_index": self._current_waypoint_index,
            "total_waypoints": len(self.waypoints),
            "target": f"({wp['x']}, {wp['y']})" if wp else "none",
            "recording": self._recording,
            "recorded_count": len(self._recorded_waypoints),
        }
