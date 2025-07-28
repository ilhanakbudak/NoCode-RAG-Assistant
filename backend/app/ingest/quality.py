# backend/app/ingest/quality.py

import logging
from typing import List, Dict
from app.config.settings import settings
from app.ingest.embedder import get_embeddings, cosine_similarity

logger = logging.getLogger(__name__)

def score_chunk_quality(chunks: List[Dict]) -> List[Dict]:
    """
    Add `chunk_quality_score` to each chunk based on cosine similarity
    with the previous chunk.
    """
    if not settings.enable_chunk_quality_score or len(chunks) < 2:
        return chunks

    logger.info("Scoring chunk quality based on adjacent cosine similarity")

    # Get all chunk texts
    texts = [chunk["text"] for chunk in chunks]
    embeddings = get_embeddings(texts)

    for i in range(1, len(chunks)):
        score = cosine_similarity(embeddings[i - 1], embeddings[i])
        chunks[i]["metadata"]["chunk_quality_score"] = round(score, 4)

        # Optionally flag poor coherence
        if score < settings.quality_score_threshold:
            chunks[i]["metadata"]["low_quality_flag"] = True
            logger.debug(f"Chunk {i} has low quality score: {score:.4f}")
        else:
            chunks[i]["metadata"]["low_quality_flag"] = False

    # First chunk has no previous comparison
    chunks[0]["metadata"]["chunk_quality_score"] = None
    chunks[0]["metadata"]["low_quality_flag"] = False

    return chunks
