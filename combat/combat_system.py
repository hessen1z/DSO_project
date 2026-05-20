"""
Combat System
=============
Handles target selection, attack rotation, and skill usage.
Uses the humanizer for all input to look natural.
"""

import time
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("combat")


class CombatSystem:
    """
    Combat system that handles targeting and attacking enemies.

    Features:
    - Target selection with priority (boss > elite > enemy)
    - Skill rotation with cooldown tracking
    - Auto-attack between skills
    - Target switching when current target dies
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict):
        """
        Initialize the combat system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Combat configuration dict
        """
        self.state = game_state
        self.input = humanizer

        # Config
        self.skills = config.get("skills", ["1", "2", "3"])
        self.skill_cooldowns = config.get("skill_cooldowns", [2.0, 5.0, 8.0])
        self.basic_attack_key = config.get("basic_attack_key", "1")
        self.target_priority = config.get("target_priority", ["boss", "elite", "enemy"])
        self.attack_range = config.get("attack_range", 150)
        self.target_click_offset = config.get("target_click_offset", 3)

        # Cooldown tracking
        self._skill_last_used = {}
        for skill in self.skills:
            self._skill_last_used[skill] = 0

        # Combat state
        self._current_skill_index = 0
        self._last_attack_time = 0
        self._attack_count = 0

        logger.info(f"CombatSystem initialized | Skills: {self.skills} | "
                    f"Cooldowns: {self.skill_cooldowns}")

    def execute(self):
        """
        Execute one combat tick.
        Called by the decision engine when in COMBAT state.
        """
        # Step 1: Ensure we have a target
        target = self._select_target()
        if target is None:
            logger.debug("No target available")
            return

        # Step 2: Click on target to select it
        self._target_enemy(target)

        # Step 3: Use next available skill
        self._use_skill()

        self._attack_count += 1

    def _select_target(self):
        """
        Select the best target based on priority.
        Prioritizes: boss > elite > enemy, then nearest.

        Returns:
            Detection object of the selected target, or None
        """
        current_target = self.state.current_target

        # Keep current target if still valid
        if current_target is not None:
            return current_target

        # Find new target by priority
        all_targets = self.state.all_targets  # Already sorted: boss, elite, enemy
        if not all_targets:
            return None

        # Pick the nearest target (all_targets is pre-sorted by priority)
        # Within each priority tier, pick the nearest
        best_target = None
        best_distance = float('inf')

        for target in all_targets:
            dist = target.distance_to(
                self.state._screen_center_x,
                self.state._screen_center_y
            )
            # Priority weighting: bosses and elites get distance bonus
            if target.class_name == "boss":
                dist *= 0.3  # Heavily prioritize bosses
            elif target.class_name == "elite":
                dist *= 0.6  # Prioritize elites

            if dist < best_distance:
                best_distance = dist
                best_target = target

        if best_target:
            self.state.current_target = best_target
            logger.debug(f"Target selected: {best_target.class_name} at "
                         f"({best_target.center_x}, {best_target.center_y})")

        return best_target

    def _target_enemy(self, target):
        """
        Click on the enemy to target it.

        Args:
            target: Detection object with center coordinates
        """
        # Click on enemy position
        self.input.click(target.center_x, target.center_y)
        self.input.delay(0.05, 0.15)

    def _use_skill(self):
        """Use the next available skill in rotation."""
        now = time.time()

        # Try each skill in rotation
        for i in range(len(self.skills)):
            skill_index = (self._current_skill_index + i) % len(self.skills)
            skill_key = self.skills[skill_index]

            # Check cooldown
            cooldown = self.skill_cooldowns[skill_index] if skill_index < len(self.skill_cooldowns) else 1.0
            last_used = self._skill_last_used.get(skill_key, 0)

            if now - last_used >= cooldown:
                # Skill is ready — use it
                self.input.press_key(skill_key)
                self._skill_last_used[skill_key] = now
                self._current_skill_index = (skill_index + 1) % len(self.skills)
                logger.debug(f"Used skill: {skill_key}")
                return

        # All skills on cooldown — use basic attack
        self.input.press_key(self.basic_attack_key)
        self._last_attack_time = now
        logger.debug("Basic attack")

    def reset(self):
        """Reset combat state."""
        self._current_skill_index = 0
        self._attack_count = 0
        self.state.current_target = None
        for skill in self.skills:
            self._skill_last_used[skill] = 0
        logger.debug("Combat state reset")

    def get_status(self) -> dict:
        """Get combat status for logging/overlay."""
        target = self.state.current_target
        return {
            "attack_count": self._attack_count,
            "current_skill_index": self._current_skill_index,
            "has_target": target is not None,
            "target_class": target.class_name if target else "none",
        }
