# backend/app/routes/upload.py

import logging
import json
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, Form, Query, HTTPException
from app.ingest import parser, indexer
from app.config.settings import settings
from app.ingest.vector_store import client, get_database_info, get_data_directories
from app.ingest.quality import score_chunk_quality

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

upload_router = APIRouter()

def save_original_file(company_id: str, filename: str, file_content: bytes, document_hash: str) -> str:
    """Save original file to documents directory with hash-based naming"""
    directories = get_data_directories()
    company_dir = directories["documents"] / company_id
    company_dir.mkdir(parents=True, exist_ok=True)
    
    # Use hash in filename to handle duplicates and ensure uniqueness
    file_extension = Path(filename).suffix
    safe_filename = f"{document_hash[:12]}_{filename}"
    file_path = company_dir / safe_filename
    
    try:
        with open(file_path, 'wb') as f:
            f.write(file_content)
        logger.info(f"Saved original file: {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"Failed to save original file: {e}")
        raise

def delete_original_file(company_id: str, document_hash: str, filename: str) -> bool:
    """Delete original file from documents directory"""
    directories = get_data_directories()
    company_dir = directories["documents"] / company_id
    
    # Try to find file by hash-based name first
    file_extension = Path(filename).suffix
    hash_based_filename = f"{document_hash[:12]}_{filename}"
    hash_based_path = company_dir / hash_based_filename
    
    # Also try original filename as fallback
    original_path = company_dir / filename
    
    deleted = False
    for file_path in [hash_based_path, original_path]:
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted original file: {file_path}")
                deleted = True
            except Exception as e:
                logger.error(f"Failed to delete original file {file_path}: {e}")
    
    return deleted

def save_document_metadata(company_id: str, filename: str, file_size: int, 
                          document_hash: str, chunks_stored: int, original_file_path: str) -> None:
    """Save document metadata for tracking and management"""
    directories = get_data_directories()
    metadata_file = directories["metadata"] / f"{company_id}_documents.json"
    
    # Load existing metadata
    documents_metadata = []
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                documents_metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load existing metadata: {e}")
            documents_metadata = []
    
    # Add new document metadata
    document_info = {
        "filename": filename,
        "document_hash": document_hash,
        "file_size_bytes": file_size,
        "chunks_stored": chunks_stored,
        "upload_timestamp": datetime.now().isoformat(),
        "company_id": company_id,
        "original_file_path": original_file_path
    }
    
    # Remove any existing entry with same filename or hash (replace)
    documents_metadata = [
        doc for doc in documents_metadata 
        if doc.get("filename") != filename and doc.get("document_hash") != document_hash
    ]
    documents_metadata.append(document_info)
    
    # Save updated metadata
    try:
        with open(metadata_file, 'w') as f:
            json.dump(documents_metadata, f, indent=2)
        logger.info(f"Saved metadata for document: {filename}")
    except Exception as e:
        logger.error(f"Failed to save document metadata: {e}")

def get_company_documents(company_id: str) -> list:
    """Get list of documents for a company"""
    directories = get_data_directories()
    metadata_file = directories["metadata"] / f"{company_id}_documents.json"
    
    if not metadata_file.exists():
        return []
    
    try:
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load company documents: {e}")
        return []

def remove_document_metadata(company_id: str, document_hash: str) -> tuple[bool, dict]:
    """Remove document from metadata tracking and return the removed document info"""
    directories = get_data_directories()
    metadata_file = directories["metadata"] / f"{company_id}_documents.json"
    
    if not metadata_file.exists():
        return False, {}
    
    try:
        with open(metadata_file, 'r') as f:
            documents_metadata = json.load(f)
        
        # Find and remove the document by hash
        removed_doc = None
        original_count = len(documents_metadata)
        new_metadata = []
        
        for doc in documents_metadata:
            if doc.get("document_hash") == document_hash:
                removed_doc = doc
            else:
                new_metadata.append(doc)
        
        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(new_metadata, f, indent=2)
        
        # If no documents left, delete the metadata file
        if not new_metadata:
            metadata_file.unlink()
            logger.info(f"Deleted empty metadata file: {metadata_file}")
        
        removed = len(new_metadata) < original_count
        if removed:
            logger.info(f"Removed metadata for document with hash: {document_hash[:16]}...")
        
        return removed, removed_doc or {}
        
    except Exception as e:
        logger.error(f"Failed to remove document metadata: {e}")
        return False, {}

@upload_router.post("/")
async def upload_file(file: UploadFile, company_id: str = Form(...)):
    """Enhanced file upload with comprehensive validation and processing"""
    logger.info(f"Received upload request | File: {file.filename} | Company: {company_id}")
    
    # ---------------------------
    # Input Validation
    # ---------------------------
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if not company_id.strip():
        raise HTTPException(status_code=400, detail="Company ID is required")
    
    # Validate file type
    if not settings.is_supported_file_type(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Supported types: {settings.supported_file_types}"
        )
    
    # Read and validate file content
    try:
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        if file_size > settings.get_max_file_size_bytes():
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
            )
        
        logger.info(f"File validation passed | Size: {file_size} bytes")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error reading uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to read uploaded file")
    
    # ---------------------------
    # Temporary File Processing
    # ---------------------------
    temp_path = Path(f"/tmp/{file.filename}")
    
    try:
        # Save uploaded file temporarily
        with temp_path.open("wb") as f:
            f.write(file_content)
        logger.info(f"Saved uploaded file to temporary path: {temp_path}")
        
        # ---------------------------
        # Parse text from file
        # ---------------------------
        try:
            text_content = parser.load_file_text(temp_path)
            if not text_content.strip():
                raise HTTPException(status_code=400, detail="Document contains no readable text")
            
            logger.info(f"Extracted text from file | Length: {len(text_content)} characters")
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"File parsing error: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error during file parsing: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse document content")
        
        # ---------------------------
        # Smart Text Chunking
        # ---------------------------
        from app.ingest.chunker import chunk_document
        
        # Determine document type from file extension
        file_extension = Path(file.filename).suffix.lower()
        document_type_map = {
            '.pdf': 'pdf',
            '.docx': 'docx', 
            '.doc': 'docx',
            '.txt': 'txt'
        }
        document_type = document_type_map.get(file_extension, 'generic')
        
        logger.info(f"Using document type: {document_type} for file: {file.filename}")

        # Log chunking statistics
        chunk_types = {}
        total_words = 0
        total_sentences = 0
    
        # Use smart chunker
        try:
            chunk_results = chunk_document(
                text=text_content,
                document_type=document_type,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap
            )


            if settings.enable_chunk_quality_score:
                chunk_results = score_chunk_quality(chunk_results)
            
            if not chunk_results:
                raise HTTPException(status_code=400, detail="Document produced no valid chunks after smart processing")
            
            # Extract text from chunk results for storage
            chunks = [chunk_data["text"] for chunk_data in chunk_results]
            
            # Safety check against very large documents
            if len(chunks) > settings.max_chunks_per_document:
                logger.warning(f"Document too large, truncating from {len(chunks)} to {settings.max_chunks_per_document} chunks")
                chunks = chunks[:settings.max_chunks_per_document]
                chunk_results = chunk_results[:settings.max_chunks_per_document]
            

            
            for chunk_data in chunk_results:
                metadata = chunk_data["metadata"]
                chunk_type = metadata.get("chunk_type", "unknown")
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
                total_words += metadata.get("word_count", 0)
                total_sentences += metadata.get("sentence_count", 0)
            
            logger.info(f"Smart chunking completed | Chunks: {len(chunks)} | Types: {chunk_types} | Words: {total_words} | Sentences: {total_sentences}")
            
        except Exception as e:
            logger.exception(f"Smart chunking failed, falling back to basic chunking: {e}")
            
            # Fallback to basic chunking if smart chunker fails
            chunks = []
            start = 0
            while start < len(text_content):
                end = start + settings.chunk_size
                chunk = text_content[start:end]
                
                if len(chunk.strip()) >= settings.min_chunk_length:
                    chunks.append(chunk.strip())
                
                start = end - settings.chunk_overlap
                
                if len(chunks) > settings.max_chunks_per_document:
                    break
            
            logger.info(f"Fallback chunking completed | Chunks: {len(chunks)}")
            
            if not chunks:
                raise HTTPException(status_code=400, detail="Document produced no valid chunks")
        
        # ---------------------------
        # Store chunks in vector DB with enhanced metadata
        # ---------------------------
        storage_result = indexer.store_chunks(
            text_chunks=chunks, 
            namespace=company_id, 
            document_content=text_content
        )
        
        if storage_result["status"] == "error":
            raise HTTPException(status_code=500, detail=storage_result["message"])
        
        if storage_result["status"] == "duplicate":
            logger.info(f"Duplicate document detected: {file.filename}")
            return {
                "status": "duplicate",
                "message": storage_result["message"],
                "filename": file.filename,
                "document_hash": storage_result["document_hash"],
                "existing_chunks": storage_result["existing_chunks"]
            }
        
        # ---------------------------
        # Save original file
        # ---------------------------
        original_file_path = ""
        try:
            original_file_path = save_original_file(
                company_id=company_id,
                filename=file.filename,
                file_content=file_content,
                document_hash=storage_result["document_hash"]
            )
        except Exception as e:
            logger.warning(f"Failed to save original file (non-critical): {e}")
        
        # ---------------------------
        # Save document metadata
        # ---------------------------
        try:
            save_document_metadata(
                company_id=company_id,
                filename=file.filename,
                file_size=file_size,
                document_hash=storage_result["document_hash"],
                chunks_stored=storage_result["chunks_stored"],
                original_file_path=original_file_path
            )
        except Exception as e:
            logger.warning(f"Failed to save document metadata (non-critical): {e}")
        
        # ---------------------------
        # Success response with detailed information
        # ---------------------------
        response = {
            "status": "success",
            "message": storage_result["message"],
            "filename": file.filename,
            "file_size_bytes": file_size,
            "document_hash": storage_result["document_hash"][:16] + "...",  # Truncated for security
            "chunks_stored": storage_result["chunks_stored"],
            "chunks_skipped": storage_result.get("chunks_skipped", 0),
            "total_chunks_in_collection": storage_result.get("total_in_collection", 0),
            "original_file_saved": bool(original_file_path),
            "processing_settings": {
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "min_chunk_length": settings.min_chunk_length,
                "document_type": document_type,
                "chunking_method": "smart" if 'chunk_results' in locals() else "fallback"
            }
        }
        
        # Add chunking statistics if available
        if 'chunk_results' in locals() and chunk_results:
            chunk_stats = {
                "chunk_types": chunk_types,
                "total_words": total_words,
                "total_sentences": total_sentences,
                "avg_words_per_chunk": round(total_words / len(chunks), 1) if chunks else 0,
                "avg_sentences_per_chunk": round(total_sentences / len(chunks), 1) if chunks else 0
            }
            response["chunking_statistics"] = chunk_stats
        
        logger.info(f"✅ Upload completed successfully | File: {file.filename} | Chunks: {storage_result['chunks_stored']} | Method: {response['processing_settings']['chunking_method']}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Upload processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
                logger.info(f"Temporary file deleted: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")


@upload_router.get("/files")
def list_company_files(company_id: str = Query(...)):
    """Get list of uploaded files for a company"""
    logger.info(f"Retrieving file list for company: {company_id}")
    
    try:
        documents = get_company_documents(company_id)
        
        # Get collection statistics
        collection_stats = indexer.get_collection_stats(company_id)
        
        return {
            "company_id": company_id,
            "documents": documents,
            "total_documents": len(documents),
            "collection_stats": collection_stats
        }
        
    except Exception as e:
        logger.exception(f"Failed to retrieve file list: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve file list")


@upload_router.delete("/{filename}")
def delete_file(filename: str, company_id: str = Query(...)):
    """Enhanced file deletion with proper cleanup of all data"""
    logger.info(f"Received delete request | File: {filename} | Company: {company_id}")
    
    try:
        # Get document metadata to find the hash
        documents = get_company_documents(company_id)
        target_document = None
        
        for doc in documents:
            if doc.get("filename") == filename:
                target_document = doc
                break
        
        if not target_document:
            raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
        
        document_hash = target_document.get("document_hash")
        if not document_hash:
            raise HTTPException(status_code=500, detail="Document hash not found in metadata")
        
        # ---------------------------
        # Delete chunks from vector store
        # ---------------------------
        deletion_result = indexer.delete_document_chunks(company_id, document_hash)
        
        if deletion_result["status"] == "error":
            raise HTTPException(status_code=500, detail=deletion_result["message"])
        
        # ---------------------------
        # Delete original file
        # ---------------------------
        original_file_deleted = delete_original_file(company_id, document_hash, filename)
        
        # ---------------------------
        # Remove from metadata tracking
        # ---------------------------
        metadata_removed, removed_doc = remove_document_metadata(company_id, document_hash)
        
        response = {
            "status": "deleted",
            "filename": filename,
            "chunks_deleted": deletion_result["deleted_count"],
            "document_hash": document_hash[:16] + "...",  # Truncated for security
            "metadata_removed": metadata_removed,
            "original_file_deleted": original_file_deleted,
            "cleanup_summary": {
                "vector_chunks": deletion_result["deleted_count"],
                "metadata_entry": metadata_removed,
                "original_file": original_file_deleted
            }
        }
        
        if deletion_result["status"] == "not_found":
            response["warning"] = "No chunks found in vector store, but other data was cleaned up"
        
        logger.info(f"🗑️ File deletion completed | File: {filename} | Chunks deleted: {deletion_result['deleted_count']} | Original file deleted: {original_file_deleted}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Deletion failed for file '{filename}': {e}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@upload_router.get("/system/info")
def get_system_info():
    """Get system information and database statistics"""
    try:
        db_info = get_database_info()
        directories = get_data_directories()
        
        # Get storage usage info
        storage_info = {}
        for name, path in directories.items():
            if Path(path).exists():
                total_size = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
                file_count = len(list(Path(path).rglob('*')))
                storage_info[name] = {
                    "path": str(path),
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "file_count": file_count
                }
        
        return {
            "database_info": db_info,
            "data_directories": {k: str(v) for k, v in directories.items()},
            "storage_usage": storage_info,
            "settings": {
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "retrieval_top_k": settings.retrieval_top_k,
                "max_file_size_mb": settings.max_file_size_mb,
                "supported_file_types": settings.supported_file_types,
                "keep_original_files": True  # Now we always keep originals
            },
            "status": "healthy"
        }
        
    except Exception as e:
        logger.exception(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system information")