import os
import json
from utils.logger import get_logger

logger = get_logger("knowledge_loader")

KNOWLEDGE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mapping of file keys to JSON files
CLASS_FILES = {
    "ranger": "ranger.json",
    "mage": "spellweaver.json",
    "spellweaver": "spellweaver.json",
    "dragonknight": "dragonknight.json",
    "dk": "dragonknight.json",
    "steam": "steam_mechanicus.json",
    "steam_mechanicus": "steam_mechanicus.json"
}

_cache = {}

def get_class_knowledge(class_name: str) -> dict:
    """
    Load and return the full class knowledge dictionary.
    Caches the results to prevent repeated disk I/O.
    """
    key = class_name.lower().strip()
    if key in _cache:
        return _cache[key]

    filename = CLASS_FILES.get(key)
    if not filename:
        logger.warning(f"No knowledge file found for class: {class_name}")
        return {}

    filepath = os.path.join(KNOWLEDGE_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            _cache[key] = data
            # Also cache other aliases
            for alias, fname in CLASS_FILES.items():
                if fname == filename:
                    _cache[alias] = data
            return data
    except Exception as e:
        logger.error(f"Failed to load knowledge file {filepath}: {e}")
        return {}

def get_default_macro_slots(class_name: str) -> list:
    """
    Return the pre-configured default macro slots (10 slots) for the class.
    """
    knowledge = get_class_knowledge(class_name)
    return knowledge.get("default_macro_slots", [])

def get_threat_rules(class_name: str) -> list:
    """
    Return the threat rules (IF/THEN behavior rules) for the class.
    """
    knowledge = get_class_knowledge(class_name)
    return knowledge.get("threat_rules", [])

def get_decision_profile(class_name: str) -> dict:
    """
    Return the decision parameters (HP panic thresholds, range, kiting state).
    """
    knowledge = get_class_knowledge(class_name)
    return knowledge.get("decision_profile", {})

def get_skill_by_name(class_name: str, skill_name: str) -> dict:
    """
    Retrieve info on a specific skill.
    """
    knowledge = get_class_knowledge(class_name)
    for skill in knowledge.get("skills", []):
        if skill["name"].lower() == skill_name.lower():
            return skill
    return {}
