"""
retriever.py
────────────
Tenant-aware hybrid retriever (FAISS semantic + BM25 keyword).
Loads the correct vector store per tenant and caches it.
"""

import os
from functools import lru_cache

from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever

from src.vectorstores.unified_store_adapter import UnifiedStoreAdapter
from src.utils.embedding_utils import get_embedding_model
from src.services.document_processor import load_documents, chunk_documents


# ── Simple Ensemble Retriever (combine multiple retrievers) ────
class SimpleEnsembleRetriever(BaseRetriever):
    """Combine results from multiple retrievers with custom weights."""
    
    def __init__(self, retrievers: list, weights: list):
        """
        Args:
            retrievers: List of retrievers
            weights: List of weights (must sum to 1.0)
        """
        super().__init__()
        self.retrievers = retrievers
        self.weights = weights
        
    def _get_relevant_documents(self, query: str):
        """Get documents from all retrievers and combine with weights."""
        all_docs = []
        doc_scores = {}
        
        # Get documents from each retriever with weighted scores
        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                if hasattr(retriever, 'get_relevant_documents'):
                    docs = retriever.get_relevant_documents(query)
                else:
                    docs = retriever.invoke({"query": query} if isinstance(retriever, dict) else query)
                
                # Add weighted documents
                for i, doc in enumerate(docs):
                    doc_id = doc.page_content[:100]  # Use content as ID
                    score = weight * (1.0 / (i + 1))  # Inverse rank weighting
                    
                    if doc_id in doc_scores:
                        doc_scores[doc_id] = (doc_scores[doc_id][0], doc_scores[doc_id][1] + score)
                    else:
                        doc_scores[doc_id] = (doc, score)
                        all_docs.append(doc)
            except Exception as e:
                print(f"Warning: Retriever failed: {e}")
                continue
        
        # Sort by combined score
        sorted_docs = sorted(
            all_docs,
            key=lambda doc: doc_scores[doc.page_content[:100]][1],
            reverse=True
        )
        
        return sorted_docs
    
    async def _aget_relevant_documents(self, query: str):
        """Async version."""
        return self._get_relevant_documents(query)


# ── Embedding model (shared across all tenants) ────────────────
@lru_cache(maxsize=1)
def _get_cached_embedding_model():
    """Load embedding model once — shared across all tenants."""
    return get_embedding_model()


# ── Retriever cache ────────────────────────────────────────────
_retriever_cache: dict = {}


