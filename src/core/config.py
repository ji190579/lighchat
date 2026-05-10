import os
import yaml
from pathlib import Path


def load_config(path="config.yaml"):
    """
    Load configuration from a YAML file (works in script or notebook).

    Args:
        path (str): Path to the YAML config file.

    Returns:
        dict: Parsed configuration dictionary.
    """
    try:
        base_dir = Path(__file__).parent.parent.parent  # Navigate to project root
        abs_path = base_dir / path

        with open(abs_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {abs_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file: {e}")


def get_embeddings_config(config):
    """Extract embeddings configuration."""
    return config.get("huggingface", {})


def get_vectorstore_config(config):
    """Extract vectorstore configuration."""
    return config.get("vectorstore", {})


def get_llm_config(config):
    """Extract LLM configuration."""
    return config.get("llm", {})
