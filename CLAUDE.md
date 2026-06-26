# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LightChat is a multi-tenant RAG SaaS API. Each tenant gets an isolated AI assistant backed by its own FAISS vector index, persona, and behavior profile. The API is served by FastAPI and uses LangChain to orchestrate retrieval + LLM generation.

## Commands

**Run the API:**
```bash
python -m uvicorn src.api.chat_api:app --reload
```

**Build the vector index for a tenant (must run before API can serve that tenant):**
```bash
python notebooks/train_local.py --tenant {tenant_id}
```

**Run both (API + any co-processes):**
```bash
python -m notebooks.start_both_any
```

**Validate a tenant config and check for missing FAISS indexes:**
```bash
python -m src.core.tenant_manager
```

**Preview the assembled system prompt for a tenant:**
```bash
python -m src.core.prompt_builder {tenant_id}
```

**Test the FAQ handler directly:**
```bash
python src/services/faq_handler.py
```

## Architecture

### Request pipeline

`POST /api/{tenant_id}/chat` → `chat_with_model()` in [src/services/chat_service.py](src/services/chat_service.py):

1. **Noise filter** — empty, numeric, or repetitive messages are routed to a canned greeting.
2. **FAQ check** — cosine similarity against `FAQ_DATABASE` in [src/data/faq.py](src/data/faq.py) using `sentence-transformers/all-MiniLM-L6-v2`. Threshold: 0.65. Hits short-circuit the LLM entirely.
3. **Greeting check** — keyword list + message length guard.
4. **RAG** — retrieve docs from FAISS+BM25 hybrid retriever, then invoke the LangChain `create_stuff_documents_chain`.
5. **Strict-RAG guard** — if `behavior == "strict_rag"` and no docs retrieved, return `no_context_reply` without calling the LLM.
6. **Hallucination validator** — post-LLM check that also falls back to `no_context_reply` if strict_rag and response lacks "don't have"-style phrases.

Every response path appends to `history` (UI tuples) and `chat_history` (LangChain messages) and logs to `logs/{tenant_id}/debug_trace.jsonl`.

### Multi-tenant config

Configs merge at three levels (tenant overrides global):

| File | Content |
|---|---|
| `config.yaml` | Global LLM defaults, embedding model, vectorstore path template |
| `tenants/{tenant_id}/config.json` | Behavior, LLM override, vector store index name, retrieval k, UI labels |
| `tenants/{tenant_id}/persona.json` | Name, role, language, response_prefix, expertise, off_topic_reply, no_context_reply |

`get_full_tenant_config(tenant_id)` in [src/core/tenant_manager.py](src/core/tenant_manager.py) merges all three and is `lru_cache`d. Call `reload_tenant(tenant_id)` or `reload_all()` after changing config files.

### LLM factory

[src/core/llm_factory.py](src/core/llm_factory.py) reads `config.yaml` and returns a LangChain LLM. Supported providers:
- `groq` — env var: `GROK_API_KEY` (note: not `GROQ_API_KEY`)
- `openai` — env var: `OPENAI_API_KEY`
- `ollama` — local Ollama; supports `think: false` flag for Qwen 3.5 via a raw HTTP wrapper `OllamaRawLLM`
- `llama_server` — OpenAI-compatible local server

### Retriever

[src/services/retriever.py](src/services/retriever.py) builds a `SimpleEnsembleRetriever` combining:
- **FAISS** (semantic, `sentence-transformers/all-MiniLM-L6-v2` embeddings, default weight 0.6)
- **BM25** (keyword, loaded from `tenants/{tenant_id}/data/`, default weight 0.4)

Set `use_hybrid: false` in a tenant's `retrieval` config to fall back to semantic-only. FAISS index path: `tenants/{tenant_id}/vector_store/{index_name}/`.

Retrievers are cached in a module-level dict. Call `invalidate_retriever_cache(tenant_id)` after rebuilding an index.

### Prompt building

[src/core/prompt_builder.py](src/core/prompt_builder.py) assembles the system prompt from:
1. `src/data/templates/base_prompt.json` — template with `{name}`, `{role}`, `{rules}`, `{context}` placeholders
2. `tenants/{tenant_id}/persona.json` — fills identity fields
3. `src/data/behaviors/{behavior_id}.json` — fills `{rules}` and `{allowed_topics}`

The `{context}` placeholder is left intact for LangChain to fill at runtime.

Available behavior profiles: `strict_rag`, `balanced_rag`, `technical_support`, `business_assistant`.

### Chains

`_build_tenant_chain(tenant_id)` in [src/services/chat_service.py](src/services/chat_service.py) is `lru_cache`d (maxsize=20). It builds and returns `(question_answer_chain, retriever, config)`. Call `invalidate_tenant_chain(tenant_id)` after any config change.

### Vector store abstraction

[src/vectorstores/unified_store_adapter.py](src/vectorstores/unified_store_adapter.py) wraps FAISS and Pinecone behind a uniform interface. Training writes to `tenants/{tenant_id}/vector_store/{index_name}/` and saves chunked data to `tenants/{tenant_id}/output_training_data/docs_chunked.json`.

## Tenant layout

```
tenants/{tenant_id}/
├── config.json          # behavior, LLM, vector store, retrieval, UI
├── persona.json         # name, role, language, expertise, reply fallbacks
├── data/                # source documents for training (md, docx, pdf, txt)
├── vector_store/        # FAISS indexes (built by train_local.py)
├── output_training_data/# chunked JSON written during training
├── ai_faq.txt           # optional tenant-specific FAQ (not used by FAQHandler directly)
└── README.md
```

## Environment variables

| Variable | Purpose |
|---|---|
| `GROK_API_KEY` | Groq API key (provider `groq`) |
| `OPENAI_API_KEY` | OpenAI API key (provider `openai`) |
| `GMAIL_USER` | Gmail address for the `/contact` endpoint |
| `GMAIL_APP_PASSWORD` | Gmail app password for SMTP |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (default includes localhost and jitechonline.com) |

## Key invariants

- A tenant's FAISS index **must exist** before the API can serve it. Missing index raises `FileNotFoundError` with a hint to run `train_local.py`.
- All `lru_cache`d objects (config, chain, retriever) must be invalidated explicitly after config changes — there is no file-watch invalidation.
- The Groq env var is `GROK_API_KEY`, not `GROQ_API_KEY`.
- `globaldata/` contains training reference documents and is not application code. `env/` is the Python virtual environment — neither should be edited.
