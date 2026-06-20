"""
chat_service.py
───────────────
Tenant-aware RAG chat service.
Builds chains per tenant using prompt_builder + retriever.
"""

import os
import json
from datetime import datetime
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.messages import HumanMessage, AIMessage

from src.services.retriever import setup_retriever
from src.core.llm_factory import build_llm
from src.core.prompt_builder import build_system_prompt
from src.core.tenant_manager import get_full_tenant_config
from src.utils.chat_utils import (
    compress_chat_history,
    is_greeting_or_compliment,
    is_noise_or_greeting_message,
    random_greeting_response,
    check_faq,
)

load_dotenv()
os.makedirs("chat_logs", exist_ok=True)
os.makedirs("logs", exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# STRICT RAG VALIDATOR — Detect hallucinations
# ═══════════════════════════════════════════════════════════════

def _is_likely_hallucination(response: str, retrieved_docs: list, behavior: str) -> bool:
    """
    For strict_rag behavior, check if response seems to be hallucinated.
    
    Returns True if:
      - No documents were retrieved AND
      - Response doesn't indicate lack of knowledge
    """
    if behavior != "strict_rag":
        return False
    
    if not retrieved_docs:
        # Response should explicitly say "don't have notes" or similar
        don_t_have_phrases = [
            "don't have",
            "no information",
            "no specific notes",
            "not available",
            "cannot find",
            "i don't have"
        ]
        response_lower = response.lower()
        has_no_knowledge_phrase = any(phrase in response_lower for phrase in don_t_have_phrases)
        
        if not has_no_knowledge_phrase:
            print(f"⚠️  STRICT_RAG: Response appears to be hallucinated (no docs, no 'don't have' phrase)")
            return True
    
    return False


# ═══════════════════════════════════════════════════════════════
# CHAIN BUILDER — cached per tenant
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=20)
def _build_tenant_chain(tenant_id: str):
    """
    Build and cache the RAG chain for a tenant.
    Called once per tenant — subsequent calls return cached chain.
    """
    print(f"Building chain for tenant: {tenant_id}")

    # Load full merged config
    config = get_full_tenant_config(tenant_id)

    # Build LLM from tenant config
    from src.core.config import load_config
    global_config = load_config()
    llm = build_llm(config=global_config)

    # Build retriever for this tenant
    retriever = setup_retriever(tenant_id, config)

    # Build system prompt from tenant persona + behavior
    system_prompt = build_system_prompt(tenant_id)

    # Build prompt template
    my_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])

    # Document prompt — clean source names
    document_prompt = ChatPromptTemplate.from_template(
        "Source: {source}\n"
        "Content:\n{page_content}\n"
        "-----"
    )

    # Build QA chain
    question_answer_chain = create_stuff_documents_chain(
        llm,
        my_prompt,
        document_prompt=document_prompt
    )

    print(f"Chain ready for tenant: {tenant_id}")
    return question_answer_chain, retriever, config


def invalidate_tenant_chain(tenant_id: str):
    """Clear cached chain for a tenant — call after config changes."""
    _build_tenant_chain.cache_clear()
    print(f"Chain cache cleared for: {tenant_id}")


# ═══════════════════════════════════════════════════════════════
# RETRIEVAL HELPER
# ═══════════════════════════════════════════════════════════════

def retrieve_docs_safe(retriever, query: str) -> list:
    """Universal retriever call — handles any LangChain version."""
    try:
        return retriever.invoke(query)
    except AttributeError:
        return retriever.get_relevant_documents(query)
    except TypeError:
        return retriever.invoke({"query": query})


def _serialize_chat_history(chat_history):
    serialized = []
    for msg in chat_history or []:
        role = getattr(msg, "role", None) or getattr(msg, "type", None)
        if not role:
            role = msg.__class__.__name__.lower()
        serialized.append({
            "role": role,
            "content": getattr(msg, "content", str(msg))
        })
    return serialized


# ═══════════════════════════════════════════════════════════════
# MAIN CHAT FUNCTION
# ═══════════════════════════════════════════════════════════════

