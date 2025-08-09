"""Enhanced citation generator with relevance scoring and source deduplication."""

import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Set, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import structlog
from shared.models import SearchResult

logger = structlog.get_logger(__name__)

class CitationFormat(str, Enum):
    """Supported citation formats."""
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    IEEE = "ieee"
    HARVARD = "harvard"
    SIMPLE = "simple"

class CitationStyle(str, Enum):
    """Citation styling options."""
    NUMBERED = "numbered"
    AUTHOR_YEAR = "author_year"
    FOOTNOTE = "footnote"
    INLINE = "inline"

@dataclass
class SourceMetadata:
    """Enhanced source metadata for citations."""
    title: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[str] = None
    source_type: Optional[str] = None  # document, webpage, database_record, etc.
    url: Optional[str] = None
    page_numbers: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    database_name: Optional[str] = None
    access_date: Optional[str] = None

@dataclass
class Citation:
    """Citation with enhanced metadata and formatting."""
    id: str
    index: int
    content_snippet: str
    source_identifier: str
    relevance_score: float
    confidence_score: float
    metadata: SourceMetadata
    formatted_citation: str
    question_context: str
    deduplication_hash: str
    created_at: datetime

class CitationGenerator:
    """Enhanced citation generator with relevance scoring and deduplication."""
    
    def __init__(
        self,
        default_format: CitationFormat = CitationFormat.SIMPLE,
        default_style: CitationStyle = CitationStyle.NUMBERED,
        max_snippet_length: int = 200,
        min_relevance_threshold: float = 0.1,
        enable_deduplication: bool = True,
        similarity_threshold: float = 0.8
    ):
        self.default_format = default_format
        self.default_style = default_style
        self.max_snippet_length = max_snippet_length
        self.min_relevance_threshold = min_relevance_threshold
        self.enable_deduplication = enable_deduplication
        self.similarity_threshold = similarity_threshold
        
        # Statistics
        self.citation_count = 0
        self.deduplication_count = 0
        self.format_usage = {format.value: 0 for format in CitationFormat}
        
        # Deduplication cache
        self.seen_citations: Set[str] = set()
        
        # Pattern matchers for source parsing
        self.url_pattern = re.compile(r'https?://[^\s]+')
        self.doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+')
        self.isbn_pattern = re.compile(r'(?:ISBN[:\s]*)?(?:\d{1,5}[- ]?)?\d{1,7}[- ]?\d{1,7}[- ]?[\dX]')
    
    async def generate_citations(
        self, 
        search_results: List[SearchResult], 
        question: str,
        format_type: Optional[CitationFormat] = None,
        style: Optional[CitationStyle] = None,
        max_citations: int = 10
    ) -> List[Citation]:
        """Generate enhanced citations from search results."""
        if not search_results:
            return []
        
        format_type = format_type or self.default_format
        style = style or self.default_style
        
        try:
            # Filter by relevance threshold
            filtered_results = [
                result for result in search_results
                if result.score >= self.min_relevance_threshold
            ][:max_citations]
            
            if not filtered_results:
                logger.warning(
                    "No search results meet minimum relevance threshold",
                    threshold=self.min_relevance_threshold,
                    max_score=max(r.score for r in search_results) if search_results else 0
                )
                return []
            
            # Calculate enhanced relevance scores
            enhanced_results = await self._enhance_relevance_scores(
                filtered_results, question
            )
            
            # Generate citations with deduplication
            citations = []
            seen_hashes = set()
            
            for i, result in enumerate(enhanced_results):
                try:
                    citation = await self._create_citation(
                        result, 
                        question, 
                        i + 1, 
                        format_type, 
                        style
                    )
                    
                    # Deduplication check
                    if self.enable_deduplication:
                        if citation.deduplication_hash in seen_hashes:
                            self.deduplication_count += 1
                            logger.debug(
                                "Duplicate citation filtered",
                                hash=citation.deduplication_hash[:8],
                                source=citation.source_identifier
                            )
                            continue
                        seen_hashes.add(citation.deduplication_hash)
                    
                    citations.append(citation)
                    self.citation_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to create citation",
                        error=str(e),
                        result_id=result.id,
                        source=result.source
                    )
                    continue
            
            # Update format usage statistics
            self.format_usage[format_type.value] += len(citations)
            
            # Re-index citations after deduplication
            for i, citation in enumerate(citations):
                citation.index = i + 1
                citation.formatted_citation = self._format_citation(
                    citation, format_type, style
                )
            
            logger.info(
                "Citations generated successfully",
                total_results=len(search_results),
                filtered_results=len(filtered_results),
                final_citations=len(citations),
                deduplicated=self.deduplication_count,
                format=format_type.value,
                style=style.value
            )
            
            return citations
            
        except Exception as e:
            logger.error("Citation generation failed", error=str(e))
            return []
    
    async def generate_bibliography(
        self, 
        citations: List[Citation],
        format_type: Optional[CitationFormat] = None
    ) -> str:
        """Generate a formatted bibliography from citations."""
        if not citations:
            return ""
        
        format_type = format_type or self.default_format
        
        try:
            bibliography_entries = []
            
            for citation in citations:
                if format_type == CitationFormat.APA:
                    entry = self._format_apa_bibliography(citation)
                elif format_type == CitationFormat.MLA:
                    entry = self._format_mla_bibliography(citation)
                elif format_type == CitationFormat.CHICAGO:
                    entry = self._format_chicago_bibliography(citation)
                elif format_type == CitationFormat.IEEE:
                    entry = self._format_ieee_bibliography(citation)
                elif format_type == CitationFormat.HARVARD:
                    entry = self._format_harvard_bibliography(citation)
                else:
                    entry = self._format_simple_bibliography(citation)
                
                bibliography_entries.append(entry)
            
            bibliography = "\n".join(bibliography_entries)
            
            logger.debug(
                "Bibliography generated",
                citation_count=len(citations),
                format=format_type.value
            )
            
            return bibliography
            
        except Exception as e:
            logger.error("Bibliography generation failed", error=str(e))
            return ""
    
    def get_citation_stats(self) -> Dict[str, Any]:
        """Get citation generation statistics."""
        total_citations = sum(self.format_usage.values())
        
        return {
            "total_citations_generated": self.citation_count,
            "deduplication_count": self.deduplication_count,
            "deduplication_rate": (
                self.deduplication_count / max(self.citation_count + self.deduplication_count, 1)
            ),
            "format_usage": dict(self.format_usage),
            "settings": {
                "default_format": self.default_format.value,
                "default_style": self.default_style.value,
                "max_snippet_length": self.max_snippet_length,
                "min_relevance_threshold": self.min_relevance_threshold,
                "enable_deduplication": self.enable_deduplication,
                "similarity_threshold": self.similarity_threshold,
            }
        }
    
    # Private methods
    
    async def _enhance_relevance_scores(
        self, 
        results: List[SearchResult], 
        question: str
    ) -> List[SearchResult]:
        """Enhance relevance scores with additional factors."""
        try:
            # Extract question keywords for relevance boost
            question_keywords = self._extract_keywords(question.lower())
            
            enhanced_results = []
            
            for result in results:
                # Base score from search engine
                base_score = result.score
                
                # Content quality score
                content_quality = self._calculate_content_quality(result.content)
                
                # Keyword overlap boost
                content_keywords = self._extract_keywords(result.content.lower())
                keyword_overlap = len(question_keywords & content_keywords) / max(len(question_keywords), 1)
                
                # Source credibility score
                source_credibility = self._calculate_source_credibility(result)
                
                # Recency boost (if available)
                recency_boost = self._calculate_recency_boost(result)
                
                # Combined enhanced score
                enhanced_score = (
                    base_score * 0.4 +
                    content_quality * 0.2 +
                    keyword_overlap * 0.2 +
                    source_credibility * 0.1 +
                    recency_boost * 0.1
                )
                
                # Create enhanced result
                enhanced_result = SearchResult(
                    id=result.id,
                    content=result.content,
                    score=min(enhanced_score, 1.0),  # Cap at 1.0
                    metadata={
                        **result.metadata,
                        "original_score": base_score,
                        "content_quality": content_quality,
                        "keyword_overlap": keyword_overlap,
                        "source_credibility": source_credibility,
                        "recency_boost": recency_boost,
                    },
                    source=result.source
                )
                
                enhanced_results.append(enhanced_result)
            
            # Sort by enhanced score
            enhanced_results.sort(key=lambda x: x.score, reverse=True)
            
            return enhanced_results
            
        except Exception as e:
            logger.error("Relevance enhancement failed", error=str(e))
            return results
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract keywords from text."""
        # Simple keyword extraction (could be enhanced with NLP)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'this',
            'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can'
        }
        
        return {word for word in words if word not in stop_words and len(word) > 2}
    
    def _calculate_content_quality(self, content: str) -> float:
        """Calculate content quality score."""
        if not content:
            return 0.0
        
        # Basic quality indicators
        score = 0.0
        
        # Length penalty/bonus (optimal range)
        length = len(content.split())
        if 20 <= length <= 300:
            score += 0.3
        elif length > 300:
            score += 0.2
        else:
            score += 0.1
        
        # Sentence structure
        sentences = content.count('.') + content.count('!') + content.count('?')
        if sentences > 0:
            avg_sentence_length = length / sentences
            if 10 <= avg_sentence_length <= 25:
                score += 0.2
            else:
                score += 0.1
        
        # Capitalization (indicates proper formatting)
        if content[0].isupper():
            score += 0.1
        
        # Punctuation (indicates complete sentences)
        if any(content.endswith(p) for p in '.!?'):
            score += 0.1
        
        # Special characters that might indicate structured data
        if any(char in content for char in ':;-()[]{}'):
            score += 0.1
        
        # Numbers (might indicate data/facts)
        if re.search(r'\d+', content):
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_source_credibility(self, result: SearchResult) -> float:
        """Calculate source credibility score."""
        score = 0.5  # Base score
        
        metadata = result.metadata or {}
        source = result.source or ""
        
        # Known credible source patterns
        credible_domains = {
            '.edu', '.gov', '.org', 'wikipedia.org', 'scholar.google',
            'pubmed', 'arxiv.org', 'jstor.org', 'springer.com', 'ieee.org'
        }
        
        if any(domain in source.lower() for domain in credible_domains):
            score += 0.3
        
        # Has author information
        if metadata.get('author') or 'author' in metadata:
            score += 0.1
        
        # Has publication date
        if metadata.get('publication_date') or 'date' in metadata:
            score += 0.1
        
        # Has DOI or ISBN
        if (metadata.get('doi') or self.doi_pattern.search(source) or
            metadata.get('isbn') or self.isbn_pattern.search(source)):
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_recency_boost(self, result: SearchResult) -> float:
        """Calculate recency boost score."""
        # Simple recency boost based on metadata
        metadata = result.metadata or {}
        
        # If we have indexed_at timestamp
        if 'indexed_at' in metadata:
            try:
                indexed_date = datetime.fromisoformat(metadata['indexed_at'].replace('Z', '+00:00'))
                days_old = (datetime.utcnow() - indexed_date.replace(tzinfo=None)).days
                
                if days_old <= 1:
                    return 1.0
                elif days_old <= 7:
                    return 0.8
                elif days_old <= 30:
                    return 0.6
                elif days_old <= 365:
                    return 0.4
                else:
                    return 0.2
            except:
                pass
        
        return 0.5  # Default neutral score
    
    async def _create_citation(
        self,
        result: SearchResult,
        question: str,
        index: int,
        format_type: CitationFormat,
        style: CitationStyle
    ) -> Citation:
        """Create citation from search result."""
        # Parse source metadata
        metadata = self._parse_source_metadata(result)
        
        # Create content snippet
        snippet = self._create_content_snippet(result.content, question)
        
        # Calculate confidence score
        confidence = self._calculate_confidence_score(result, question)
        
        # Generate deduplication hash
        dedup_hash = self._generate_dedup_hash(result, snippet)
        
        # Create citation
        citation = Citation(
            id=result.id,
            index=index,
            content_snippet=snippet,
            source_identifier=result.source or f"Document-{result.id}",
            relevance_score=result.score,
            confidence_score=confidence,
            metadata=metadata,
            formatted_citation="",  # Will be set by _format_citation
            question_context=question,
            deduplication_hash=dedup_hash,
            created_at=datetime.utcnow()
        )
        
        # Format citation
        citation.formatted_citation = self._format_citation(citation, format_type, style)
        
        return citation
    
    def _parse_source_metadata(self, result: SearchResult) -> SourceMetadata:
        """Parse source metadata from search result."""
        metadata = result.metadata or {}
        source = result.source or ""
        
        return SourceMetadata(
            title=metadata.get('title') or self._extract_title_from_content(result.content),
            author=metadata.get('author'),
            publication_date=metadata.get('publication_date') or metadata.get('date'),
            source_type=metadata.get('data_format') or metadata.get('source_type') or 'document',
            url=source if self.url_pattern.match(source) else None,
            page_numbers=metadata.get('page_numbers'),
            publisher=metadata.get('publisher'),
            doi=self._extract_doi(source) or metadata.get('doi'),
            isbn=self._extract_isbn(source) or metadata.get('isbn'),
            database_name=metadata.get('database_name') or metadata.get('table_name'),
            access_date=datetime.utcnow().strftime('%Y-%m-%d')
        )
    
    def _extract_title_from_content(self, content: str) -> Optional[str]:
        """Extract title from content if not provided."""
        if not content:
            return None
        
        # Take first sentence as title (simple heuristic)
        sentences = re.split(r'[.!?]', content)
        if sentences:
            title = sentences[0].strip()
            # Limit title length
            return title[:100] + '...' if len(title) > 100 else title
        
        return None
    
    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI from text."""
        match = self.doi_pattern.search(text)
        return match.group(0) if match else None
    
    def _extract_isbn(self, text: str) -> Optional[str]:
        """Extract ISBN from text."""
        match = self.isbn_pattern.search(text)
        return match.group(0) if match else None
    
    def _create_content_snippet(self, content: str, question: str) -> str:
        """Create relevant content snippet."""
        if not content:
            return ""
        
        # Try to find most relevant part based on question keywords
        question_keywords = self._extract_keywords(question.lower())
        
        if question_keywords:
            # Find sentences containing question keywords
            sentences = re.split(r'[.!?]', content)
            scored_sentences = []
            
            for sentence in sentences:
                if len(sentence.strip()) < 20:  # Skip very short sentences
                    continue
                
                sentence_keywords = self._extract_keywords(sentence.lower())
                overlap_score = len(question_keywords & sentence_keywords)
                
                if overlap_score > 0:
                    scored_sentences.append((sentence.strip(), overlap_score))
            
            if scored_sentences:
                # Sort by relevance and take best sentences
                scored_sentences.sort(key=lambda x: x[1], reverse=True)
                best_sentences = [s[0] for s in scored_sentences[:2]]
                snippet = '. '.join(best_sentences)
                
                if len(snippet) <= self.max_snippet_length:
                    return snippet
        
        # Fallback: take beginning of content
        if len(content) <= self.max_snippet_length:
            return content
        
        # Truncate at word boundary
        truncated = content[:self.max_snippet_length]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + '...'
    
    def _calculate_confidence_score(self, result: SearchResult, question: str) -> float:
        """Calculate confidence score for citation."""
        # Base score from search relevance
        confidence = result.score
        
        # Boost for high-quality sources
        metadata = result.metadata or {}
        if metadata.get('source_credibility', 0) > 0.7:
            confidence = min(confidence + 0.1, 1.0)
        
        # Boost for recent content
        if metadata.get('recency_boost', 0) > 0.8:
            confidence = min(confidence + 0.05, 1.0)
        
        return confidence
    
    def _generate_dedup_hash(self, result: SearchResult, snippet: str) -> str:
        """Generate deduplication hash."""
        # Combine key identifying information
        hash_input = f"{result.source}|{snippet[:50]}|{result.metadata.get('title', '')}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _format_citation(
        self,
        citation: Citation,
        format_type: CitationFormat,
        style: CitationStyle
    ) -> str:
        """Format citation according to specified format and style."""
        if format_type == CitationFormat.APA:
            return self._format_apa_citation(citation, style)
        elif format_type == CitationFormat.MLA:
            return self._format_mla_citation(citation, style)
        elif format_type == CitationFormat.CHICAGO:
            return self._format_chicago_citation(citation, style)
        elif format_type == CitationFormat.IEEE:
            return self._format_ieee_citation(citation, style)
        elif format_type == CitationFormat.HARVARD:
            return self._format_harvard_citation(citation, style)
        else:
            return self._format_simple_citation(citation, style)
    
    def _format_simple_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format simple citation."""
        if style == CitationStyle.NUMBERED:
            return f"[{citation.index}] {citation.source_identifier}"
        elif style == CitationStyle.INLINE:
            author = citation.metadata.author or "Unknown"
            date = citation.metadata.publication_date or "n.d."
            return f"({author}, {date})"
        else:
            return f"{citation.index}. {citation.source_identifier}"
    
    def _format_apa_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format APA citation."""
        meta = citation.metadata
        
        # Author (Year). Title. Source.
        author = meta.author or "Unknown Author"
        year = meta.publication_date or "n.d."
        title = meta.title or "Untitled"
        
        if style == CitationStyle.NUMBERED:
            return f"[{citation.index}] {author} ({year}). {title}"
        else:
            return f"{author} ({year}). {title}"
    
    def _format_mla_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format MLA citation."""
        meta = citation.metadata
        
        # Author. "Title." Source, Date.
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        
        if style == CitationStyle.NUMBERED:
            return f"[{citation.index}] {author}. \"{title}.\" {source}, {date}."
        else:
            return f"{author}. \"{title}.\" {source}, {date}."
    
    def _format_chicago_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format Chicago citation."""
        meta = citation.metadata
        
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        
        if style == CitationStyle.NUMBERED:
            return f"{citation.index}. {author}, \"{title},\" {source} ({date})."
        else:
            return f"{author}. \"{title}.\" {source} ({date})."
    
    def _format_ieee_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format IEEE citation."""
        meta = citation.metadata
        
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        
        return f"[{citation.index}] {author}, \"{title},\" {source}, {date}."
    
    def _format_harvard_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format Harvard citation."""
        meta = citation.metadata
        
        author = meta.author or "Unknown Author"
        year = meta.publication_date or "n.d."
        title = meta.title or "Untitled"
        
        if style == CitationStyle.NUMBERED:
            return f"[{citation.index}] {author} {year}, '{title}'"
        else:
            return f"{author} {year}, '{title}'"
    
    # Bibliography formatting methods
    
    def _format_simple_bibliography(self, citation: Citation) -> str:
        """Format simple bibliography entry."""
        return f"{citation.index}. {citation.source_identifier} - {citation.content_snippet}"
    
    def _format_apa_bibliography(self, citation: Citation) -> str:
        """Format APA bibliography entry."""
        meta = citation.metadata
        author = meta.author or "Unknown Author"
        year = meta.publication_date or "n.d."
        title = meta.title or "Untitled"
        url = meta.url or ""
        
        entry = f"{author} ({year}). {title}."
        if url:
            entry += f" Retrieved from {url}"
        
        return entry
    
    def _format_mla_bibliography(self, citation: Citation) -> str:
        """Format MLA bibliography entry."""
        meta = citation.metadata
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        url = meta.url or ""
        access_date = meta.access_date or ""
        
        entry = f"{author}. \"{title}.\" {source}, {date}."
        if url and access_date:
            entry += f" Web. {access_date}."
        
        return entry
    
    def _format_chicago_bibliography(self, citation: Citation) -> str:
        """Format Chicago bibliography entry."""
        meta = citation.metadata
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        url = meta.url or ""
        access_date = meta.access_date or ""
        
        entry = f"{author}. \"{title}.\" {source} ({date})."
        if url:
            entry += f" Accessed {access_date}. {url}."
        
        return entry
    
    def _format_ieee_bibliography(self, citation: Citation) -> str:
        """Format IEEE bibliography entry."""
        meta = citation.metadata
        author = meta.author or "Unknown Author"
        title = meta.title or "Untitled"
        source = citation.source_identifier
        date = meta.publication_date or "n.d."
        
        return f"{author}, \"{title},\" {source}, {date}."
    
    def _format_harvard_bibliography(self, citation: Citation) -> str:
        """Format Harvard bibliography entry."""
        meta = citation.metadata
        author = meta.author or "Unknown Author"
        year = meta.publication_date or "n.d."
        title = meta.title or "Untitled"
        source = citation.source_identifier
        
        return f"{author} {year}, '{title}', {source}."