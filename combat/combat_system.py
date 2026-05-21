"""
Combat System
=============
Handles target selection, attack rotation, and skill usage.

Features:
- Combo Engine: Sequential skill chains (stun → debuff → burst → finisher)
- Escape Logic: Danger-score-based retreat when HP critical or surrounded
- Tactical kiting: Clicks away from enemies to create distance before re-engaging
- Priority targeting: boss > elite > enemy with weighted distance scoring
"""

import time
import math
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("combat")


class CombatSystem:
    """
    Advanced combat system with combo chaining and smart escape logic.

    Danger Score Formula:
        score = (low_hp_weight if hp_critical)
              + (nearby_enemy_weight * nearby_count)
              + (boss_danger_weight if boss_detected)
              + (potion_cooldown_weight if potion_unavailable)

    When danger_score >= threshold → RETREAT mode is activated.
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict):
        self.state = game_state
        self.input = humanizer

        # --- Basic combat config ---
        self.skills = config.get("skills", ["1", "2", "3"])
        self.skill_cooldowns = config.get("skill_cooldowns", [2.0, 5.0, 8.0])
        self.basic_attack_key = config.get("basic_attack_key", "1")
        self.target_priority = config.get("target_priority", ["boss", "elite", "enemy"])
        self.attack_range = config.get("attack_range", 150)
        self.target_click_offset = config.get("target_click_offset", 3)

        # --- Combo Engine ---
        self.combo_enabled = config.get("combo_enabled", True)
        self.combo_sequence = config.get("combo_sequence", self.skills)
        self.combo_cooldowns = config.get("combo_cooldowns", self.skill_cooldowns)
        self._combo_step = 0               # Current step in the combo sequence
        self._combo_last_used = {}
        for key in self.combo_sequence:
            self._combo_last_used[key] = 0

        # --- Escape Logic ---
        escape_cfg = config.get("escape_logic", {})
        self.escape_enabled = escape_cfg.get("enabled", True)
        self.hp_escape_threshold = escape_cfg.get("hp_escape_threshold", 25)
        self.danger_score_threshold = escape_cfg.get("danger_score_threshold", 70)
        self.escape_skill = escape_cfg.get("escape_skill", None)
        self.escape_skill_cooldown = escape_cfg.get("escape_skill_cooldown", 12.0)
        self.retreat_distance = escape_cfg.get("retreat_distance", 300)
        self.surrounded_enemy_count = escape_cfg.get("surrounded_enemy_count", 3)
        self.boss_danger_weight = escape_cfg.get("boss_danger_weight", 40)
        self.nearby_enemy_weight = escape_cfg.get("nearby_enemy_weight", 15)
        self.low_hp_weight = escape_cfg.get("low_hp_weight", 30)
        self.potion_cooldown_weight = escape_cfg.get("potion_cooldown_weight", 10)

        # --- Escape state ---
        self._escape_last_used = 0
        self._retreating = False
        self._retreat_start_time = 0
        self._retreat_duration = 1.5  # Seconds to keep retreating

        # --- Cooldown tracking (basic rotation fallback) ---
        self._skill_last_used = {}
        for skill in self.skills:
            self._skill_last_used[skill] = 0

        # --- Combat counters ---
        self._current_skill_index = 0
        self._last_attack_time = 0
        self._attack_count = 0

        logger.info(
            f"CombatSystem initialized | Combo: {self.combo_sequence} | "
            f"Escape threshold: {self.hp_escape_threshold}% HP / "
            f"danger≥{self.danger_score_threshold}"
        )

    # =========================================================
    # Main Execute
    # =========================================================

    def execute(self):
        """
        Execute one combat tick.
        Called by the decision engine when in COMBAT state.
        """
        # Step 1: Calculate current danger level
        danger = self._calculate_danger_score()
        logger.debug(f"Danger score: {danger:.0f}")

        # Step 2: Check if we should retreat instead of fight
        if self.escape_enabled and danger >= self.danger_score_threshold:
            self._execute_retreat()
            return

        # Step 3: We're safe enough — select and attack a target
        self._retreating = False
        target = self._select_target()
        if target is None:
            logger.debug("No target available")
            return

        # Step 4: Click on target to select it
        self._target_enemy(target)

        # Step 5: Use next combo step or skill rotation
        if self.combo_enabled:
            self._use_combo_skill()
        else:
            self._use_skill()

        self._attack_count += 1

    # =========================================================
    # Danger Score
    # =========================================================

    def _calculate_danger_score(self) -> float:
        """
        Calculate a composite danger score from multiple threat factors.

        Returns:
            float: 0–100+ score. Higher = more dangerous.
        """
        score = 0.0

        # Factor 1: Low HP
        hp = self.state.hp_percent
        if hp < self.hp_escape_threshold:
            score += self.low_hp_weight * (1.0 - hp / self.hp_escape_threshold)

        # Factor 2: Surrounded by many enemies
        all_targets = self.state.all_targets
        nearby_count = len(all_targets)
        if nearby_count >= self.surrounded_enemy_count:
            score += self.nearby_enemy_weight * (nearby_count - self.surrounded_enemy_count + 1)

        # Factor 3: Boss in range
        has_boss = any(t.class_name == "boss" for t in all_targets)
        if has_boss:
            score += self.boss_danger_weight

        # Factor 4: Escape skill cooldown (potion availability approximation)
        now = time.time()
        if self.escape_skill and now - self._escape_last_used < self.escape_skill_cooldown:
            score += self.potion_cooldown_weight

        return min(score, 100.0)

    # =========================================================
    # Retreat / Escape
    # =========================================================

    def _execute_retreat(self):
        """
        Activate retreat mode:
        1. Fire escape/mobility skill if available.
        2. Click in the direction OPPOSITE to the nearest enemy.
        """
        now = time.time()

        # Use escape skill if off cooldown
        if self.escape_skill:
            if now - self._escape_last_used >= self.escape_skill_cooldown:
                logger.info(f"🏃 RETREAT — Using escape skill: {self.escape_skill}")
                self.input.press_key(self.escape_skill)
                self._escape_last_used = now
                self.input.delay(0.05, 0.1)

        # Click in the opposite direction from the nearest enemy
        nearest = self.state.nearest_enemy
        if nearest:
            cx = self.state._screen_center_x
            cy = self.state._screen_center_y

            # Vector from screen center to enemy
            ex, ey = nearest.center_x, nearest.center_y
            dx = cx - ex
            dy = cy - ey
            dist = math.sqrt(dx * dx + dy * dy) or 1.0

            # Normalize and scale to retreat_distance
            nx = int(cx + (dx / dist) * self.retreat_distance)
            ny = int(cy + (dy / dist) * self.retreat_distance)

            # Clamp to screen bounds (assume 1920×1080)
            nx = max(50, min(1870, nx))
            ny = max(50, min(1030, ny))

            logger.info(f"🏃 Retreating to ({nx}, {ny}) away from {nearest.class_name}")
            self.input.right_click(nx, ny)
            self.input.delay(0.1, 0.2)

        self._retreating = True

    # =========================================================
    # Targeting
    # =========================================================

    def _select_target(self):
        """
        Select best target by priority: boss > elite > enemy (nearest within tier).

        Returns:
            Detection object, or None
        """
        # Keep locking current target if it still exists
        if self.state.current_target is not None:
            return self.state.current_target

        all_targets = self.state.all_targets
        if not all_targets:
            return None

        cx = self.state._screen_center_x
        cy = self.state._screen_center_y

        best_target = None
        best_score = float("inf")

        for target in all_targets:
            dist = target.distance_to(cx, cy)

            # Priority weight (lower = higher priority)
            if target.class_name == "boss":
                dist *= 0.3
            elif target.class_name == "elite":
                dist *= 0.6

            if dist < best_score:
                best_score = dist
                best_target = target

        if best_target:
            self.state.current_target = best_target
            logger.debug(
                f"Target selected: {best_target.class_name} at "
                f"({best_target.center_x}, {best_target.center_y})"
            )

        return best_target

    def _target_enemy(self, target):
        """Click on the enemy to lock on it."""
        self.input.click(target.center_x, target.center_y)
        self.input.delay(0.05, 0.12)

    # =========================================================
    # Combo Engine
    # =========================================================

    def _use_combo_skill(self):
        """
        Execute the next step in the configured combo sequence.
        Waits for the skill's cooldown before advancing.

        Combo example: ["2", "3", "1", "1", "1"]
        Bot presses them in order, respecting each key's cooldown.
        """
        now = time.time()

        # Find the next ready step in the combo
        for i in range(len(self.combo_sequence)):
            step_idx = (self._combo_step + i) % len(self.combo_sequence)
            skill_key = self.combo_sequence[step_idx]

            cooldown = (
                self.combo_cooldowns[step_idx]
                if step_idx < len(self.combo_cooldowns)
                else 1.0
            )
            last_used = self._combo_last_used.get(skill_key, 0)

            if now - last_used >= cooldown:
                self.input.press_key(skill_key)
                self._combo_last_used[skill_key] = now
                self._combo_step = (step_idx + 1) % len(self.combo_sequence)
                logger.debug(f"Combo step {step_idx}: skill [{skill_key}]")
                return

        # All combo skills on cooldown — basic auto attack
        self.input.press_key(self.basic_attack_key)
        logger.debug("All combo skills on cooldown — basic auto attack")

    def _use_skill(self):
        """Fallback: use next available skill in the simple rotation."""
        now = time.time()

        for i in range(len(self.skills)):
            skill_index = (self._current_skill_index + i) % len(self.skills)
            skill_key = self.skills[skill_index]

            cooldown = (
                self.skill_cooldowns[skill_index]
                if skill_index < len(self.skill_cooldowns)
                else 1.0
            )
            last_used = self._skill_last_used.get(skill_key, 0)

            if now - last_used >= cooldown:
                self.input.press_key(skill_key)
                self._skill_last_used[skill_key] = now
                self._current_skill_index = (skill_index + 1) % len(self.skills)
                logger.debug(f"Used skill: {skill_key}")
                return

        # Fallback: basic attack
        self.input.press_key(self.basic_attack_key)
        self._last_attack_time = now
        logger.debug("Basic attack (all skills on cooldown)")

    # =========================================================
    # State / Status
    # =========================================================

    def reset(self):
        """Reset combat state (called on bot stop/restart)."""
        self._current_skill_index = 0
        self._combo_step = 0
        self._attack_count = 0
        self._retreating = False
        self.state.current_target = None
        for skill in self.skills:
            self._skill_last_used[skill] = 0
        for key in self.combo_sequence:
            self._combo_last_used[key] = 0
        logger.debug("Combat state reset")

    def get_status(self) -> dict:
        """Get combat status for logging/overlay."""
        target = self.state.current_target
        return {
            "attack_count": self._attack_count,
            "combo_step": self._combo_step,
            "combo_skill": self.combo_sequence[self._combo_step] if self.combo_sequence else "?",
            "retreating": self._retreating,
            "danger_score": round(self._calculate_danger_score(), 1),
            "has_target": target is not None,
            "target_class": target.class_name if target else "none",
        }