def chat_with_model(
    tenant_id: str,
    history: list,
    new_message: str,
    chat_history: list
) -> tuple[list, str]:
    """
    Main RAG chat function.

    Args:
        tenant_id:    e.g. "jihad", "azentio"
        history:      list of (user, bot) tuples for UI display
        new_message:  current user message
        chat_history: list of HumanMessage/AIMessage for LLM context

    Returns:
        (updated_history, cleared_input)
    """
    question_answer_chain, retriever, config = _build_tenant_chain(tenant_id)
    trimmed_history = compress_chat_history(chat_history, max_turns=5, max_length=300)

    print(f"\n{'='*60}")
    print(f"Incoming message: '{new_message}' | tenant: {tenant_id}")
    print(f"{'='*60}")

    # ── Noise or greeting-like filter ──────────────────────────
    if is_noise_or_greeting_message(new_message):
        persona = config.get("persona", {})
        result = random_greeting_response(
            profile_name=persona.get("name", tenant_id)
        )
        print("DEBUG: noisy or greeting-like message routed to greeting")
        history.append((new_message, result))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=result)
        ])
        _log_debug(tenant_id, new_message, [], result, chat_history)
        return history, ""

    # ── FAQ check ──────────────────────────────────────────────
    print("DEBUG: running FAQ check")
    faq_result = check_faq(new_message, threshold=0.65)

    if faq_result:
        bot_reply  = faq_result["answer"]
        confidence = faq_result["score"]
        matched_q  = faq_result["matched_question"]

        print(f"FAQ HIT! Matched: '{matched_q}' | Score: {confidence:.2%}")

        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=bot_reply)
        ])
        history.append((new_message, bot_reply))
        _log_debug(tenant_id, new_message, [], bot_reply, chat_history)
        _log_faq_usage(tenant_id, new_message, matched_q, confidence, bot_reply)
        return history, ""

    # ── Greeting check ─────────────────────────────────────────
    if is_greeting_or_compliment(new_message):
        persona = config.get("persona", {})
        result = random_greeting_response(
            profile_name=persona.get("name", tenant_id)
        )
        print("DEBUG: greeting branch selected")
        history.append((new_message, result))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=result)
        ])
        return history, ""

    # ── RAG retrieval + LLM ────────────────────────────────────
    print("DEBUG: no FAQ match, routing to RAG/LLM...")

    retrieved_docs = retrieve_docs_safe(retriever, new_message)

    # ── STRICT RAG GUARD: If no docs and behavior is strict_rag, don't call LLM ──
    if not retrieved_docs and config.get("behavior") == "strict_rag":
        persona = config.get("persona", {})
        no_context_reply = persona.get(
            "no_context_reply",
            "I don't have specific notes on this topic yet."
        )
        print(f"STRICT_RAG: No documents retrieved. Using no_context_reply.")
        history.append((new_message, no_context_reply))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=no_context_reply)
        ])
        _log_debug(tenant_id, new_message, [], no_context_reply, chat_history)
        return history, ""

    result = question_answer_chain.invoke({
        "input":        new_message,
        "chat_history": trimmed_history,
        "context":      retrieved_docs
    })

    bot_reply = result

    # ── STRICT RAG VALIDATOR: Catch hallucinations ──────────────
    if _is_likely_hallucination(bot_reply, retrieved_docs, config.get("behavior")):
        persona = config.get("persona", {})
        bot_reply = persona.get(
            "no_context_reply",
            "I don't have specific notes on this topic yet."
        )
        print(f"STRICT_RAG: Hallucination detected. Using no_context_reply instead.")

    # Debug log
    _log_debug(tenant_id, new_message, retrieved_docs, bot_reply, chat_history)

    chat_history.extend([
        HumanMessage(content=new_message),
        AIMessage(content=bot_reply)
    ])
    history.append((new_message, bot_reply))

    return history, ""


# ═══════════════════════════════════════════════════════════════
# STREAMING CHAT
# ═══════════════════════════════════════════════════════════════

