# backend/app/ingest/indexer.py

import logging
import hashlib
from typing import List, Dict, Any
from app.ingest.vector_store import client, embedding_func, get_database_info
from app.config.settings import settings

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def generate_document_hash(content: str) -> str:
    """Generate SHA-256 hash for document content to detect duplicates"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def generate_chunk_id(namespace: str, doc_hash: str, chunk_index: int) -> str:
    """Generate predictable chunk IDs for better tracking"""
    return f"{namespace}_{doc_hash[:8]}_{chunk_index:04d}"

def store_chunks(text_chunks: List[str], namespace: str, document_content: str = "") -> Dict[str, Any]:
    """
    Store text chunks in vector database with enhanced metadata tracking
    
    Args:
        text_chunks: List of text chunks to store
        namespace: Company/namespace identifier
        document_content: Full document content for hashing (optional)
    
    Returns:
        Dictionary with storage results and metadata
    """
    logger.info(f"Storing {len(text_chunks)} chunk(s) into vector DB | Namespace: '{namespace}'")
    
    # Generate document hash for duplicate detection
    doc_hash = generate_document_hash(document_content or "".join(text_chunks))
    logger.info(f"Document hash: {doc_hash[:16]}...")
    
    try:
        # Create or access collection for the given namespace
        collection = client.get_or_create_collection(
            name=namespace,
            embedding_function=embedding_func
        )
        logger.debug(f"Vector collection '{namespace}' ready")
        
        # Check for existing document by hash
        existing_chunks = []
        try:
            # Query for existing chunks with this document hash
            existing_results = collection.get(
                where={"document_hash": doc_hash}
            )
            existing_chunks = existing_results.get("ids", [])
            
            if existing_chunks:
                logger.warning(f"Found {len(existing_chunks)} existing chunks with same hash. Skipping duplicate upload.")
                return {
                    "status": "duplicate",
                    "message": "Document already exists in the database",
                    "document_hash": doc_hash,
                    "existing_chunks": len(existing_chunks),
                    "chunks_stored": 0
                }
        except Exception as e:
            logger.debug(f"No existing chunks found (this is normal for new documents): {e}")
        
        # Store new chunks
        stored_count = 0
        chunk_ids = []
        documents = []
        metadatas = []
        
        for idx, chunk in enumerate(text_chunks):
            # Skip empty or very short chunks
            if len(chunk.strip()) < 10:
                logger.debug(f"Skipping short chunk {idx}: {len(chunk)} characters")
                continue
                
            chunk_id = generate_chunk_id(namespace, doc_hash, idx)
            chunk_ids.append(chunk_id)
            documents.append(chunk.strip())
            metadatas.append({
                "document_hash": doc_hash,
                "chunk_index": idx,
                "chunk_length": len(chunk),
                "namespace": namespace
            })
            stored_count += 1
            
            logger.debug(f"Prepared chunk ID: {chunk_id} | Length: {len(chunk)} characters")
        
        # Batch insert all chunks
        if chunk_ids:
            collection.add(
                documents=documents,
                ids=chunk_ids,
                metadatas=metadatas
            )
            logger.info(f"✅ Successfully stored {stored_count} chunks into collection '{namespace}'")
        else:
            logger.warning("No valid chunks to store after filtering")
        
        # Get updated collection info
        collection_count = collection.count()
        
        return {
            "status": "success",
            "message": f"Successfully stored {stored_count} chunks",
            "document_hash": doc_hash,
            "chunks_stored": stored_count,
            "chunks_skipped": len(text_chunks) - stored_count,
            "total_in_collection": collection_count
        }
        
    except Exception as e:
        logger.exception(f"❌ Failed to store chunks in namespace '{namespace}': {e}")
        return {
            "status": "error",
            "message": f"Failed to store chunks: {str(e)}",
            "chunks_stored": 0
        }

def get_collection_stats(namespace: str) -> Dict[str, Any]:
    """Get statistics about a specific collection"""
    try:
        collection = client.get_or_create_collection(
            name=namespace,
            embedding_function=embedding_func
        )
        
        count = collection.count()
        
        # Get sample of documents to analyze
        sample_results = collection.get(limit=min(10, count))
        
        stats = {
            "namespace": namespace,
            "total_chunks": count,
            "sample_chunks": len(sample_results.get("documents", [])),
            "status": "healthy" if count > 0 else "empty"
        }
        
        # Analyze document hashes if available
        if sample_results.get("metadatas"):
            doc_hashes = set()
            for metadata in sample_results["metadatas"]:
                if metadata and "document_hash" in metadata:
                    doc_hashes.add(metadata["document_hash"])
            stats["estimated_documents"] = len(doc_hashes)
        
        return stats
        
    except Exception as e:
        logger.exception(f"Error getting collection stats for '{namespace}': {e}")
        return {
            "namespace": namespace,
            "status": "error",
            "error": str(e)
        }

def delete_document_chunks(namespace: str, document_hash: str) -> Dict[str, Any]:
    """Delete all chunks belonging to a specific document"""
    logger.info(f"Deleting document chunks | Namespace: {namespace} | Hash: {document_hash[:16]}...")
    
    try:
        collection = client.get_or_create_collection(
            name=namespace,
            embedding_function=embedding_func
        )
        
        # Find all chunks with this document hash
        results = collection.get(
            where={"document_hash": document_hash}
        )
        
        chunk_ids = results.get("ids", [])
        
        if not chunk_ids:
            logger.warning(f"No chunks found for document hash {document_hash[:16]}...")
            return {
                "status": "not_found",
                "message": "No chunks found for this document",
                "deleted_count": 0
            }
        
        # Delete the chunks
        collection.delete(ids=chunk_ids)
        
        # Check if collection is empty after deletion
        remaining_count = collection.count()
        
        logger.info(f"🗑️ Deleted {len(chunk_ids)} chunks for document {document_hash[:16]}... | Remaining in collection: {remaining_count}")
        
        return {
            "status": "success",
            "message": f"Deleted {len(chunk_ids)} chunks",
            "deleted_count": len(chunk_ids),
            "document_hash": document_hash,
            "remaining_chunks_in_collection": remaining_count
        }
        
    except Exception as e:
        logger.exception(f"Error deleting document chunks: {e}")
        return {
            "status": "error",
            "message": f"Failed to delete chunks: {str(e)}",
            "deleted_count": 0
        }

def cleanup_empty_collection(namespace: str) -> Dict[str, Any]:
    """Clean up collection if it's empty (optional utility function)"""
    try:
        collection = client.get_or_create_collection(
            name=namespace,
            embedding_function=embedding_func
        )
        
        count = collection.count()
        
        if count == 0:
            # Note: ChromaDB doesn't have a direct "delete collection" in the basic client
            # But we can clear all data which effectively empties it
            logger.info(f"Collection '{namespace}' is empty after deletions")
            return {
                "status": "empty",
                "message": f"Collection '{namespace}' is now empty",
                "action": "no_action_needed"
            }
        else:
            return {
                "status": "not_empty",
                "message": f"Collection '{namespace}' still has {count} chunks",
                "remaining_count": count
            }
            
    except Exception as e:
        logger.exception(f"Error checking collection status: {e}")
        return {
            "status": "error",
            "message": f"Failed to check collection status: {str(e)}"
        }