def setup_retriever(tenant_id: str, config: dict):
    """
    Load or create a retriever for the given tenant.

    Args:
        tenant_id: e.g. "jihad", "azentio"
        config:    full tenant config from tenant_manager.get_full_tenant_config()

    Returns:
        LangChain retriever ready to call .invoke(query)
    """
    # Return cached retriever if already loaded
    if tenant_id in _retriever_cache:
        print(f"Using cached retriever for tenant: {tenant_id}")
        return _retriever_cache[tenant_id]

    re_process_data = config.get("re_process_data", False)
    vs_config       = config.get("vector_store", {})
    provider        = vs_config.get("provider", "faiss").lower()
    index_name      = vs_config.get("index_name", f"{tenant_id}-index")
    persist_path    = vs_config.get("persist_path", f"tenants/{tenant_id}/vector_store")
    
    retrieval_cfg   = config.get("retrieval", {})
    k               = retrieval_cfg.get("k", 10)
    search_type     = retrieval_cfg.get("search_type", "similarity")
    use_hybrid      = retrieval_cfg.get("use_hybrid", True)  # Enable hybrid by default
    semantic_weight = retrieval_cfg.get("semantic_weight", 0.6)
    keyword_weight  = retrieval_cfg.get("keyword_weight", 0.4)

    # Full path to FAISS index
    faiss_store_path = os.path.join(persist_path, index_name)

    print(f"Setting up retriever for tenant: {tenant_id}")
    print(f"  Provider:   {provider}")
    print(f"  Index:      {index_name}")
    print(f"  Path:       {faiss_store_path}")
    print(f"  k:          {k}")

    embedding_model = _get_cached_embedding_model()

    # Build config compatible with UnifiedStoreAdapter
    adapter_config = _build_adapter_config(config)

    store = UnifiedStoreAdapter(
        provider,
        index_name,
        cfg=adapter_config,
        embeddings=embedding_model,
    )

    vector_store = None

    # ── FAISS (local) ──────────────────────────────────────────
    if provider == "faiss":
        if os.path.exists(faiss_store_path) and not re_process_data:
            print(f"  Loading existing FAISS index...")
            try:
                vector_store = store.from_existing_index(index_name, embedding_model)
                print(f"  Successfully loaded FAISS index")
            except Exception as e:
                print(f"  Failed to load FAISS index: {e}")
                vector_store = None

        if vector_store is None:
            raise FileNotFoundError(
                f"FAISS index not found at: {faiss_store_path}\n"
                f"Build it with: python train_local.py --tenant {tenant_id}"
            )

    # ── Cloud (Pinecone, etc.) ─────────────────────────────────
    else:
        try:
            index_names = store.list_indexes().names()
            if index_name in index_names and not re_process_data:
                print(f"  Connecting to cloud index: {index_name}")
                vector_store = store.from_existing_index(index_name, embedding_model)
            else:
                raise Exception(
                    f"Cloud index '{index_name}' does not exist. "
                    f"Build it with: python train_local.py --tenant {tenant_id}"
                )
        except Exception as e:
            raise Exception(f"Cloud vector store error: {e}")

    # ── Build retriever ────────────────────────────────────────
    # Semantic retriever (FAISS)
    semantic_retriever = vector_store.as_retriever(
        search_type=search_type,
        search_kwargs={"k": k}
    )

    # Hybrid: combine FAISS + BM25
    if use_hybrid:
        print(f"  Setting up hybrid retriever (semantic + keyword)...")
        print(f"    Weights: semantic={semantic_weight}, keyword={keyword_weight}")
        
        # Load documents for BM25
        data_path = os.path.join("tenants", tenant_id, "data")
        if not os.path.exists(data_path):
            print(f"  ⚠️  Data folder not found at {data_path}, using semantic-only retrieval")
            retriever = semantic_retriever
        else:
            try:
                # Load and chunk documents (same as training)
                docs = load_documents(data_path)
                docs_chunked = chunk_documents(
                    docs, 
                    keywords_chunk=True, 
                    summary_chunk=False, 
                    page=config.get("chuncking_profile", False)
                )
                
                # Build BM25 retriever
                bm25_retriever = BM25Retriever.from_documents(docs_chunked)
                
                # Combine with custom ensemble retriever
                retriever = SimpleEnsembleRetriever(
                    retrievers=[semantic_retriever, bm25_retriever],
                    weights=[semantic_weight, keyword_weight]
                )
                print(f"  ✅ Hybrid retriever ready (FAISS + BM25)")
            except Exception as e:
                print(f"  ⚠️  Failed to setup BM25: {e}")
                print(f"  Fallback to semantic-only retrieval")
                retriever = semantic_retriever
    else:
        print(f"  Using semantic-only retrieval")
        retriever = semantic_retriever

    # Cache it
    _retriever_cache[tenant_id] = retriever
    print(f"  Retriever ready for tenant: {tenant_id}")

    return retriever


def invalidate_retriever_cache(tenant_id: str = None):
    """
    Invalidate retriever cache.
    Call after rebuilding FAISS index for a tenant.

    Args:
        tenant_id: specific tenant to invalidate, or None for all
    """
    global _retriever_cache
    if tenant_id:
        _retriever_cache.pop(tenant_id, None)
        print(f"Retriever cache cleared for: {tenant_id}")
    else:
        _retriever_cache.clear()
        print("All retriever caches cleared")


def _build_adapter_config(tenant_config: dict) -> dict:
    """
    Build config dict compatible with UnifiedStoreAdapter.
    Maps tenant config structure to what the adapter expects.
    """
    vs = tenant_config.get("vector_store", {})

    return {
        "vectorstore": {
            "provider":   vs.get("provider", "faiss"),
            "index_name": vs.get("index_name", "default"),
            "dimension":  vs.get("dimension", 384),
            "metric":     vs.get("metric", "cosine"),
            "faiss": {
                "persist_path": vs.get("persist_path", "tenants/default/vector_store")
            },
            "pinecone": tenant_config.get("pinecone", {})
        }
    }
