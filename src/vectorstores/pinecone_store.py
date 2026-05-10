from typing import List, Dict, Any, Optional, Tuple
from pinecone import Pinecone, ServerlessSpec
from .base_store import BaseVectorStore

class PineconeStore(BaseVectorStore):
    def __init__(self, api_key: str, index_name: str, dimension: int, metric: str, cloud: str, region: str):
        super().__init__(dimension, metric)
        self.index_name = index_name
        self.pc = Pinecone(api_key=api_key)
        self.cloud = cloud
        self.region = region
        self.index = None

    def create_index(self) -> None:
        names = self.pc.list_indexes().names()
        if self.index_name not in names:
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )
        self.index = self.pc.Index(self.index_name)

    def upsert(self, ids: List[str], vectors: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None) -> None:
        assert self.index is not None, "Index not initialized. Call create_index() first."
        items = []
        for i, vec in enumerate(vectors):
            md = metadatas[i] if metadatas else None
            items.append({"id": ids[i], "values": vec, "metadata": md})
        self.index.upsert(items)

    def query(self, query_vector: List[float], top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        assert self.index is not None, "Index not initialized. Call create_index() first."
        res = self.index.query(vector=query_vector, top_k=top_k, include_metadata=True, filter=where)
        out = []
        for m in res["matches"]:
            out.append((m["id"], float(m["score"]), m.get("metadata", {})))
        return out

    def persist(self) -> None:
        # Managed by Pinecone (nothing to do)
        return

    def load(self) -> None:
        # Ensure handle is available
        self.index = self.pc.Index(self.index_name)
    def exists(self) -> bool:
     return self.index_name in self.pc.list_indexes().names()
