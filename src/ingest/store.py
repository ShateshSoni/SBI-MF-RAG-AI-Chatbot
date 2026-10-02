"""ChromaDB persistent store for embedded chunks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import register_embedding_function

from src.config import EMBEDDING_MODEL, Settings
from src.ingest.chunk import Chunk

logger = logging.getLogger(__name__)


class CollectionModelMismatch(Exception):
    """Raised when the on-disk collection was built with a different embedding model."""


@register_embedding_function
class _ExplicitEmbeddings(chromadb.EmbeddingFunction):
    def __init__(self) -> None:
        return

    @staticmethod
    def name() -> str:
        return "explicit"

    def __call__(self, input):  # noqa: A002
        raise RuntimeError("embeddings must be passed explicitly")

    def embed_query(self, input):  # noqa: A002
        raise RuntimeError("embeddings must be passed explicitly")

    @staticmethod
    def build_from_config(config):
        return _ExplicitEmbeddings()

    def get_config(self):
        return {}

    def default_space(self) -> str:
        return "cosine"


def coerce_metadata(raw: dict[str, Any]) -> dict[str, str | int | float | bool]:
    coerced: dict[str, str | int | float | bool] = {}
    for key, value in raw.items():
        if key == "page_no":
            coerced[key] = 0 if value is None else int(value)
        elif value is None:
            coerced[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            coerced[key] = value
        else:
            coerced[key] = str(value)
    return coerced


def chunk_metadata(chunk: Chunk, ingested_at: str) -> dict[str, str | int | float | bool]:
    return coerce_metadata(
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "source_url": chunk.source_url,
            "doc_title": chunk.doc_title,
            "doc_type": chunk.doc_type,
            "scheme": chunk.scheme,
            "scheme_category": chunk.scheme_category,
            "section": chunk.section,
            "page_no": chunk.page_no,
            "as_of_date": chunk.as_of_date,
            "ingested_at": ingested_at,
            "char_len": chunk.char_len,
            "token_len": chunk.token_len,
        }
    )


class Store:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        embedding = _ExplicitEmbeddings()
        name = settings.chroma_collection
        try:
            self.collection = self.client.get_collection(name=name, embedding_function=embedding)
        except Exception:
            self.collection = self.client.create_collection(
                name=name,
                metadata={
                    "hnsw:space": "cosine",
                    "embed_model": settings.embedding_model,
                    "chunk_schema": 2,
                },
                embedding_function=embedding,
            )

    def assert_model_match(self) -> None:
        stored = (self.collection.metadata or {}).get("embed_model")
        if stored != self.settings.embedding_model:
            raise CollectionModelMismatch(
                f"collection embed_model is {stored}, expected {self.settings.embedding_model}"
            )
        if stored != EMBEDDING_MODEL:
            raise CollectionModelMismatch(f"unexpected embedding model {stored}")

    def upsert_chunks(self, chunks: list[Chunk], vectors) -> None:
        if not chunks:
            return
        ingested_at = datetime.now(timezone.utc).isoformat()
        batch = 128
        for start in range(0, len(chunks), batch):
            group = chunks[start : start + batch]
            payload = vectors[start : start + batch]
            embeddings = [
                [float(value) for value in row]
                for row in payload
            ]
            self.collection.upsert(
                ids=[chunk.chunk_id for chunk in group],
                documents=[chunk.text for chunk in group],
                embeddings=embeddings,
                metadatas=[chunk_metadata(chunk, ingested_at) for chunk in group],
            )

    def delete_doc(self, doc_id: str) -> None:
        try:
            self.collection.delete(where={"doc_id": doc_id})
        except Exception:
            logger.info("no chunks to delete for %s", doc_id)

    def query(self, vector, top_k: int, where: dict | None = None) -> dict:
        kwargs: dict[str, Any] = {
            "query_embeddings": [[float(value) for value in vector]],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = self.collection.query(**kwargs)
        return {
            "documents": (result.get("documents") or [[]])[0],
            "metadatas": (result.get("metadatas") or [[]])[0],
            "distances": (result.get("distances") or [[]])[0],
        }

    def count(self) -> int:
        return int(self.collection.count())


def get_store(settings: Settings | None = None) -> Store:
    return Store(settings or Settings())
