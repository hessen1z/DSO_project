"""
Decision Engine
===============
FSM-based decision system — the "brain" that chooses what to do.
Uses priority-based state transitions to handle all game situations.

State Machine:
    IDLE → MOVING → COMBAT → LOOTING → HEALING → DEAD → SELLING → STUCK

Priority: DEAD > HEALING > COMBAT > LOOTING > SELLING > MOVING > IDLE
"""

import time
from state.game_state import GameState
from utils.logger import get_logger

logger = get_logger("decision")


class DecisionEngine:
    """
    Finite State Machine decision engine.

    Evaluates game state and decides which action to take.
    Actions are delegated to the appropriate subsystems.
    """

    def __init__(self, game_state: GameState, config: dict):
        """
        Initialize the decision engine.

        Args:
            game_state: Reference to the central GameState
            config: Full bot configuration dict
        """
        self.state = game_state
        self.config = config

        # Action handlers — set by main.py after all systems initialize
        self.on_combat = None       # combat_system.execute
        self.on_navigate = None     # waypoint_system.execute
        self.on_loot = None         # loot_system.execute
        self.on_heal = None         # potion_system.execute
        self.on_death = None        # death_recovery.execute
        self.on_sell = None         # inventory_system.execute
        self.on_stuck = None        # anti_stuck.execute

        # Thresholds from config
        potion_cfg = config.get("potion", {})
        self.hp_heal_threshold = potion_cfg.get("hp_threshold", 40)
        self.hp_recovery_target = potion_cfg.get("hp_recovery_target", 70)

        # Timing
        self._last_decision_time = 0
        self._decision_count = 0

        logger.info(f"DecisionEngine initialized | HP Threshold: {self.hp_heal_threshold}%")

    def evaluate(self) -> str:
        """
        Evaluate the current game state and decide what to do.

        Returns:
            The action/state that was chosen
        """
        self._decision_count += 1
        current_state = self.state.bot_state

        # ==========================================
        # PRIORITY 1: Death (highest priority)
        # ==========================================
        if self.state.is_dead:
            self.state.bot_state = GameState.STATE_DEAD
            self._execute_action("death")
            return GameState.STATE_DEAD

        # ==========================================
        # PRIORITY 2: Healing (critical HP)
        # ==========================================
        if self.state.hp_percent < self.hp_heal_threshold:
            self.state.bot_state = GameState.STATE_HEALING
            self._execute_action("heal")
            return GameState.STATE_HEALING

        # ==========================================
        # PRIORITY 3: Combat (enemies detected)
        # ==========================================
        if self.state.has_enemies:
            self.state.bot_state = GameState.STATE_COMBAT
            self._execute_action("combat")
            return GameState.STATE_COMBAT

        # ==========================================
        # PRIORITY 4: Looting (loot detected, no enemies)
        # ==========================================
        if self.state.has_loot:
            self.state.bot_state = GameState.STATE_LOOTING
            self._execute_action("loot")
            return GameState.STATE_LOOTING

        # ==========================================
        # PRIORITY 5: Sell (inventory full)
        # ==========================================
        if self.state.inventory_full:
            self.state.bot_state = GameState.STATE_SELLING
            self._execute_action("sell")
            return GameState.STATE_SELLING

        # ==========================================
        # PRIORITY 6: Anti-stuck check
        # ==========================================
        anti_stuck_cfg = self.config.get("anti_stuck", {})
        stuck_threshold = anti_stuck_cfg.get("stuck_threshold", 3.0)
        if self.state.is_stuck(stuck_threshold):
            self.state.bot_state = GameState.STATE_STUCK
            self._execute_action("stuck")
            return GameState.STATE_STUCK

        # ==========================================
        # PRIORITY 7: Navigate (nothing else to do)
        # ==========================================
        self.state.bot_state = GameState.STATE_MOVING
        self._execute_action("navigate")
        return GameState.STATE_MOVING

    def _execute_action(self, action_name: str):
        """
        Execute the appropriate action handler.

        Args:
            action_name: Name of the action to execute
        """
        handlers = {
            "combat": self.on_combat,
            "navigate": self.on_navigate,
            "loot": self.on_loot,
            "heal": self.on_heal,
            "death": self.on_death,
            "sell": self.on_sell,
            "stuck": self.on_stuck,
        }

        handler = handlers.get(action_name)
        if handler:
            try:
                handler()
            except Exception as e:
                logger.error(f"Action '{action_name}' error: {e}")
        else:
            logger.debug(f"No handler registered for action: {action_name}")

    def get_status(self) -> dict:
        """Get decision engine status for logging/overlay."""
        return {
            "decision_count": self._decision_count,
            "current_state": self.state.bot_state,
            "has_enemies": self.state.has_enemies,
            "has_loot": self.state.has_loot,
            "hp": self.state.hp_percent,
            "is_dead": self.state.is_dead,
        }
