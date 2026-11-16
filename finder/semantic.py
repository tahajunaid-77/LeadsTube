"""Meaning fingerprints ("embeddings") for leads, so LeadTube understands that
"C-suite mentor", "leadership advisor" and "executive coach" mean much the same.

Runs locally with a small model (fastembed, BAAI/bge-small-en-v1.5, ~64 MB in
.models/). If fastembed isn't installed, every function here quietly returns
None and LeadTube works exactly as before.

What uses it
  * icp_similarity(row): how close a channel is to your ideal lead (ICP.md, section 1)
  * learning.py: leads that MEAN the same as the ones you rated Good / Low
  * keyword variations: only search phrases close to your ICP are kept
"""

import hashlib
import json
import threading

from settings import DATA_DIR, ROOT
import icp

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_DIR = ROOT / ".models"
CACHE_FILE = DATA_DIR / "embeddings.json"     # {channel_link: {"h": text hash, "v": [384 numbers]}}

_state = {"model": None, "failed": False, "cache": None, "dirty": False, "icp": None}
_lock = threading.Lock()


def _np():
    import numpy
    return numpy


def available():
    if _state["failed"]:
        return False
    try:
        import fastembed  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        _state["failed"] = True
        return False


def _model():
    if _state["model"] is None and not _state["failed"]:
        try:
            from fastembed import TextEmbedding
            _state["model"] = TextEmbedding(MODEL_NAME, cache_dir=str(MODEL_DIR))
        except Exception as e:
            print(f"  (meaning model unavailable, using words only: {e})")
            _state["failed"] = True
    return _state["model"]


def embed_texts(texts):
    """Unit-length vectors for texts (None if the model isn't available)."""
    if not available():
        return None
    with _lock:
        model = _model()
        if model is None:
            return None
        np = _np()
        vecs = np.array(list(model.embed(list(texts))), dtype="float32")
    return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)


def lead_text(row):
    """What a channel is about: description (main) + recent video titles + name."""
    recent = row.get("recent_videos") or row.get("latest_video_title") or ""
    return (f"{row.get('channel_name', '')}. {(row.get('description') or '')[:1500]}"
            f" | Recent videos: {recent[:800]}")


def _cache():
    if _state["cache"] is None:
        try:
            _state["cache"] = json.loads(CACHE_FILE.read_text())
        except Exception:
            _state["cache"] = {}
    return _state["cache"]


def save_cache():
    with _lock:
        if _state["dirty"]:
            CACHE_FILE.write_text(json.dumps(_state["cache"], separators=(",", ":")))
            _state["dirty"] = False


def lead_vectors(rows):
    """Vectors for many leads, from the cache when the text hasn't changed."""
    if not available():
        return None
    np = _np()
    cache = _cache()
    texts = [lead_text(r) for r in rows]
    hashes = [hashlib.md5(t.encode()).hexdigest()[:12] for t in texts]
    keys = [r.get("channel_link") or h for r, h in zip(rows, hashes)]
    missing = [i for i, (k, h) in enumerate(zip(keys, hashes)) if cache.get(k, {}).get("h") != h]
    if missing:
        vecs = embed_texts([texts[i] for i in missing])
        if vecs is None:
            return None
        with _lock:
            for i, v in zip(missing, vecs):
                cache[keys[i]] = {"h": hashes[i], "v": [round(float(x), 4) for x in v]}
            _state["dirty"] = True
    return np.array([cache[k]["v"] for k in keys], dtype="float32")


def lead_vector(row, cache=True):
    """One lead's vector. cache=False for channels that may be skipped (not stored)."""
    if cache:
        v = lead_vectors([row])
        return None if v is None else v[0]
    v = embed_texts([lead_text(row)])
    return None if v is None else v[0]


def icp_vector():
    if _state["icp"] is None:
        text = icp.text("ideal lead")            # ICP.md, section 1
        vec = embed_texts([text]) if text else None
        _state["icp"] = vec[0] if vec is not None else False
    return _state["icp"] if _state["icp"] is not False else None


def icp_similarity(row, vector=None):
    """0..1: how close this channel's meaning is to your ICP (None without the model)."""
    icp, v = icp_vector(), (vector if vector is not None else lead_vector(row))
    if icp is None or v is None:
        return None
    return float(v @ icp)


def phrase_icp_similarity(phrases):
    """Similarity of short search phrases to the ICP (None without the model)."""
    icp = icp_vector()
    vecs = embed_texts([f"YouTube channel about {p}" for p in phrases]) if phrases else None
    if icp is None or vecs is None:
        return None
    return [float(x) for x in vecs @ icp]
