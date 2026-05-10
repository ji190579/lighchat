from __future__ import annotations
import os
from pathlib import Path
from typing import Any, List

from langchain_community.vectorstores import FAISS, Chroma
from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec
from .pinecone_store import PineconeStore


class _NamesWrapper:
    """Wrapper so all providers return .names() like Pinecone does."""
    def __init__(self, names_list: List[str]):
        self._names = names_list

    def names(self) -> List[str]:
        return self._names


class UnifiedStoreAdapter:
    """
    Unified interface for Pinecone (SDK v6), FAISS, and Chroma.
    - Pinecone path returns your PineconeStore (SDK wrapper).
    - FAISS/Chroma path returns their respective LangChain vectorstores.
    """

    def __init__(self, provider: str, index_name: str, cfg: dict, embeddings):
        self.provider = provider.lower()
        self.index_name = index_name
        self.cfg = cfg
        self.embeddings = embeddings
        self._pc: Pinecone | None = None

        if self.provider == "pinecone":
            api_key = (
                cfg["vectorstore"]["pinecone"].get("api_key")
                or os.getenv("PINECONE_API_KEY")
            )
            if not api_key:
                raise ValueError("Missing Pinecone API key.")
            self._pc = Pinecone(api_key=api_key)

    def list_indexes(self):
        """Return an object with .names() -> list[str] for compatibility."""
        if self.provider == "pinecone":
            assert self._pc is not None
            return _NamesWrapper(self._pc.list_indexes().names())

        if self.provider == "faiss":
            base_path = Path(self.cfg["vectorstore"]["faiss"].get("persist_path", "faiss_index"))
            # ✅ Check in the index_name subdirectory
            index_path = base_path / self.index_name
            exists = (index_path / "index.faiss").exists() and (index_path / "index.pkl").exists()
            return _NamesWrapper([self.index_name] if exists else [])

        if self.provider == "chroma":
            pdir = Path(self.cfg["vectorstore"]["chroma"].get("persist_directory", "chroma_index"))
            exists = (pdir / "chroma.sqlite").exists() or (pdir.exists() and any(pdir.iterdir()))
            return _NamesWrapper([self.index_name] if exists else [])

        raise ValueError(f"Unsupported vectorstore provider: {self.provider}")

    def from_existing_index(self, index_name: str, embeddings):
        """Connect to an existing index/collection for any backend."""
        if self.provider == "pinecone":
            dim = int(self.cfg["vectorstore"].get("dimension", 384))
            metric = self.cfg["vectorstore"].get("metric", "cosine").lower()
            cloud = self.cfg["vectorstore"]["pinecone"].get("cloud", "aws")
            region = self.cfg["vectorstore"]["pinecone"].get("region", "us-east-1")
            api_key = self.cfg["vectorstore"]["pinecone"].get("api_key") or os.getenv("PINECONE_API_KEY")

            store = PineconeStore(
                api_key=api_key,
                index_name=index_name,
                dimension=dim,
                metric=metric,
                cloud=cloud,
                region=region,
            )
            store.load()
            return store

        if self.provider == "faiss":
            base_path = Path(self.cfg["vectorstore"]["faiss"].get("persist_path", "faiss_index"))
            full_path = base_path / index_name
            
            # 🔍 DEBUG PRINTS
            print(f"🔍 DEBUG from_existing_index():")
            print(f"   - index_name param: '{index_name}'")
            print(f"   - base_path: {base_path}")
            print(f"   - full_path: {full_path}")
            print(f"   - full_path exists: {full_path.exists()}")
            print(f"   - index.faiss exists: {(full_path / 'index.faiss').exists()}")
            print(f"   - index.pkl exists: {(full_path / 'index.pkl').exists()}")
            print(f"   - About to load from: '{str(full_path)}'")
            
            return FAISS.load_local(
                str(full_path),
                embeddings,
                allow_dangerous_deserialization=True,
            )

        if self.provider == "chroma":
            pdir = self.cfg["vectorstore"]["chroma"].get("persist_directory", "chroma_index")
            return Chroma(
                collection_name=index_name,
                embedding_function=embeddings,
                persist_directory=pdir,
            )

        raise ValueError(f"Unsupported vectorstore provider: {self.provider}")

    # ✅ Move this inside the class (correct indentation)
    def upload_docs(self, docs: List[Any]):
        """
        Create/upload documents for any backend.
        Accepts: List[Document] | List[dict] | List[str]
        Returns the connected store (PineconeStore/FAISS/Chroma).
        """

        def _ensure_docs(items: List[Any]) -> List[Document]:
            if not items:
                return []
            first = items[0]
            if isinstance(first, Document):
                return items
            if isinstance(first, dict):
                out: List[Document] = []
                for i, d in enumerate(items):
                    text = d.get("text") or d.get("page_content") or ""
                    if not text:
                        continue
                    md = dict(d.get("metadata", {}))
                    for k in ("id", "source", "title", "chapter"):
                        if k in d and k not in md:
                            md[k] = d[k]
                    md.setdefault("id", d.get("id", str(i)))
                    out.append(Document(page_content=text, metadata=md))
                return out
            if isinstance(first, str):
                return [Document(page_content=s, metadata={}) for s in items]
            raise TypeError("docs must be List[Document] | List[dict] | List[str]")

        docs = _ensure_docs(docs)

        dim = int(self.cfg["vectorstore"].get("dimension", 384))
        metric = self.cfg["vectorstore"].get("metric", "cosine").lower()

        if self.provider == "pinecone":
            cloud = self.cfg["vectorstore"]["pinecone"].get("cloud", "aws")
            region = self.cfg["vectorstore"]["pinecone"].get("region", "us-east-1")
            api_key = self.cfg["vectorstore"]["pinecone"].get("api_key") or os.getenv("PINECONE_API_KEY")

            assert self._pc is not None
            names = self._pc.list_indexes().names()
            if self.index_name not in names:
                self._pc.create_index(
                    name=self.index_name,
                    dimension=dim,
                    metric=metric,
                    spec=ServerlessSpec(cloud=cloud, region=region),
                )

            store = PineconeStore(
                api_key=api_key,
                index_name=self.index_name,
                dimension=dim,
                metric=metric,
                cloud=cloud,
                region=region,
            )
            store.load()

            texts = [d.page_content for d in docs]
            ids = [d.metadata.get("id", str(i)) for i, d in enumerate(docs)]
            metadatas = [d.metadata for d in docs]
            vectors = self.embeddings.embed_documents(texts)

            store.upsert(ids=ids, vectors=vectors, metadatas=metadatas)
            return store

      
        

        if self.provider == "faiss":
            store = FAISS.from_documents(docs, self.embeddings)
            base_path = Path(self.cfg["vectorstore"]["faiss"].get("persist_path", "faiss_index"))
            # ✅ Include index_name in the path
            full_path = base_path / self.index_name
            full_path.mkdir(parents=True, exist_ok=True)
            store.save_local(str(full_path))
            return store

        if self.provider == "chroma":
            pdir = self.cfg["vectorstore"]["chroma"].get("persist_directory", "chroma_index")
            store = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                collection_name=self.index_name,
                persist_directory=pdir,
            )
            store.persist()
            return store

        raise ValueError(f"Unsupported vectorstore provider: {self.provider}")
