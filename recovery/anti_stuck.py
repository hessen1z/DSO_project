"""
Anti-Stuck System
=================
Detects when the bot is stuck and performs recovery actions.
"""

import time
import random
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("anti_stuck")


class AntiStuck:
    """
    Anti-stuck detection and recovery system.

    Monitors the bot's state duration and performs recovery actions
    when it appears stuck:
    1. Random mouse movement
    2. Jump (space)
    3. Rotate camera
    4. Return to nearest waypoint
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict,
                 waypoint_system=None):
        """
        Initialize the anti-stuck system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Anti-stuck configuration dict
            waypoint_system: Reference to the navigation system
        """
        self.state = game_state
        self.input = humanizer
        self.waypoints = waypoint_system

        # Config
        self.enabled = config.get("enabled", True)
        self.check_interval = config.get("check_interval", 5.0)
        self.stuck_threshold = config.get("stuck_threshold", 3.0)
        self.max_retries = config.get("max_retries", 5)

        # State
        self._retry_count = 0
        self._last_check_time = 0
        self._total_stuck_events = 0
        self._recovery_actions = [
            self._action_random_move,
            self._action_jump,
            self._action_rotate_camera,
            self._action_return_waypoint,
            self._action_full_reset,
        ]

        logger.info(f"AntiStuck initialized | Enabled: {self.enabled} | "
                    f"Threshold: {self.stuck_threshold}s | Max retries: {self.max_retries}")

    def execute(self):
        """
        Execute one anti-stuck tick.
        Called by the decision engine when in STUCK state.
        """
        if not self.enabled:
            return

        self._total_stuck_events += 1
        logger.warning(f"Stuck detected! Attempt {self._retry_count + 1}/{self.max_retries}")

        # Try recovery actions in escalating order
        action_index = min(self._retry_count, len(self._recovery_actions) - 1)
        action = self._recovery_actions[action_index]

        try:
            action()
        except Exception as e:
            logger.error(f"Recovery action failed: {e}")

        self._retry_count += 1

        # If max retries exceeded, do full reset
        if self._retry_count >= self.max_retries:
            logger.warning("Max retries reached — performing full reset")
            self._action_full_reset()
            self._retry_count = 0

        # After recovery, return to IDLE
        self.state.bot_state = GameState.STATE_IDLE

    def _action_random_move(self):
        """Recovery action 1: Random mouse movement and click."""
        logger.info("Recovery: Random movement")
        center_x = self.state._screen_center_x
        center_y = self.state._screen_center_y
        self.input.random_movement(center_x, center_y, radius=200)
        self.input.delay(0.5, 1.0)

    def _action_jump(self):
        """Recovery action 2: Jump."""
        logger.info("Recovery: Jump")
        self.input.press_key("space")
        self.input.delay(0.3, 0.5)
        # Also do a random movement
        self._action_random_move()

    def _action_rotate_camera(self):
        """Recovery action 3: Rotate camera."""
        logger.info("Recovery: Rotate camera")
        import pyautogui

        # Hold right mouse button and drag to rotate camera
        center_x = self.state._screen_center_x
        center_y = self.state._screen_center_y

        pyautogui.mouseDown(button="middle", x=center_x, y=center_y)
        self.input.delay(0.1, 0.2)

        # Drag to rotate
        offset = random.randint(100, 300) * random.choice([-1, 1])
        self.input.move_mouse(center_x + offset, center_y)
        self.input.delay(0.1, 0.2)

        pyautogui.mouseUp(button="middle")
        self.input.delay(0.3, 0.5)

        # Move after rotation
        self._action_random_move()

    def _action_return_waypoint(self):
        """Recovery action 4: Return to nearest waypoint."""
        logger.info("Recovery: Return to waypoint")
        if self.waypoints and self.waypoints.total_waypoints > 0:
            self.waypoints.go_to_first()
            self.waypoints.execute()
        else:
            self._action_random_move()
        self.input.delay(1.0, 2.0)

    def _action_full_reset(self):
        """Recovery action 5: Full reset — aggressive recovery."""
        logger.warning("Recovery: FULL RESET")

        # Multiple random movements
        for _ in range(3):
            self._action_random_move()
            self.input.delay(0.3, 0.5)

        # Jump
        self.input.press_key("space")
        self.input.delay(0.5, 1.0)

        # Return to first waypoint
        if self.waypoints:
            self.waypoints.go_to_first()

        self._retry_count = 0

    def on_successful_action(self):
        """Call this when the bot successfully performs an action (resets stuck counter)."""
        self._retry_count = 0

    def get_status(self) -> dict:
        """Get anti-stuck status."""
        return {
            "enabled": self.enabled,
            "retry_count": self._retry_count,
            "total_stuck_events": self._total_stuck_events,
        }
