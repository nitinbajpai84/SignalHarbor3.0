"""The local embedding model (BAAI/bge-small-en-v1.5, quantized ONNX, about 70 MB, through fastembed). Runs on this machine only: a
passage's text is never sent to an embedding service. The model is downloaded once from Hugging Face into `data/_models/` and loaded
lazily, once per process. If it is missing or fails to load, `embed` raises `Unavailable` and search falls back to words only; a failed
load is remembered and not retried for 10 minutes. Once the model is in the cache, Hugging Face is never contacted again (HF_HUB_OFFLINE).

Multilingual upgrade: set SH_EMBED_MODEL=intfloat/multilingual-e5-small (fastembed supports it); vectors are tied to the model
name, so after changing it run `tools/reindex_vectors.py <company> --all`.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import numpy as np

MODEL = os.environ.get("SH_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
CACHE = Path(__file__).resolve().parents[2] / "data" / "_models"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: " if "bge" in MODEL else "query: "
PASSAGE_PREFIX = "" if "bge" in MODEL else "passage: "
_lock, _enc, _model = threading.Lock(), threading.Lock(), None  # _lock: loading; _enc: one batch encode at a time
_failed: float | None = None  # when the model last failed to load; no retry for RETRY_AFTER seconds (never a download per call)
RETRY_AFTER, BATCH = 600, 64


class Unavailable(RuntimeError):
    """The embedding model cannot be used (not downloaded, not installed, failed to load)."""


def _load():
    global _model, _failed
    with _lock:
        if _model is None:
            if _failed is not None and time.monotonic() - _failed < RETRY_AFTER:
                raise Unavailable("the embedding model failed to load; not retrying yet")
            try:
                if any(CACHE.glob("models--*/snapshots/*")):
                    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # downloaded once: never go to the network again (before fastembed is imported)
                from fastembed import TextEmbedding
                CACHE.mkdir(parents=True, exist_ok=True)
                _model = TextEmbedding(MODEL, cache_dir=str(CACHE))
            except Exception as e:  # noqa: BLE001 - any failure means words-only search
                _failed = time.monotonic()
                raise Unavailable(str(e)[:200]) from e
        return _model


def embed(texts: list[str], query: bool = False) -> np.ndarray:
    """float32, one unit-length row per text. Encoded in batches, the lock released between them, so a question's embedding
    never waits behind a whole file."""
    m = _load()
    pre = QUERY_PREFIX if query else PASSAGE_PREFIX
    parts = []
    try:
        for i in range(0, len(texts), BATCH):
            with _enc:
                parts.append(np.array(list(m.embed([pre + t for t in texts[i:i + BATCH]])), dtype=np.float32))
        v = np.concatenate(parts) if parts else np.zeros((0, 1), np.float32)
    except Exception as e:  # noqa: BLE001
        raise Unavailable(str(e)[:200]) from e
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
