from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from src.core.config import load_config


def get_embedding_model():
    """
    Initialize and return a HuggingFace embedding model.

    Returns:
        HuggingFaceEmbeddings: Initialized embedding model
    """
    config = load_config()
    model_id = config["huggingface"]["model_id"]
    cache_dir = Path(config["huggingface"]["cache_dir"])

    cache_dir.mkdir(parents=True, exist_ok=True)

    embedding_model = HuggingFaceEmbeddings(
        model_name=model_id,
        cache_folder=str(cache_dir),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    return embedding_model
