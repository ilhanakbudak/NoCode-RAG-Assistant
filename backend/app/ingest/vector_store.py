# backend/app/ingest/vector_store.py

import logging
import os
from pathlib import Path

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    from chromadb.config import Settings

    # ---------------------------
    # Data Directory Configuration
    # ---------------------------
    # Create data directory structure
    BASE_DIR = Path(__file__).parent.parent.parent  # Points to backend/
    DATA_DIR = BASE_DIR / "data"
    CHROMA_DB_DIR = DATA_DIR / "chroma_db"
    DOCUMENTS_DIR = DATA_DIR / "documents"
    METADATA_DIR = DATA_DIR / "metadata"

    # Ensure directories exist
    for directory in [DATA_DIR, CHROMA_DB_DIR, DOCUMENTS_DIR, METADATA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

    # ---------------------------
    # ChromaDB Client with Persistent Storage
    # ---------------------------
    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_DIR),
        settings=Settings(
            anonymized_telemetry=False,  # Disable telemetry for privacy
            allow_reset=True  # Allow database reset for development
        )
    )
    logger.info(f"ChromaDB persistent client initialized at: {CHROMA_DB_DIR}")

    # Set up embedding function
    embedding_func = SentenceTransformerEmbeddingFunction()
    logger.info("SentenceTransformerEmbeddingFunction loaded")

    # ---------------------------
    # Helper Functions for Data Management
    # ---------------------------
    def get_data_directories():
        """Return all data directory paths for external access"""
        return {
            "base": BASE_DIR,
            "data": DATA_DIR,
            "chroma_db": CHROMA_DB_DIR,
            "documents": DOCUMENTS_DIR,
            "metadata": METADATA_DIR
        }

    def get_database_info():
        """Get information about the current database state"""
        try:
            collections = client.list_collections()
            total_collections = len(collections)
            
            collection_info = []
            for collection in collections:
                count = collection.count()
                collection_info.append({
                    "name": collection.name,
                    "count": count
                })
            
            return {
                "total_collections": total_collections,
                "collections": collection_info,
                "database_path": str(CHROMA_DB_DIR)
            }
        except Exception as e:
            logger.error(f"Error getting database info: {e}")
            return {"error": str(e)}

except Exception as e:
    logger.exception(f"❌ Failed to initialize vector store or embedding function: {e}")
    raise