def chat_with_model_stream(
    tenant_id: str,
    history: list,
    new_message: str,
    chat_history: list
):
    """
    Streaming version — yields tokens as they arrive.
    Use for real-time UI streaming responses.
    """
    question_answer_chain, retriever, config = _build_tenant_chain(tenant_id)
    trimmed_history = compress_chat_history(chat_history, max_turns=5, max_length=300)

    print(f"Streaming incoming message: '{new_message}' | tenant: {tenant_id}")
    print("DEBUG: running FAQ check")

    # ── FAQ ────────────────────────────────────────────────────
    faq_result = check_faq(new_message, threshold=0.65)
    if faq_result:
        bot_reply  = faq_result["answer"]
        confidence = faq_result["score"]
        matched_q  = faq_result["matched_question"]

        print(f"FAQ HIT! Matched: '{matched_q}' | Score: {confidence:.2%}")
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=bot_reply)
        ])
        history.append((new_message, bot_reply))
        _log_faq_usage(tenant_id, new_message, matched_q, confidence, bot_reply)
        yield bot_reply
        return

    # ── Greeting ───────────────────────────────────────────────
    if is_greeting_or_compliment(new_message):
        persona = config.get("persona", {})
        result = random_greeting_response(
            profile_name=persona.get("name", tenant_id)
        )
        print("DEBUG: greeting branch selected")
        history.append((new_message, result))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=result)
        ])
        yield result
        return

    # ── RAG streaming ──────────────────────────────────────────
    print(f"Streaming RAG for tenant: {tenant_id}")
    retrieved_docs = retrieve_docs_safe(retriever, new_message)

    # ── STRICT RAG GUARD: If no docs and behavior is strict_rag, don't call LLM ──
    if not retrieved_docs and config.get("behavior") == "strict_rag":
        persona = config.get("persona", {})
        no_context_reply = persona.get(
            "no_context_reply",
            "I don't have specific notes on this topic yet."
        )
        print(f"STRICT_RAG: No documents retrieved. Using no_context_reply.")
        history.append((new_message, no_context_reply))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=no_context_reply)
        ])
        _log_debug(tenant_id, new_message, [], no_context_reply)
        yield no_context_reply
        return

    full_response  = ""

    for chunk in question_answer_chain.stream({
        "input":        new_message,
        "chat_history": trimmed_history,
        "context":      retrieved_docs
    }):
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        full_response += token
        yield token

    # ── STRICT RAG VALIDATOR: Check for hallucinations (post-stream) ──
    if _is_likely_hallucination(full_response, retrieved_docs, config.get("behavior")):
        persona = config.get("persona", {})
        fallback_reply = persona.get(
            "no_context_reply",
            "I don't have specific notes on this topic yet."
        )
        print(f"STRICT_RAG: Hallucination detected in stream. Logging fallback instead.")
        full_response = fallback_reply

    chat_history.extend([
        HumanMessage(content=new_message),
        AIMessage(content=full_response)
    ])
    history.append((new_message, full_response))
    _log_debug(tenant_id, new_message, retrieved_docs, full_response, chat_history)


# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════

def _log_debug(tenant_id: str, question: str, docs: list, answer: str, chat_history=None):
    """Log RAG debug trace per tenant."""
    tenant_log_dir = f"logs/{tenant_id}"
    os.makedirs(tenant_log_dir, exist_ok=True)
    # best-effort: capture LLM provider/model from config
    try:
        from src.core.config import load_config
        cfg = load_config()
        llm_cfg = cfg.get("llm", {})
        provider = llm_cfg.get("provider", "")
        model_name = ""
        if provider == "groq":
            model_name = llm_cfg.get("groq", {}).get("model", "")
        elif provider == "openai":
            model_name = llm_cfg.get("openai", {}).get("model", "")
        elif provider == "ollama":
            active = llm_cfg.get("ollama", {}).get("active_model")
            model_name = llm_cfg.get("ollama", {}).get("models", {}).get(active, {}).get("model_name", "")
        elif provider == "llama_server":
            model_name = llm_cfg.get("llama_server", {}).get("model", "")
    except Exception:
        provider = None
        model_name = None

    # token counting (best-effort): try tiktoken, then HF tokenizer
    input_text = question or ""
    output_text = answer or ""
    input_tokens = None
    output_tokens = None
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model_name) if model_name else tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        input_tokens = len(enc.encode(input_text))
        output_tokens = len(enc.encode(output_text))
    except Exception:
        try:
            from transformers import AutoTokenizer
            if model_name:
                tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
            else:
                tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)
            input_tokens = len(tokenizer(input_text).get("input_ids", []))
            output_tokens = len(tokenizer(output_text).get("input_ids", []))
        except Exception:
            input_tokens = None
            output_tokens = None

    system_prompt = None
    try:
        system_prompt = build_system_prompt(tenant_id)
    except Exception as e:
        print(f"WARNING: Could not build system prompt for logging: {e}")

    payload = {
        "timestamp":    datetime.now().isoformat(),
        "tenant":       tenant_id,
        "input":        question,
        "top_k_docs":   [doc.page_content[:300] for doc in docs],
        "sources":      [doc.metadata.get("source", "") for doc in docs],
        "output":       answer,
        "chat_history": _serialize_chat_history(chat_history),
        "system_prompt": system_prompt,
        "llm_provider": provider,
        "llm_model":    model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    with open(f"{tenant_log_dir}/debug_trace.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _log_faq_usage(
    tenant_id: str,
    user_question: str,
    matched_question: str,
    confidence: float,
    answer: str
):
    """Log FAQ hits for analytics per tenant."""
    tenant_log_dir = f"logs/{tenant_id}"
    os.makedirs(tenant_log_dir, exist_ok=True)

    entry = {
        "timestamp":       datetime.now().isoformat(),
        "tenant":          tenant_id,
        "user_question":   user_question,
        "matched_faq":     matched_question,
        "confidence":      confidence,
        "answer_preview":  answer[:200],
        "source":          "FAQ"
    }

    with open(f"{tenant_log_dir}/faq_usage.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
