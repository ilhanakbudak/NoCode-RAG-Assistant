# backend/app/ingest/chunker.py

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from app.config.settings import settings
from app.llm.tokenizer import get_tokenizer

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class ChunkMetadata:
    """Metadata for each text chunk"""
    chunk_index: int
    start_char: int
    end_char: int
    chunk_type: str  # 'paragraph', 'sentence_group', 'overflow'
    word_count: int
    sentence_count: int
    has_title: bool = False
    section_header: Optional[str] = None

class DocumentChunker:
    """Smart text chunking with semantic awareness"""
    
    def __init__(self, 
                 chunk_size: int = None,
                 chunk_overlap: int = None,
                 min_chunk_length: int = None):
        
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.min_chunk_length = min_chunk_length or settings.min_chunk_length

        # New: Token-aware configuration
        self.token_chunk_size = settings.token_chunk_size
        self.token_overlap = settings.token_chunk_overlap
        self.tokenizer = get_tokenizer()
                
        # Sentence boundary patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')
        self.paragraph_breaks = re.compile(r'\n\s*\n')
        self.section_headers = re.compile(r'^[A-Z][A-Z\s]{2,}:?\s*$|^\d+\.\s+[A-Z]|^#+\s+')
        
        logger.info(f"DocumentChunker initialized | Chunk size: {self.chunk_size} | Overlap: {self.chunk_overlap}")
    
    def chunk_text(self, text: str, document_type: str = "generic") -> List[Dict[str, Any]]:
        """
        Main chunking method that routes to appropriate strategy
        
        Args:
            text: Raw text content to chunk
            document_type: Type of document (pdf, docx, txt, generic)
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        logger.info(f"Starting chunking process | Document type: {document_type} | Text length: {len(text)}")
        
        # Preprocess text
        cleaned_text = self._preprocess_text(text)
        
        # Choose chunking strategy based on document type
        if document_type.lower() == "pdf":
            chunks = self._chunk_pdf_style(cleaned_text)
        elif document_type.lower() == "docx":
            chunks = self._chunk_structured_document(cleaned_text)
        else:
            chunks = self._chunk_generic_text(cleaned_text)
        
        # Add overlap and finalize
        final_chunks = self._add_overlap_and_validate(chunks, cleaned_text)
        
        logger.info(f"Chunking completed | Generated {len(final_chunks)} chunks")
        return final_chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens using the configured tokenizer"""
        if not self.tokenizer:
            return len(text) // 4  # fallback estimate
        return len(self.tokenizer.encode(text, add_special_tokens=False))
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize text before chunking"""
        logger.debug("Preprocessing text...")
        
        # Normalize whitespace but preserve paragraph breaks
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n[ \t]+', '\n', text)  # Remove spaces after newlines
        text = re.sub(r'[ \t]+\n', '\n', text)  # Remove spaces before newlines
        
        # Normalize paragraph breaks (max 2 consecutive newlines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove excessive spaces around punctuation
        text = re.sub(r'\s+([.!?;,:])', r'\1', text)
        text = re.sub(r'([.!?])\s+', r'\1 ', text)
        
        # Clean up common document artifacts
        text = re.sub(r'\f', '\n\n', text)  # Form feeds to paragraph breaks
        text = text.strip()
        
        logger.debug(f"Text preprocessing completed | Length: {len(text)}")
        return text
    
    def _chunk_generic_text(self, text: str) -> List[Dict[str, Any]]:
        """Default chunking strategy for generic text"""
        logger.debug("Using generic text chunking strategy")
        
        # Split by paragraphs first
        paragraphs = self.paragraph_breaks.split(text)
        chunks = []
        current_chunk = ""
        chunk_index = 0
        start_char = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < self.min_chunk_length:
                continue
            
            # If paragraph fits in current chunk by token count
            if self._count_tokens(current_chunk + "\n\n" + para) <= self.token_chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Save current chunk
                if current_chunk:
                    chunk_data = self._create_chunk_data(
                        current_chunk, chunk_index, start_char, "paragraph"
                    )
                    chunks.append(chunk_data)
                    chunk_index += 1
                    start_char += len(current_chunk)
                
                # Handle large paragraphs that exceed token limit
                if self._count_tokens(para) > self.token_chunk_size:
                    sentence_chunks = self._split_by_sentences(para, chunk_index, start_char)
                    chunks.extend(sentence_chunks)
                    chunk_index += len(sentence_chunks)
                    start_char += len(para)
                    current_chunk = ""
                else:
                    current_chunk = para
        
        # Add remaining content
        if current_chunk:
            chunk_data = self._create_chunk_data(
                current_chunk, chunk_index, start_char, "paragraph"
            )
            chunks.append(chunk_data)
        
        return chunks
    
    def _split_by_sentences(self, text: str, start_index: int, start_char: int) -> List[Dict[str, Any]]:
        """Split large text by sentences when paragraphs are too big"""
        logger.debug(f"Splitting large text by sentences | Length: {len(text)}")
        
        sentences = self.sentence_endings.split(text)
        chunks = []
        current_chunk = ""
        chunk_index = start_index
        char_offset = start_char
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Add sentence ending back (except for last sentence)
            if i < len(sentences) - 1:
                sentence += ". "
            
            # Token-aware limit
            if self._count_tokens(current_chunk + sentence) <= self.token_chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunk_data = self._create_chunk_data(
                        current_chunk, chunk_index, char_offset, "sentence_group"
                    )
                    chunks.append(chunk_data)
                    chunk_index += 1
                    char_offset += len(current_chunk)
                
                if self._count_tokens(sentence) > self.token_chunk_size:
                    overflow_chunks = self._split_overflow_text(sentence, chunk_index, char_offset)
                    chunks.extend(overflow_chunks)
                    chunk_index += len(overflow_chunks)
                    char_offset += len(sentence)
                    current_chunk = ""
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunk_data = self._create_chunk_data(
                current_chunk, chunk_index, char_offset, "sentence_group"
            )
            chunks.append(chunk_data)
        
        return chunks
    
    def _split_overflow_text(self, text: str, start_index: int, start_char: int) -> List[Dict[str, Any]]:
        """Handle text that's too long even for sentence-based chunking"""
        logger.debug(f"Handling overflow text | Length: {len(text)}")
        
        chunks = []
        chunk_index = start_index
        
        words = text.split()
        current_chunk_words = []
        for word in words:
            trial_chunk = " ".join(current_chunk_words + [word])
            if self._count_tokens(trial_chunk) <= self.token_chunk_size:
                current_chunk_words.append(word)
            else:
                chunk_text = " ".join(current_chunk_words)
                chunk_data = self._create_chunk_data(
                    chunk_text, chunk_index, start_char, "overflow"
                )
                chunks.append(chunk_data)
                chunk_index += 1
                start_char += len(chunk_text)
                current_chunk_words = [word]
        
        if current_chunk_words:
            chunk_text = " ".join(current_chunk_words)
            chunk_data = self._create_chunk_data(
                chunk_text, chunk_index, start_char, "overflow"
            )
            chunks.append(chunk_data)
        
        return chunks
    
    def _create_chunk_data(self, text: str, index: int, start_char: int, chunk_type: str) -> Dict[str, Any]:
        """Create chunk data dictionary with metadata"""
        
        word_count = len(text.split())
        sentence_count = len(self.sentence_endings.split(text))
        token_count = self._count_tokens(text)
        
        has_title = bool(self.section_headers.match(text.split('\n')[0]))
        section_header = text.split('\n')[0].strip() if has_title else None
        
        metadata = ChunkMetadata(
            chunk_index=index,
            start_char=start_char,
            end_char=start_char + len(text),
            chunk_type=chunk_type,
            word_count=word_count,
            sentence_count=sentence_count,
            has_title=has_title,
            section_header=section_header
        )
        metadata_dict = metadata.__dict__
        metadata_dict["token_count"] = token_count  # ← Add token count

        return {
            "text": text.strip(),
            "metadata": metadata_dict
        }
    
    def _chunk_structured_document(self, text: str) -> List[Dict[str, Any]]:
        """Chunking strategy for structured documents (DOCX)"""
        logger.debug("Using structured document chunking strategy")
        return self._chunk_generic_text(text)
    
    def _chunk_pdf_style(self, text: str) -> List[Dict[str, Any]]:
        """Chunking strategy optimized for PDF documents"""
        logger.debug("Using PDF-style chunking strategy")
        return self._chunk_generic_text(text)
    
    def _add_overlap_and_validate(self, chunks: List[Dict[str, Any]], original_text: str) -> List[Dict[str, Any]]:
        """Add overlap between chunks and validate results"""
        logger.debug(f"Adding overlap and validating {len(chunks)} chunks")
        
        if not chunks or self.chunk_overlap <= 0:
            return self._filter_valid_chunks(chunks)
        
        final_chunks = []
        
        for i, chunk in enumerate(chunks):
            chunk_text = chunk["text"]
            
            if i > 0 and self.chunk_overlap > 0:
                prev_chunk_text = chunks[i-1]["text"]
                overlap_text = prev_chunk_text[-self.chunk_overlap:].strip()
                overlap_text = self._find_good_overlap(overlap_text)
                
                if overlap_text:
                    chunk_text = overlap_text + " " + chunk_text
            
            updated_chunk = chunk.copy()
            updated_chunk["text"] = chunk_text
            updated_chunk["metadata"]["has_overlap"] = i > 0 and self.chunk_overlap > 0
            
            final_chunks.append(updated_chunk)
        
        return self._filter_valid_chunks(final_chunks)
    
    def _find_good_overlap(self, text: str) -> str:
        """Find a good breaking point for overlap text"""
        if len(text) < 20:
            return ""
        
        sentences = self.sentence_endings.split(text)
        if len(sentences) > 1:
            return sentences[-1].strip()
        
        words = text.split()
        if len(words) > 5:
            return " ".join(words[-5:])
        
        return text
    
    def _filter_valid_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out chunks that don't meet quality criteria"""
        valid_chunks = []
        
        for chunk in chunks:
            text = chunk["text"].strip()
            
            if len(text) < self.min_chunk_length:
                logger.debug(f"Skipping short chunk: {len(text)} characters")
                continue
            
            if len(re.sub(r'[^\w]', '', text)) < 5:
                logger.debug("Skipping chunk with minimal content")
                continue
            
            valid_chunks.append(chunk)
        
        logger.debug(f"Filtered to {len(valid_chunks)} valid chunks from {len(chunks)} total")
        return valid_chunks


# Convenience function for easy import
def chunk_document(text: str, document_type: str = "generic", 
                  chunk_size: int = None, chunk_overlap: int = None) -> List[Dict[str, Any]]:
    """
    Convenience function to chunk a document with smart text processing
    
    Args:
        text: Document text to chunk
        document_type: Type of document (pdf, docx, txt, generic)
        chunk_size: Override default chunk size
        chunk_overlap: Override default chunk overlap
        
    Returns:
        List of chunk dictionaries with text and metadata
    """
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk_text(text, document_type)
