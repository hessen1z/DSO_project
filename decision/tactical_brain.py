"""
Tactical Brain Layer
====================
The AI "thinking" layer between raw GameState and action execution.

Instead of simple if/else rules, it calculates weighted danger scores,
evaluates skill intents, and recommends the best tactical response.

Architecture:
    GameState → TacticalBrain.evaluate() → Recommendation dict
                                         → CombatSystem picks best skill
                                         → DecisionEngine selects movement style

Key Systems:
    1. Danger Score Analysis       → How dangerous is the current situation?
    2. Target Priority Engine      → Which enemy to engage first?
    3. Skill Intent Evaluator      → Which skill best fits the intent?
    4. Movement Style Advisor      → melee / kite / retreat
    5. Combat Mode Selector        → farm / boss / retreat
"""

import time
from utils.logger import get_logger
from knowledge.knowledge_loader import get_class_knowledge

logger = get_logger("tactical_brain")


class TacticalBrain:
    """
    AI Tactical Decision Layer.

    Transforms raw game state into weighted tactical recommendations,
    giving the bot genuine situational awareness instead of hard-coded rules.
    """

    # ── Danger score thresholds ─────────────────────────────────────────────
    DANGER_SAFE     = 0.5   # Farm normally
    DANGER_CAUTION  = 1.0   # Use defensive skills
    DANGER_CRITICAL = 1.5   # Escape skills should fire
    DANGER_RETREAT  = 2.0   # Immediately disengage

    # ── Intent → acceptable macro conditions ────────────────────────────────
    INTENT_CONDITIONS = {
        "escape":     ["low_hp", "surrounded", "boss_detected"],
        "aoe_burst":  ["surrounded"],
        "buff":       ["always", "off_cooldown"],
        "cc":         ["enemy_in_range", "boss_detected"],
        "heal":       ["low_hp"],
        "single_dps": ["enemy_in_range", "always"],
    }

    def __init__(self, game_state, config: dict):
        self.state  = game_state
        self.config = config

        self._active_class    = config.get("combat", {}).get("class_profile", "ranger")
        self._class_knowledge = {}
        self._skill_catalog   = {}   # skill_name.lower() → skill dict

        self._load_class_knowledge()

        # Cached outputs between eval intervals
        self._last_danger_score       = 0.0
        self._last_combat_mode        = "farm"
        self._last_recommended_intent = "single_dps"
        self._last_movement_style     = "melee"
        self._last_primary_target     = None
        self._last_eval_time          = 0.0
        self._eval_interval           = 0.1   # max 10 evaluations / sec

        logger.info(f"TacticalBrain initialized | Class: {self._active_class} | "
                    f"Skills loaded: {len(self._skill_catalog)}")

    # =========================================================
    # Knowledge Loading
    # =========================================================

    def _load_class_knowledge(self):
        """Load skill knowledge for the active class."""
        try:
            data = get_class_knowledge(self._active_class)
            if data:
                self._class_knowledge = data
                for skill in data.get("skills", []):
                    name = skill.get("name", "")
                    if name:
                        self._skill_catalog[name.lower()] = skill
                logger.info(f"Loaded {len(self._skill_catalog)} skills for '{self._active_class}'")
        except Exception as e:
            logger.error(f"TacticalBrain: failed to load class knowledge — {e}")

    def switch_class(self, class_name: str):
        """Hot-switch class and reload knowledge."""
        self._active_class = class_name.lower()
        self._skill_catalog.clear()
        self._class_knowledge = {}
        self._load_class_knowledge()

    # =========================================================
    # Main Evaluation Entry Point
    # =========================================================

    def evaluate(self) -> dict:
        """
        Full tactical evaluation.  Called each logic tick.

        Returns:
            dict with keys:
                danger_score      (float)
                danger_level      (str)    SAFE / CAUTION / CRITICAL / RETREAT
                combat_mode       (str)    farm / boss / retreat
                movement_style    (str)    melee / kite / retreat
                recommended_intent(str)    escape / aoe_burst / cc / buff / single_dps
                primary_target    (Detection | None)
                should_retreat    (bool)
                nearby_count      (int)
        """
        now = time.time()
        if now - self._last_eval_time < self._eval_interval:
            return self._cached()

        self._last_eval_time = now

        enemies     = self.state.enemies
        all_targets = self.state.all_targets
        hp          = self.state.hp_percent
        bosses      = getattr(self.state, "_bosses",  [])
        elites      = getattr(self.state, "_elites",  [])

        danger = self._calc_danger(enemies, elites, bosses, hp)
        self._last_danger_score = danger

        primary = self._pick_target(all_targets, bosses, elites, enemies)
        self._last_primary_target = primary

        mode = self._combat_mode(bosses, danger)
        self._last_combat_mode = mode

        movement = self._movement_style(danger, mode, hp)
        self._last_movement_style = movement

        intent = self._recommend_intent(danger, hp, len(enemies), len(elites), len(bosses), movement)
        self._last_recommended_intent = intent

        rec = {
            "danger_score":         round(danger, 3),
            "danger_level":         self._danger_label(danger),
            "combat_mode":          mode,
            "movement_style":       movement,
            "recommended_intent":   intent,
            "primary_target":       primary,
            "should_retreat":       danger >= self.DANGER_RETREAT,
            "nearby_count":         len(all_targets),
        }

        logger.debug(
            f"Brain: danger={danger:.2f}({self._danger_label(danger)}) "
            f"mode={mode} move={movement} intent={intent} targets={len(all_targets)}"
        )
        return rec

    # =========================================================
    # Danger Score
    # =========================================================

    def _calc_danger(self, enemies, elites, bosses, hp) -> float:
        """
        Weighted danger score:
            each normal enemy  +0.4
            each elite         +0.8
            each boss          +1.5
            HP < 40%           +0.6 … +1.8
            surrounded 3+      +0.3
            surrounded 5+      +0.5
        """
        score = 0.0
        score += len(enemies) * 0.4
        score += len(elites)  * 0.8
        score += len(bosses)  * 1.5

        if hp < 20:
            score += 1.8
        elif hp < 30:
            score += 1.2
        elif hp < 40:
            score += 0.6

        total = len(enemies) + len(elites) + len(bosses)
        if total >= 5:
            score += 0.5
        elif total >= 3:
            score += 0.3

        return round(score, 3)

    # =========================================================
    # Target Priority
    # =========================================================

    def _pick_target(self, all_targets, bosses, elites, enemies):
        """Boss > Elite > Nearest normal enemy."""
        if bosses:
            return bosses[0]
        if elites:
            return elites[0]
        if enemies:
            cx = getattr(self.state, "_screen_center_x", 960)
            cy = getattr(self.state, "_screen_center_y", 540)
            return min(enemies, key=lambda d: d.distance_to(cx, cy))
        return None

    # =========================================================
    # Combat Mode
    # =========================================================

    def _combat_mode(self, bosses, danger) -> str:
        if bosses:
            return "boss"
        if danger >= self.DANGER_RETREAT:
            return "retreat"
        return "farm"

    # =========================================================
    # Movement Style
    # =========================================================

    def _movement_style(self, danger, mode, hp) -> str:
        if mode == "retreat" or danger >= self.DANGER_RETREAT:
            return "retreat"

        preferred = "melee"
        if self._class_knowledge:
            preferred = self._class_knowledge.get("combat_style", {}).get("preferred_range", "melee")

        if danger >= self.DANGER_CRITICAL:
            return "retreat" if hp < 35 else "kite"

        if danger >= self.DANGER_CAUTION:
            return "kite"

        return preferred if preferred in ("melee", "kite") else "melee"

    # =========================================================
    # Skill Intent
    # =========================================================

    def _recommend_intent(self, danger, hp, n_enemy, n_elite, n_boss, movement) -> str:
        if movement == "retreat" or danger >= self.DANGER_RETREAT:
            return "escape"
        if n_enemy + n_elite >= 3:
            return "aoe_burst"
        if n_boss > 0 and danger >= self.DANGER_CAUTION:
            return "cc"
        if danger < self.DANGER_SAFE:
            return "buff"
        return "single_dps"

    def get_best_slot_for_intent(self, intent: str, macro_slots: list) -> dict:
        """
        Find the best macro slot that matches a tactical intent.

        Checks slot["intent"] first (exact match = 2 pts),
        then falls back to slot["condition"] vs INTENT_CONDITIONS (1 pt).
        """
        conditions = self.INTENT_CONDITIONS.get(intent, ["always"])
        candidates = []

        for slot in macro_slots:
            slot_intent    = slot.get("intent",    "single_dps")
            slot_condition = slot.get("condition", "always")

            if slot_intent == intent:
                candidates.append((slot, 2))
            elif slot_condition in conditions:
                candidates.append((slot, 1))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def get_skill_data(self, skill_name: str) -> dict:
        """Return full skill metadata from the knowledge base."""
        return self._skill_catalog.get(skill_name.lower(), {})

    # =========================================================
    # Helpers
    # =========================================================

    def _cached(self) -> dict:
        return {
            "danger_score":         self._last_danger_score,
            "danger_level":         self._danger_label(self._last_danger_score),
            "combat_mode":          self._last_combat_mode,
            "movement_style":       self._last_movement_style,
            "recommended_intent":   self._last_recommended_intent,
            "primary_target":       self._last_primary_target,
            "should_retreat":       self._last_danger_score >= self.DANGER_RETREAT,
            "nearby_count":         len(self.state.all_targets),
        }

    def _danger_label(self, score: float) -> str:
        if score < self.DANGER_SAFE:     return "SAFE"
        if score < self.DANGER_CAUTION:  return "CAUTION"
        if score < self.DANGER_CRITICAL: return "CRITICAL"
        return "RETREAT"

    def get_status(self) -> dict:
        return {
            "danger_score":       self._last_danger_score,
            "danger_level":       self._danger_label(self._last_danger_score),
            "combat_mode":        self._last_combat_mode,
            "movement_style":     self._last_movement_style,
            "recommended_intent": self._last_recommended_intent,
            "active_class":       self._active_class,
            "skills_loaded":      len(self._skill_catalog),
        }
