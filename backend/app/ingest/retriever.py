# backend/app/ingest/retriever.py

import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from app.config.settings import settings
from app.ingest.vector_store import client, embedding_func

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class QueryProcessor:
    """Handles query preprocessing and expansion"""
    
    def __init__(self):
        # Common abbreviations and expansions
        self.abbreviations = {
            "info": "information",
            "docs": "documents",
            "config": "configuration",
            "admin": "administration",
            "mgmt": "management",
            "proc": "process procedure",
            "req": "requirement requirements",
            "spec": "specification specifications"
        }
        
        # Stop words to potentially remove from queries
        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could", "should"
        }
    
    def preprocess_query(self, query: str) -> Dict[str, Any]:
        """
        Preprocess and analyze the user query
        
        Args:
            query: Raw user query
            
        Returns:
            Dictionary with processed query and metadata
        """
        logger.debug(f"Preprocessing query: '{query}'")
        
        original_query = query.strip()
        processed_query = original_query.lower()
        
        # Basic cleaning
        processed_query = re.sub(r'[^\w\s]', ' ', processed_query)
        processed_query = re.sub(r'\s+', ' ', processed_query).strip()
        
        # Expand abbreviations
        expanded_terms = []
        for word in processed_query.split():
            if word in self.abbreviations:
                expanded_terms.append(self.abbreviations[word])
            else:
                expanded_terms.append(word)
        
        # Create expanded query
        expanded_query = ' '.join(expanded_terms)
        
        # Extract key terms (remove stop words for keyword matching)
        key_terms = [word for word in expanded_query.split() if word not in self.stop_words and len(word) > 2]
        
        # Detect query type/intent
        query_intent = self._detect_query_intent(original_query)
        
        result = {
            "original": original_query,
            "processed": processed_query,
            "expanded": expanded_query,
            "key_terms": key_terms,
            "intent": query_intent,
            "length": len(original_query.split())
        }
        
        logger.debug(f"Query preprocessing result: {result}")
        return result
    
    def _detect_query_intent(self, query: str) -> str:
        """Detect the intent/type of the query"""
        query_lower = query.lower()
        
        # Question patterns
        if any(word in query_lower for word in ["how", "what", "when", "where", "why", "who"]):
            return "question"
        
        # Instruction/procedure seeking
        if any(word in query_lower for word in ["how to", "steps", "process", "procedure", "instruction"]):
            return "instruction"
        
        # Definition seeking
        if any(word in query_lower for word in ["what is", "define", "definition", "meaning"]):
            return "definition"
        
        # Troubleshooting
        if any(word in query_lower for word in ["error", "problem", "issue", "fix", "solve", "troubleshoot"]):
            return "troubleshooting"
        
        # General information
        return "information"

