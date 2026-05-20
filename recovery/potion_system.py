"""
Potion System
=============
Monitors HP and uses healing potions when health drops below threshold.
"""

import time
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("potion")


class PotionSystem:
    """
    Automatic potion usage system.

    Monitors HP bar detection and presses the potion key
    when HP drops below a configurable threshold.
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict):
        """
        Initialize the potion system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Potion configuration dict
        """
        self.state = game_state
        self.input = humanizer

        # Config
        self.hp_threshold = config.get("hp_threshold", 40)
        self.potion_key = config.get("potion_key", "F1")
        self.cooldown = config.get("cooldown", 5.0)
        self.hp_recovery_target = config.get("hp_recovery_target", 70)

        # State
        self._last_potion_time = 0
        self._potions_used = 0

        logger.info(f"PotionSystem initialized | Threshold: {self.hp_threshold}% | "
                    f"Key: {self.potion_key} | Cooldown: {self.cooldown}s")

    def execute(self):
        """
        Execute one healing tick.
        Called by the decision engine when in HEALING state.
        """
        now = time.time()

        # Check cooldown
        if now - self._last_potion_time < self.cooldown:
            logger.debug(f"Potion on cooldown — {self.cooldown - (now - self._last_potion_time):.1f}s remaining")
            return

        # Check if HP is below threshold
        if self.state.hp_percent < self.hp_threshold:
            logger.info(f"HP {self.state.hp_percent:.0f}% < {self.hp_threshold}% — using potion ({self.potion_key})")
            self.input.press_key(self.potion_key)
            self._last_potion_time = now
            self._potions_used += 1
            self.state.record_potion()
            self.input.delay(0.1, 0.3)

    def should_heal(self) -> bool:
        """Check if healing is needed."""
        return self.state.hp_percent < self.hp_threshold

    def is_healed(self) -> bool:
        """Check if HP has recovered enough to stop healing."""
        return self.state.hp_percent >= self.hp_recovery_target

    def get_status(self) -> dict:
        """Get potion status for logging/overlay."""
        now = time.time()
        cd_remaining = max(0, self.cooldown - (now - self._last_potion_time))
        return {
            "potions_used": self._potions_used,
            "hp": self.state.hp_percent,
            "on_cooldown": cd_remaining > 0,
            "cooldown_remaining": round(cd_remaining, 1),
        }
