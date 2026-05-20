"""
╔══════════════════════════════════════════════════════════════════╗
║              DRAKENSANG AI VISION BOT v1.0                      ║
║              ═══════════════════════════                         ║
║  AI-powered MMO bot using computer vision (YOLOv8)              ║
║  Captures screen → Detects game elements → Makes decisions      ║
║  → Executes actions with human-like input                       ║
║                                                                  ║
║  Hotkeys:                                                        ║
║    F9  = Start/Stop bot                                          ║
║    F10 = Record waypoint (mouse position)                        ║
║    F11 = Capture screenshot for training dataset                 ║
║    F12 = Toggle overlay                                          ║
║    F8  = Emergency stop (exit)                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import threading
from datetime import datetime

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger, get_logger
from capture.screen_capture import ScreenCapture
from detection.yolo_detector import YOLODetector
from state.game_state import GameState
from decision.decision_engine import DecisionEngine
from combat.combat_system import CombatSystem
from navigation.waypoint_system import WaypointSystem
from loot.loot_system import LootSystem
from recovery.potion_system import PotionSystem
from recovery.death_recovery import DeathRecovery
from recovery.anti_stuck import AntiStuck
from inventory.inventory_system import InventorySystem
from input.humanizer import Humanizer
from ui.overlay import Overlay


class DrakensangBot:
    """
    Main bot controller that initializes and orchestrates all systems.

    Architecture:
        Thread 1: Screen Capture (60 FPS)
        Thread 2: YOLO Detection (10 FPS)
        Thread 3: Main Logic Loop (20 FPS)
        Thread 4: Overlay UI
        Main Thread: Hotkey listener
    """

    BANNER = r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ██████╗ ██████╗  █████╗ ██╗  ██╗███████╗███╗   ██╗        ║
    ║   ██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝██╔════╝████╗  ██║        ║
    ║   ██║  ██║██████╔╝███████║█████╔╝ █████╗  ██╔██╗ ██║        ║
    ║   ██║  ██║██╔══██╗██╔══██║██╔═██╗ ██╔══╝  ██║╚██╗██║        ║
    ║   ██████╔╝██║  ██║██║  ██║██║  ██╗███████╗██║ ╚████║        ║
    ║   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝        ║
    ║                                                              ║
    ║              ★ AI VISION BOT v1.0 ★                          ║
    ║                                                              ║
    ║   [F9]  Start/Stop    [F10] Record Waypoint                  ║
    ║   [F11] Capture Screen [F7]  Toggle Auto Dataset             ║
    ║   [F12] Toggle Overlay [F8]  Emergency Stop                  ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """

    def __init__(self):
        """Initialize the bot with all systems."""
        # Load config
        self.config = self._load_config()

        # Setup logging
        general = self.config.get("general", {})
        self.logger = setup_logger(
            level=general.get("log_level", "INFO"),
            log_file=general.get("log_file", "bot.log")
        )
        self.log = get_logger("main")

        print(self.BANNER)
        self.log.info("Initializing Drakensang AI Bot...")

        # Main loop config
        self.main_loop_fps = general.get("main_loop_fps", 20)
        self.main_loop_interval = 1.0 / self.main_loop_fps

        # Bot control
        self._bot_active = False
        self._running = True
        self._logic_thread = None

        # Auto dataset capture control
        self._auto_capture = False
        self._auto_capture_thread = None

        # Initialize all systems
        self._init_systems()

        # Wire up decision engine
        self._wire_decision_engine()

        # Start auto capture daemon thread
        self._auto_capture_thread = threading.Thread(target=self._auto_capture_loop, daemon=True, name="AutoCaptureThread")
        self._auto_capture_thread.start()

        self.log.info("═══ All systems initialized ═══")

    def _load_config(self) -> dict:
        """Load configuration from settings.json."""
        config_path = os.path.join(os.path.dirname(__file__), "config", "settings.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"[WARNING] Config not found: {config_path} — using defaults")
            return {}
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid config JSON: {e}")
            return {}

    def _init_systems(self):
        """Initialize all bot systems."""
        self.log.info("Initializing systems...")

        # 1. Humanizer (needed by most systems)
        self.humanizer = Humanizer(self.config.get("humanizer", {}))

        # 2. Screen Capture
        self.capture = ScreenCapture(self.config.get("capture", {}))

        # 3. YOLO Detector
        self.detector = YOLODetector(self.config.get("detection", {}))

        # 4. Game State
        self.game_state = GameState()

        # 5. Navigation
        self.navigation = WaypointSystem(
            self.game_state, self.humanizer,
            self.config.get("navigation", {})
        )

        # 6. Combat
        self.combat = CombatSystem(
            self.game_state, self.humanizer,
            self.config.get("combat", {})
        )

        # 7. Loot
        self.loot = LootSystem(
            self.game_state, self.humanizer,
            self.config.get("loot", {})
        )

        # 8. Potion
        self.potion = PotionSystem(
            self.game_state, self.humanizer,
            self.config.get("potion", {})
        )

        # 9. Death Recovery
        self.death_recovery = DeathRecovery(
            self.game_state, self.humanizer,
            self.config.get("death", {}),
            waypoint_system=self.navigation
        )

        # 10. Anti-Stuck
        self.anti_stuck = AntiStuck(
            self.game_state, self.humanizer,
            self.config.get("anti_stuck", {}),
            waypoint_system=self.navigation
        )

        # 11. Inventory
        self.inventory = InventorySystem(
            self.game_state, self.humanizer,
            self.config.get("inventory", {}),
            waypoint_system=self.navigation
        )

        # 12. Decision Engine
        self.decision = DecisionEngine(
            self.game_state, self.config
        )

        # 13. Overlay
        self.overlay = Overlay(
            self.config.get("overlay", {}),
            capture_system=self.capture,
            detector=self.detector,
            game_state=self.game_state,
            waypoint_system=self.navigation
        )

    def _wire_decision_engine(self):
        """Connect decision engine to action handlers."""
        self.decision.on_combat = self.combat.execute
        self.decision.on_navigate = self.navigation.execute
        self.decision.on_loot = self.loot.execute
        self.decision.on_heal = self.potion.execute
        self.decision.on_death = self.death_recovery.execute
        self.decision.on_sell = self.inventory.execute
        self.decision.on_stuck = self.anti_stuck.execute

        self.log.info("Decision engine wired to all action handlers")

    # =========================================================
    # Main Logic Loop
    # =========================================================

    def _logic_loop(self):
        """
        Main bot logic loop — runs in its own thread.
        Captures → Detects → Decides → Acts
        """
        self.log.info("Logic thread started")

        while self._running:
            loop_start = time.time()

            if self._bot_active:
                try:
                    # Step 1: Get latest detections from detector thread
                    detections = self.detector.detections

                    # Step 2: Update game state
                    self.game_state.update_from_detections(detections)

                    # Step 3: Decision engine evaluates and acts
                    action = self.decision.evaluate()

                    # Step 4: Anti-stuck resets on successful action
                    if action not in (GameState.STATE_STUCK, GameState.STATE_IDLE):
                        self.anti_stuck.on_successful_action()

                except Exception as e:
                    self.log.error(f"Logic loop error: {e}")

            # Frame rate limiting
            elapsed = time.time() - loop_start
            sleep_time = self.main_loop_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.log.info("Logic thread stopped")

    # =========================================================
    # Bot Control
    # =========================================================

    def start_bot(self):
        """Start the bot (begin capturing, detecting, acting)."""
        if self._bot_active:
            self.log.warning("Bot is already active")
            return

        self.log.info("═══ STARTING BOT ═══")

        # Start capture thread
        self.capture.start()
        time.sleep(0.5)  # Wait for first frame

        # Start detection thread
        self.detector.start(self.capture.get_frame_for_detection)

        # Start overlay
        self.overlay.start()

        # Start logic loop
        self._bot_active = True
        self._logic_thread = threading.Thread(target=self._logic_loop, daemon=True, name="LogicThread")
        self._logic_thread.start()

        self.log.info("═══ BOT IS NOW ACTIVE ═══")
        self.game_state.bot_state = GameState.STATE_IDLE

    def stop_bot(self):
        """Stop the bot (pause all actions)."""
        if not self._bot_active:
            self.log.warning("Bot is already stopped")
            return

        self.log.info("═══ STOPPING BOT ═══")

        self._bot_active = False
        self.game_state.bot_state = GameState.STATE_PAUSED

        # Stop systems
        self.capture.stop()
        self.detector.stop()
        self.overlay.stop()

        # Wait for logic thread
        if self._logic_thread and self._logic_thread.is_alive():
            self._logic_thread.join(timeout=3.0)

        self.log.info("═══ BOT STOPPED ═══")

        # Print session stats
        stats = self.game_state.stats
        self.log.info(f"Session Stats: Kills={stats['enemies_killed']} | "
                      f"Loot={stats['loot_picked']} | Potions={stats['potions_used']} | "
                      f"Deaths={stats['deaths']} | Time={stats['session_time_str']}")

    def toggle_bot(self):
        """Toggle bot on/off."""
        if self._bot_active:
            self.stop_bot()
        else:
            self.start_bot()

    def toggle_auto_capture(self):
        """Toggle auto-capture of training screenshots."""
        self._auto_capture = not self._auto_capture
        status = "ENABLED" if self._auto_capture else "DISABLED"
        self.log.info(f"Auto dataset capture is now {status}")
        print(f"\n[AUTO-CAPTURE] Dataset capture {status}!\n")

    def _auto_capture_loop(self):
        """Loop that saves screenshots periodically for training data."""
        self.log.info("Auto-capture dataset thread loop started")
        last_capture_time = 0
        
        while self._running:
            if self._auto_capture:
                # Get capture parameters dynamically in case config changes
                general_cfg = self.config.get("general", {})
                interval = general_cfg.get("auto_capture_interval", 2.0)
                max_images = general_cfg.get("max_dataset_images", 1000)
                
                # Check rate limit
                now = time.time()
                if now - last_capture_time >= interval:
                    # Check dataset file count
                    dataset_dir = os.path.join(os.path.dirname(__file__), "dataset")
                    os.makedirs(dataset_dir, exist_ok=True)
                    try:
                        num_files = len([f for f in os.listdir(dataset_dir) if f.endswith(".png")])
                    except Exception:
                        num_files = 0
                    
                    if num_files >= max_images:
                        self.log.warning(f"Reached max dataset images count ({max_images}). Auto capture stopped.")
                        self._auto_capture = False
                        continue
                        
                    self.capture_training_image()
                    last_capture_time = now
            time.sleep(0.1)

    def capture_training_image(self):
        """Capture the current frame and save it to the dataset folder for training."""
        try:
            dataset_dir = os.path.join(os.path.dirname(__file__), "dataset")
            os.makedirs(dataset_dir, exist_ok=True)
            
            # Ensure capture is running to get a frame
            is_temp_capture = False
            if not self.capture._running:
                self.capture.start()
                time.sleep(0.5)
                is_temp_capture = True
                
            frame = self.capture.frame
            if frame is not None:
                filename = f"drakensang_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
                filepath = os.path.join(dataset_dir, filename)
                import cv2
                cv2.imwrite(filepath, frame)
                self.log.info(f"Saved dataset screenshot: {filepath}")
            else:
                self.log.warning("No frame available to capture screenshot.")
                
            if is_temp_capture:
                self.capture.stop()
        except Exception as e:
            self.log.error(f"Failed to capture screenshot: {e}")

    def emergency_stop(self):
        """Emergency stop — shut everything down immediately."""
        self.log.critical("═══ EMERGENCY STOP ═══")
        self._bot_active = False
        self._running = False
        self.stop_bot()

    # =========================================================
    # Hotkey System
    # =========================================================

    def _setup_hotkeys(self):
        """Set up keyboard hotkeys using pynput."""
        from pynput import keyboard

        hotkey_cfg = self.config.get("hotkeys", {})

        # Map config keys to pynput keys
        key_map = {
            "f7": keyboard.Key.f7,
            "f8": keyboard.Key.f8,
            "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10,
            "f11": keyboard.Key.f11,
            "f12": keyboard.Key.f12,
        }

        start_stop_key = key_map.get(hotkey_cfg.get("start_stop", "f9"), keyboard.Key.f9)
        record_key = key_map.get(hotkey_cfg.get("record_waypoint", "f10"), keyboard.Key.f10)
        screenshot_key = key_map.get(hotkey_cfg.get("capture_screenshot", "f11"), keyboard.Key.f11)
        auto_capture_key = key_map.get(hotkey_cfg.get("toggle_auto_capture", "f7"), keyboard.Key.f7)
        overlay_key = key_map.get(hotkey_cfg.get("toggle_overlay", "f12"), keyboard.Key.f12)
        emergency_key = key_map.get(hotkey_cfg.get("emergency_stop", "f8"), keyboard.Key.f8)

        def on_press(key):
            try:
                if key == start_stop_key:
                    self.log.info("Hotkey: Toggle Bot")
                    self.toggle_bot()
                elif key == record_key:
                    self.log.info("Hotkey: Record Waypoint")
                    self.navigation.record_mouse_position()
                elif key == screenshot_key:
                    self.log.info("Hotkey: Capture Screenshot")
                    self.capture_training_image()
                elif key == auto_capture_key:
                    self.log.info("Hotkey: Toggle Auto-Capture")
                    self.toggle_auto_capture()
                elif key == overlay_key:
                    self.log.info("Hotkey: Toggle Overlay")
                    self.overlay.toggle()
                elif key == emergency_key:
                    self.log.info("Hotkey: Emergency Stop")
                    self.emergency_stop()
                    return False  # Stop listener
            except Exception as e:
                self.log.error(f"Hotkey error: {e}")

        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        self.log.info(f"Hotkeys registered: Start/Stop={hotkey_cfg.get('start_stop', 'F9').upper()}, "
                      f"Record={hotkey_cfg.get('record_waypoint', 'F10').upper()}, "
                      f"Screenshot={hotkey_cfg.get('capture_screenshot', 'F11').upper()}, "
                      f"AutoCapture={hotkey_cfg.get('toggle_auto_capture', 'F7').upper()}, "
                      f"Overlay={hotkey_cfg.get('toggle_overlay', 'F12').upper()}, "
                      f"Emergency={hotkey_cfg.get('emergency_stop', 'F8').upper()}")

        return listener

    # =========================================================
    # Main Run
    # =========================================================

    def run(self):
        """Main entry point — run the bot."""
        self.log.info("Starting Drakensang AI Bot...")

        # Setup hotkeys
        listener = self._setup_hotkeys()

        self.log.info("Bot is ready! Press F9 to start, F8 to exit.")
        print("\n" + "="*60)
        print("  BOT READY — Press F9 to START, F8 to EXIT")
        print("="*60 + "\n")

        # Keep main thread alive
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.log.info("Keyboard interrupt detected")

        # Cleanup
        self.stop_bot()
        listener.stop()
        self.log.info("Bot shutdown complete. Goodbye!")


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":
    bot = DrakensangBot()
    bot.run()
