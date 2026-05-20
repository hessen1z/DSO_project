"""
Game State System
=================
Central game state aggregator — the "brain" of the bot.
Collects all detection results and maintains a unified state
that the decision engine uses to make choices.
"""

import time
import threading
import math
from collections import deque
from utils.logger import get_logger

logger = get_logger("state")


class GameState:
    """
    Thread-safe central game state that aggregates all detection data.

    This is the single source of truth for the bot's understanding
    of what's happening in the game.
    """

    # Bot FSM states
    STATE_IDLE = "IDLE"
    STATE_MOVING = "MOVING"
    STATE_COMBAT = "COMBAT"
    STATE_LOOTING = "LOOTING"
    STATE_HEALING = "HEALING"
    STATE_DEAD = "DEAD"
    STATE_SELLING = "SELLING"
    STATE_STUCK = "STUCK"
    STATE_PAUSED = "PAUSED"

    def __init__(self):
        """Initialize the game state."""
        self._lock = threading.RLock()

        # === Detection Data ===
        self._enemies = []
        self._elites = []
        self._bosses = []
        self._loot_items = []
        self._portals = []
        self._npcs = []

        # === Derived State ===
        self._nearest_enemy = None
        self._nearest_loot = None
        self._current_target = None
        self._target_lock_time = 0

        # === Health ===
        self._hp_percent = 100.0
        self._hp_bar_detected = False

        # === Status Flags ===
        self._is_dead = False
        self._inventory_full = False

        # === Bot State ===
        self._bot_state = self.STATE_IDLE
        self._previous_state = self.STATE_IDLE
        self._state_start_time = time.time()

        # === Position Tracking (for anti-stuck) ===
        self._position_history = deque(maxlen=50)
        self._last_position_time = time.time()

        # === Statistics ===
        self._enemies_killed = 0
        self._loot_picked = 0
        self._potions_used = 0
        self._deaths = 0
        self._session_start = time.time()

        # === Screen Info ===
        self._screen_center_x = 960
        self._screen_center_y = 540

        logger.info("GameState initialized")

    # =========================================================
    # Properties with thread-safe access
    # =========================================================

    @property
    def bot_state(self) -> str:
        with self._lock:
            return self._bot_state

    @bot_state.setter
    def bot_state(self, new_state: str):
        with self._lock:
            if new_state != self._bot_state:
                self._previous_state = self._bot_state
                self._bot_state = new_state
                self._state_start_time = time.time()
                logger.info(f"State: {self._previous_state} → {new_state}")

    @property
    def previous_state(self) -> str:
        with self._lock:
            return self._previous_state

    @property
    def state_duration(self) -> float:
        """How long we've been in the current state (seconds)."""
        with self._lock:
            return time.time() - self._state_start_time

    @property
    def enemies(self) -> list:
        with self._lock:
            return self._enemies.copy()

    @property
    def nearest_enemy(self):
        with self._lock:
            return self._nearest_enemy

    @property
    def current_target(self):
        with self._lock:
            return self._current_target

    @current_target.setter
    def current_target(self, target):
        with self._lock:
            self._current_target = target
            if target:
                self._target_lock_time = time.time()

    @property
    def loot_items(self) -> list:
        with self._lock:
            return self._loot_items.copy()

    @property
    def nearest_loot(self):
        with self._lock:
            return self._nearest_loot

    @property
    def hp_percent(self) -> float:
        with self._lock:
            return self._hp_percent

    @property
    def is_dead(self) -> bool:
        with self._lock:
            return self._is_dead

    @property
    def inventory_full(self) -> bool:
        with self._lock:
            return self._inventory_full

    @property
    def has_enemies(self) -> bool:
        with self._lock:
            return len(self._enemies) > 0 or len(self._elites) > 0 or len(self._bosses) > 0

    @property
    def has_loot(self) -> bool:
        with self._lock:
            return len(self._loot_items) > 0

    @property
    def all_targets(self) -> list:
        """Get all combat targets (enemies + elites + bosses)."""
        with self._lock:
            return self._bosses.copy() + self._elites.copy() + self._enemies.copy()

    @property
    def stats(self) -> dict:
        """Get session statistics."""
        with self._lock:
            elapsed = time.time() - self._session_start
            return {
                "enemies_killed": self._enemies_killed,
                "loot_picked": self._loot_picked,
                "potions_used": self._potions_used,
                "deaths": self._deaths,
                "session_time": elapsed,
                "session_time_str": time.strftime("%H:%M:%S", time.gmtime(elapsed))
            }

    # =========================================================
    # Update Methods
    # =========================================================

    def update_from_detections(self, detections: list):
        """
        Update game state from YOLO detection results.

        Args:
            detections: List of Detection objects from YOLODetector
        """
        with self._lock:
            # Clear previous detections
            self._enemies = []
            self._elites = []
            self._bosses = []
            self._loot_items = []
            self._portals = []
            self._npcs = []
            self._is_dead = False
            self._inventory_full = False
            self._hp_bar_detected = False

            # Categorize detections
            for det in detections:
                cls = det.class_name.lower()

                if cls == "enemy":
                    self._enemies.append(det)
                elif cls == "elite":
                    self._elites.append(det)
                elif cls == "boss":
                    self._bosses.append(det)
                elif cls == "loot":
                    self._loot_items.append(det)
                elif cls == "portal":
                    self._portals.append(det)
                elif cls == "npc":
                    self._npcs.append(det)
                elif cls == "dead_screen":
                    self._is_dead = True
                elif cls == "hp_bar":
                    self._hp_bar_detected = True
                    # Estimate HP from bar width ratio (can be refined)
                    self._estimate_hp(det)
                elif cls == "inventory_full":
                    self._inventory_full = True

            # Find nearest enemy (to screen center)
            all_enemies = self._bosses + self._elites + self._enemies
            if all_enemies:
                self._nearest_enemy = min(
                    all_enemies,
                    key=lambda d: d.distance_to(self._screen_center_x, self._screen_center_y)
                )
            else:
                self._nearest_enemy = None

            # Find nearest loot
            if self._loot_items:
                self._nearest_loot = min(
                    self._loot_items,
                    key=lambda d: d.distance_to(self._screen_center_x, self._screen_center_y)
                )
            else:
                self._nearest_loot = None

            # Validate current target still exists
            if self._current_target:
                target_still_exists = any(
                    d.distance_to(self._current_target.center_x, self._current_target.center_y) < 50
                    for d in all_enemies
                )
                if not target_still_exists:
                    self._current_target = None

            # Track position (using screen center for now — could use character detection)
            now = time.time()
            if now - self._last_position_time >= 0.5:
                self._position_history.append({
                    "time": now,
                    "enemies": len(all_enemies),
                    "state": self._bot_state
                })
                self._last_position_time = now

    def _estimate_hp(self, hp_bar_detection):
        """
        Estimate HP percentage from HP bar detection.
        This is a rough estimate based on the detected HP bar width.

        Args:
            hp_bar_detection: Detection object for HP bar
        """
        # HP estimation can be refined based on game-specific HP bar characteristics
        # For now, we use the width ratio as a basic estimate
        # A full HP bar should have a known width, and the detected width ratio gives HP%
        # This needs calibration for the specific game
        pass  # HP stays at default until calibrated

    def set_hp(self, percent: float):
        """Manually set HP percentage (for testing or alternative detection)."""
        with self._lock:
            self._hp_percent = max(0, min(100, percent))

    def set_screen_size(self, width: int, height: int):
        """Set screen dimensions for center calculations."""
        with self._lock:
            self._screen_center_x = width // 2
            self._screen_center_y = height // 2

    # =========================================================
    # Statistics Updates
    # =========================================================

    def record_kill(self):
        with self._lock:
            self._enemies_killed += 1

    def record_loot(self):
        with self._lock:
            self._loot_picked += 1

    def record_potion(self):
        with self._lock:
            self._potions_used += 1

    def record_death(self):
        with self._lock:
            self._deaths += 1

    # =========================================================
    # Anti-Stuck Helpers
    # =========================================================

    def is_stuck(self, threshold_seconds: float = 3.0) -> bool:
        """
        Check if the bot might be stuck.
        Stuck = in COMBAT or MOVING state for too long without progress.

        Args:
            threshold_seconds: Time threshold to consider stuck

        Returns:
            True if potentially stuck
        """
        with self._lock:
            if self._bot_state in (self.STATE_PAUSED, self.STATE_DEAD, self.STATE_IDLE):
                return False

            # If in same state for too long
            if self.state_duration > threshold_seconds * 3:
                return True

            return False

    def get_state_summary(self) -> dict:
        """Get a summary of the current game state for logging/overlay."""
        with self._lock:
            return {
                "bot_state": self._bot_state,
                "enemies": len(self._enemies),
                "elites": len(self._elites),
                "bosses": len(self._bosses),
                "loot": len(self._loot_items),
                "hp": self._hp_percent,
                "is_dead": self._is_dead,
                "inventory_full": self._inventory_full,
                "has_target": self._current_target is not None,
                "state_duration": round(self.state_duration, 1),
                **self.stats
            }

    def reset(self):
        """Reset all state (for restart)."""
        with self._lock:
            self._enemies.clear()
            self._elites.clear()
            self._bosses.clear()
            self._loot_items.clear()
            self._portals.clear()
            self._npcs.clear()
            self._nearest_enemy = None
            self._nearest_loot = None
            self._current_target = None
            self._hp_percent = 100.0
            self._is_dead = False
            self._inventory_full = False
            self._bot_state = self.STATE_IDLE
            self._position_history.clear()
            logger.info("GameState reset")