class ContextRetriever:
    """Enhanced context retrieval with intelligent ranking"""
    
    def __init__(self):
        self.query_processor = QueryProcessor()
    
    def retrieve_context(self, query: str, namespace: str) -> str:
        """
        Enhanced context retrieval with intelligent processing
        
        Args:
            query: User query
            namespace: Company namespace
            
        Returns:
            Formatted context string
        """
        logger.info(f"Retrieving context | Namespace: {namespace} | Query: '{query}'")
        
        try:
            # Process the query
            query_data = self.query_processor.preprocess_query(query)
            
            # Get collection
            collection = client.get_or_create_collection(
                name=namespace,
                embedding_function=embedding_func,
                metadata={"hnsw:space": "cosine"}  # optional, just for clarity
            )
            logger.debug(f"Vector collection '{namespace}' loaded")
            
            # Retrieve relevant chunks
            retrieved_chunks = self._retrieve_relevant_chunks(collection, query_data)
            
            if not retrieved_chunks:
                logger.warning(f"No relevant chunks found for query: '{query}'")
                return ""
            
            # Rank and select best chunks
            ranked_chunks = self._rank_chunks(retrieved_chunks, query_data)
            
            # Format context for LLM
            formatted_context = self._format_context(ranked_chunks, query_data)
            
            logger.info(f"Context retrieval completed | Chunks used: {len(ranked_chunks)} | Context length: {len(formatted_context)}")
            return formatted_context
            
        except Exception as e:
            logger.exception(f"Error during context retrieval for query: '{query}' in namespace: '{namespace}'")
            return ""
    
    def _retrieve_relevant_chunks(self, collection, query_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve potentially relevant chunks using multiple strategies"""
        
        start = time.perf_counter()
        # Primary vector search with expanded query
        vector_results = collection.query(
            query_texts=[query_data["expanded"]],
            n_results=min(settings.retrieval_top_k * 2, 20),  # Get more candidates for ranking
            include=["documents", "metadatas", "distances"]
        )
        elapsed = time.perf_counter() - start
        logger.info(f"Vector search completed in {elapsed:.3f}s | Results: {len(vector_results.get('documents', [[]])[0])}")
        chunks = []
        
        if vector_results.get("documents") and vector_results["documents"][0]:
            documents = vector_results["documents"][0]
            metadatas = vector_results.get("metadatas", [[]])[0]
            distances = vector_results.get("distances", [[]])[0]
            
            for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas or [{}] * len(documents), distances)):
                chunk_data = {
                    "text": doc,
                    "metadata": metadata or {},
                    "vector_distance": distance,
                    "vector_rank": i,
                    "retrieval_method": "vector"
                }
                chunks.append(chunk_data)
        
        # Keyword-based filtering for additional relevance
        if query_data["key_terms"]:
            chunks = self._apply_keyword_filtering(chunks, query_data["key_terms"])
        
        logger.debug(f"Retrieved {len(chunks)} candidate chunks")
        return chunks
    
    def _apply_keyword_filtering(self, chunks: List[Dict[str, Any]], key_terms: List[str]) -> List[Dict[str, Any]]:
        """Apply keyword-based filtering and scoring"""
        
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            
            # Count keyword matches
            keyword_matches = sum(1 for term in key_terms if term in text_lower)
            chunk["keyword_matches"] = keyword_matches
            chunk["keyword_score"] = keyword_matches / len(key_terms) if key_terms else 0
            
            # Boost score for exact phrase matches
            if len(key_terms) > 1:
                phrase = " ".join(key_terms)
                if phrase in text_lower:
                    chunk["has_exact_phrase"] = True
                    chunk["keyword_score"] += 0.3
                else:
                    chunk["has_exact_phrase"] = False
        
        # Filter out chunks with very low keyword relevance (unless vector score is very high)
        filtered_chunks = []
        for chunk in chunks:
            # Keep chunk if it has good vector similarity OR good keyword match
            if chunk["keyword_matches"] > 0 or chunk["vector_distance"] < 0.5:
                filtered_chunks.append(chunk)
        
        logger.debug(f"Keyword filtering: {len(chunks)} -> {len(filtered_chunks)} chunks")
        return filtered_chunks
    
    def _rank_chunks(self, chunks: List[Dict[str, Any]], query_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank chunks based on multiple relevance factors"""
        
        if not chunks:
            return []
        
        # Calculate composite relevance scores
        for chunk in chunks:
            score = 0.0
            
            # Vector similarity (lower distance = higher relevance)
            vector_score = max(0, 1 - chunk.get("vector_distance", 1))
            score += vector_score * 0.6  # 60% weight
            
            # Keyword relevance
            keyword_score = chunk.get("keyword_score", 0)
            score += keyword_score * 0.3  # 30% weight
            
            # Metadata-based scoring
            metadata = chunk.get("metadata", {})
            
            # Prefer chunks with titles/headers for certain query types
            if query_data["intent"] in ["definition", "information"] and metadata.get("has_title"):
                score += 0.1
            
            # Prefer paragraph chunks over sentence fragments
            chunk_type = metadata.get("chunk_type", "")
            if chunk_type == "paragraph":
                score += 0.05
            elif chunk_type == "sentence_group":
                score += 0.02
            
            # Penalize very short chunks
            word_count = metadata.get("word_count", len(chunk["text"].split()))
            if word_count < 20:
                score -= 0.1
            
            # Boost longer, more comprehensive chunks for complex queries
            if query_data["length"] > 5 and word_count > 100:
                score += 0.05
            
            chunk["relevance_score"] = score
        
        # Sort by relevance score (descending)
        ranked_chunks = sorted(chunks, key=lambda x: x["relevance_score"], reverse=True)
        
        # Take top N chunks based on settings
        top_chunks = ranked_chunks[:settings.retrieval_top_k]
        
        logger.debug(f"Ranked chunks: top {len(top_chunks)} selected")
        for i, chunk in enumerate(top_chunks[:3]):  # Log top 3 for debugging
            logger.debug(f"Rank {i+1}: score={chunk['relevance_score']:.3f}, "
                        f"vector_dist={chunk.get('vector_distance', 0):.3f}, "
                        f"keywords={chunk.get('keyword_matches', 0)}")
        
        return top_chunks
    
    def _format_context(self, chunks: List[Dict[str, Any]], query_data: Dict[str, Any]) -> str:
        """Format selected chunks into context for the LLM"""
        
        if not chunks:
            return ""
        
        context_parts = []
        
        # Add query-relevant context header for complex queries
        if query_data["intent"] in ["instruction", "troubleshooting"]:
            context_parts.append("RELEVANT PROCEDURES AND INSTRUCTIONS:")
        elif query_data["intent"] == "definition":
            context_parts.append("RELEVANT DEFINITIONS AND EXPLANATIONS:")
        else:
            context_parts.append("RELEVANT INFORMATION:")
        
        # Add chunks with optional metadata
        for i, chunk in enumerate(chunks, 1):
            text = chunk["text"].strip()
            metadata = chunk.get("metadata", {})
            
            # Add section header if available
            if metadata.get("section_header"):
                context_parts.append(f"\n[Section: {metadata['section_header']}]")
            
            # Add the chunk text
            context_parts.append(f"\n{text}")
            
            # Add separator between chunks (except for last)
            if i < len(chunks):
                context_parts.append("\n" + "-" * 40)
        
        context = "\n".join(context_parts)
        
        # Trim if too long (safety check)
        max_context_length = 4000  # Reasonable limit for most LLMs
        if len(context) > max_context_length:
            context = context[:max_context_length] + "\n[...content truncated for length...]"
            logger.warning(f"Context truncated to {max_context_length} characters")
        
        return context

# Create global instance for easy import
_retriever_instance = ContextRetriever()

def retrieve_context(query: str, namespace: str) -> str:
    """
    Main function for context retrieval - maintains backward compatibility
    
    Args:
        query: User query
        namespace: Company namespace
        
    Returns:
        Formatted context string
    """
    return _retriever_instance.retrieve_context(query, namespace)