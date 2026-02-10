"""
embedding.py - 本地 Embedding 模組

使用 sentence-transformers 的 bge-m3 模型（1024 維度）。
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Lazy load to avoid slow import on module load
_model = None
_model_name = "BAAI/bge-m3"


def get_model():
    """Get or initialize the embedding model (lazy loading)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {_model_name}")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
        logger.info(f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


def get_embedding_dimension() -> int:
    """Get the embedding dimension (1024 for bge-m3)."""
    return 1024


def embed_texts(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """
    Embed a list of texts.

    Args:
        texts: List of texts to embed
        batch_size: Batch size for encoding

    Returns:
        numpy array of shape (len(texts), 1024)
    """
    if not texts:
        return np.array([])

    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True  # L2 normalize for cosine similarity
    )
    return embeddings


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single text.

    Args:
        text: Text to embed

    Returns:
        numpy array of shape (1024,)
    """
    return embed_texts([text])[0]


def warmup() -> None:
    """Warmup the model by loading it and running a test embedding."""
    model = get_model()
    _ = model.encode(["測試"])
    logger.info("Embedding model warmed up")
