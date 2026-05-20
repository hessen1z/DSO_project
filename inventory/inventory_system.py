"""
Inventory System
================
Detects when inventory is full and handles selling items to NPCs.
"""

import time
from state.game_state import GameState
from input.humanizer import Humanizer
from utils.logger import get_logger

logger = get_logger("inventory")


class InventorySystem:
    """
    Inventory management system.

    When inventory is detected as full:
    1. Navigate to the nearest NPC (using waypoint)
    2. Open the shop
    3. Sell all junk items
    4. Return to farming route
    """

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict,
                 waypoint_system=None):
        """
        Initialize the inventory system.

        Args:
            game_state: Reference to the central GameState
            humanizer: Reference to the Humanizer for input
            config: Inventory configuration dict
            waypoint_system: Reference to the navigation system
        """
        self.state = game_state
        self.input = humanizer
        self.waypoints = waypoint_system

        # Config
        self.sell_key = config.get("sell_key", "s")
        self.npc_waypoint_index = config.get("npc_waypoint_index", 0)
        self.sell_delay = config.get("sell_delay", 1.0)

        # State
        self._selling = False
        self._sell_start_time = 0
        self._total_sells = 0
        self._sell_step = 0  # 0=navigate, 1=interact, 2=sell, 3=close, 4=return

        logger.info(f"InventorySystem initialized | Sell key: {self.sell_key} | "
                    f"NPC waypoint: {self.npc_waypoint_index}")

    def execute(self):
        """
        Execute one sell tick.
        Called by the decision engine when in SELLING state.
        """
        if not self._selling:
            self._start_selling()

        # Execute current step
        steps = [
            self._step_navigate_to_npc,
            self._step_interact_npc,
            self._step_sell_items,
            self._step_close_shop,
            self._step_return_to_farm,
        ]

        if self._sell_step < len(steps):
            steps[self._sell_step]()
        else:
            self._finish_selling()

    def _start_selling(self):
        """Start the selling process."""
        self._selling = True
        self._sell_start_time = time.time()
        self._sell_step = 0
        self._total_sells += 1
        logger.info(f"Starting sell sequence #{self._total_sells}")

    def _step_navigate_to_npc(self):
        """Step 0: Navigate to NPC waypoint."""
        logger.info("Sell step 0: Navigating to NPC")
        if self.waypoints:
            self.waypoints.go_to_waypoint(self.npc_waypoint_index)
            self.waypoints.execute()
        self.input.delay(1.0, 2.0)
        self._sell_step = 1

    def _step_interact_npc(self):
        """Step 1: Interact with NPC."""
        logger.info("Sell step 1: Interacting with NPC")
        # Click on NPC (usually detected by YOLO, or near waypoint position)
        npcs = self.state._npcs
        if npcs:
            npc = npcs[0]
            self.input.click(npc.center_x, npc.center_y)
        else:
            # Click center of screen as fallback
            self.input.click(self.state._screen_center_x, self.state._screen_center_y)

        self.input.delay(0.5, 1.0)
        self._sell_step = 2

    def _step_sell_items(self):
        """Step 2: Sell items."""
        logger.info("Sell step 2: Selling items")

        # Press sell key (game-specific)
        self.input.press_key(self.sell_key)
        self.input.delay(self.sell_delay, self.sell_delay + 0.5)

        # Press Enter to confirm (if needed)
        self.input.press_key("enter")
        self.input.delay(0.3, 0.5)

        self._sell_step = 3

    def _step_close_shop(self):
        """Step 3: Close the shop window."""
        logger.info("Sell step 3: Closing shop")
        self.input.press_key("escape")
        self.input.delay(0.5, 1.0)
        self._sell_step = 4

    def _step_return_to_farm(self):
        """Step 4: Return to farming route."""
        logger.info("Sell step 4: Returning to farm")
        if self.waypoints:
            self.waypoints.go_to_first()
        self._sell_step = 5  # Will trigger finish

    def _finish_selling(self):
        """Finish the selling process."""
        self._selling = False
        self._sell_step = 0
        logger.info("Sell sequence complete — returning to farming")
        self.state.bot_state = GameState.STATE_IDLE

    def get_status(self) -> dict:
        """Get inventory status."""
        return {
            "selling": self._selling,
            "sell_step": self._sell_step,
            "total_sells": self._total_sells,
            "inventory_full": self.state.inventory_full,
        }
