"""
prompt_builder.py
─────────────────
Builds the final system prompt for any tenant by combining:
  1. Base template   (src/data/templates/base_prompt.json)
  2. Tenant persona  (tenants/{tenant_id}/persona.json)
  3. Behavior rules  (src/data/behaviors/{behavior_id}.json)

Usage:
    from src.core.prompt_builder import build_system_prompt, build_contextualize_prompt
    system_prompt       = build_system_prompt("jihad")
    contextualize_prompt = build_contextualize_prompt("jihad")
"""

import json
import os
from functools import lru_cache
from pathlib import Path

BEHAVIORS_DIR = Path("src/data/behaviors")
TEMPLATES_DIR = Path("src/data/templates")


# ── Loaders ────────────────────────────────────────────────────

@lru_cache(maxsize=10)
def _load_behavior(behavior_id: str) -> dict:
    """Load and cache a behavior JSON file."""
    path = BEHAVIORS_DIR / f"{behavior_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Behavior '{behavior_id}' not found at {path}. "
            f"Available: {[f.stem for f in BEHAVIORS_DIR.glob('*.json')]}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_base_template() -> dict:
    """Load and cache the base prompt template."""
    path = TEMPLATES_DIR / "base_prompt.json"
    if not path.exists():
        # Fallback built-in template
        return {
            "template": (
                "You are {name}, {role}.\n"
                "{language_rule}\n\n"
                "Every answer must start with '{response_prefix}'.\n\n"
                "ALLOWED TOPICS: {allowed_topics}\n\n"
                "RULES:\n{rules}\n\n"
                "The context below includes retrieved document chunks:\n"
                "{context}\n\n"
                "Answer the user question:"
            ),
            "contextualize_template": (
                "Given the chat history and the latest user message, "
                "rewrite the user's question as a standalone version "
                "that makes sense without chat history. Do not answer it."
            )
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Language rule builder ──────────────────────────────────────

def _build_language_rule(language: str) -> str:
    rules = {
        "auto": (
            "Always reply in the exact language used by the user. "
            "If the user writes in Arabic or Lebanese dialect, reply in Arabic. "
            "If they write in English, reply in English."
        ),
        "en":   "Always reply in English regardless of the user's language.",
        "ar":   "Always reply in Arabic regardless of the user's language.",
        "fr":   "Always reply in French regardless of the user's language.",
    }
    return rules.get(language, rules["auto"])


# ── Rules builder ──────────────────────────────────────────────

def _build_rules(behavior: dict, persona: dict) -> str:
    """
    Build numbered rules string from behavior,
    filling persona placeholders.
    """
    expertise_str = ", ".join(persona.get("expertise", ["general"]))
    profile_url   = persona.get("profile_url", "")
    off_topic     = persona.get("off_topic_reply", "I cannot help with that topic.")
    no_context    = persona.get("no_context_reply", "I don't have information on this topic.")

    rules = []
    for i, rule in enumerate(behavior.get("rules", []), 1):
        rule = (
            rule
            .replace("{expertise}",    expertise_str)
            .replace("{profile_url}",  profile_url)
            .replace("{off_topic}",    off_topic)
            .replace("{no_context}",   no_context)
        )
        rules.append(f"{i}. {rule}")

    return "\n".join(rules)


# ── Allowed topics builder ─────────────────────────────────────

def _build_allowed_topics(behavior: dict, persona: dict) -> str:
    topics = behavior.get("allowed_topics", ["all"])
    if topics == ["all"]:
        expertise = persona.get("expertise", [])
        return ", ".join(expertise) if expertise else "all topics"
    return ", ".join(topics)


# ── Main builders ──────────────────────────────────────────────

@lru_cache(maxsize=20)
def build_system_prompt(tenant_id: str) -> str:
    """
    Build the complete system prompt for a tenant.
    Result is cached — call invalidate_prompt_cache() after config changes.

    Args:
        tenant_id: e.g. "jihad", "azentio"

    Returns:
        Complete system prompt string with {context} placeholder intact
        for LangChain to fill at runtime.
    """
    from src.core.tenant_manager import get_full_tenant_config

    cfg      = get_full_tenant_config(tenant_id)
    persona  = cfg["persona"]
    behavior = _load_behavior(cfg["behavior"])
    template = _load_base_template()

    language_rule   = _build_language_rule(persona.get("language", "auto"))
    rules_str       = _build_rules(behavior, persona)
    allowed_topics  = _build_allowed_topics(behavior, persona)

    prompt = template["template"].format(
        name            = persona["name"],
        role            = persona["role"],
        language_rule   = language_rule,
        response_prefix = persona["response_prefix"],
        allowed_topics  = allowed_topics,
        rules           = rules_str,
        context         = "{context}",   # keep as LangChain placeholder
    )

    return prompt


@lru_cache(maxsize=20)
def build_contextualize_prompt(tenant_id: str) -> str:
    """
    Build the contextualize prompt (for history-aware retrieval).
    This rewrites the user question as standalone before retrieval.
    """
    template = _load_base_template()
    return template.get(
        "contextualize_template",
        (
            "Given the chat history and the latest user message, "
            "rewrite the user's question as a standalone version "
            "that makes sense without chat history. Do not answer it."
        )
    )


# ── Cache management ───────────────────────────────────────────

def invalidate_prompt_cache():
    """Clear all prompt caches — call after updating config or behavior files."""
    build_system_prompt.cache_clear()
    build_contextualize_prompt.cache_clear()
    _load_behavior.cache_clear()
    _load_base_template.cache_clear()
    print("Prompt cache cleared")


# ── Debug ──────────────────────────────────────────────────────

def preview_prompt(tenant_id: str):
    """Print a preview of the system prompt for a tenant."""
    prompt = build_system_prompt(tenant_id)
    print(f"\n{'='*60}")
    print(f"SYSTEM PROMPT — tenant: {tenant_id}")
    print(f"{'='*60}")
    print(prompt[:1500])
    if len(prompt) > 1500:
        print(f"\n... ({len(prompt)} total chars)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys
    tenant = sys.argv[1] if len(sys.argv) > 1 else "jihad"
    preview_prompt(tenant)
