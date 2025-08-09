"""Hybrid search engine combining semantic and keyword search."""

import asyncio
import time
from typing import List, Dict, Any, Optional
import structlog
from shared.models import SearchResult, VectorSearchType
from shared.monitoring import monitor_vector_operation

logger = structlog.get_logger(__name__)

class HybridSearchEngine:
    """Hybrid search combining dense and sparse retrieval."""
    
    def __init__(self, vector_db, embedding_engine, dense_weight=0.7, sparse_weight=0.3):
        self.vector_db = vector_db
        self.embedding_engine = embedding_engine
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        search_type: VectorSearchType = VectorSearchType.HYBRID,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        """Perform hybrid search."""
        
        if search_type == VectorSearchType.DENSE:
            return await self._dense_search(query, top_k, similarity_threshold, filters)
        elif search_type == VectorSearchType.SPARSE:
            return await self._sparse_search(query, top_k, similarity_threshold, filters)
        else:  # HYBRID
            return await self._hybrid_search(query, top_k, similarity_threshold, filters)
    
    async def _dense_search(self, query: str, top_k: int, threshold: float, filters: Optional[Dict]) -> List[SearchResult]:
        """Dense vector search using embeddings."""
        async with monitor_vector_operation("dense_search"):
            query_embedding = await self.embedding_engine.encode(query)
            
            results = await self.vector_db.search(
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=threshold,
                filter_conditions=filters,
            )
            
            return [
                SearchResult(
                    id=result["id"],
                    content=result["payload"].get("content", ""),
                    score=result["score"],
                    metadata=result["payload"],
                    source=result["payload"].get("source"),
                )
                for result in results
            ]
    
    async def _sparse_search(self, query: str, top_k: int, threshold: float, filters: Optional[Dict]) -> List[SearchResult]:
        """Sparse keyword search using TF-IDF and BM25-like scoring."""
        try:
            # Extract query terms
            query_terms = self._extract_terms(query.lower())
            if not query_terms:
                return []
            
            # Get all documents from vector database for sparse search
            # In production, this would be optimized with a separate keyword index
            all_docs = await self._get_all_documents_for_sparse_search()
            
            if not all_docs:
                return []
            
            # Calculate BM25 scores
            scored_results = []
            
            for doc in all_docs:
                score = self._calculate_bm25_score(query_terms, doc)
                if score >= threshold:
                    result = SearchResult(
                        id=doc['id'],
                        content=doc['content'],
                        score=score,
                        metadata=doc.get('metadata', {}),
                        source=doc.get('source')
                    )
                    scored_results.append(result)
            
            # Sort by score and return top_k
            scored_results.sort(key=lambda x: x.score, reverse=True)
            return scored_results[:top_k]
            
        except Exception as e:
            logger.error("Sparse search failed", error=str(e))
            return []
    
    async def _hybrid_search(self, query: str, top_k: int, threshold: float, filters: Optional[Dict]) -> List[SearchResult]:
        """Hybrid search combining dense and sparse results with improved ranking."""
        try:
            # Get results from both approaches with expanded top_k
            expansion_factor = 3
            expanded_k = min(top_k * expansion_factor, 100)
            
            dense_results, sparse_results = await asyncio.gather(
                self._dense_search(query, expanded_k, threshold * 0.6, filters),
                self._sparse_search(query, expanded_k, threshold * 0.6, filters),
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(dense_results, Exception):
                logger.error("Dense search failed", error=str(dense_results))
                dense_results = []
            
            if isinstance(sparse_results, Exception):
                logger.error("Sparse search failed", error=str(sparse_results))
                sparse_results = []
            
            # Normalize scores within each result set
            dense_results = self._normalize_scores(dense_results)
            sparse_results = self._normalize_scores(sparse_results)
            
            # Combine and re-rank results with improved algorithm
            combined_results = self._combine_results_advanced(dense_results, sparse_results, top_k, threshold)
            
            return combined_results
            
        except Exception as e:
            logger.error("Hybrid search failed", error=str(e))
            # Fallback to dense search only
            return await self._dense_search(query, top_k, threshold, filters)
    
    def _combine_results(self, dense_results: List[SearchResult], sparse_results: List[SearchResult], top_k: int) -> List[SearchResult]:
        """Combine dense and sparse results with weighted scoring."""
        result_map = {}
        
        # Add dense results
        for result in dense_results:
            weighted_score = result.score * self.dense_weight
            result_map[result.id] = SearchResult(
                id=result.id,
                content=result.content,
                score=weighted_score,
                metadata=result.metadata,
                source=result.source,
            )
        
        # Add sparse results
        for result in sparse_results:
            weighted_score = result.score * self.sparse_weight
            if result.id in result_map:
                # Combine scores
                result_map[result.id].score += weighted_score
            else:
                result_map[result.id] = SearchResult(
                    id=result.id,
                    content=result.content,
                    score=weighted_score,
                    metadata=result.metadata,
                    source=result.source,
                )
        
        # Sort by combined score and return top_k
        combined = list(result_map.values())
        combined.sort(key=lambda x: x.score, reverse=True)
        
        return combined[:top_k]
    
    def _extract_terms(self, text: str) -> List[str]:
        """Extract search terms from text."""
        import re
        # Simple tokenization and stop word removal
        terms = re.findall(r'\b\w{2,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'this',
            'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can'
        }
        
        return [term for term in terms if term not in stop_words and len(term) > 2]
    
    async def _get_all_documents_for_sparse_search(self) -> List[Dict]:
        """Get all documents for sparse search (optimized for production)."""
        try:
            # In production, this should use a proper search index
            # For now, we'll get a sample from the vector database
            search_results = await self.vector_db.scroll(
                limit=10000,  # Limit for performance
                with_payload=True
            )
            
            documents = []
            for result in search_results:
                documents.append({
                    'id': result['id'],
                    'content': result['payload'].get('content', ''),
                    'metadata': result['payload'],
                    'source': result['payload'].get('source')
                })
            
            return documents
            
        except Exception as e:
            logger.error("Failed to get documents for sparse search", error=str(e))
            return []
    
    def _calculate_bm25_score(self, query_terms: List[str], document: Dict) -> float:
        """Calculate BM25 score for document."""
        try:
            content = document.get('content', '').lower()
            doc_terms = self._extract_terms(content)
            
            if not doc_terms:
                return 0.0
            
            # BM25 parameters
            k1 = 1.2
            b = 0.75
            avgdl = 100  # Average document length (approximate)
            
            score = 0.0
            doc_length = len(doc_terms)
            
            for term in query_terms:
                if term in doc_terms:
                    # Term frequency in document
                    tf = doc_terms.count(term)
                    
                    # Inverse document frequency (simplified)
                    idf = 2.0  # Simplified IDF
                    
                    # BM25 formula
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * (doc_length / avgdl))
                    
                    score += idf * (numerator / denominator)
            
            # Normalize score to 0-1 range
            return min(score / len(query_terms), 1.0)
            
        except Exception as e:
            logger.error("BM25 score calculation failed", error=str(e))
            return 0.0
    
    def _normalize_scores(self, results: List[SearchResult]) -> List[SearchResult]:
        """Normalize scores to 0-1 range."""
        if not results:
            return results
        
        max_score = max(result.score for result in results)
        if max_score == 0:
            return results
        
        for result in results:
            result.score = result.score / max_score
        
        return results
    
    def _combine_results_advanced(
        self, 
        dense_results: List[SearchResult], 
        sparse_results: List[SearchResult], 
        top_k: int,
        threshold: float
    ) -> List[SearchResult]:
        """Advanced result combination with reciprocal rank fusion."""
        try:
            # Create result maps with rank-based scoring
            result_map = {}
            
            # Add dense results with reciprocal rank fusion
            for rank, result in enumerate(dense_results, 1):
                rrf_score = 1.0 / (rank + 60)  # RRF with k=60
                weighted_score = result.score * self.dense_weight + rrf_score * 0.1
                
                result_map[result.id] = SearchResult(
                    id=result.id,
                    content=result.content,
                    score=weighted_score,
                    metadata={
                        **result.metadata,
                        'dense_score': result.score,
                        'dense_rank': rank,
                        'sparse_score': 0.0,
                        'sparse_rank': None,
                        'fusion_type': 'dense_only',
                    },
                    source=result.source
                )
            
            # Add sparse results with reciprocal rank fusion
            for rank, result in enumerate(sparse_results, 1):
                rrf_score = 1.0 / (rank + 60)
                weighted_score = result.score * self.sparse_weight + rrf_score * 0.1
                
                if result.id in result_map:
                    # Combine scores for documents found in both searches
                    existing = result_map[result.id]
                    combined_score = existing.score + weighted_score
                    
                    # Update metadata
                    existing.score = combined_score
                    existing.metadata.update({
                        'sparse_score': result.score,
                        'sparse_rank': rank,
                        'fusion_type': 'dense_sparse',
                    })
                else:
                    # New document from sparse search only
                    result_map[result.id] = SearchResult(
                        id=result.id,
                        content=result.content,
                        score=weighted_score,
                        metadata={
                            **result.metadata,
                            'dense_score': 0.0,
                            'dense_rank': None,
                            'sparse_score': result.score,
                            'sparse_rank': rank,
                            'fusion_type': 'sparse_only',
                        },
                        source=result.source
                    )
            
            # Filter by threshold and sort
            filtered_results = [
                result for result in result_map.values() 
                if result.score >= threshold
            ]
            
            filtered_results.sort(key=lambda x: x.score, reverse=True)
            
            logger.debug(
                "Advanced hybrid search completed",
                dense_count=len(dense_results),
                sparse_count=len(sparse_results),
                combined_count=len(result_map),
                filtered_count=len(filtered_results),
                threshold=threshold
            )
            
            return filtered_results[:top_k]
            
        except Exception as e:
            logger.error("Advanced result combination failed", error=str(e))
            # Fallback to simple combination
            return self._combine_results(dense_results, sparse_results, top_k)