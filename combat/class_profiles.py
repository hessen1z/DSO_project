"""
Class Combat Profiles
=====================
Preset combat configurations for each Drakensang Online character class.

Each profile defines:
    - skills: Available skill keys
    - skill_cooldowns: Cooldown per skill (seconds)
    - combo_sequence: Optimal DPS rotation
    - combo_cooldowns: Cooldown per combo step
    - basic_attack_key: Default auto-attack key
    - engagement_range: Preferred distance to enemy (pixels)
    - kite_enabled: Whether the class should kite (move while attacking)
    - kite_distance: Pixels to maintain from enemy when kiting
    - preferred_range: "melee" or "ranged" — affects positioning logic
    - aoe_skill: Key for AoE skill (used when surrounded)
    - aoe_enemy_threshold: Number of nearby enemies to trigger AoE
"""

from utils.logger import get_logger

logger = get_logger("profiles")


# ═══════════════════════════════════════════════════════════
# Class Profile Definitions
# ═══════════════════════════════════════════════════════════

PROFILES = {
    "ranger": {
        "display_name": "Ranger",
        "description": "Ranged DPS — kites enemies with precision shots",
        "preferred_range": "ranged",
        "engagement_range": 350,

        "skills": ["1", "2", "3", "4", "5"],
        "skill_cooldowns": [0.0, 3.0, 6.0, 10.0, 15.0],
        "basic_attack_key": "1",

        "combo_enabled": True,
        "combo_sequence": ["2", "3", "1", "1", "5", "1", "1"],
        "combo_cooldowns": [0.0, 3.0, 6.0, 0.0, 0.0, 15.0, 0.0, 0.0],

        "kite_enabled": True,
        "kite_distance": 250,

        "aoe_skill": "3",
        "aoe_enemy_threshold": 3,

        "escape_logic": {
            "enabled": True,
            "hp_escape_threshold": 30,
            "danger_score_threshold": 65,
            "escape_skill": "4",
            "escape_skill_cooldown": 12.0,
            "retreat_distance": 350,
            "surrounded_enemy_count": 3,
            "boss_danger_weight": 35,
            "nearby_enemy_weight": 15,
            "low_hp_weight": 35,
            "potion_cooldown_weight": 10,
        },
    },

    "mage": {
        "display_name": "Spellweaver",
        "description": "Ranged AoE caster — massive damage, fragile",
        "preferred_range": "ranged",
        "engagement_range": 400,

        "skills": ["1", "2", "3", "4", "5"],
        "skill_cooldowns": [0.0, 4.0, 8.0, 12.0, 20.0],
        "basic_attack_key": "1",

        "combo_enabled": True,
        "combo_sequence": ["3", "2", "5", "1", "1", "1"],
        "combo_cooldowns": [0.0, 8.0, 4.0, 20.0, 0.0, 0.0, 0.0],

        "kite_enabled": True,
        "kite_distance": 300,

        "aoe_skill": "3",
        "aoe_enemy_threshold": 2,

        "escape_logic": {
            "enabled": True,
            "hp_escape_threshold": 35,
            "danger_score_threshold": 60,
            "escape_skill": "4",
            "escape_skill_cooldown": 15.0,
            "retreat_distance": 400,
            "surrounded_enemy_count": 2,
            "boss_danger_weight": 45,
            "nearby_enemy_weight": 20,
            "low_hp_weight": 30,
            "potion_cooldown_weight": 15,
        },
    },

    "dragonknight": {
        "display_name": "Dragonknight",
        "description": "Melee tank — close-range brawler, high survivability",
        "preferred_range": "melee",
        "engagement_range": 80,

        "skills": ["1", "2", "3", "4", "5"],
        "skill_cooldowns": [0.0, 3.0, 5.0, 8.0, 15.0],
        "basic_attack_key": "1",

        "combo_enabled": True,
        "combo_sequence": ["2", "3", "4", "1", "1", "1"],
        "combo_cooldowns": [0.0, 3.0, 5.0, 8.0, 0.0, 0.0, 0.0],

        "kite_enabled": False,
        "kite_distance": 0,

        "aoe_skill": "3",
        "aoe_enemy_threshold": 3,

        "escape_logic": {
            "enabled": True,
            "hp_escape_threshold": 20,
            "danger_score_threshold": 80,
            "escape_skill": "5",
            "escape_skill_cooldown": 15.0,
            "retreat_distance": 200,
            "surrounded_enemy_count": 5,
            "boss_danger_weight": 30,
            "nearby_enemy_weight": 10,
            "low_hp_weight": 35,
            "potion_cooldown_weight": 10,
        },
    },

    "steam": {
        "display_name": "Steam Mechanicus",
        "description": "Mid-range hybrid — turrets and mechanical attacks",
        "preferred_range": "ranged",
        "engagement_range": 250,

        "skills": ["1", "2", "3", "4", "5"],
        "skill_cooldowns": [0.0, 4.0, 6.0, 10.0, 18.0],
        "basic_attack_key": "1",

        "combo_enabled": True,
        "combo_sequence": ["2", "4", "3", "1", "1", "1"],
        "combo_cooldowns": [0.0, 4.0, 10.0, 6.0, 0.0, 0.0, 0.0],

        "kite_enabled": True,
        "kite_distance": 180,

        "aoe_skill": "3",
        "aoe_enemy_threshold": 3,

        "escape_logic": {
            "enabled": True,
            "hp_escape_threshold": 25,
            "danger_score_threshold": 70,
            "escape_skill": "5",
            "escape_skill_cooldown": 18.0,
            "retreat_distance": 280,
            "surrounded_enemy_count": 3,
            "boss_danger_weight": 35,
            "nearby_enemy_weight": 15,
            "low_hp_weight": 30,
            "potion_cooldown_weight": 10,
        },
    },

    "custom": {
        "display_name": "Custom",
        "description": "User-defined — reads everything from settings.json",
        "preferred_range": "melee",
        "engagement_range": 150,

        "skills": ["1", "2", "3"],
        "skill_cooldowns": [2.0, 5.0, 8.0],
        "basic_attack_key": "1",

        "combo_enabled": True,
        "combo_sequence": ["2", "3", "1", "1", "1"],
        "combo_cooldowns": [0.0, 5.0, 8.0, 2.0, 2.0],

        "kite_enabled": False,
        "kite_distance": 0,

        "aoe_skill": None,
        "aoe_enemy_threshold": 3,

        "escape_logic": {
            "enabled": True,
            "hp_escape_threshold": 25,
            "danger_score_threshold": 70,
            "escape_skill": "4",
            "escape_skill_cooldown": 12.0,
            "retreat_distance": 300,
            "surrounded_enemy_count": 3,
            "boss_danger_weight": 40,
            "nearby_enemy_weight": 15,
            "low_hp_weight": 30,
            "potion_cooldown_weight": 10,
        },
    },
}


def get_profile(class_name: str) -> dict:
    """
    Get a class combat profile by name.

    Args:
        class_name: One of 'ranger', 'mage', 'dragonknight', 'steam', 'custom'

    Returns:
        Profile dict with all combat parameters
    """
    key = class_name.lower().strip()
    if key in PROFILES:
        logger.info(f"Loaded class profile: {PROFILES[key]['display_name']}")
        return PROFILES[key].copy()
    else:
        logger.warning(f"Unknown class '{class_name}' — defaulting to 'custom'")
        return PROFILES["custom"].copy()


def get_all_profile_names() -> list:
    """Return a list of all available profile keys."""
    return list(PROFILES.keys())


def get_all_display_names() -> dict:
    """Return a mapping of profile_key → display_name."""
    return {k: v["display_name"] for k, v in PROFILES.items()}
