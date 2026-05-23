"""
Combat System
=============
Handles target selection, attack rotation, and skill usage.

Features:
- Combo Engine: Sequential skill chains (stun → debuff → burst → finisher)
- Escape Logic: Danger-score-based retreat when HP critical or surrounded
- Tactical kiting: Clicks away from enemies to create distance before re-engaging
- Priority targeting: boss > elite > enemy with weighted distance scoring
- Class Profiles: Ranger / Mage / DK / Steam with tailored combat parameters
- Action Locking: Thread-safe input serialization via global ActionLock
"""

import os
import json
import time
import math
from state.game_state import GameState
from input.humanizer import Humanizer
from input.action_lock import ActionLock
from combat.class_profiles import get_profile
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

    def __init__(self, game_state: GameState, humanizer: Humanizer, config: dict,
                 action_lock: ActionLock = None):
        self.state = game_state
        self.input = humanizer
        self.action_lock = action_lock or ActionLock(enabled=False)

        # --- Load class profile (overlay on top of config) ---
        self._active_class = config.get("active_class", "custom")
        profile = get_profile(self._active_class)

        # Profile values are defaults; explicit config values override them
        def _cfg(key, fallback_profile_key=None):
            """Get value from config, falling back to profile, then a default."""
            pk = fallback_profile_key or key
            return config.get(key, profile.get(pk))

        # --- Basic combat config ---
        self.skills = _cfg("skills")
        self.skill_cooldowns = _cfg("skill_cooldowns")
        self.basic_attack_key = _cfg("basic_attack_key")
        self.target_priority = config.get("target_priority", ["boss", "elite", "enemy"])
        self.attack_range = _cfg("attack_range", "engagement_range")
        self.target_click_offset = config.get("target_click_offset", 3)

        # --- Class behavior ---
        self.preferred_range = profile.get("preferred_range", "melee")
        self.kite_enabled = _cfg("kite_enabled")
        self.kite_distance = _cfg("kite_distance")
        self.aoe_skill = _cfg("aoe_skill")
        self.aoe_enemy_threshold = _cfg("aoe_enemy_threshold")

        # --- Combo Engine ---
        self.combo_enabled = _cfg("combo_enabled")
        self.combo_sequence = _cfg("combo_sequence")
        self.combo_cooldowns = _cfg("combo_cooldowns")
        self._combo_step = 0               # Current step in the combo sequence
        self._combo_last_used = {}
        for key in self.combo_sequence:
            self._combo_last_used[key] = 0

        # --- Escape Logic ---
        # Profile's escape_logic is the base; config's escape_logic overrides
        profile_escape = profile.get("escape_logic", {})
        config_escape = config.get("escape_logic", {})
        escape_cfg = {**profile_escape, **config_escape}

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

        # --- Macro Engine ---
        self.macro_enabled = config.get("macro_enabled", True)
        self.active_macro_profile = config.get("macro_profile_name", "Default")
        self._macro_last_used = {}
        self._load_macro_profile(self.active_macro_profile)

        # --- Tactical Brain reference (set by main.py after brain is created) ---
        self.tactical_brain = None

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
        self._aoe_last_used = 0

        logger.info(
            f"CombatSystem initialized | Class: {profile.get('display_name', self._active_class)} | "
            f"Combo: {self.combo_sequence} | Range: {self.preferred_range} | "
            f"Kite: {self.kite_enabled} | "
            f"Macro Enabled: {self.macro_enabled} ({self.active_macro_profile}) | "
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
        All input actions are wrapped in the global action lock.
        """
        with self.action_lock.acquire("combat") as acquired:
            if not acquired:
                logger.debug("Combat skipped — action lock unavailable")
                return

            # Step 1: Calculate current danger level
            danger = self._calculate_danger_score()
            logger.debug(f"Danger score: {danger:.0f}")

            # Step 2: Check if we should retreat instead of fight
            if self.escape_enabled and danger >= self.danger_score_threshold:
                self._execute_retreat()
                return

            # Step 3: We're safe enough — select and attack a target
            self._retreating = False

            # Step 3b: Ask TacticalBrain for a situational assessment
            tac = None
            if self.tactical_brain is not None:
                tac = self.tactical_brain.evaluate()
                # Use brain's primary target preference if available
                target = tac.get("primary_target") or self._select_target()
            else:
                target = self._select_target()

            if target is None:
                logger.debug("No target available")
                return

            # Step 4: Kiting — maintain distance for ranged classes
            movement_style = tac.get("movement_style", "melee") if tac else ("kite" if self.kite_enabled else "melee")
            if movement_style == "kite" and target:
                self._execute_kite(target)

            # Step 5: AoE check — use AoE if surrounded
            all_targets = self.state.all_targets
            if (self.aoe_skill and len(all_targets) >= self.aoe_enemy_threshold
                    and time.time() - self._aoe_last_used > 5.0):
                logger.info(f"⚡ AoE triggered — {len(all_targets)} enemies, [{self.aoe_skill}]")
                self.input.press_key(self.aoe_skill)
                self._aoe_last_used = time.time()
                self.input.delay(0.05, 0.1)
                return

            # Step 6: Click on target to select it
            self._target_enemy(target)

            # Step 7: Skill selection — Ranger specialized logic or TacticalBrain intent
            if self._active_class == "ranger":
                self._execute_ranger_combat(target, tac)
            elif tac and self.macro_enabled and self.tactical_brain is not None:
                intent = tac.get("recommended_intent", "single_dps") if isinstance(tac, dict) else "single_dps"
                
                # Filter macro slots to find the highest priority one for this intent that is off cooldown
                best_slot = None
                matching_slots = []
                now = time.time()
                
                for slot in self.macro_slots:
                    if not isinstance(slot, dict):
                        continue
                    slot_intent = slot.get("intent", "single_dps")
                    slot_condition = slot.get("condition", "always")
                    key = slot.get("key")
                    if not key:
                        continue
                    
                    # Check cooldown
                    cooldown = slot.get("cooldown", 0.0)
                    last_used = self._macro_last_used.get(key, 0)
                    if now - last_used < cooldown:
                        continue
                        
                    # Evaluate condition
                    if not self._evaluate_condition(slot_condition, slot, target):
                        continue
                        
                    # Calculate matching score
                    score = 0
                    conditions = self.tactical_brain.INTENT_CONDITIONS.get(intent, ["always"])
                    if slot_intent == intent:
                        score = 2
                    elif slot_condition in conditions:
                        score = 1
                        
                    if score > 0:
                        matching_slots.append((slot, score))
                        
                if matching_slots:
                    # Sort by score descending
                    matching_slots.sort(key=lambda x: x[1], reverse=True)
                    best_slot = matching_slots[0][0]
                    
                if best_slot:
                    # Use intent-recommended slot
                    key   = best_slot.get("key", "")
                    delay = best_slot.get("delay", 0.1)
                    if key:
                        logger.info(f"Brain intent={intent} → skill [{key}] ({best_slot.get('label', '')})") 
                        self.input.delay(delay * 0.5, delay)
                        self.input.press_key(key)
                        self._macro_last_used[key] = time.time()
                        self.input.delay(0.05, 0.12)
                        self._attack_count += 1
                        return
                # Fallback to standard macro if brain found no match
                self._use_macro_skill(target)
            elif self.macro_enabled:
                self._use_macro_skill(target)
            elif self.combo_enabled:
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
    # Kiting (ranged class positioning)
    # =========================================================

    def _execute_kite(self, target):
        """
        Maintain kite distance from the target for ranged classes.
        If the enemy is too close, step backward before attacking.
        """
        if not target:
            return

        cx = self.state._screen_center_x
        cy = self.state._screen_center_y
        dist = target.distance_to(cx, cy)

        # If enemy is closer than our kite distance, step back
        if dist < self.kite_distance * 0.6:
            dx = cx - target.center_x
            dy = cy - target.center_y
            norm = math.sqrt(dx * dx + dy * dy) or 1.0

            step = self.kite_distance * 0.4
            kx = int(cx + (dx / norm) * step)
            ky = int(cy + (dy / norm) * step)

            # Clamp to screen
            kx = max(50, min(1870, kx))
            ky = max(50, min(1030, ky))

            logger.debug(f"Kiting away to ({kx}, {ky}), enemy dist={dist:.0f}px")
            self.input.right_click(kx, ky)
            self.input.delay(0.08, 0.15)

    # =========================================================
    # Class Profile Switching
    # =========================================================

    def switch_class(self, class_name: str):
        """
        Hot-switch the combat profile to a different class.

        Args:
            class_name: One of 'ranger', 'mage', 'dragonknight', 'steam', 'custom'
        """
        profile = get_profile(class_name)
        self._active_class = class_name

        self.skills = profile.get("skills", self.skills)
        self.skill_cooldowns = profile.get("skill_cooldowns", self.skill_cooldowns)
        self.basic_attack_key = profile.get("basic_attack_key", self.basic_attack_key)
        self.attack_range = profile.get("engagement_range", self.attack_range)
        self.preferred_range = profile.get("preferred_range", self.preferred_range)
        self.kite_enabled = profile.get("kite_enabled", self.kite_enabled)
        self.kite_distance = profile.get("kite_distance", self.kite_distance)
        self.aoe_skill = profile.get("aoe_skill", self.aoe_skill)
        self.aoe_enemy_threshold = profile.get("aoe_enemy_threshold", self.aoe_enemy_threshold)
        self.combo_enabled = profile.get("combo_enabled", self.combo_enabled)
        self.combo_sequence = profile.get("combo_sequence", self.combo_sequence)
        self.combo_cooldowns = profile.get("combo_cooldowns", self.combo_cooldowns)

        # Update escape logic
        esc = profile.get("escape_logic", {})
        self.escape_enabled = esc.get("enabled", self.escape_enabled)
        self.hp_escape_threshold = esc.get("hp_escape_threshold", self.hp_escape_threshold)
        self.danger_score_threshold = esc.get("danger_score_threshold", self.danger_score_threshold)
        self.escape_skill = esc.get("escape_skill", self.escape_skill)
        self.retreat_distance = esc.get("retreat_distance", self.retreat_distance)

        # Reset combo state
        self._combo_step = 0
        self._combo_last_used = {k: 0 for k in self.combo_sequence}
        self._skill_last_used = {s: 0 for s in self.skills}

        logger.info(f"Switched class profile to: {profile.get('display_name', class_name)}")

    @property
    def active_class(self) -> str:
        """Get the currently active class profile name."""
        return self._active_class

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
            "active_class": self._active_class,
            "attack_count": self._attack_count,
            "combo_step": self._combo_step,
            "combo_skill": self.combo_sequence[self._combo_step] if self.combo_sequence else "?",
            "retreating": self._retreating,
            "kiting": self.kite_enabled,
            "danger_score": round(self._calculate_danger_score(), 1),
            "has_target": target is not None,
            "target_class": target.class_name if target else "none",
        }

    # =========================================================
    # Macro Engine Internals
    # =========================================================

    def _load_macro_profile(self, name: str):
        """Load macro profile from config/macro_profiles/name.json."""
        self.macro_slots = []
        self.prioritize_elites = True
        self.auto_dodge_boss_aoe = True
        self.mana_conservation = False

        filename = f"{name.lower().strip()}.json"
        path = os.path.join("config", "macro_profiles", filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.macro_slots = data.get("slots", [])
                    self.prioritize_elites = data.get("prioritize_elites", True)
                    self.auto_dodge_boss_aoe = data.get("auto_dodge_boss_aoe", True)
                    self.mana_conservation = data.get("mana_conservation", False)
                    logger.info(f"Loaded macro profile: {name} with {len(self.macro_slots)} slots")
                    
                    # Update active class and switch profile dynamically
                    profile_class = data.get("active_class")
                    if profile_class:
                        self.switch_class(profile_class)
                        logger.info(f"Dynamically switched combat profile to class: {profile_class}")
                    
                    # Initialize last used timers for macro keys
                    for slot in self.macro_slots:
                        if isinstance(slot, dict):
                            key = slot.get("key")
                            if key and key not in self._macro_last_used:
                                self._macro_last_used[key] = 0
                    return
            except Exception as e:
                logger.error(f"Error loading macro profile {path}: {e}")

        # Fallback to default.json
        default_path = os.path.join("config", "macro_profiles", "default.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.macro_slots = data.get("slots", [])
                    self.prioritize_elites = data.get("prioritize_elites", True)
                    self.auto_dodge_boss_aoe = data.get("auto_dodge_boss_aoe", True)
                    self.mana_conservation = data.get("mana_conservation", False)
                    logger.info("Loaded default macro profile")
                    
                    # Update active class and switch profile dynamically
                    profile_class = data.get("active_class")
                    if profile_class:
                        self.switch_class(profile_class)
                        logger.info(f"Dynamically switched combat profile to class: {profile_class}")
                    
                    for slot in self.macro_slots:
                        if isinstance(slot, dict):
                            key = slot.get("key")
                            if key and key not in self._macro_last_used:
                                self._macro_last_used[key] = 0
                    return
            except Exception as e:
                logger.error(f"Error loading default macro profile: {e}")

        # In-memory fallback if default files fail to load
        self.macro_slots = [
            {"label": "Basic Attack", "key": "q", "condition": "always", "cooldown": 0.0, "range": 9999, "delay": 0.1},
            {"label": "Skill 1", "key": "1", "condition": "enemy_in_range", "cooldown": 3.0, "range": 400, "delay": 0.15},
            {"label": "Skill 2", "key": "2", "condition": "enemy_in_range", "cooldown": 6.0, "range": 500, "delay": 0.2}
        ]
        for slot in self.macro_slots:
            self._macro_last_used[slot["key"]] = 0

    def _use_macro_skill(self, target):
        """
        Evaluate all configured macro slots in priority order.
        Casts the first skill whose condition is met and is off cooldown.
        """
        now = time.time()
        for idx, slot in enumerate(self.macro_slots):
            key = slot.get("key")
            if not key:
                continue

            cooldown = slot.get("cooldown", 0.0)
            last_used = self._macro_last_used.get(key, 0)

            # Check cooldown
            if now - last_used < cooldown:
                continue

            # Evaluate condition
            condition = slot.get("condition", "always")
            if self._evaluate_condition(condition, slot, target):
                logger.debug(f"Macro Slot {idx+1} [{slot.get('label', key)}]: Condition '{condition}' met. Casting [{key}]")
                self.input.press_key(key)
                self._macro_last_used[key] = now
                delay = slot.get("delay", 0.1)
                self.input.delay(delay, delay + 0.05)
                return

        # Default fallback
        self.input.press_key(self.basic_attack_key)
        logger.debug("No macro condition met — falling back to basic attack")

    def _evaluate_condition(self, condition: str, slot: dict, target) -> bool:
        cond = condition.lower().strip()

        if cond == "always":
            return True

        elif cond == "enemy_in_range":
            if not target:
                return False
            cx = self.state._screen_center_x
            cy = self.state._screen_center_y
            dist = target.distance_to(cx, cy)
            return dist <= slot.get("range", 9999)

        elif cond == "low_hp":
            # Check player HP percentage from state
            return self.state.hp_percent < 40

        elif cond == "surrounded":
            # Surrounded if 3 or more targets
            return len(self.state.all_targets) >= 3

        elif cond == "boss_detected":
            # Check if any boss in range
            return any(t.class_name == "boss" for t in self.state.all_targets)

        elif cond in ("off_cooldown", "buff_expired"):
            return True

        return False

    def _execute_ranger_combat(self, target, tac):
        """
        Specialized highly intelligent combat routine for the Ranger class.
        Executes: Decoy (Tree/Wild Pack) -> Adrenaline (Concentration) ->
        Hunting Trap -> Explosive Arrow -> Thicket of Thorns / AoE -> Precise Shot Spam.
        Also prioritizes marked targets if possible.
        """
        now = time.time()
        all_targets = self.state.all_targets
        
        # 1. Decoy / Tree Summon (Key 8)
        # Cast Wild Pack (decoy/tree) at the start of a combat encounter to gather enemies.
        # Cooldown: 50s. We trigger it if there are 3+ enemies or a boss.
        last_decoy = self._macro_last_used.get("8", 0)
        if now - last_decoy > 50.0 and (len(all_targets) >= 3 or any(t.class_name == "boss" for t in all_targets)):
            logger.info("🌲 Summoning Decoy/Tree (Wild Pack) to group enemies")
            self.input.press_key("8")
            self._macro_last_used["8"] = now
            self.input.delay(0.15, 0.22)
            self._attack_count += 1
            return

        # 2. Adrenaline (Key 7)
        # Restores Concentration. We cast it when we need to dump mana or reset,
        # or when we are about to spam Precise Shot. Cooldown: 20s.
        last_adrenaline = self._macro_last_used.get("7", 0)
        # We can trigger it if our attack count is high or if we are low on mana (approximated after a couple of Precise Shots).
        if now - last_adrenaline > 20.0 and (self._attack_count % 6 == 0):
            logger.info("⚡ Using Adrenaline to reset Concentration/Mana")
            self.input.press_key("7")
            self._macro_last_used["7"] = now
            self.input.delay(0.1, 0.15)
            self._attack_count += 1
            return

        # 3. Target lock and marking priority
        # Let's check if there is any target that is elite or boss. If we just clicked target, we lock it.
        # Click on target to select/lock it.
        self._target_enemy(target)

        # 4. Hunting Trap (Key 3)
        # Lay trap to Mark and slow enemies. Cooldown: 8s.
        # We throw it at the target's location.
        last_trap = self._macro_last_used.get("3", 0)
        if now - last_trap > 8.0:
            logger.info("🎯 Laying Hunting Trap to group and Mark enemies")
            self.input.press_key("3")
            self._macro_last_used["3"] = now
            self.input.delay(0.18, 0.25)
            self._attack_count += 1
            return

        # 5. Explosive Arrow (Key 9)
        # High damage AoE that deals double damage to Marked. Cooldown: 5s.
        # Best used right after Hunting Trap!
        last_explosive = self._macro_last_used.get("9", 0)
        if now - last_explosive > 5.0 and now - last_trap < 4.0:
            logger.info("💥 Firing Explosive Arrow on Marked enemies")
            self.input.press_key("9")
            self._macro_last_used["9"] = now
            self.input.delay(0.18, 0.25)
            self._attack_count += 1
            return

        # 6. Net (Key 5) or Scatter Shot (Key 6) or Thicket/Death Sweep (Key 2)
        # CC / AoE filler.
        last_net = self._macro_last_used.get("5", 0)
        if now - last_net > 10.0 and (any(t.class_name in ("boss", "elite") for t in all_targets) or len(all_targets) >= 3):
            logger.info("🕸️ Casting Net/Thorns (CC)")
            self.input.press_key("5")
            self._macro_last_used["5"] = now
            self.input.delay(0.15, 0.2)
            self._attack_count += 1
            return

        # 7. Precise Shot spam (Key 1)
        # Main single target and marked DPS skill. Cooldown: 0s.
        # Spams this skill to deal massive damage.
        logger.debug("🎯 Spamming Precise Shot (Main DPS)")
        self.input.press_key("1")
        self.input.delay(0.12, 0.18)
        self._attack_count += 1

        # Fallback basic attack (Key q) if Precise Shot is somehow not castable
        # or as a filler attack every couple of shots
        if self._attack_count % 4 == 0:
            self.input.press_key("q")
            self.input.delay(0.08, 0.12)

