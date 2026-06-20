import os
import requests
from typing import Optional, List, Any

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM as Ollama
from langchain_core.language_models.llms import LLM
from dotenv import load_dotenv

from src.core.config import load_config


def build_llm(config: dict = None, config_path: str = "config.yaml"):
    """
      Factory that reads config.yaml and returns the appropriate LangChain LLM.

    Usage:
        llm = build_llm()                          # uses config.yaml defaults
        llm = build_llm(config_path="my_cfg.yaml") # custom path
        llm = build_llm(config=my_dict)            # pass config dict directly
    """
    if config is None:
        config = load_config(config_path)

    llm_cfg = config.get("llm", {})
    provider = llm_cfg.get("provider", "groq")

    print(f"🤖 LLM Provider: [{provider.upper()}]")
    load_dotenv()

    # ── Groq ──────────────────────────────────────────────────────────────
    if provider == "groq":
        cfg = llm_cfg["groq"]
        return ChatGroq(
            groq_api_key=os.environ["GROK_API_KEY"],
            model=cfg["model"],
            temperature=cfg.get("temperature", 0.1),
        )

    # ── OpenAI ────────────────────────────────────────────────────────────
    elif provider == "openai":
        cfg = llm_cfg["openai"]
        return ChatOpenAI(
            openai_api_key=os.environ["OPENAI_API_KEY"],
            model=cfg["model"],
            temperature=cfg.get("temperature", 0.1),
        )

    # ── Local llama-server (OpenAI-compatible) ────────────────────────────
    elif provider == "llama_server":
        cfg = llm_cfg["llama_server"]
        return ChatOpenAI(
            base_url=cfg["base_url"],
            openai_api_key="none",           # required but ignored by llama-server
            model=cfg.get("model", "local"),
            temperature=cfg.get("temperature", 0.1),
        )

    # ── Ollama (local, two models) ────────────────────────────────────────
    elif provider == "ollama":
        return _build_ollama_llm(llm_cfg["ollama"])

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Valid options: groq | openai | ollama | llama_server"
        )


def _build_ollama_llm(ollama_cfg: dict):
    """
    Builds an Ollama-backed LLM.
    Uses OllamaRawLLM wrapper when 'think' flag is needed (e.g. qwen3.5).
    """
    base_url  = ollama_cfg.get("base_url", "http://localhost:11434")
    active    = ollama_cfg.get("active_model", "coder")
    model_cfg = ollama_cfg["models"][active]

    model_name  = model_cfg["model_name"]
    temperature = model_cfg.get("temperature", 0.1)
    options     = model_cfg.get("options", {})
    think       = model_cfg.get("think", None)   # only Qwen 3.5 uses this

    print(f"   └─ Ollama model: {model_name}  |  think={think}")

    # Qwen 3.5 needs 'think' sent via raw HTTP — LangChain Ollama doesn't support it
    if think is not None:
        return OllamaRawLLM(
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            options=options,
            think=think,
        )

    # Standard LangChain Ollama wrapper for qwen2.5-coder and others
    return Ollama(
        base_url=base_url,
        model=model_name,
        temperature=temperature,
        **options,
    )


class OllamaRawLLM(LLM):
    """
    Minimal LangChain-compatible LLM that calls Ollama's /api/generate directly.
    Required for models like qwen3.5 that need the 'think: false' flag,
    which LangChain's built-in Ollama wrapper does not support.
    """
    base_url:    str            = "http://localhost:11434"
    model_name:  str            = "qwen3.5:4b-q4_K_M"
    temperature: float          = 0.1
    options:     dict           = {}
    think:       Optional[bool] = None

    @property
    def _llm_type(self) -> str:
        return "ollama_raw"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        payload = {
            "model":   self.model_name,
            "prompt":  prompt,
            "stream":  False,
            "options": {**self.options, "temperature": self.temperature},
        }
        if self.think is not None:
            payload["think"] = self.think

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]
