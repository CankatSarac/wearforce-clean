"""
Intent classification using transformers and rule-based approaches.

Features:
- Multi-model intent classification
- Confidence scoring
- Custom intent registration
- Fallback to rule-based classification
- Performance monitoring
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import structlog
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

from shared.models import Intent, Language
from shared.monitoring import get_metrics

logger = structlog.get_logger(__name__)


@dataclass
class IntentDefinition:
    """Intent definition with patterns and examples."""
    name: str
    description: str
    keywords: List[str]
    patterns: List[str]
    examples: List[str]
    confidence_threshold: float = 0.7


class IntentClassifier:
    """Intent classifier with ML and rule-based approaches."""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.intent_definitions: Dict[str, IntentDefinition] = {}
        self.model_name = "microsoft/DialoGPT-medium"  # Placeholder - use actual intent classification model
        
        # Statistics
        self.classification_count = 0
        self.successful_classifications = 0
        self.avg_confidence = 0.0
        
        # Intent definitions
        self._register_default_intents()
    
    async def initialize(self) -> None:
        """Initialize the intent classifier."""
        logger.info("Initializing intent classifier")
        
        try:
            # Load tokenizer and model
            # In production, use a proper intent classification model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            
            # Set to evaluation mode
            self.model.eval()
            
            logger.info("Intent classifier initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize intent classifier", error=str(e))
            # Continue without ML model - use rule-based only
            self.model = None
            self.tokenizer = None
    
    async def classify(self, text: str, language: Language = Language.ENGLISH) -> Optional[Intent]:
        """Classify intent from text."""
        self.classification_count += 1
        start_time = time.time()
        
        try:
            # Try ML classification first
            ml_intent = await self._classify_with_ml(text)
            
            # Try rule-based classification
            rule_intent = await self._classify_with_rules(text)
            
            # Combine results
            final_intent = self._combine_classification_results(ml_intent, rule_intent)
            
            if final_intent:
                self.successful_classifications += 1
                self._update_confidence_stats(final_intent.confidence)
            
            # Record metrics
            processing_time = time.time() - start_time
            metrics = get_metrics()
            if metrics:
                metrics.record_inference("intent_classification", processing_time)
            
            return final_intent
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            return None
    
    def register_intent(self, intent_def: IntentDefinition) -> None:
        """Register a new intent definition."""
        self.intent_definitions[intent_def.name] = intent_def
        logger.info(f"Registered intent: {intent_def.name}")
    
    def unregister_intent(self, intent_name: str) -> None:
        """Unregister an intent."""
        if intent_name in self.intent_definitions:
            del self.intent_definitions[intent_name]
            logger.info(f"Unregistered intent: {intent_name}")
    
    def list_intents(self) -> List[str]:
        """List available intents."""
        return list(self.intent_definitions.keys())
    
    def get_stats(self) -> Dict[str, any]:
        """Get classification statistics."""
        return {
            "classification_count": self.classification_count,
            "successful_classifications": self.successful_classifications,
            "success_rate": self.successful_classifications / max(self.classification_count, 1),
            "avg_confidence": self.avg_confidence,
            "available_intents": len(self.intent_definitions),
            "model_available": self.model is not None,
        }
    
    async def _classify_with_ml(self, text: str) -> Optional[Intent]:
        """Classify intent using ML model."""
        if not self.model or not self.tokenizer:
            return None
        
        try:
            # This is a placeholder implementation
            # In production, you would use a proper intent classification model
            # For now, return None to rely on rule-based classification
            return None
            
        except Exception as e:
            logger.error("ML intent classification failed", error=str(e))
            return None
    
    async def _classify_with_rules(self, text: str) -> Optional[Intent]:
        """Classify intent using rule-based approach."""
        text_lower = text.lower()
        best_match = None
        best_score = 0.0
        
        for intent_name, intent_def in self.intent_definitions.items():
            score = self._calculate_rule_score(text_lower, intent_def)
            
            if score > best_score and score >= intent_def.confidence_threshold:
                best_score = score
                best_match = Intent(
                    name=intent_name,
                    confidence=score,
                    parameters=self._extract_parameters(text, intent_def),
                )
        
        return best_match
    
    def _calculate_rule_score(self, text: str, intent_def: IntentDefinition) -> float:
        """Calculate rule-based confidence score."""
        total_score = 0.0
        components = 0
        
        # Keyword matching
        keyword_matches = sum(1 for keyword in intent_def.keywords if keyword.lower() in text)
        if intent_def.keywords:
            keyword_score = keyword_matches / len(intent_def.keywords)
            total_score += keyword_score * 0.4
            components += 1
        
        # Pattern matching
        pattern_matches = 0
        for pattern in intent_def.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                pattern_matches += 1
        
        if intent_def.patterns:
            pattern_score = min(pattern_matches / len(intent_def.patterns), 1.0)
            total_score += pattern_score * 0.6
            components += 1
        
        return total_score / max(components, 1)
    
    def _extract_parameters(self, text: str, intent_def: IntentDefinition) -> Dict[str, str]:
        """Extract parameters from text based on intent definition."""
        parameters = {}
        
        # Extract common parameters based on intent type
        if "contact" in intent_def.name.lower():
            # Extract names, emails, phone numbers
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            if email_match:
                parameters["email"] = email_match.group()
            
            phone_match = re.search(r'\b\d{3}-\d{3}-\d{4}\b|\b\d{10}\b', text)
            if phone_match:
                parameters["phone"] = phone_match.group()
        
        elif "order" in intent_def.name.lower():
            # Extract product names, quantities, prices
            quantity_match = re.search(r'\b(\d+)\s*(piece|item|unit|quantity)', text, re.IGNORECASE)
            if quantity_match:
                parameters["quantity"] = quantity_match.group(1)
        
        return parameters
    
    def _combine_classification_results(
        self, 
        ml_intent: Optional[Intent], 
        rule_intent: Optional[Intent]
    ) -> Optional[Intent]:
        """Combine ML and rule-based classification results."""
        if ml_intent and rule_intent:
            # Choose the one with higher confidence
            if ml_intent.confidence >= rule_intent.confidence:
                return ml_intent
            else:
                return rule_intent
        elif ml_intent:
            return ml_intent
        elif rule_intent:
            return rule_intent
        else:
            return None
    
    def _update_confidence_stats(self, confidence: float) -> None:
        """Update confidence statistics."""
        alpha = 0.1
        self.avg_confidence = alpha * confidence + (1 - alpha) * self.avg_confidence
    
    def _register_default_intents(self) -> None:
        """Register default intent definitions."""
        
        # CRM Intents
        self.register_intent(IntentDefinition(
            name="create_contact",
            description="Create a new contact",
            keywords=["create", "add", "new", "contact", "person", "customer"],
            patterns=[
                r"create.*contact",
                r"add.*contact",
                r"new.*contact",
                r"add.*customer",
            ],
            examples=[
                "Create a new contact for John Doe",
                "Add a customer named Jane Smith",
                "I want to create a contact",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="search_contact",
            description="Search for existing contacts",
            keywords=["search", "find", "look", "contact", "customer"],
            patterns=[
                r"search.*contact",
                r"find.*contact",
                r"look.*for.*contact",
                r"search.*customer",
            ],
            examples=[
                "Search for John Doe",
                "Find contact information for Jane",
                "Look for customer Smith",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="update_contact",
            description="Update existing contact",
            keywords=["update", "edit", "modify", "change", "contact"],
            patterns=[
                r"update.*contact",
                r"edit.*contact",
                r"modify.*contact",
                r"change.*contact",
            ],
            examples=[
                "Update John's contact information",
                "Edit customer details",
                "Change contact phone number",
            ],
        ))
        
        # ERP Intents
        self.register_intent(IntentDefinition(
            name="create_order",
            description="Create a new order",
            keywords=["create", "place", "new", "order", "purchase"],
            patterns=[
                r"create.*order",
                r"place.*order",
                r"new.*order",
                r"make.*purchase",
            ],
            examples=[
                "Create a new order for product X",
                "Place an order for 10 items",
                "I want to make a purchase",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="search_order",
            description="Search for orders",
            keywords=["search", "find", "check", "order", "status"],
            patterns=[
                r"search.*order",
                r"find.*order",
                r"check.*order",
                r"order.*status",
            ],
            examples=[
                "Search for order #12345",
                "Find my recent orders",
                "Check order status",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="get_inventory",
            description="Get inventory information",
            keywords=["inventory", "stock", "available", "quantity"],
            patterns=[
                r"check.*inventory",
                r"get.*stock",
                r"available.*quantity",
                r"how.*many.*in.*stock",
            ],
            examples=[
                "Check inventory for product X",
                "How many items are in stock?",
                "Get available quantity",
            ],
        ))
        
        # General Intents
        self.register_intent(IntentDefinition(
            name="schedule_meeting",
            description="Schedule a meeting",
            keywords=["schedule", "meeting", "appointment", "calendar"],
            patterns=[
                r"schedule.*meeting",
                r"book.*appointment",
                r"set.*up.*meeting",
                r"arrange.*meeting",
            ],
            examples=[
                "Schedule a meeting with John",
                "Book an appointment for tomorrow",
                "Set up a meeting for next week",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="generate_report",
            description="Generate reports",
            keywords=["generate", "create", "report", "analytics", "summary"],
            patterns=[
                r"generate.*report",
                r"create.*report",
                r"get.*analytics",
                r"show.*summary",
            ],
            examples=[
                "Generate sales report",
                "Create monthly summary", 
                "Show analytics for last quarter",
            ],
        ))
        
        self.register_intent(IntentDefinition(
            name="greeting",
            description="Greeting or hello",
            keywords=["hello", "hi", "hey", "good", "morning", "afternoon"],
            patterns=[
                r"^(hello|hi|hey)",
                r"good\s+(morning|afternoon|evening)",
                r"how.*are.*you",
            ],
            examples=[
                "Hello",
                "Hi there",
                "Good morning",
            ],
            confidence_threshold=0.5,
        ))
        
        self.register_intent(IntentDefinition(
            name="help",
            description="Request for help",
            keywords=["help", "assist", "support", "how", "what"],
            patterns=[
                r"can.*you.*help",
                r"i.*need.*help",
                r"how.*do.*i",
                r"what.*can.*you.*do",
            ],
            examples=[
                "Can you help me?",
                "I need assistance",
                "What can you do?",
            ],
            confidence_threshold=0.5,
        ))