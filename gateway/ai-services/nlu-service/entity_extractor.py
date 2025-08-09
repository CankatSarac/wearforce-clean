"""Enhanced entity extractor with spaCy NLP integration and business-specific entity types.

Features:
- spaCy NLP pipeline integration
- Business-specific entity recognition
- Custom entity patterns
- Confidence scoring
- Multi-language support
- Entity linking and normalization
"""

import asyncio
import re
import time
from typing import List, Optional, Dict, Any, Tuple, Set
from dataclasses import dataclass
import structlog

# Try to import spaCy, fallback to regex if not available
try:
    import spacy
    from spacy.matcher import Matcher, PhraseMatcher
    from spacy.lang.en import English
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Matcher = None
    PhraseMatcher = None
    English = None

from shared.models import Entity, Language
from shared.monitoring import get_metrics
from shared.exceptions import ValidationError, ServiceUnavailableError

logger = structlog.get_logger(__name__)


@dataclass
class EntityPattern:
    """Custom entity pattern definition."""
    label: str
    patterns: List[str]  # Regex patterns
    examples: List[str]
    confidence_boost: float = 0.1  # Boost confidence for matched patterns
    is_business_entity: bool = False


class BusinessEntityRecognizer:
    """Business-specific entity recognizer using patterns and rules."""
    
    def __init__(self):
        self.patterns = self._initialize_business_patterns()
        self.compiled_patterns = {}
        self._compile_patterns()
    
    def _initialize_business_patterns(self) -> Dict[str, EntityPattern]:
        """Initialize business-specific entity patterns."""
        return {
            # Contact Information
            "EMPLOYEE_ID": EntityPattern(
                label="EMPLOYEE_ID",
                patterns=[
                    r'\b[Ee][Mm][Pp][-_]?\d{4,8}\b',
                    r'\b[Ee]\d{4,8}\b',
                    r'\b[Ii][Dd][-_]?\d{4,8}\b',
                    r'\bemployee\s+(?:id|number)[-_:.]?\s*(\d{4,8})\b'
                ],
                examples=["EMP-1234", "E12345", "ID-5678", "employee id 9876"],
                is_business_entity=True
            ),
            
            "CUSTOMER_ID": EntityPattern(
                label="CUSTOMER_ID",
                patterns=[
                    r'\b[Cc][Uu][Ss][Tt][-_]?\d{4,8}\b',
                    r'\b[Cc]\d{4,8}\b',
                    r'\bcustomer\s+(?:id|number)[-_:.]?\s*(\d{4,8})\b'
                ],
                examples=["CUST-1234", "C12345", "customer id 5678"],
                is_business_entity=True
            ),
            
            "ORDER_ID": EntityPattern(
                label="ORDER_ID",
                patterns=[
                    r'\b[Oo][Rr][Dd][-_]?\d{4,10}\b',
                    r'\b[Oo]\d{4,10}\b',
                    r'\border\s+(?:id|number)[-_:.]?\s*(\d{4,10})\b',
                    r'\b#\d{4,10}\b'
                ],
                examples=["ORD-123456", "O123456", "order number 789012", "#456789"],
                is_business_entity=True
            ),
            
            "PRODUCT_CODE": EntityPattern(
                label="PRODUCT_CODE",
                patterns=[
                    r'\b[Pp][Rr][Oo][-_]?\d{3,8}\b',
                    r'\b[Pp]\d{3,8}\b',
                    r'\bproduct\s+(?:code|id)[-_:.]?\s*([A-Z0-9]{3,8})\b',
                    r'\b[A-Z]{2,4}[-_]?\d{3,6}\b'
                ],
                examples=["PRO-123", "P4567", "product code ABC123", "SKU-456"],
                is_business_entity=True
            ),
            
            # Financial Information
            "INVOICE_NUMBER": EntityPattern(
                label="INVOICE_NUMBER",
                patterns=[
                    r'\b[Ii][Nn][Vv][-_]?\d{4,10}\b',
                    r'\binvoice\s+(?:number|no)[-_:.]?\s*(\d{4,10})\b',
                    r'\b[Ii][Nn]\d{4,10}\b'
                ],
                examples=["INV-12345", "invoice number 67890", "IN123456"],
                is_business_entity=True
            ),
            
            "PURCHASE_ORDER": EntityPattern(
                label="PURCHASE_ORDER",
                patterns=[
                    r'\b[Pp][Oo][-_]?\d{4,10}\b',
                    r'\bpurchase\s+order\s+(?:number|no)?[-_:.]?\s*(\d{4,10})\b',
                    r'\bp\.?o\.?\s+(?:number|no)?[-_:.]?\s*(\d{4,10})\b'
                ],
                examples=["PO-12345", "purchase order 67890", "P.O. 123456"],
                is_business_entity=True
            ),
            
            # Dates and Times (Business Context)
            "DELIVERY_DATE": EntityPattern(
                label="DELIVERY_DATE",
                patterns=[
                    r'\bdelivery\s+(?:date|time|by)[-_:.]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                    r'\bdeliver\s+(?:on|by)[-_:.]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                    r'\bdue\s+(?:date|by)[-_:.]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
                ],
                examples=["delivery date 12/31/2023", "deliver by 01-15-2024", "due by 2023-12-25"],
                is_business_entity=True
            ),
            
            "MEETING_TIME": EntityPattern(
                label="MEETING_TIME",
                patterns=[
                    r'\bmeeting\s+(?:at|time)[-_:.]?\s*(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)',
                    r'\bat\s+(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s+(?:meeting|appointment)',
                    r'\b(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)\s+meeting'
                ],
                examples=["meeting at 2:30 PM", "at 14:00 meeting", "3:45 PM meeting"],
                is_business_entity=True
            ),
            
            # Department and Role Information
            "DEPARTMENT": EntityPattern(
                label="DEPARTMENT",
                patterns=[
                    r'\b(?:sales|marketing|hr|human resources|it|finance|accounting|operations|support|engineering|development|research|legal)\s+(?:department|dept|team)\b',
                    r'\b(?:sales|marketing|hr|finance|accounting|operations|support|engineering|development|research|legal)\s+(?:division|unit)\b'
                ],
                examples=["sales department", "HR team", "finance division"],
                is_business_entity=True
            ),
            
            "JOB_TITLE": EntityPattern(
                label="JOB_TITLE",
                patterns=[
                    r'\b(?:manager|director|supervisor|coordinator|specialist|analyst|executive|assistant|representative|agent|lead|senior|junior)\s+\w+\b',
                    r'\b(?:ceo|cto|cfo|coo|vp|vice president|president)\b',
                    r'\b(?:sales|marketing|hr|finance|accounting|operations|support|engineering|development)\s+(?:manager|director|lead)\b'
                ],
                examples=["sales manager", "HR director", "senior analyst", "CEO", "vice president"],
                is_business_entity=True
            ),
            
            # Location Information
            "OFFICE_LOCATION": EntityPattern(
                label="OFFICE_LOCATION",
                patterns=[
                    r'\b(?:office|branch|location|site)\s+(?:in|at)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'\b([A-Z][a-z]+)\s+(?:office|branch|location|site)\b',
                    r'\bheadquarters\s+(?:in|at)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
                ],
                examples=["office in New York", "Chicago branch", "headquarters in Seattle"],
                is_business_entity=True
            ),
            
            # Technical Information
            "TICKET_ID": EntityPattern(
                label="TICKET_ID",
                patterns=[
                    r'\b[Tt][Ii][Cc][Kk][Ee][Tt][-_]?\d{4,8}\b',
                    r'\b[Tt]\d{4,8}\b',
                    r'\bticket\s+(?:id|number)[-_:.]?\s*(\d{4,8})\b',
                    r'\b(?:bug|issue|case)\s+(?:id|number)?[-_:.]?\s*(\d{4,8})\b'
                ],
                examples=["TICKET-1234", "T5678", "ticket number 9012", "bug 3456"],
                is_business_entity=True
            ),
            
            "PROJECT_CODE": EntityPattern(
                label="PROJECT_CODE",
                patterns=[
                    r'\b[Pp][Rr][Jj][-_]?[A-Z0-9]{3,8}\b',
                    r'\bproject\s+(?:code|id)[-_:.]?\s*([A-Z0-9]{3,8})\b',
                    r'\b[A-Z]{2,4}[-_]?\d{3,4}\b'
                ],
                examples=["PRJ-ABC123", "project code XYZ456", "DEV-001"],
                is_business_entity=True
            )
        }
    
    def _compile_patterns(self):
        """Compile regex patterns for better performance."""
        for label, pattern_def in self.patterns.items():
            compiled = []
            for pattern in pattern_def.patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Failed to compile pattern for {label}: {pattern}", error=str(e))
            self.compiled_patterns[label] = compiled
    
    def extract_entities(self, text: str) -> List[Tuple[str, int, int, str, float]]:
        """Extract business entities from text.
        
        Returns:
            List of tuples: (text, start, end, label, confidence)
        """
        entities = []
        
        for label, compiled_patterns in self.compiled_patterns.items():
            pattern_def = self.patterns[label]
            
            for pattern in compiled_patterns:
                for match in pattern.finditer(text):
                    # Extract the actual entity text
                    entity_text = match.group(1) if match.groups() else match.group(0)
                    
                    # Calculate confidence (higher for business entities)
                    confidence = 0.85 if pattern_def.is_business_entity else 0.75
                    confidence += pattern_def.confidence_boost
                    confidence = min(confidence, 1.0)
                    
                    entities.append((
                        entity_text.strip(),
                        match.start(),
                        match.end(),
                        label,
                        confidence
                    ))
        
        return entities


