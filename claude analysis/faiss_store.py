from typing import List, Dict, Any, Optional, Tuple
import os, json
import numpy as np
import faiss
from .base_store import BaseVectorStore

def _normalize(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
    return v / norms

class FaissStore(BaseVectorStore):
    """Simple FAISS index with id->row map + metadata sidecar."""
    def __init__(self, persist_path: str, dimension: int, metric: str):
        super().__init__(dimension, metric)
        self.persist_path = persist_path  # directory
        os.makedirs(self.persist_path, exist_ok=True)
        self.index_fp = os.path.join(self.persist_path, "faiss.index")
        self.meta_fp = os.path.join(self.persist_path, "meta.json")
        self.idmap: List[str] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.index = None

    def create_index(self) -> None:
        if self.metric == "cosine":
            self.index = faiss.IndexFlatIP(self.dimension)
        elif self.metric in ("l2", "euclidean"):
            self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)

        # Load existing if present
        if os.path.exists(self.index_fp) and os.path.getsize(self.index_fp) > 0:
            self.load()

    def upsert(self, ids: List[str], vectors: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None) -> None:
        assert self.index is not None, "Index not initialized. Call create_index() first."
        X = np.array(vectors, dtype="float32")
        if isinstance(self.index, faiss.IndexFlatIP) and self.metric == "cosine":
            X = _normalize(X)
        start_len = len(self.idmap)
        self.index.add(X)
        for i, _id in enumerate(ids):
            row = start_len + i
            if row >= len(self.idmap):
                self.idmap.append(_id)
            else:
                self.idmap[row] = _id
            if metadatas:
                self.metadata[_id] = metadatas[i]
        self.persist()

    def query(self, query_vector: List[float], top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        assert self.index is not None, "Index not initialized. Call create_index() first."
        q = np.array([query_vector], dtype="float32")
        if isinstance(self.index, faiss.IndexFlatIP) and self.metric == "cosine":
            q = _normalize(q)
        D, I = self.index.search(q, top_k)
        out: List[Tuple[str, float, Dict[str, Any]]] = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1: 
                continue
            _id = self.idmap[idx] if idx < len(self.idmap) else str(idx)
            md = self.metadata.get(_id, {})
            score = float(dist if self.metric in ("ip", "cosine") else -dist)
            # naive metadata filter (optional)
            if where:
                pass  # implement if you need it
            out.append((_id, score, md))
        return out

    def persist(self) -> None:
        assert self.index is not None
        faiss.write_index(self.index, self.index_fp)
        with open(self.meta_fp, "w", encoding="utf-8") as f:
            json.dump({"idmap": self.idmap, "metadata": self.metadata}, f)

    def load(self) -> None:
        if os.path.exists(self.index_fp):
            self.index = faiss.read_index(self.index_fp)
        if os.path.exists(self.meta_fp):
            with open(self.meta_fp, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.idmap = data.get("idmap", [])
                self.metadata = data.get("metadata", {})
    def exists(self) -> bool:
        """Return True if a saved FAISS index already exists."""
        return os.path.exists(self.index_fp) and os.path.getsize(self.index_fp) > 0    