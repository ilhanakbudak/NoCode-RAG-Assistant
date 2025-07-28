# backend/app/config/settings.py

from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # LLM Configuration
    ollama_model: str = "mistral"
    
    # Document Processing Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200  # New: overlap between chunks
    min_chunk_length: int = 10  # New: minimum chunk length to store

    # Token-Aware Chunking
    token_chunk_size: int = 512
    token_chunk_overlap: int = 30
    tokenizer_model: str = "bert-base-uncased"

    # Chunk Quality Scoring
    enable_chunk_quality_score: bool = True
    quality_score_threshold: float = 0.85  # below this is considered "low quality"

    # Embedding Configuration
    embedding_model_name: str = "bge-large-en-v1.5"
    embedding_model_device: str = "cpu"  # or "cuda"

    # Generation Parameters
    generation_temperature: float = 0.2
    generation_top_p: float = 0.95
    generation_max_tokens: int = 512

    # Retrieval Configuration
    retrieval_top_k: int = 3
    similarity_threshold: float = 0.7  # New: minimum similarity score
    
    # File Management Configuration
    max_file_size_mb: int = 50  # New: maximum file size in MB
    supported_file_types: list = [".txt", ".pdf", ".docx"]  # New: allowed file extensions
    keep_original_files: bool = False  # New: whether to backup original files
    
    # Data Storage Configuration
    data_cleanup_enabled: bool = True  # New: enable automatic cleanup of orphaned data
    max_chunks_per_document: int = 1000  # New: safety limit for very large documents
    
    # Performance Configuration
    enable_caching: bool = True  # New: enable response caching
    cache_ttl_minutes: int = 30  # New: cache time-to-live in minutes
    
    # Development Configuration
    debug_mode: bool = False  # New: enable detailed debugging
    log_level: str = "INFO"  # New: logging level
    
    class Config:
        env_file = ".env"
        
    def get_max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    def is_supported_file_type(self, filename: str) -> bool:
        """Check if file type is supported"""
        file_extension = Path(filename).suffix.lower()
        return file_extension in self.supported_file_types
    
    def validate_chunk_size(self) -> bool:
        """Validate chunk size configuration"""
        return (
            self.chunk_size > 0 and
            self.chunk_overlap >= 0 and
            self.chunk_overlap < self.chunk_size and
            self.min_chunk_length > 0
        )

settings = Settings()
