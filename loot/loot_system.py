"""
Loot System
===========
Detects and picks up loot drops after combat.
Moves to loot position and clicks to pick up.
"""

import time
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("loot")


class LootSystem:
    """
    Loot pickup system.

    Detects loot drops via YOLO detection and picks them up
    by clicking on their positions.
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict):
        """
        Initialize the loot system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Loot configuration dict
        """
        self.state = game_state
        self.input = humanizer

        # Config
        self.pickup_delay = config.get("pickup_delay", 0.3)
        self.max_attempts = config.get("max_pickup_attempts", 3)
        self.loot_radius = config.get("loot_radius", 100)

        # State
        self._pickup_attempts = 0
        self._last_pickup_time = 0
        self._total_pickups = 0

        logger.info(f"LootSystem initialized | Delay: {self.pickup_delay}s | "
                    f"Max attempts: {self.max_attempts}")

    def execute(self):
        """
        Execute one loot tick.
        Called by the decision engine when in LOOTING state.
        """
        # Rate limit
        now = time.time()
        if now - self._last_pickup_time < self.pickup_delay:
            return

        # Get nearest loot
        nearest = self.state.nearest_loot
        if nearest is None:
            self._pickup_attempts = 0
            return

        # Move to loot and click
        logger.debug(f"Picking up loot at ({nearest.center_x}, {nearest.center_y})")
        self.input.click(nearest.center_x, nearest.center_y)
        self._last_pickup_time = now
        self._pickup_attempts += 1
        self._total_pickups += 1
        self.state.record_loot()

        # If we've tried too many times on the same loot, skip it
        if self._pickup_attempts >= self.max_attempts:
            logger.warning("Max pickup attempts reached — skipping loot")
            self._pickup_attempts = 0

        # Small delay after pickup
        self.input.delay(0.1, 0.3)

    def reset(self):
        """Reset loot state."""
        self._pickup_attempts = 0

    def get_status(self) -> dict:
        """Get loot status for logging/overlay."""
        return {
            "total_pickups": self._total_pickups,
            "loot_available": len(self.state.loot_items),
            "pickup_attempts": self._pickup_attempts,
        }
