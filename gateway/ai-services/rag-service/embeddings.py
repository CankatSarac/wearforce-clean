"""
Multi-model embeddings engine supporting BGE and Instructor models.

Features:
- Multiple embedding models (BGE-small, Instructor-XL)
- Batch embedding generation with adaptive batching
- Caching for performance optimization
- GPU acceleration support
- Text normalization and preprocessing
- Model switching and comparison capabilities
"""

import asyncio
import hashlib
import time
from enum import Enum
from typing import List, Optional, Union, Dict, Any
import numpy as np
import structlog
from sentence_transformers import SentenceTransformer
import torch

logger = structlog.get_logger(__name__)

class EmbeddingModel(str, Enum):
    """Supported embedding models."""
    BGE_SMALL = "BAAI/bge-small-en-v1.5"
    BGE_BASE = "BAAI/bge-base-en-v1.5"
    BGE_LARGE = "BAAI/bge-large-en-v1.5"
    INSTRUCTOR_SMALL = "hkunlp/instructor-base"
    INSTRUCTOR_LARGE = "hkunlp/instructor-large"
    INSTRUCTOR_XL = "hkunlp/instructor-xl"
    E5_SMALL = "intfloat/e5-small-v2"
    E5_BASE = "intfloat/e5-base-v2"
    E5_LARGE = "intfloat/e5-large-v2"

