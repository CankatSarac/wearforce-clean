"""Comprehensive conversation manager with Redis-backed history.

Features:
- Redis-backed conversation storage
- Message threading and context management
- Conversation analytics and insights
- State persistence and recovery
- Automatic cleanup and archiving
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import structlog
from shared.database import ConversationStore
from shared.models import MessageRole, ConversationMessage
from shared.monitoring import get_metrics
from shared.exceptions import ValidationError, ServiceUnavailableError

logger = structlog.get_logger(__name__)


class ConversationContext:
    """Enhanced conversation context with state tracking."""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.message_count = 0
        self.user_intents = []
        self.active_tools = set()
        self.current_topic = None
        self.confidence_scores = []
        self.error_count = 0
        self.agent_switches = 0
        
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def add_intent(self, intent: str, confidence: float):
        """Track user intents over time."""
        self.user_intents.append({
            'intent': intent,
            'confidence': confidence,
            'timestamp': time.time()
        })
        self.confidence_scores.append(confidence)
    
    def get_dominant_intent(self) -> Optional[str]:
        """Get the most common intent in recent conversation."""
        if not self.user_intents:
            return None
        
        # Get intents from last 10 messages
        recent_intents = self.user_intents[-10:]
        intent_counts = {}
        
        for intent_data in recent_intents:
            intent = intent_data['intent']
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        return max(intent_counts, key=intent_counts.get) if intent_counts else None
    
    def get_average_confidence(self) -> float:
        """Get average confidence score."""
        return sum(self.confidence_scores) / len(self.confidence_scores) if self.confidence_scores else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'conversation_id': self.conversation_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'message_count': self.message_count,
            'user_intents': self.user_intents,
            'active_tools': list(self.active_tools),
            'current_topic': self.current_topic,
            'confidence_scores': self.confidence_scores,
            'error_count': self.error_count,
            'agent_switches': self.agent_switches,
            'dominant_intent': self.get_dominant_intent(),
            'avg_confidence': self.get_average_confidence()
        }


class ConversationManager:
    """Enhanced conversation manager with comprehensive state management."""
    
    def __init__(
        self, 
        conversation_store: ConversationStore, 
        max_history: int = 50,
        context_window: int = 10,
        cleanup_interval: int = 3600  # 1 hour
    ):
        self.conversation_store = conversation_store
        self.max_history = max_history
        self.context_window = context_window
        self.cleanup_interval = cleanup_interval
        
        # In-memory context cache for active conversations
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        
        # Statistics
        self.total_conversations = 0
        self.total_messages = 0
        self.active_conversations = 0
        
        # Background cleanup task
        self._cleanup_task = None
        self._running = False
    
    async def initialize(self):
        """Initialize conversation manager."""
        logger.info("Initializing conversation manager")
        
        # Start background cleanup task
        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        logger.info("Conversation manager initialized")
    
    async def close(self):
        """Close conversation manager."""
        logger.info("Closing conversation manager")
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Conversation manager closed")
    
    async def get_conversation_history(
        self, 
        conversation_id: str, 
        limit: int = 10,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """Get conversation history with enhanced metadata."""
        try:
            # Update context activity
            if conversation_id in self.conversation_contexts:
                self.conversation_contexts[conversation_id].update_activity()
            
            # Get messages from store
            messages = await self.conversation_store.get_messages(conversation_id, limit)
            
            # Enhance messages with metadata if requested
            if include_metadata:
                messages = await self._enhance_messages_with_metadata(conversation_id, messages)
            
            return messages
            
        except Exception as e:
            logger.error("Failed to get conversation history", 
                        conversation_id=conversation_id, error=str(e))
            raise
    
    async def add_message(
        self, 
        conversation_id: str, 
        message: Dict[str, Any],
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        tools_used: Optional[List[str]] = None
    ) -> None:
        """Add message to conversation with enhanced tracking."""
        try:
            # Ensure conversation context exists
            if conversation_id not in self.conversation_contexts:
                await self._create_conversation_context(conversation_id)
            
            context = self.conversation_contexts[conversation_id]
            
            # Enhance message with metadata
            enhanced_message = {
                **message,
                'timestamp': message.get('timestamp', time.time()),
                'message_id': f"{conversation_id}_{context.message_count}",
                'sequence_number': context.message_count,
            }
            
            # Add intent and confidence if provided
            if intent and confidence:
                enhanced_message['intent'] = intent
                enhanced_message['confidence'] = confidence
                context.add_intent(intent, confidence)
            
            # Track tool usage
            if tools_used:
                enhanced_message['tools_used'] = tools_used
                context.active_tools.update(tools_used)
            
            # Store message
            await self.conversation_store.add_message(conversation_id, enhanced_message)
            
            # Update context
            context.message_count += 1
            context.update_activity()
            
            # Update statistics
            self.total_messages += 1
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_counter("conversation_messages_added", "nlu_service")
            
            logger.debug("Message added to conversation", 
                        conversation_id=conversation_id,
                        message_count=context.message_count)
            
        except Exception as e:
            logger.error("Failed to add message to conversation", 
                        conversation_id=conversation_id, error=str(e))
            raise
    
    async def create_conversation(
        self, 
        conversation_id: str, 
        initial_message: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationContext:
        """Create a new conversation with enhanced initialization."""
        try:
            # Create conversation context
            context = await self._create_conversation_context(conversation_id)
            
            # Add metadata if provided
            if metadata:
                await self.conversation_store.set_metadata(conversation_id, metadata)
            
            # Add initial message if provided
            if initial_message:
                await self.add_message(conversation_id, initial_message)
            
            # Update statistics
            self.total_conversations += 1
            self.active_conversations += 1
            
            logger.info("Conversation created", 
                       conversation_id=conversation_id,
                       user_id=user_id)
            
            return context
            
        except Exception as e:
            logger.error("Failed to create conversation", 
                        conversation_id=conversation_id, error=str(e))
            raise
    
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation with cleanup."""
        try:
            # Remove from store
            await self.conversation_store.delete_conversation(conversation_id)
            
            # Remove from context cache
            if conversation_id in self.conversation_contexts:
                del self.conversation_contexts[conversation_id]
                self.active_conversations -= 1
            
            logger.info("Conversation deleted", conversation_id=conversation_id)
            
        except Exception as e:
            logger.error("Failed to delete conversation", 
                        conversation_id=conversation_id, error=str(e))
            raise
    
    async def get_conversation_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context."""
        if conversation_id not in self.conversation_contexts:
            # Try to load from store metadata
            try:
                metadata = await self.conversation_store.get_metadata(conversation_id)
                if metadata:
                    await self._create_conversation_context(conversation_id)
            except:
                return None
        
        return self.conversation_contexts.get(conversation_id)
    
    async def update_conversation_topic(
        self, 
        conversation_id: str, 
        topic: str
    ) -> None:
        """Update conversation topic."""
        context = await self.get_conversation_context(conversation_id)
        if context:
            context.current_topic = topic
            context.update_activity()
    
    async def get_conversation_summary(
        self, 
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get conversation summary with analytics."""
        try:
            context = await self.get_conversation_context(conversation_id)
            if not context:
                raise ValidationError(f"Conversation {conversation_id} not found")
            
            # Get recent messages for analysis
            messages = await self.get_conversation_history(conversation_id, limit=50)
            
            # Analyze conversation
            analysis = await self._analyze_conversation(messages, context)
            
            return {
                'conversation_id': conversation_id,
                'context': context.to_dict(),
                'message_count': len(messages),
                'duration_minutes': (context.last_activity - context.created_at).total_seconds() / 60,
                'analysis': analysis,
            }
            
        except Exception as e:
            logger.error("Failed to get conversation summary", 
                        conversation_id=conversation_id, error=str(e))
            raise
    
    async def get_active_conversations(self, limit: int = 10) -> List[str]:
        """Get list of active conversation IDs."""
        # Sort by last activity
        sorted_contexts = sorted(
            self.conversation_contexts.items(),
            key=lambda x: x[1].last_activity,
            reverse=True
        )
        
        return [conv_id for conv_id, _ in sorted_contexts[:limit]]
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation manager statistics."""
        return {
            'total_conversations': self.total_conversations,
            'total_messages': self.total_messages,
            'active_conversations': self.active_conversations,
            'cached_contexts': len(self.conversation_contexts),
            'avg_messages_per_conversation': self.total_messages / max(self.total_conversations, 1),
        }
    
    # Private methods
    async def _create_conversation_context(self, conversation_id: str) -> ConversationContext:
        """Create new conversation context."""
        context = ConversationContext(conversation_id)
        self.conversation_contexts[conversation_id] = context
        return context
    
    async def _enhance_messages_with_metadata(
        self, 
        conversation_id: str, 
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enhance messages with additional metadata."""
        enhanced_messages = []
        
        for i, message in enumerate(messages):
            enhanced_message = message.copy()
            
            # Add position metadata
            enhanced_message['position'] = i
            enhanced_message['is_latest'] = (i == len(messages) - 1)
            
            # Add time since previous message
            if i > 0:
                prev_timestamp = messages[i-1].get('timestamp', 0)
                curr_timestamp = message.get('timestamp', 0)
                enhanced_message['time_since_previous'] = curr_timestamp - prev_timestamp
            
            enhanced_messages.append(enhanced_message)
        
        return enhanced_messages
    
    async def _analyze_conversation(
        self, 
        messages: List[Dict[str, Any]], 
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Analyze conversation for insights."""
        analysis = {
            'message_distribution': {'user': 0, 'assistant': 0, 'system': 0},
            'avg_message_length': 0,
            'response_times': [],
            'intent_changes': 0,
            'tool_usage_count': len(context.active_tools),
            'error_rate': context.error_count / max(context.message_count, 1),
        }
        
        total_length = 0
        prev_intent = None
        
        for message in messages:
            role = message.get('role', 'user')
            analysis['message_distribution'][role] += 1
            
            content = message.get('content', '')
            total_length += len(content)
            
            # Track intent changes
            current_intent = message.get('intent')
            if current_intent and current_intent != prev_intent:
                analysis['intent_changes'] += 1
                prev_intent = current_intent
        
        if messages:
            analysis['avg_message_length'] = total_length / len(messages)
        
        return analysis
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of inactive conversations."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_inactive_conversations()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in periodic cleanup", error=str(e))
    
    async def _cleanup_inactive_conversations(self):
        """Clean up inactive conversation contexts."""
        cutoff_time = datetime.utcnow() - timedelta(hours=1)  # 1 hour inactive
        
        inactive_conversations = []
        
        for conv_id, context in self.conversation_contexts.items():
            if context.last_activity < cutoff_time:
                inactive_conversations.append(conv_id)
        
        # Remove inactive conversations from memory
        for conv_id in inactive_conversations:
            del self.conversation_contexts[conv_id]
            self.active_conversations -= 1
        
        if inactive_conversations:
            logger.info(f"Cleaned up {len(inactive_conversations)} inactive conversation contexts")