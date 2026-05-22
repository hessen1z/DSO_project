import os
import sys
import time
import math
import json
import threading

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state.game_state import GameState

# Mock classes for testing without the actual game running
class MockHumanizer:
    def __init__(self, cfg):
        pass

class MockActionLock:
    def __init__(self, enabled=True, timeout=3.0):
        pass
    def acquire(self, name):
        class LockContext:
            def __enter__(self):
                return True
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
        return LockContext()

class MockNavigation:
    def __init__(self, state):
        self.state = state
        self.waypoints = []
        self._current_waypoint_index = 0
        self.active_map_name = "q5"
        self._player_minimap_pos = (960, 540)
        self.minimap_enabled = True
        self._recording = False
        
    @property
    def current_index(self):
        return self._current_waypoint_index
        
    @property
    def player_minimap_pos(self):
        return self._player_minimap_pos

    def _save_waypoints(self):
        # Save to maps folder
        os.makedirs(os.path.join("config", "maps"), exist_ok=True)
        path = os.path.join("config", "maps", f"{self.active_map_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.waypoints, f, indent=4)

class MockCombat:
    def __init__(self):
        self.combo_enabled = True
        self.combo_sequence = ["2", "3", "1", "1", "1"]
        self.combo_cooldowns = [0.0, 5.0, 8.0, 2.0, 2.0]
        self.active_class = "mage"
        self._combo_step = 0
        
    def get_status(self):
        return {
            "active_class": self.active_class,
            "danger_score": 15,
            "combo_step": self._combo_step,
            "combo_skill": self.combo_sequence[self._combo_step] if self.combo_sequence else "?"
        }

class MockDetector:
    def __init__(self, cfg):
        self.detections = []
        self.fps = 12.5

class MockBot:
    def __init__(self):
        self._bot_active = True
        self.game_state = GameState()
        self.game_state.set_hp(92)
        self.game_state.bot_state = "MOVING"
        self.navigation = MockNavigation(self.game_state)
        self.combat = MockCombat()
        self.detector = MockDetector({})
        
    def toggle_bot(self):
        self._bot_active = not self._bot_active

def simulate_player_walk(bot):
    """Simulates player dot walking along active waypoints on the map."""
    while True:
        if bot._bot_active and bot.navigation.waypoints:
            wp_len = len(bot.navigation.waypoints)
            idx = bot.navigation._current_waypoint_index
            target_wp = bot.navigation.waypoints[idx]
            
            tx = target_wp.get("mx", 960)
            ty = target_wp.get("my", 540)
            
            px, py = bot.navigation._player_minimap_pos
            dx = tx - px
            dy = ty - py
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < 15:
                # Arrived, advance
                bot.navigation._current_waypoint_index = (idx + 1) % wp_len
            else:
                # Step closer
                step = 6
                bot.navigation._player_minimap_pos = (
                    px + (dx / dist) * step,
                    py + (dy / dist) * step
                )
        time.sleep(0.1)

if __name__ == "__main__":
    print("[INFO] Creating mock bot instance...")
    bot = MockBot()
    
    # Try loading existing waypoints
    try:
        q5_json = os.path.join("config", "maps", "q5.json")
        if os.path.exists(q5_json):
            with open(q5_json, "r") as f:
                bot.navigation.waypoints = json.load(f)
                print(f"[INFO] Loaded {len(bot.navigation.waypoints)} waypoints for test.")
    except Exception as e:
        print(f"[WARNING] Could not load waypoints: {e}")
        
    # Start walk simulation thread
    threading.Thread(target=simulate_player_walk, args=(bot,), daemon=True).start()
    
    # Start main GUI
    from ui.main_gui import MainGUI
    print("[INFO] Starting Main GUI dashboard (Authenticating test)...")
    gui = MainGUI(bot, username="DevTester", license_key="TEST-KEY-1337-OK", authenticated=True)
    
    # Switch to waypoint page automatically to show the new interactive view
    gui.root.after(300, lambda: gui.show_page("waypoints"))
    
    gui.root.mainloop()
