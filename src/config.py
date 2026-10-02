"""Runtime settings, paths, and thresholds for the FAQ assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOKENIZER_TOKEN_LIMIT = 250
TOP_K = 5
SIM_FLOOR = 0.35
CHUNK_TARGET_CHARS = 900
CHUNK_OVERLAP_CHARS = 120
MAX_QUERY_CHARS = 500
COLLECTION = "mf_faq_v1"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_BATCH_SIZE = 64

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
RAW_TEXT_DIR = DATA_DIR / "raw_text"
CACHE_DIR = DATA_DIR / "cache"
HASH_CACHE = CACHE_DIR / "hashes.json"
EMBED_CACHE = CACHE_DIR / "embedded.json"
ARTIFACTS_DIR = Path("artifacts")
LOGS_DIR = Path("logs")
CHROMA_DIR = Path("./chroma_db")
SOURCES_CSV = Path("config/sources.csv")


class ConfigurationError(Exception):
    """Raised when required configuration, such as the Groq key, is missing."""


@dataclass(frozen=True)
class Settings:
    embedding_model: str = EMBEDDING_MODEL
    llm_provider: str = "groq"
    llm_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm_temperature: float = 0.0
    # A 3-sentence answer plus a long source URL and the freshness line runs to
    # roughly 250 tokens, so anything under that truncates the citation away.
    llm_max_tokens: int = 1024
    llm_timeout_s: float = 20.0
    chunk_target_chars: int = CHUNK_TARGET_CHARS
    chunk_overlap_chars: int = CHUNK_OVERLAP_CHARS
    tokenizer_token_limit: int = TOKENIZER_TOKEN_LIMIT
    top_k: int = TOP_K
    sim_floor: float = SIM_FLOOR
    embed_batch_size: int = EMBED_BATCH_SIZE
    max_query_chars: int = MAX_QUERY_CHARS
    chroma_dir: Path = CHROMA_DIR
    chroma_collection: str = COLLECTION

    @property
    def api_key(self) -> str:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise ConfigurationError("GROQ_API_KEY missing — copy .env.example to .env")
        return key

    def ensure_dirs(self) -> None:
        for path in (DATA_DIR, RAW_DIR, RAW_TEXT_DIR, CACHE_DIR, ARTIFACTS_DIR, LOGS_DIR):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return cls(llm_model=model)
