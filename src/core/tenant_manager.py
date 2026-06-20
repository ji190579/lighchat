"""
tenant_manager.py
─────────────────
Loads, validates and caches tenant configurations.
Merges global config.yaml with per-tenant config.json + persona.json.
"""

import json
import os
import yaml
from pathlib import Path
from functools import lru_cache

TENANTS_DIR  = Path("tenants")
GLOBAL_CONFIG = Path("config.yaml")


# ── Global config ──────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_global_config() -> dict:
    """Load and cache global config.yaml."""
    if not GLOBAL_CONFIG.exists():
        raise FileNotFoundError(f"Global config not found: {GLOBAL_CONFIG}")
    with open(GLOBAL_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Tenant existence ───────────────────────────────────────────
def tenant_exists(tenant_id: str) -> bool:
    """Check if tenant folder and config exist."""
    config_path = TENANTS_DIR / tenant_id / "config.json"
    return config_path.exists()


def list_tenants() -> list[str]:
    """Return list of all configured tenant IDs."""
    if not TENANTS_DIR.exists():
        return []
    return [
        d.name for d in TENANTS_DIR.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    ]


# ── Tenant config ──────────────────────────────────────────────
@lru_cache(maxsize=20)
def get_tenant_config(tenant_id: str) -> dict:
    """
    Load and cache tenant config.json.
    Raises ValueError if tenant not found.
    """
    config_path = TENANTS_DIR / tenant_id / "config.json"
    if not config_path.exists():
        raise ValueError(
            f"Tenant '{tenant_id}' not found. "
            f"Available tenants: {list_tenants()}"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=20)
def get_tenant_persona(tenant_id: str) -> dict:
    """
    Load and cache tenant persona.json.
    Returns empty dict if persona file missing.
    """
    persona_path = TENANTS_DIR / tenant_id / "persona.json"
    if not persona_path.exists():
        return {}
    with open(persona_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Merged config ──────────────────────────────────────────────
@lru_cache(maxsize=20)
def get_full_tenant_config(tenant_id: str) -> dict:
    """
    Merge global config + tenant config + persona into one dict.
    Tenant values override global defaults.

    Returns complete config with all fields guaranteed.
    """
    global_cfg = load_global_config()
    tenant_cfg = get_tenant_config(tenant_id)
    persona    = get_tenant_persona(tenant_id)

    # Resolve vector store path — fill {tenant_id} template
    vs_path = (
        global_cfg.get("vectorstore", {})
        .get("faiss", {})
        .get("persist_path", "tenants/{tenant_id}/vector_store")
        .replace("{tenant_id}", tenant_id)
    )

    # Tenant vector store overrides global
    tenant_vs = tenant_cfg.get("vector_store", {})

    # LLM — tenant can override provider and model
    global_llm  = global_cfg.get("llm", {})
    tenant_llm  = tenant_cfg.get("llm", {})
    llm_provider = tenant_llm.get("provider", global_llm.get("provider", "groq"))
    llm_model    = tenant_llm.get("model", global_llm.get(llm_provider, {}).get("model", "llama3-8b-8192"))
    llm_temp     = tenant_llm.get("temperature", global_llm.get(llm_provider, {}).get("temperature", 0.1))

    return {
        # Identity
        "tenant_id": tenant_id,
        "version":   tenant_cfg.get("version", "1.0.0"),
        "active":    tenant_cfg.get("active", True),

        # Persona
        "persona": {
            "name":            persona.get("name", tenant_id),
            "role":            persona.get("role", "AI Assistant"),
            "language":        persona.get("language", "auto"),
            "response_prefix": persona.get("response_prefix", "Assistant:"),
            "profile_url":     persona.get("profile_url", ""),
            "expertise":       persona.get("expertise", ["general"]),
            "greeting_style":  persona.get("greeting_style", "professional"),
            "off_topic_reply": persona.get("off_topic_reply", "I cannot help with that topic."),
            "no_context_reply":persona.get("no_context_reply", "I don't have information on this topic."),
        },

        # Behavior
        "behavior": tenant_cfg.get("behavior", "balanced_rag"),

        # Vector store
        "vector_store": {
            "provider":   tenant_vs.get("provider", global_cfg.get("vectorstore", {}).get("provider", "faiss")),
            "index_name": tenant_vs.get("index_name", f"{tenant_id}-index"),
            "persist_path": tenant_vs.get("persist_path", vs_path),
            "dimension":  tenant_vs.get("dimension", global_cfg.get("vectorstore", {}).get("dimension", 384)),
            "metric":     tenant_vs.get("metric", global_cfg.get("vectorstore", {}).get("metric", "cosine")),
        },

        # LLM
        "llm": {
            "provider":    llm_provider,
            "model":       llm_model,
            "temperature": llm_temp,
            "full_config": global_llm,   # full config for factory
        },

        # Retrieval
        "retrieval": {
            "k":           tenant_cfg.get("retrieval", {}).get("k", 10),
            "search_type": tenant_cfg.get("retrieval", {}).get("search_type", "similarity"),
        },

        # Embeddings (always global)
        "embeddings": {
            "model_id":  global_cfg.get("huggingface", {}).get("model_id", "sentence-transformers/all-MiniLM-L6-v2"),
            "cache_dir": global_cfg.get("huggingface", {}).get("cache_dir", ".cache/huggingface"),
        },

        # UI
        "ui": tenant_cfg.get("ui", {
            "title":       f"{tenant_id} Assistant",
            "subtitle":    "Powered by AI",
            "avatar":      "🤖",
            "theme_color": "#1a73e8",
            "position":    "bottom-right",
        }),

        # Plan + image processing
        "plan":             tenant_cfg.get("plan", "starter"),
        "image_processing": tenant_cfg.get("image_processing", "ocr"),

        # Global flags
        "re_process_data":       global_cfg.get("re_process_data", False),
        "use_query_contextuale": global_cfg.get("use_query_contextuale", False),
        "chuncking_profile":     global_cfg.get("chuncking_profile", False),
    }


# ── Cache invalidation ─────────────────────────────────────────
def reload_tenant(tenant_id: str):
    """
    Invalidate cache for a specific tenant.
    Call this after updating tenant config files.
    """
    get_tenant_config.cache_clear()
    get_tenant_persona.cache_clear()
    get_full_tenant_config.cache_clear()
    print(f"Cache cleared for tenant: {tenant_id}")


def reload_all():
    """Invalidate all caches — call after bulk config updates."""
    load_global_config.cache_clear()
    get_tenant_config.cache_clear()
    get_tenant_persona.cache_clear()
    get_full_tenant_config.cache_clear()
    print("All tenant caches cleared")


# ── Validation ─────────────────────────────────────────────────
def validate_tenant(tenant_id: str) -> list[str]:
    """
    Validate tenant config and return list of issues.
    Empty list = all good.
    """
    issues = []

    if not tenant_exists(tenant_id):
        return [f"Tenant '{tenant_id}' does not exist"]

    config  = get_tenant_config(tenant_id)
    persona = get_tenant_persona(tenant_id)

    # Required config fields
    if not config.get("behavior"):
        issues.append("Missing: behavior")
    if not config.get("vector_store", {}).get("index_name"):
        issues.append("Missing: vector_store.index_name")

    # Required persona fields
    if not persona.get("name"):
        issues.append("Missing persona: name")
    if not persona.get("response_prefix"):
        issues.append("Missing persona: response_prefix")

    # Check vector store exists on disk
    vs_path = Path(
        config.get("vector_store", {})
        .get("persist_path", f"tenants/{tenant_id}/vector_store")
    )
    index_name = config.get("vector_store", {}).get("index_name", "")
    faiss_index = vs_path / index_name / "index.faiss"

    if not faiss_index.exists():
        issues.append(
            f"FAISS index not found at {faiss_index}. "
            f"Run: python train_local.py --tenant {tenant_id}"
        )

    return issues


# ── Debug ──────────────────────────────────────────────────────
def print_tenant_summary(tenant_id: str):
    """Print a human-readable summary of tenant config."""
    try:
        cfg = get_full_tenant_config(tenant_id)
        issues = validate_tenant(tenant_id)

        print(f"\nTenant: {tenant_id}")
        print(f"  Name:      {cfg['persona']['name']}")
        print(f"  Role:      {cfg['persona']['role']}")
        print(f"  Behavior:  {cfg['behavior']}")
        print(f"  LLM:       {cfg['llm']['provider']} / {cfg['llm']['model']}")
        print(f"  Plan:      {cfg['plan']}")
        print(f"  Index:     {cfg['vector_store']['index_name']}")
        print(f"  k:         {cfg['retrieval']['k']}")
        print(f"  Issues:    {issues if issues else 'none'}")
    except Exception as e:
        print(f"  Error loading tenant: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("Tenant Manager — Status")
    print("=" * 50)

    tenants = list_tenants()
    if not tenants:
        print("No tenants found. Run: python setup_tenants.py")
    else:
        print(f"Found {len(tenants)} tenants: {tenants}")
        for t in tenants:
            print_tenant_summary(t)
