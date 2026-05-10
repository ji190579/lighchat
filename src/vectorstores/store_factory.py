import os
from typing import Dict, Any
from .pinecone_store import PineconeStore
# from .chroma_store import ChromaStore
from .faiss_store import FaissStore
from .base_store import BaseVectorStore

def create_vectorstore(cfg: Dict[str, Any]) -> BaseVectorStore:
    vs = cfg["vectorstore"]
    provider = vs["provider"].lower()
    dim = int(vs.get("dimension", 384))
    metric = vs.get("metric", "cosine").lower()
    index_name = vs.get("index_name", "default-index")

    if provider == "pinecone":
        pcfg = vs["pinecone"]
        api_key = pcfg.get("api_key") or os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Pinecone API key missing (config.vectorstore.pinecone.api_key or PINECONE_API_KEY).")
        return PineconeStore(
            api_key=api_key,
            index_name=index_name,
            dimension=dim,
            metric=metric,
            cloud=pcfg.get("cloud", "aws"),
            region=pcfg.get("region", "us-east-1"),
        )

    if provider == "chroma":
        ccfg = vs["chroma"]
        return ChromaStore(
            persist_directory=ccfg.get("persist_directory", "chroma_index"),
            collection=index_name,
            dimension=dim,
            metric=metric,
        )

    if provider == "faiss":
        fcfg = vs["faiss"]
        return FaissStore(
            persist_path=fcfg.get("persist_path", "faiss_index"),
            dimension=dim,
            metric=metric,
        )

    raise ValueError(f"Unsupported vector store provider: {provider}")
