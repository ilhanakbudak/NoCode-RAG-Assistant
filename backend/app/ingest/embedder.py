# backend/app/ingest/embedder.py

import logging
from sentence_transformers import SentenceTransformer, util
from app.config.settings import settings
import torch

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_model_cache = {}

def get_embedder():
    """
    Load or reuse a SentenceTransformer embedding model based on settings
    """
    model_name = settings.embedding_model_name
    device = settings.embedding_model_device

    if model_name in _model_cache:
        return _model_cache[model_name]

    try:
        model = SentenceTransformer(model_name, device=device)
        _model_cache[model_name] = model
        logger.info(f"Embedding model loaded: {model_name} ({device})")
        return model
    except Exception as e:
        logger.exception(f"Failed to load embedding model '{model_name}': {e}")
        raise

def get_embedding(text: str) -> list[float]:
    model = get_embedder()
    vec = model.encode([text], convert_to_tensor=True)[0]
    return torch.nn.functional.normalize(vec, p=2, dim=0).tolist()

def get_embeddings(texts: list[str]) -> list:
    model = get_embedder()
    vecs = model.encode(texts, convert_to_tensor=True)
    return torch.nn.functional.normalize(vecs, p=2, dim=1)

def cosine_similarity(vec1, vec2) -> float:
    return float(util.cos_sim(vec1, vec2).item())