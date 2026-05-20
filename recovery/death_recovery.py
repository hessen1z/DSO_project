"""
Death Recovery System
=====================
Detects death screen, revives character, and returns to farming area.
"""

import time
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("death")


class DeathRecovery:
    """
    Death detection and recovery system.

    When the death screen is detected:
    1. Wait a moment
    2. Click the revive button
    3. Wait for respawn
    4. Return to farming area (first waypoint)
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict,
                 waypoint_system=None):
        """
        Initialize the death recovery system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Death configuration dict
            waypoint_system: Reference to the navigation system
        """
        self.state = game_state
        self.input = humanizer
        self.waypoints = waypoint_system

        # Config
        self.revive_delay = config.get("revive_delay", 2.0)
        self.return_delay = config.get("return_to_farm_delay", 3.0)

        # State
        self._recovering = False
        self._recovery_start_time = 0
        self._total_recoveries = 0

        logger.info(f"DeathRecovery initialized | Revive delay: {self.revive_delay}s")

    def execute(self):
        """
        Execute one death recovery tick.
        Called by the decision engine when in DEAD state.
        """
        if not self.state.is_dead:
            # Recovery complete
            if self._recovering:
                self._finish_recovery()
            return

        if not self._recovering:
            self._start_recovery()

        # Wait for revive delay
        elapsed = time.time() - self._recovery_start_time
        if elapsed < self.revive_delay:
            logger.debug(f"Waiting to revive... {elapsed:.1f}/{self.revive_delay}s")
            return

        # Try to click revive button (center of screen is a common position)
        # This should be adjusted based on the actual revive button position
        screen_center_x = self.state._screen_center_x
        screen_center_y = self.state._screen_center_y

        logger.info("Clicking revive button")
        self.input.click(screen_center_x, screen_center_y + 100)
        self.input.delay(0.5, 1.0)

        # Press Enter as fallback (some games use Enter to confirm revive)
        self.input.press_key("enter")
        self.input.delay(0.5, 1.0)

    def _start_recovery(self):
        """Start the recovery process."""
        self._recovering = True
        self._recovery_start_time = time.time()
        self._total_recoveries += 1
        self.state.record_death()
        logger.warning(f"Death detected! Starting recovery #{self._total_recoveries}")

    def _finish_recovery(self):
        """Finish recovery and return to farming."""
        self._recovering = False
        logger.info("Recovery complete — returning to farming area")

        # Return to first waypoint
        if self.waypoints:
            self.waypoints.go_to_first()

        # Wait before resuming
        self.input.delay(self.return_delay, self.return_delay + 1.0)

    def get_status(self) -> dict:
        """Get death recovery status."""
        return {
            "recovering": self._recovering,
            "total_deaths": self._total_recoveries,
            "is_dead": self.state.is_dead,
        }
