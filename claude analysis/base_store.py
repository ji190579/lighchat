from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterable, Tuple

class BaseVectorStore(ABC):
    """Minimal common interface across providers."""

    def __init__(self, dimension: int, metric: str):
        self.dimension = dimension
        self.metric = metric

    @abstractmethod
    def create_index(self) -> None:
        ...

    @abstractmethod
    def upsert(self, ids: List[str], vectors: List[List[float]], metadatas: Optional[List[Dict[str, Any]]] = None) -> None:
        ...

    @abstractmethod
    def query(self, query_vector: List[float], top_k: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Return [(id, score, metadata), ...]"""
        ...

    @abstractmethod
    def persist(self) -> None:
        ...

    @abstractmethod
    def load(self) -> None:
        ...
