"""Shared MiniLM encoder used for chunks and, later, questions."""

from __future__ import annotations

import numpy as np

from src.config import EMBEDDING_MODEL, EMBED_BATCH_SIZE

_ENCODER = None
_DIM_CHECKED = False


def get_encoder():
    global _ENCODER
    if _ENCODER is None:
        from sentence_transformers import SentenceTransformer

        _ENCODER = SentenceTransformer(EMBEDDING_MODEL)
    return _ENCODER


def encode(texts: list[str]) -> np.ndarray:
    global _DIM_CHECKED
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    vectors = get_encoder().encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    array = np.asarray(vectors)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if not _DIM_CHECKED:
        if array.shape[1] != 384:
            raise RuntimeError(f"expected 384-d embeddings, got {array.shape[1]}")
        _DIM_CHECKED = True
    return array
