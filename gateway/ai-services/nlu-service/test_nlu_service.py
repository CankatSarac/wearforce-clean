"""Comprehensive tests for NLU/Agent Router Service."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
import time

from shared.models import Intent, Entity, Language
from shared.exceptions import ValidationError, ServiceUnavailableError

# Import service components
from conversation_manager import ConversationManager, ConversationContext
from tool_dispatcher import ToolDispatcher, ToolDefinition
from intent_classifier import IntentClassifier
from entity_extractor import EntityExtractor, BusinessEntityRecognizer
from langgraph_orchestrator import LangGraphOrchestrator


class TestConversationManager:
    """Test conversation manager functionality."""
    
    @pytest.fixture
    async def conversation_store_mock(self):
        """Mock conversation store."""
        store = AsyncMock()
        store.get_messages.return_value = []
        store.add_message.return_value = None
        store.delete_conversation.return_value = None
        store.set_metadata.return_value = None
        store.get_metadata.return_value = {}
        return store
    
    @pytest.fixture
    async def conversation_manager(self, conversation_store_mock):
        """Create conversation manager with mocked dependencies."""
        manager = ConversationManager(
            conversation_store=conversation_store_mock,
            max_history=50,
            context_window=10
        )
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, conversation_manager):
        """Test conversation creation."""
        conv_id = "test-conv-123"
        initial_message = {"role": "user", "content": "Hello"}
        
        context = await conversation_manager.create_conversation(
            conversation_id=conv_id,
            initial_message=initial_message
        )
        
        assert context.conversation_id == conv_id
        assert context.message_count == 1
        assert conv_id in conversation_manager.conversation_contexts
    
    @pytest.mark.asyncio
    async def test_add_message_with_intent(self, conversation_manager):
        """Test adding message with intent tracking."""
        conv_id = "test-conv-123"
        await conversation_manager.create_conversation(conv_id)
        
        message = {"role": "user", "content": "Create a new contact"}
        await conversation_manager.add_message(
            conversation_id=conv_id,
            message=message,
            intent="create_contact",
            confidence=0.9,
            tools_used=["create_crm_contact"]
        )
        
        context = conversation_manager.conversation_contexts[conv_id]
        assert len(context.user_intents) == 1
        assert context.user_intents[0]["intent"] == "create_contact"
        assert "create_crm_contact" in context.active_tools
    
    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conversation_manager, conversation_store_mock):
        """Test getting conversation history."""
        conv_id = "test-conv-123"
        mock_messages = [
            {"role": "user", "content": "Hello", "timestamp": time.time()},
            {"role": "assistant", "content": "Hi there!", "timestamp": time.time()}
        ]
        conversation_store_mock.get_messages.return_value = mock_messages
        
        history = await conversation_manager.get_conversation_history(conv_id, limit=10)
        
        assert len(history) == 2
        conversation_store_mock.get_messages.assert_called_once_with(conv_id, 10)
    
    @pytest.mark.asyncio
    async def test_conversation_analytics(self, conversation_manager):
        """Test conversation analytics and insights."""
        conv_id = "test-conv-123"
        context = await conversation_manager.create_conversation(conv_id)
        
        # Add multiple intents
        await conversation_manager.add_message(
            conv_id, 
            {"role": "user", "content": "Create contact"}, 
            intent="create_contact",
            confidence=0.9
        )
        await conversation_manager.add_message(
            conv_id, 
            {"role": "user", "content": "Create another contact"}, 
            intent="create_contact",
            confidence=0.8
        )
        
        dominant_intent = context.get_dominant_intent()
        avg_confidence = context.get_average_confidence()
        
        assert dominant_intent == "create_contact"
        assert avg_confidence == 0.85


class TestToolDispatcher:
    """Test tool dispatcher functionality."""
    
    @pytest.fixture
    def tool_dispatcher(self):
        """Create tool dispatcher with mocked HTTP client."""
        dispatcher = ToolDispatcher(
            crm_api_url="http://localhost:3000/api",
            erp_api_url="http://localhost:3001/api"
        )
        return dispatcher
    
    @pytest.mark.asyncio
    async def test_register_tool(self, tool_dispatcher):
        """Test tool registration."""
        await tool_dispatcher.initialize()
        
        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            service_type="test",
            endpoint="http://test.com/api",
            required_parameters=["param1"]
        )
        
        tool_dispatcher.register_tool(tool)
        assert "test_tool" in tool_dispatcher.tools
        assert tool_dispatcher.tools["test_tool"].name == "test_tool"
    
    @pytest.mark.asyncio
    async def test_tool_validation(self, tool_dispatcher):
        """Test tool parameter validation."""
        await tool_dispatcher.initialize()
        
        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            service_type="test",
            endpoint="http://test.com/api",
            required_parameters=["param1"],
            parameters_schema={
                "param1": {"type": "string", "required": True},
                "param2": {"type": "integer", "required": False}
            }
        )
        tool_dispatcher.register_tool(tool)
        
        # Valid parameters
        valid_params = {"param1": "value1", "param2": 42}
        tool_dispatcher._validate_parameters(tool, valid_params)
        
        # Missing required parameter
        with pytest.raises(ValidationError, match="Required parameter 'param1' missing"):
            tool_dispatcher._validate_parameters(tool, {})
        
        # Wrong type
        with pytest.raises(ValidationError, match="should be string"):
            tool_dispatcher._validate_parameters(tool, {"param1": 123})
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, tool_dispatcher):
        """Test tool rate limiting."""
        await tool_dispatcher.initialize()
        
        # Test rate limiter
        rate_limiter = tool_dispatcher.rate_limiter
        tool_name = "test_tool"
        rate_limit = 5
        
        # Should allow first 5 calls
        for _ in range(5):
            assert rate_limiter.can_execute(tool_name, rate_limit)
            rate_limiter.record_call(tool_name)
        
        # Should block 6th call
        assert not rate_limiter.can_execute(tool_name, rate_limit)
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_mock(self, tool_dispatcher):
        """Test tool execution with mocked HTTP response."""
        await tool_dispatcher.initialize()
        
        # Mock HTTP client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": "test result"}
        
        with patch.object(tool_dispatcher, 'http_client') as mock_client:
            mock_client.request.return_value = mock_response
            
            # Create test tool
            tool = ToolDefinition(
                name="test_tool",
                description="Test tool",
                service_type="test",
                endpoint="http://test.com/api",
                method="POST",
                required_parameters=["param1"]
            )
            tool_dispatcher.register_tool(tool)
            
            # Execute tool
            result = await tool_dispatcher.execute_tool("test_tool", {"param1": "value1"})
            
            assert result["success"] is True
            assert result["data"]["success"] is True
            mock_client.request.assert_called_once()


class TestIntentClassifier:
    """Test intent classifier functionality."""
    
    @pytest.fixture
    def intent_classifier(self):
        """Create intent classifier."""
        classifier = IntentClassifier()
        return classifier
    
    @pytest.mark.asyncio
    async def test_initialize(self, intent_classifier):
        """Test intent classifier initialization."""
        await intent_classifier.initialize()
        # Should not raise exception even if ML model fails to load
        assert len(intent_classifier.intent_definitions) > 0
    
    @pytest.mark.asyncio
    async def test_rule_based_classification(self, intent_classifier):
        """Test rule-based intent classification."""
        await intent_classifier.initialize()
        
        # Test create contact intent
        intent = await intent_classifier.classify("Create a new contact for John Doe")
        assert intent is not None
        assert intent.name == "create_contact"
        assert intent.confidence > 0.7
        
        # Test search contact intent
        intent = await intent_classifier.classify("Find contact information for Jane")
        assert intent is not None
        assert intent.name == "search_contact"
        
        # Test greeting intent
        intent = await intent_classifier.classify("Hello there")
        assert intent is not None
        assert intent.name == "greeting"
    
    @pytest.mark.asyncio
    async def test_parameter_extraction(self, intent_classifier):
        """Test parameter extraction from text."""
        await intent_classifier.initialize()
        
        intent = await intent_classifier.classify("Create contact for john.doe@company.com")
        assert intent is not None
        assert "email" in intent.parameters
        assert intent.parameters["email"] == "john.doe@company.com"
    
    def test_intent_registration(self, intent_classifier):
        """Test custom intent registration."""
        from intent_classifier import IntentDefinition
        
        custom_intent = IntentDefinition(
            name="custom_intent",
            description="Custom intent",
            keywords=["custom", "test"],
            patterns=[r"custom\s+test"],
            examples=["custom test"]
        )
        
        intent_classifier.register_intent(custom_intent)
        assert "custom_intent" in intent_classifier.intent_definitions
        
        intent_classifier.unregister_intent("custom_intent")
        assert "custom_intent" not in intent_classifier.intent_definitions


class TestEntityExtractor:
    """Test entity extractor functionality."""
    
    @pytest.fixture
    def entity_extractor(self):
        """Create entity extractor."""
        extractor = EntityExtractor(use_business_recognizer=True)
        return extractor
    
    @pytest.mark.asyncio
    async def test_initialize(self, entity_extractor):
        """Test entity extractor initialization."""
        await entity_extractor.initialize()
        # Should not raise exception even if spaCy model fails to load
        assert entity_extractor.business_recognizer is not None
    
    @pytest.mark.asyncio
    async def test_regex_entity_extraction(self, entity_extractor):
        """Test basic regex-based entity extraction."""
        await entity_extractor.initialize()
        
        text = "Contact john.doe@company.com at (555) 123-4567 for order #12345"
        entities = await entity_extractor.extract(text)
        
        entity_labels = [e.label for e in entities]
        assert "EMAIL" in entity_labels
        assert "PHONE" in entity_labels
        
        # Find email entity
        email_entities = [e for e in entities if e.label == "EMAIL"]
        assert len(email_entities) == 1
        assert email_entities[0].text == "john.doe@company.com"
    
    @pytest.mark.asyncio
    async def test_business_entity_extraction(self, entity_extractor):
        """Test business-specific entity extraction."""
        await entity_extractor.initialize()
        
        text = "Please check order ORD-123456 for customer CUST-5678 and employee EMP-9012"
        entities = await entity_extractor.extract(text)
        
        entity_labels = [e.label for e in entities]
        assert "ORDER_ID" in entity_labels
        assert "CUSTOMER_ID" in entity_labels
        assert "EMPLOYEE_ID" in entity_labels
        
        # Verify specific extractions
        order_entities = [e for e in entities if e.label == "ORDER_ID"]
        assert len(order_entities) == 1
        assert "123456" in order_entities[0].text
    
    @pytest.mark.asyncio
    async def test_entity_deduplication(self, entity_extractor):
        """Test entity deduplication."""
        await entity_extractor.initialize()
        
        # Create overlapping entities manually
        entities = [
            Entity(text="John", label="PERSON", start=0, end=4, confidence=0.8),
            Entity(text="John Doe", label="PERSON", start=0, end=8, confidence=0.9),  # Higher confidence
            Entity(text="Doe", label="PERSON", start=5, end=8, confidence=0.7)
        ]
        
        deduplicated = entity_extractor._deduplicate_entities(entities)
        
        # Should keep the higher confidence "John Doe" entity
        assert len(deduplicated) == 1
        assert deduplicated[0].text == "John Doe"
        assert deduplicated[0].confidence == 0.9
    
    def test_business_entity_patterns(self):
        """Test business entity pattern recognition."""
        recognizer = BusinessEntityRecognizer()
        
        text = "Check ticket TICKET-1234 for project PRJ-ABC123"
        entities = recognizer.extract_entities(text)
        
        assert len(entities) == 2
        
        # Check ticket ID
        ticket_entities = [e for e in entities if e[3] == "TICKET_ID"]  # label is at index 3
        assert len(ticket_entities) == 1
        assert "1234" in ticket_entities[0][0]  # text is at index 0
        
        # Check project code
        project_entities = [e for e in entities if e[3] == "PROJECT_CODE"]
        assert len(project_entities) == 1
        assert "ABC123" in project_entities[0][0]


class TestLangGraphOrchestrator:
    """Test LangGraph orchestrator functionality."""
    
    @pytest.fixture
    async def orchestrator_components(self):
        """Create mocked components for orchestrator."""
        intent_classifier = AsyncMock()
        intent_classifier.classify.return_value = Intent(
            name="create_contact", 
            confidence=0.9,
            parameters={}
        )
        
        entity_extractor = AsyncMock()
        entity_extractor.extract.return_value = [
            Entity(text="John Doe", label="PERSON", start=0, end=8, confidence=0.9)
        ]
        
        tool_dispatcher = AsyncMock()
        tool_dispatcher.execute_tool.return_value = {
            "success": True,
            "data": {"contact_id": "12345"},
            "tool_name": "create_crm_contact"
        }
        
        conversation_manager = AsyncMock()
        conversation_manager.get_conversation_history.return_value = []
        
        return {
            "intent_classifier": intent_classifier,
            "entity_extractor": entity_extractor,
            "tool_dispatcher": tool_dispatcher,
            "conversation_manager": conversation_manager
        }
    
    @pytest.fixture
    async def orchestrator(self, orchestrator_components):
        """Create LangGraph orchestrator with mocked dependencies."""
        orchestrator = LangGraphOrchestrator(
            intent_classifier=orchestrator_components["intent_classifier"],
            entity_extractor=orchestrator_components["entity_extractor"],
            tool_dispatcher=orchestrator_components["tool_dispatcher"],
            conversation_manager=orchestrator_components["conversation_manager"]
        )
        await orchestrator.initialize()
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.compiled_workflow is not None
        assert orchestrator.workflow is not None
        assert len(orchestrator.agents) == 4  # Four agent types
    
    @pytest.mark.asyncio
    async def test_process_request(self, orchestrator, orchestrator_components):
        """Test request processing through orchestrator."""
        # Mock HTTP client for LLM service
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "I've created the contact successfully."}
            }]
        }
        
        with patch.object(orchestrator, 'http_client') as mock_client:
            mock_client.post.return_value = mock_response
            
            result = await orchestrator.process_request(
                text="Create a contact for John Doe",
                conversation_id="test-conv-123",
                user_id="user-123"
            )
            
            assert "actions" in result
            assert "response" in result
            assert "reasoning" in result
            assert "confidence" in result
    
    def test_routing_logic(self, orchestrator):
        """Test request routing logic."""
        # Test tool routing
        state = {
            "current_intent": "create_contact",
            "entities": [{"label": "PERSON", "text": "John Doe"}],
            "messages": [{"content": "create a new contact for john doe"}],
            "error_count": 0
        }
        
        route = orchestrator._route_request(state)
        assert route == "use_tools"
        
        # Test RAG routing
        state["messages"] = [{"content": "how do I create a contact?"}]
        state["current_intent"] = None
        route = orchestrator._route_request(state)
        assert route == "use_rag"
        
        # Test direct response routing
        state["messages"] = [{"content": "hello there"}]
        state["current_intent"] = "greeting"
        route = orchestrator._route_request(state)
        assert route == "direct_response"
    
    @pytest.mark.asyncio
    async def test_agent_selection(self, orchestrator):
        """Test agent type selection."""
        # CRM intent should select CRM agent
        agent_type = orchestrator._select_agent_type("create_contact", [])
        assert agent_type.value == "crm_agent"
        
        # ERP intent should select ERP agent
        agent_type = orchestrator._select_agent_type("create_order", [])
        assert agent_type.value == "erp_agent"
        
        # Business entities should select task coordinator
        entities = [{"label": "ORGANIZATION", "text": "ACME Corp"}]
        agent_type = orchestrator._select_agent_type(None, entities)
        assert agent_type.value == "task_coordinator"


@pytest.mark.asyncio
async def test_health_checks():
    """Test health check endpoints for all components."""
    # Test individual component health checks
    intent_classifier = IntentClassifier()
    await intent_classifier.initialize()
    assert len(intent_classifier.list_intents()) > 0
    
    entity_extractor = EntityExtractor()
    await entity_extractor.initialize()
    assert len(entity_extractor.list_entity_types()) > 0
    
    tool_dispatcher = ToolDispatcher(
        crm_api_url="http://localhost:3000/api",
        erp_api_url="http://localhost:3001/api"
    )
    await tool_dispatcher.initialize()
    # Health check might fail if services not running, but shouldn't raise exception
    health_result = await tool_dispatcher.health_check()
    assert isinstance(health_result, bool)


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in various components."""
    # Test intent classifier with invalid input
    classifier = IntentClassifier()
    await classifier.initialize()
    
    # Should handle empty text gracefully
    intent = await classifier.classify("")
    assert intent is None
    
    # Test entity extractor with invalid input
    extractor = EntityExtractor()
    await extractor.initialize()
    
    # Should handle empty text gracefully
    entities = await extractor.extract("")
    assert entities == []
    
    # Test tool dispatcher with invalid tool
    dispatcher = ToolDispatcher(
        crm_api_url="http://localhost:3000/api",
        erp_api_url="http://localhost:3001/api"
    )
    await dispatcher.initialize()
    
    with pytest.raises(ValidationError):
        await dispatcher.execute_tool("nonexistent_tool", {})


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v", "--tb=short"])