class EntityExtractor:
    """Enhanced entity extractor with spaCy integration and business-specific recognition."""
    
    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        use_business_recognizer: bool = True,
        confidence_threshold: float = 0.5
    ):
        self.model_name = model_name
        self.use_business_recognizer = use_business_recognizer
        self.confidence_threshold = confidence_threshold
        
        # spaCy components
        self.nlp = None
        self.matcher = None
        self.phrase_matcher = None
        
        # Business entity recognizer
        self.business_recognizer = BusinessEntityRecognizer() if use_business_recognizer else None
        
        # Regex patterns for basic entities (fallback)
        self.regex_patterns = {
            "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "PHONE": re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'),
            "URL": re.compile(r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'),
            "MONEY": re.compile(r'\$\d+(?:\.\d{2})?|\b\d+(?:\.\d{2})?\s*(?:dollars?|usd|cents?)\b'),
            "PERCENTAGE": re.compile(r'\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*percent\b'),
            "DATE": re.compile(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b|\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b'),
            "TIME": re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?\b'),
            "NUMBER": re.compile(r'\b\d+(?:\.\d+)?\b'),
            "ZIPCODE": re.compile(r'\b\d{5}(?:-\d{4})?\b'),
            "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        }
        
        # Statistics
        self.extraction_count = 0
        self.entity_counts = {}
        self.avg_confidence = 0.0
        
    async def initialize(self) -> None:
        """Initialize the entity extractor."""
        logger.info("Initializing entity extractor")
        
        try:
            if SPACY_AVAILABLE:
                await self._initialize_spacy()
            else:
                logger.warning("spaCy not available, using regex-only entity extraction")
            
            logger.info("Entity extractor initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize entity extractor", error=str(e))
            # Continue with regex-only extraction
    
    async def _initialize_spacy(self):
        """Initialize spaCy NLP pipeline."""
        try:
            # Try to load the specified model
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model: {self.model_name}")
        except OSError:
            try:
                # Fallback to English model
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded fallback spaCy model: en_core_web_sm")
            except OSError:
                try:
                    # Create blank English model
                    self.nlp = English()
                    logger.info("Created blank English spaCy model")
                except Exception as e:
                    logger.warning(f"Failed to create spaCy model: {str(e)}")
                    self.nlp = None
                    return
        
        if self.nlp:
            # Initialize matchers for custom patterns
            self.matcher = Matcher(self.nlp.vocab)
            self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
            
            # Add custom patterns
            await self._add_custom_patterns()
    
    async def _add_custom_patterns(self):
        """Add custom entity patterns to spaCy matchers."""
        if not self.matcher:
            return
        
        # Add some common business patterns
        patterns = [
            # Email pattern
            [{"LIKE_EMAIL": True}],
            
            # Phone pattern
            [{"SHAPE": "ddd-ddd-dddd"}],
            [{"SHAPE": "(ddd) ddd-dddd"}],
            
            # Money pattern
            [{"TEXT": "$"}, {"LIKE_NUM": True}],
            [{"LIKE_NUM": True}, {"LOWER": {"IN": ["dollars", "dollar", "usd"]}}],
            
            # Percentage
            [{"LIKE_NUM": True}, {"TEXT": "%"}],
            [{"LIKE_NUM": True}, {"LOWER": "percent"}],
        ]
        
        for i, pattern in enumerate(patterns):
            self.matcher.add(f"CUSTOM_{i}", [pattern])
    
    async def extract(
        self, 
        text: str, 
        language: Language = Language.ENGLISH,
        include_confidence: bool = True
    ) -> List[Entity]:
        """Extract entities from text using multiple approaches."""
        start_time = time.time()
        self.extraction_count += 1
        
        try:
            entities = []
            
            # Extract using spaCy if available
            if self.nlp:
                spacy_entities = await self._extract_with_spacy(text)
                entities.extend(spacy_entities)
            
            # Extract using business recognizer
            if self.business_recognizer:
                business_entities = await self._extract_business_entities(text)
                entities.extend(business_entities)
            
            # Extract using regex patterns (fallback or supplement)
            regex_entities = await self._extract_with_regex(text)
            entities.extend(regex_entities)
            
            # Deduplicate and filter entities
            entities = self._deduplicate_entities(entities)
            entities = self._filter_entities(entities)
            
            # Update statistics
            for entity in entities:
                self.entity_counts[entity.label] = self.entity_counts.get(entity.label, 0) + 1
            
            if entities:
                avg_conf = sum(e.confidence for e in entities) / len(entities)
                self.avg_confidence = (self.avg_confidence * (self.extraction_count - 1) + avg_conf) / self.extraction_count
            
            # Record metrics
            processing_time = time.time() - start_time
            metrics = get_metrics()
            if metrics:
                metrics.record_inference("entity_extraction", processing_time)
                metrics.record_counter("entities_extracted", "nlu_service", {"count": len(entities)})
            
            logger.debug(f"Extracted {len(entities)} entities from text", processing_time=processing_time)
            
            return entities
            
        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            return []
    
    async def _extract_with_spacy(self, text: str) -> List[Entity]:
        """Extract entities using spaCy NER."""
        entities = []
        
        try:
            doc = self.nlp(text)
            
            # Named entity recognition
            for ent in doc.ents:
                confidence = self._calculate_spacy_confidence(ent)
                if confidence >= self.confidence_threshold:
                    entities.append(Entity(
                        text=ent.text,
                        label=ent.label_,
                        start=ent.start_char,
                        end=ent.end_char,
                        confidence=confidence
                    ))
            
            # Custom matcher results
            matches = self.matcher(doc)
            for match_id, start, end in matches:
                span = doc[start:end]
                label = self.nlp.vocab.strings[match_id]
                confidence = 0.8  # Default confidence for pattern matches
                
                entities.append(Entity(
                    text=span.text,
                    label=label,
                    start=span.start_char,
                    end=span.end_char,
                    confidence=confidence
                ))
            
        except Exception as e:
            logger.warning("spaCy entity extraction failed", error=str(e))
        
        return entities
    
    async def _extract_business_entities(self, text: str) -> List[Entity]:
        """Extract business-specific entities."""
        entities = []
        
        try:
            business_entities = self.business_recognizer.extract_entities(text)
            
            for entity_text, start, end, label, confidence in business_entities:
                if confidence >= self.confidence_threshold:
                    entities.append(Entity(
                        text=entity_text,
                        label=label,
                        start=start,
                        end=end,
                        confidence=confidence
                    ))
        
        except Exception as e:
            logger.warning("Business entity extraction failed", error=str(e))
        
        return entities
    
    async def _extract_with_regex(self, text: str) -> List[Entity]:
        """Extract entities using regex patterns."""
        entities = []
        
        for label, pattern in self.regex_patterns.items():
            for match in pattern.finditer(text):
                confidence = 0.9  # High confidence for regex matches
                
                entities.append(Entity(
                    text=match.group().strip(),
                    label=label,
                    start=match.start(),
                    end=match.end(),
                    confidence=confidence
                ))
        
        return entities
    
    def _calculate_spacy_confidence(self, ent) -> float:
        """Calculate confidence score for spaCy entity."""
        # spaCy doesn't provide confidence scores directly
        # We estimate based on entity type and length
        base_confidence = 0.8
        
        # Higher confidence for well-known entity types
        high_confidence_types = {"PERSON", "ORG", "GPE", "MONEY", "DATE", "TIME"}
        if ent.label_ in high_confidence_types:
            base_confidence = 0.9
        
        # Adjust based on entity length (longer entities tend to be more reliable)
        length_boost = min(len(ent.text) * 0.01, 0.1)
        
        return min(base_confidence + length_boost, 1.0)
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities based on text span overlap."""
        if not entities:
            return entities
        
        # Sort by start position
        sorted_entities = sorted(entities, key=lambda e: (e.start, e.end))
        
        deduplicated = []
        for entity in sorted_entities:
            # Check for overlap with existing entities
            overlaps = False
            for existing in deduplicated:
                if self._entities_overlap(entity, existing):
                    # Keep the entity with higher confidence
                    if entity.confidence > existing.confidence:
                        deduplicated.remove(existing)
                        deduplicated.append(entity)
                    overlaps = True
                    break
            
            if not overlaps:
                deduplicated.append(entity)
        
        return deduplicated
    
    def _entities_overlap(self, entity1: Entity, entity2: Entity) -> bool:
        """Check if two entities overlap in their text spans."""
        return not (entity1.end <= entity2.start or entity2.end <= entity1.start)
    
    def _filter_entities(self, entities: List[Entity]) -> List[Entity]:
        """Filter entities based on confidence threshold and other criteria."""
        filtered = []
        
        for entity in entities:
            # Filter by confidence
            if entity.confidence < self.confidence_threshold:
                continue
            
            # Filter out very short entities (likely noise)
            if len(entity.text.strip()) < 2:
                continue
            
            # Filter out entities that are just numbers (unless they're business IDs)
            if (entity.text.strip().isdigit() and 
                entity.label not in ["EMPLOYEE_ID", "CUSTOMER_ID", "ORDER_ID", "INVOICE_NUMBER"]):
                continue
            
            filtered.append(entity)
        
        return filtered
    
    def list_entity_types(self) -> List[str]:
        """List all available entity types."""
        entity_types = set()
        
        # Add spaCy entity types
        if self.nlp:
            entity_types.update(self.nlp.get_pipe("ner").labels)
        
        # Add business entity types
        if self.business_recognizer:
            entity_types.update(self.business_recognizer.patterns.keys())
        
        # Add regex pattern types
        entity_types.update(self.regex_patterns.keys())
        
        return sorted(list(entity_types))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get entity extraction statistics."""
        return {
            "extraction_count": self.extraction_count,
            "avg_confidence": self.avg_confidence,
            "entity_counts": self.entity_counts,
            "available_types": len(self.list_entity_types()),
            "spacy_available": self.nlp is not None,
            "business_recognizer_enabled": self.business_recognizer is not None,
            "confidence_threshold": self.confidence_threshold,
        }
    
    def get_entity_examples(self, entity_type: str) -> List[str]:
        """Get example texts for a specific entity type."""
        if self.business_recognizer and entity_type in self.business_recognizer.patterns:
            return self.business_recognizer.patterns[entity_type].examples
        
        # Return some generic examples for common types
        examples = {
            "EMAIL": ["john.doe@company.com", "support@example.org"],
            "PHONE": ["(555) 123-4567", "555-987-6543"],
            "MONEY": ["$100.50", "250 dollars"],
            "DATE": ["12/31/2023", "2024-01-15"],
            "TIME": ["2:30 PM", "14:30"],
            "PERSON": ["John Smith", "Alice Johnson"],
            "ORG": ["Microsoft", "Google Inc"],
            "GPE": ["New York", "California"],
        }
        
        return examples.get(entity_type, [])