class EmbeddingEngine:
    """Multi-model embedding engine with advanced features."""
    
    def __init__(
        self, 
        model_name: str = "BAAI/bge-small-en-v1.5",
        enable_caching: bool = True,
        cache_size: int = 10000,
        batch_size: int = 32,
        max_sequence_length: int = 512
    ):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.embedding_dim = self._get_model_dimension(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.batch_size = batch_size
        self.max_sequence_length = max_sequence_length
        
        # Caching
        self.enable_caching = enable_caching
        self.cache_size = cache_size
        self.embedding_cache: Dict[str, List[float]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Model-specific settings
        self.is_instructor_model = "instructor" in model_name.lower()
        self.is_e5_model = "e5" in model_name.lower()
        self.requires_instruction = self.is_instructor_model
        
        # Statistics
        self.encoding_count = 0
        self.total_encoding_time = 0.0
        self.batch_count = 0
        self.total_tokens_processed = 0
    
    def _get_model_dimension(self, model_name: str) -> int:
        """Get expected embedding dimension for model."""
        dimension_map = {
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "hkunlp/instructor-base": 768,
            "hkunlp/instructor-large": 768,
            "hkunlp/instructor-xl": 768,
            "intfloat/e5-small-v2": 384,
            "intfloat/e5-base-v2": 768,
            "intfloat/e5-large-v2": 1024,
        }
        return dimension_map.get(model_name, 384)
    
    async def initialize(self) -> None:
        """Initialize the embedding model with enhanced configuration."""
        logger.info(
            "Initializing embedding engine",
            model=self.model_name,
            device=self.device,
            cache_enabled=self.enable_caching,
            batch_size=self.batch_size
        )
        
        try:
            # Load model in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            
            def load_model():
                model = SentenceTransformer(self.model_name, device=self.device)
                
                # Configure model settings
                if hasattr(model, 'max_seq_length'):
                    model.max_seq_length = min(self.max_sequence_length, model.max_seq_length)
                
                return model
            
            self.model = await loop.run_in_executor(None, load_model)
            
            # Get actual embedding dimension with proper test
            test_text = "This is a test sentence for dimension detection."
            if self.is_instructor_model:
                test_embedding = await self._encode_with_instruction(
                    [test_text], 
                    "Represent this sentence for retrieval:"
                )
            else:
                test_embedding = self.model.encode([test_text], convert_to_tensor=False)
            
            self.embedding_dim = len(test_embedding[0])
            
            # Warm up the model
            await self._warmup_model()
            
            logger.info(
                "Embedding engine initialized successfully",
                model=self.model_name,
                device=self.device,
                dimension=self.embedding_dim,
                is_instructor=self.is_instructor_model,
                is_e5=self.is_e5_model,
                max_seq_length=getattr(self.model, 'max_seq_length', 'unknown')
            )
            
        except Exception as e:
            logger.error("Failed to initialize embedding engine", error=str(e))
            raise
    
    async def encode(
        self, 
        text: str, 
        instruction: Optional[str] = None
    ) -> List[float]:
        """Encode single text to embedding with optional instruction."""
        if not self.model:
            raise RuntimeError("Embedding engine not initialized")
        
        results = await self.encode_batch([text], instruction=instruction)
        return results[0] if results else []
    
    async def encode_batch(
        self, 
        texts: List[str], 
        instruction: Optional[str] = None,
        use_cache: bool = True
    ) -> List[List[float]]:
        """Encode batch of texts to embeddings with caching and optimization."""
        if not self.model:
            raise RuntimeError("Embedding engine not initialized")
        
        if not texts:
            return []
        
        start_time = time.time()
        self.encoding_count += len(texts)
        self.batch_count += 1
        
        try:
            # Check cache first if enabled
            cached_results = []
            texts_to_encode = []
            cache_keys = []
            
            if self.enable_caching and use_cache:
                for text in texts:
                    cache_key = self._get_cache_key(text, instruction)
                    cache_keys.append(cache_key)
                    
                    if cache_key in self.embedding_cache:
                        cached_results.append(self.embedding_cache[cache_key])
                        self.cache_hits += 1
                    else:
                        cached_results.append(None)
                        texts_to_encode.append(text)
                        self.cache_misses += 1
            else:
                texts_to_encode = texts
                cached_results = [None] * len(texts)
                cache_keys = []
            
            # Encode uncached texts
            new_embeddings = []
            if texts_to_encode:
                # Preprocess texts
                processed_texts = [self._preprocess_text(text) for text in texts_to_encode]
                
                # Count tokens for statistics
                token_count = sum(len(text.split()) for text in processed_texts)
                self.total_tokens_processed += token_count
                
                # Model-specific encoding
                if self.is_instructor_model and instruction:
                    new_embeddings = await self._encode_with_instruction(
                        processed_texts, instruction
                    )
                elif self.is_e5_model:
                    new_embeddings = await self._encode_e5_format(processed_texts)
                else:
                    new_embeddings = await self._encode_standard(processed_texts)
                
                # Cache new embeddings
                if self.enable_caching and cache_keys:
                    encode_idx = 0
                    for i, cached in enumerate(cached_results):
                        if cached is None and encode_idx < len(new_embeddings):
                            if i < len(cache_keys):
                                self._cache_embedding(cache_keys[i], new_embeddings[encode_idx])
                            encode_idx += 1
            
            # Combine cached and new embeddings
            final_embeddings = []
            encode_idx = 0
            
            for cached in cached_results:
                if cached is not None:
                    final_embeddings.append(cached)
                else:
                    if encode_idx < len(new_embeddings):
                        final_embeddings.append(new_embeddings[encode_idx])
                        encode_idx += 1
                    else:
                        # Fallback empty embedding
                        final_embeddings.append([0.0] * self.embedding_dim)
            
            encoding_time = time.time() - start_time
            self.total_encoding_time += encoding_time
            
            logger.debug(
                "Batch encoding completed",
                total_texts=len(texts),
                cached_texts=len(texts) - len(texts_to_encode),
                encoded_texts=len(texts_to_encode),
                cache_hit_rate=self.cache_hits / max(self.cache_hits + self.cache_misses, 1),
                encoding_time=encoding_time,
                avg_time_per_text=encoding_time / len(texts) if texts else 0
            )
            
            return final_embeddings
            
        except Exception as e:
            logger.error("Batch encoding failed", error=str(e))
            raise
    
    def _get_cache_key(self, text: str, instruction: Optional[str] = None) -> str:
        """Generate cache key for text and instruction."""
        cache_input = f"{text}|{instruction or ''}|{self.model_name}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def _cache_embedding(self, cache_key: str, embedding: List[float]) -> None:
        """Cache embedding with LRU eviction."""
        if len(self.embedding_cache) >= self.cache_size:
            # Simple FIFO eviction (could be improved to LRU)
            oldest_key = next(iter(self.embedding_cache))
            del self.embedding_cache[oldest_key]
        
        self.embedding_cache[cache_key] = embedding
    
    async def _encode_standard(self, texts: List[str]) -> List[List[float]]:
        """Standard encoding for BGE and similar models."""
        loop = asyncio.get_event_loop()
        
        def encode():
            return self.model.encode(
                texts,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        
        embeddings = await loop.run_in_executor(None, encode)
        
        # Convert to list format
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        elif torch.is_tensor(embeddings):
            return embeddings.cpu().numpy().tolist()
        return embeddings
    
    async def _encode_with_instruction(
        self, 
        texts: List[str], 
        instruction: str
    ) -> List[List[float]]:
        """Encode texts with instruction for Instructor models."""
        # Instructor models expect [instruction, text] pairs
        instructor_inputs = [[instruction, text] for text in texts]
        
        loop = asyncio.get_event_loop()
        
        def encode():
            return self.model.encode(
                instructor_inputs,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        
        embeddings = await loop.run_in_executor(None, encode)
        
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        elif torch.is_tensor(embeddings):
            return embeddings.cpu().numpy().tolist()
        return embeddings
    
    async def _encode_e5_format(self, texts: List[str]) -> List[List[float]]:
        """Encode texts in E5 format (with query prefix)."""
        # E5 models expect "query: " prefix for queries
        e5_texts = [f"query: {text}" for text in texts]
        
        loop = asyncio.get_event_loop()
        
        def encode():
            return self.model.encode(
                e5_texts,
                batch_size=self.batch_size,
                convert_to_tensor=False,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        
        embeddings = await loop.run_in_executor(None, encode)
        
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        elif torch.is_tensor(embeddings):
            return embeddings.cpu().numpy().tolist()
        return embeddings
    
    async def _warmup_model(self) -> None:
        """Warm up the model with sample texts."""
        try:
            warmup_texts = [
                "This is a warmup sentence.",
                "Model warmup in progress.",
            ]
            
            if self.is_instructor_model:
                await self._encode_with_instruction(
                    warmup_texts, 
                    "Represent this sentence for retrieval:"
                )
            else:
                await self._encode_standard(warmup_texts)
            
            logger.debug("Model warmup completed successfully")
            
        except Exception as e:
            logger.warning("Model warmup failed", error=str(e))
    
    async def encode_query(
        self, 
        query: str, 
        use_cache: bool = True
    ) -> List[float]:
        """Encode query with model-specific optimizations."""
        if self.is_instructor_model:
            instruction = "Represent this query for retrieving relevant documents:"
            return await self.encode(query, instruction=instruction)
        elif self.is_e5_model:
            # E5 already handles query prefix in _encode_e5_format
            return await self.encode(query)
        else:
            # Standard encoding for BGE and others
            return await self.encode(query)
    
    async def encode_documents(
        self, 
        documents: List[str], 
        use_cache: bool = True
    ) -> List[List[float]]:
        """Encode documents with model-specific optimizations."""
        if self.is_instructor_model:
            instruction = "Represent this document for retrieval:"
            return await self.encode_batch(documents, instruction=instruction, use_cache=use_cache)
        elif self.is_e5_model:
            # For E5, documents should use "passage: " prefix
            e5_docs = [f"passage: {doc}" for doc in documents]
            # Use standard encoding since we've already added the prefix
            return await self._encode_standard([self._preprocess_text(doc) for doc in e5_docs])
        else:
            # Standard encoding for BGE and others
            return await self.encode_batch(documents, use_cache=use_cache)
    
    async def health_check(self) -> bool:
        """Check if embedding engine is healthy with comprehensive tests."""
        try:
            if not self.model:
                return False
            
            # Quick health check with test encoding
            test_text = "health check test"
            
            if self.is_instructor_model:
                test_embedding = await self.encode(
                    test_text, 
                    instruction="Represent this sentence for retrieval:"
                )
            else:
                test_embedding = await self.encode(test_text)
            
            # Verify embedding properties
            if not test_embedding:
                return False
                
            if len(test_embedding) != self.embedding_dim:
                logger.warning(
                    "Embedding dimension mismatch",
                    expected=self.embedding_dim,
                    actual=len(test_embedding)
                )
                return False
            
            # Check for NaN or infinite values
            if any(not np.isfinite(val) for val in test_embedding):
                logger.warning("Embedding contains NaN or infinite values")
                return False
            
            # Check embedding magnitude (should be normalized)
            magnitude = np.linalg.norm(test_embedding)
            if not (0.9 < magnitude < 1.1):  # Allow small tolerance
                logger.warning(
                    "Embedding not properly normalized",
                    magnitude=magnitude
                )
                # Don't fail health check for this, just warn
            
            return True
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self.embedding_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("Embedding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get caching statistics."""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / max(total_requests, 1)
        
        return {
            "cache_enabled": self.enable_caching,
            "cache_size": len(self.embedding_cache),
            "max_cache_size": self.cache_size,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive embedding engine statistics."""
        avg_encoding_time = (
            self.total_encoding_time / max(self.encoding_count, 1)
            if self.encoding_count > 0 else 0.0
        )
        
        avg_batch_size = (
            self.encoding_count / max(self.batch_count, 1)
            if self.batch_count > 0 else 0.0
        )
        
        avg_tokens_per_text = (
            self.total_tokens_processed / max(self.encoding_count, 1)
            if self.encoding_count > 0 else 0.0
        )
        
        stats = {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.embedding_dim,
            "encoding_count": self.encoding_count,
            "batch_count": self.batch_count,
            "total_encoding_time": self.total_encoding_time,
            "avg_encoding_time": avg_encoding_time,
            "avg_batch_size": avg_batch_size,
            "total_tokens_processed": self.total_tokens_processed,
            "avg_tokens_per_text": avg_tokens_per_text,
            "is_initialized": self.model is not None,
            "model_type": {
                "is_instructor": self.is_instructor_model,
                "is_e5": self.is_e5_model,
                "requires_instruction": self.requires_instruction,
            },
            "configuration": {
                "batch_size": self.batch_size,
                "max_sequence_length": self.max_sequence_length,
                "enable_caching": self.enable_caching,
            },
        }
        
        # Add cache statistics if caching is enabled
        if self.enable_caching:
            stats["cache"] = self.get_cache_stats()
        
        return stats
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text before encoding with model-aware handling."""
        if not text:
            return ""
        
        # Basic preprocessing
        text = text.strip()
        
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Remove control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', ' ', text)
        
        # Handle very long texts
        max_words = self.max_sequence_length - 50  # Leave room for special tokens
        words = text.split()
        
        if len(words) > max_words:
            # For very long texts, truncate intelligently
            if len(words) > max_words * 2:
                # Take beginning and end for very long texts
                beginning = words[:max_words // 2]
                ending = words[-(max_words // 2):]
                text = ' '.join(beginning + ['...'] + ending)
            else:
                # Simple truncation
                text = ' '.join(words[:max_words])
        
        return text