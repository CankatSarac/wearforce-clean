"""
LangGraph-based workflow orchestration for multi-agent conversations.

Features:
- State-based conversation flow management
- Multi-agent orchestration
- Tool execution and reasoning
- Conditional workflow routing
- Memory and context management
"""

import asyncio
import json
import time
import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum

import structlog
from langgraph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

from shared.models import AgentAction, MessageRole, Language, ChatRequest, ChatMessage
from shared.monitoring import get_metrics
from shared.exceptions import ServiceUnavailableError, ValidationError

logger = structlog.get_logger(__name__)


class ConversationState(TypedDict):
    """State for LangGraph conversation workflow."""
    messages: List[Dict[str, Any]]
    current_intent: Optional[str]
    entities: List[Dict[str, Any]]
    context: Dict[str, Any]
    conversation_id: str
    user_id: Optional[str]
    actions_taken: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    reasoning: List[str]
    confidence_score: float
    next_action: Optional[str]
    completion_status: str
    routing_decision: Optional[str]  # rag, tools, direct
    rag_context: List[Dict[str, Any]]
    error_count: int
    processing_stage: str


class WorkflowNode(str, Enum):
    """Workflow node identifiers."""
    START = "start"
    INTENT_CLASSIFICATION = "intent_classification"
    ENTITY_EXTRACTION = "entity_extraction"
    CONTEXT_ANALYSIS = "context_analysis"
    TOOL_SELECTION = "tool_selection"
    TOOL_EXECUTION = "tool_execution"
    RAG_RETRIEVAL = "rag_retrieval"
    RESPONSE_GENERATION = "response_generation"
    CONVERSATION_UPDATE = "conversation_update"
    ERROR_HANDLING = "error_handling"
    END = "end"


class AgentType(str, Enum):
    """Agent types for specialized handling."""
    CRM_AGENT = "crm_agent"
    ERP_AGENT = "erp_agent"
    GENERAL_ASSISTANT = "general_assistant"
    TASK_COORDINATOR = "task_coordinator"


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    actions: List[AgentAction]
    response: str
    reasoning: Optional[str]
    confidence: Optional[float]
    state: ConversationState
    execution_time: float


class LangGraphOrchestrator:
    """LangGraph-based orchestrator for multi-agent conversations."""
    
    def __init__(
        self,
        intent_classifier,
        entity_extractor,
        tool_dispatcher,
        conversation_manager,
        llm_service_url: str = "http://localhost:8004",
        rag_service_url: str = "http://localhost:8005",
        max_retries: int = 3,
    ):
        self.intent_classifier = intent_classifier
        self.entity_extractor = entity_extractor
        self.tool_dispatcher = tool_dispatcher
        self.conversation_manager = conversation_manager
        self.llm_service_url = llm_service_url
        self.rag_service_url = rag_service_url
        self.max_retries = max_retries
        
        # HTTP client for service communication
        self.http_client = None
        
        # Workflow graph
        self.workflow: Optional[StateGraph] = None
        self.compiled_workflow = None
        
        # Agent specializations
        self.agents = {
            AgentType.CRM_AGENT: self._create_crm_agent(),
            AgentType.ERP_AGENT: self._create_erp_agent(),
            AgentType.GENERAL_ASSISTANT: self._create_general_assistant(),
            AgentType.TASK_COORDINATOR: self._create_task_coordinator(),
        }
        
        # Statistics
        self.request_count = 0
        self.error_count = 0
        self.avg_processing_time = 0.0
    
    async def initialize(self) -> None:
        """Initialize the LangGraph orchestrator."""
        logger.info("Initializing LangGraph orchestrator")
        
        try:
            # Initialize HTTP client
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
            )
            
            # Create workflow graph
            self.workflow = StateGraph(ConversationState)
            
            # Add nodes
            self.workflow.add_node(WorkflowNode.INTENT_CLASSIFICATION, self._classify_intent)
            self.workflow.add_node(WorkflowNode.ENTITY_EXTRACTION, self._extract_entities)
            self.workflow.add_node(WorkflowNode.CONTEXT_ANALYSIS, self._analyze_context)
            self.workflow.add_node(WorkflowNode.TOOL_SELECTION, self._select_tools)
            self.workflow.add_node(WorkflowNode.TOOL_EXECUTION, self._execute_tools)
            self.workflow.add_node(WorkflowNode.RAG_RETRIEVAL, self._rag_retrieval)
            self.workflow.add_node(WorkflowNode.RESPONSE_GENERATION, self._generate_response)
            self.workflow.add_node(WorkflowNode.CONVERSATION_UPDATE, self._update_conversation)
            self.workflow.add_node(WorkflowNode.ERROR_HANDLING, self._handle_error)
            
            # Add edges with conditions
            self.workflow.set_entry_point(WorkflowNode.INTENT_CLASSIFICATION)
            
            self.workflow.add_edge(WorkflowNode.INTENT_CLASSIFICATION, WorkflowNode.ENTITY_EXTRACTION)
            self.workflow.add_edge(WorkflowNode.ENTITY_EXTRACTION, WorkflowNode.CONTEXT_ANALYSIS)
            
            # Enhanced conditional routing
            self.workflow.add_conditional_edges(
                WorkflowNode.CONTEXT_ANALYSIS,
                self._route_request,
                {
                    "use_tools": WorkflowNode.TOOL_SELECTION,
                    "use_rag": WorkflowNode.RAG_RETRIEVAL,
                    "direct_response": WorkflowNode.RESPONSE_GENERATION,
                    "error": WorkflowNode.ERROR_HANDLING,
                }
            )
            
            self.workflow.add_edge(WorkflowNode.TOOL_SELECTION, WorkflowNode.TOOL_EXECUTION)
            self.workflow.add_edge(WorkflowNode.TOOL_EXECUTION, WorkflowNode.RESPONSE_GENERATION)
            self.workflow.add_edge(WorkflowNode.RAG_RETRIEVAL, WorkflowNode.RESPONSE_GENERATION)
            self.workflow.add_edge(WorkflowNode.RESPONSE_GENERATION, WorkflowNode.CONVERSATION_UPDATE)
            self.workflow.add_edge(WorkflowNode.CONVERSATION_UPDATE, END)
            self.workflow.add_edge(WorkflowNode.ERROR_HANDLING, END)
            
            # Compile workflow
            self.compiled_workflow = self.workflow.compile()
            
            logger.info("LangGraph orchestrator initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize LangGraph orchestrator", error=str(e))
            raise
    
    async def process_request(
        self,
        text: str,
        conversation_id: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a conversation request using LangGraph workflow."""
        start_time = time.time()
        self.request_count += 1
        
        try:
            # Get conversation history
            history = await self.conversation_manager.get_conversation_history(
                conversation_id, limit=10
            )
            
            # Create initial state
            initial_state = ConversationState(
                messages=[
                    {
                        "role": "user",
                        "content": text,
                        "timestamp": time.time(),
                    }
                ],
                current_intent=None,
                entities=[],
                context=context or {},
                conversation_id=conversation_id,
                user_id=user_id,
                actions_taken=[],
                tool_results=[],
                reasoning=[],
                confidence_score=0.0,
                next_action=None,
                completion_status="pending",
                routing_decision=None,
                rag_context=[],
                error_count=0,
                processing_stage="initializing",
            )
            
            # Add conversation history to state
            for msg in history:
                initial_state["messages"].insert(-1, {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", time.time()),
                })
            
            # Execute workflow
            result_state = await self._execute_workflow(initial_state)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self._update_stats(processing_time)
            
            # Create result
            return {
                "actions": [
                    AgentAction(**action) for action in result_state["actions_taken"]
                ],
                "response": self._extract_response_from_messages(result_state["messages"]),
                "reasoning": " -> ".join(result_state["reasoning"]) if result_state["reasoning"] else None,
                "confidence": result_state["confidence_score"],
                "state": result_state,
            }
            
        except Exception as e:
            self.error_count += 1
            logger.error("Workflow execution failed", error=str(e))
            raise
    
    async def process_request_stream(
        self,
        text: str,
        conversation_id: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Process request with streaming workflow updates."""
        try:
            # Create initial state (similar to process_request)
            history = await self.conversation_manager.get_conversation_history(
                conversation_id, limit=10
            )
            
            initial_state = ConversationState(
                messages=[{"role": "user", "content": text, "timestamp": time.time()}],
                current_intent=None,
                entities=[],
                context=context or {},
                conversation_id=conversation_id,
                user_id=user_id,
                actions_taken=[],
                tool_results=[],
                reasoning=[],
                confidence_score=0.0,
                next_action=None,
                completion_status="pending",
            )
            
            # Stream workflow execution
            async for update in self._execute_workflow_stream(initial_state):
                yield json.dumps(update)
            
        except Exception as e:
            logger.error("Streaming workflow execution failed", error=str(e))
            yield json.dumps({
                "type": "error",
                "error": str(e),
                "timestamp": time.time(),
            })
    
    async def health_check(self) -> bool:
        """Check orchestrator health."""
        try:
            return (
                self.compiled_workflow is not None
                and self.intent_classifier is not None
                and self.entity_extractor is not None
                and self.tool_dispatcher is not None
            )
        except Exception:
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "avg_processing_time": self.avg_processing_time,
            "workflow_nodes": len(self.workflow.nodes) if self.workflow else 0,
            "available_agents": list(self.agents.keys()),
        }
    
    async def close(self) -> None:
        """Clean up orchestrator resources."""
        logger.info("Closing LangGraph orchestrator")
        if self.http_client:
            await self.http_client.aclose()
    
    # Workflow node implementations
    async def _classify_intent(self, state: ConversationState) -> ConversationState:
        """Classify intent from user message."""
        try:
            latest_message = state["messages"][-1]
            text = latest_message["content"]
            
            intent = await self.intent_classifier.classify(text, Language.ENGLISH)
            state["current_intent"] = intent.name if intent else None
            state["reasoning"].append(f"Classified intent: {state['current_intent']}")
            
            if intent:
                state["confidence_score"] = max(state["confidence_score"], intent.confidence)
            
            return state
            
        except Exception as e:
            logger.error("Intent classification failed", error=str(e))
            state["reasoning"].append(f"Intent classification error: {str(e)}")
            return state
    
    async def _extract_entities(self, state: ConversationState) -> ConversationState:
        """Extract entities from user message."""
        try:
            latest_message = state["messages"][-1]
            text = latest_message["content"]
            
            entities = await self.entity_extractor.extract(text, Language.ENGLISH)
            state["entities"] = [
                {
                    "text": entity.text,
                    "label": entity.label,
                    "start": entity.start,
                    "end": entity.end,
                    "confidence": entity.confidence,
                }
                for entity in entities
            ]
            
            state["reasoning"].append(f"Extracted {len(entities)} entities")
            return state
            
        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            state["reasoning"].append(f"Entity extraction error: {str(e)}")
            return state
    
    async def _analyze_context(self, state: ConversationState) -> ConversationState:
        """Analyze conversation context and determine agent type."""
        try:
            intent = state["current_intent"]
            entities = state["entities"]
            
            # Determine appropriate agent based on intent and entities
            agent_type = self._select_agent_type(intent, entities)
            state["context"]["agent_type"] = agent_type
            state["reasoning"].append(f"Selected agent type: {agent_type}")
            
            # Add context analysis
            context_analysis = {
                "has_customer_entities": any(e["label"] in ["PERSON", "ORGANIZATION"] for e in entities),
                "has_product_entities": any(e["label"] in ["PRODUCT", "MONEY"] for e in entities),
                "has_date_entities": any(e["label"] in ["DATE", "TIME"] for e in entities),
                "conversation_length": len(state["messages"]),
                "user_intent_category": self._categorize_intent(intent),
            }
            
            state["context"]["analysis"] = context_analysis
            return state
            
        except Exception as e:
            logger.error("Context analysis failed", error=str(e))
            state["reasoning"].append(f"Context analysis error: {str(e)}")
            return state
    
    def _route_request(self, state: ConversationState) -> str:
        """Enhanced routing logic for tools, RAG, or direct response."""
        intent = state["current_intent"]
        entities = state["entities"]
        user_message = state["messages"][-1]["content"].lower()
        
        # Error handling route
        if state["error_count"] > self.max_retries:
            return "error"
        
        # Tool-requiring intents
        tool_intents = [
            "create_contact", "update_contact", "search_contact",
            "create_order", "update_order", "search_order",
            "get_inventory", "update_inventory",
            "generate_report", "schedule_meeting"
        ]
        
        # RAG-requiring queries (knowledge/information requests)
        rag_keywords = [
            "how", "what", "why", "when", "where", "explain", "tell me",
            "information", "details", "documentation", "guide", "help",
            "procedure", "process", "policy", "workflow"
        ]
        
        # Check for tool usage first
        if intent in tool_intents:
            state["routing_decision"] = "tools"
            return "use_tools"
        
        # Check if entities suggest tool usage
        business_entities = ["PERSON", "ORGANIZATION", "PRODUCT", "MONEY"]
        if any(e["label"] in business_entities for e in entities):
            # If asking about specific entities, might need tools
            action_words = ["create", "update", "delete", "modify", "change"]
            if any(word in user_message for word in action_words):
                state["routing_decision"] = "tools"
                return "use_tools"
        
        # Check for RAG/knowledge queries
        if any(keyword in user_message for keyword in rag_keywords):
            # Questions about procedures, policies, or general knowledge
            if intent not in ["greeting", "help"] and len(user_message.split()) > 3:
                state["routing_decision"] = "rag"
                return "use_rag"
        
        # Default to direct response for greetings, simple queries, etc.
        state["routing_decision"] = "direct"
        return "direct_response"
    
    async def _select_tools(self, state: ConversationState) -> ConversationState:
        """Select appropriate tools for execution."""
        try:
            intent = state["current_intent"]
            entities = state["entities"]
            agent_type = state["context"].get("agent_type", AgentType.GENERAL_ASSISTANT)
            
            # Tool selection based on agent type and intent
            selected_tools = []
            
            if agent_type == AgentType.CRM_AGENT:
                selected_tools = self._select_crm_tools(intent, entities)
            elif agent_type == AgentType.ERP_AGENT:
                selected_tools = self._select_erp_tools(intent, entities)
            else:
                selected_tools = self._select_general_tools(intent, entities)
            
            state["context"]["selected_tools"] = selected_tools
            state["reasoning"].append(f"Selected tools: {[tool['name'] for tool in selected_tools]}")
            
            return state
            
        except Exception as e:
            logger.error("Tool selection failed", error=str(e))
            state["reasoning"].append(f"Tool selection error: {str(e)}")
            return state
    
    async def _execute_tools(self, state: ConversationState) -> ConversationState:
        """Execute selected tools."""
        try:
            selected_tools = state["context"].get("selected_tools", [])
            tool_results = []
            
            for tool_config in selected_tools:
                tool_name = tool_config["name"]
                parameters = tool_config.get("parameters", {})
                
                # Execute tool
                result = await self.tool_dispatcher.execute_tool(tool_name, parameters)
                
                tool_result = {
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "success": True,
                    "timestamp": time.time(),
                }
                
                tool_results.append(tool_result)
                
                # Record action
                action = {
                    "action": f"execute_{tool_name}",
                    "parameters": parameters,
                    "tool_name": tool_name,
                    "reasoning": f"Executed {tool_name} to fulfill user request",
                }
                state["actions_taken"].append(action)
            
            state["tool_results"] = tool_results
            state["reasoning"].append(f"Executed {len(tool_results)} tools")
            
            return state
            
        except Exception as e:
            logger.error("Tool execution failed", error=str(e))
            state["reasoning"].append(f"Tool execution error: {str(e)}")
            return state
    
    async def _rag_retrieval(self, state: ConversationState) -> ConversationState:
        """Retrieve relevant context using RAG service."""
        try:
            user_message = state["messages"][-1]["content"]
            
            # Call RAG service
            rag_request = {
                "question": user_message,
                "top_k": 5,
                "similarity_threshold": 0.7,
                "include_sources": True
            }
            
            if self.http_client:
                response = await self.http_client.post(
                    f"{self.rag_service_url}/rag",
                    json=rag_request,
                    timeout=30.0
                )
                response.raise_for_status()
                rag_result = response.json()
                
                # Store RAG context
                state["rag_context"] = rag_result.get("sources", [])
                state["reasoning"].append(f"Retrieved {len(state['rag_context'])} relevant documents")
            else:
                logger.warning("HTTP client not available for RAG retrieval")
                state["rag_context"] = []
            
            return state
            
        except Exception as e:
            logger.error("RAG retrieval failed", error=str(e))
            state["error_count"] += 1
            state["reasoning"].append(f"RAG retrieval error: {str(e)}")
            state["rag_context"] = []
            return state
    
    async def _generate_response(self, state: ConversationState) -> ConversationState:
        """Generate response using LLM with enhanced context."""
        try:
            state["processing_stage"] = "generating_response"
            
            # Prepare enhanced context for LLM
            context_data = {
                "intent": state["current_intent"],
                "entities": state["entities"],
                "tool_results": state["tool_results"],
                "rag_context": state["rag_context"],
                "conversation_history": state["messages"][:-1],
                "user_message": state["messages"][-1]["content"],
                "routing_decision": state["routing_decision"],
                "reasoning_chain": state["reasoning"],
            }
            
            # Select agent for response generation
            agent_type = state["context"].get("agent_type", AgentType.GENERAL_ASSISTANT)
            
            # Generate response using LLM service
            response = await self._call_llm_service(context_data, agent_type)
            
            # Add response to messages
            response_message = {
                "role": "assistant",
                "content": response,
                "timestamp": time.time(),
                "agent_type": agent_type,
                "routing_used": state["routing_decision"],
            }
            state["messages"].append(response_message)
            
            state["reasoning"].append(f"Generated response using {agent_type} via LLM service")
            state["completion_status"] = "completed"
            
            return state
            
        except Exception as e:
            logger.error("Response generation failed", error=str(e))
            state["error_count"] += 1
            state["reasoning"].append(f"Response generation error: {str(e)}")
            
            # Fallback response
            fallback_response = {
                "role": "assistant",
                "content": "I apologize, but I encountered an error while processing your request. Please try again.",
                "timestamp": time.time(),
                "routing_used": "fallback",
            }
            state["messages"].append(fallback_response)
            state["completion_status"] = "error"
            
            return state
    
    async def _handle_error(self, state: ConversationState) -> ConversationState:
        """Handle errors and provide appropriate responses."""
        try:
            error_message = {
                "role": "assistant",
                "content": "I'm experiencing some technical difficulties. Please try your request again or contact support if the problem persists.",
                "timestamp": time.time(),
                "routing_used": "error_handler",
            }
            state["messages"].append(error_message)
            state["completion_status"] = "error"
            state["reasoning"].append("Handled via error workflow")
            
            return state
            
        except Exception as e:
            logger.error("Error handler failed", error=str(e))
            # Return state as-is to prevent infinite loops
            return state
    
    async def _call_llm_service(
        self, 
        context_data: Dict[str, Any], 
        agent_type: AgentType
    ) -> str:
        """Call LLM service for response generation."""
        try:
            # Create system prompt based on agent type
            system_prompt = self._create_system_prompt(agent_type, context_data)
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history (last 5 messages to avoid context overflow)
            history = context_data.get("conversation_history", [])[-5:]
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": context_data["user_message"]
            })
            
            # Create LLM request
            llm_request = {
                "model": "gpt-oss-20b",  # or configured model
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            }
            
            if self.http_client:
                response = await self.http_client.post(
                    f"{self.llm_service_url}/v1/chat/completions",
                    json=llm_request,
                    timeout=60.0
                )
                response.raise_for_status()
                llm_result = response.json()
                
                # Extract response content
                if "choices" in llm_result and len(llm_result["choices"]) > 0:
                    return llm_result["choices"][0]["message"]["content"]
                else:
                    raise ValueError("Invalid LLM response format")
            else:
                # Fallback to simple agent response
                agent = self.agents[agent_type]
                return await agent.generate_response(context_data)
            
        except Exception as e:
            logger.error("LLM service call failed", error=str(e))
            # Fallback to simple agent response
            agent = self.agents[agent_type]
            return await agent.generate_response(context_data)
    
    def _create_system_prompt(self, agent_type: AgentType, context_data: Dict[str, Any]) -> str:
        """Create system prompt based on agent type and context."""
        base_prompt = "You are a helpful AI assistant for WearForce, a business productivity platform."
        
        if agent_type == AgentType.CRM_AGENT:
            base_prompt += " You specialize in customer relationship management tasks."
        elif agent_type == AgentType.ERP_AGENT:
            base_prompt += " You specialize in enterprise resource planning and business operations."
        elif agent_type == AgentType.TASK_COORDINATOR:
            base_prompt += " You help coordinate and manage tasks across different business systems."
        
        # Add context information
        intent = context_data.get("intent")
        if intent:
            base_prompt += f" The user's intent appears to be: {intent}."
        
        # Add tool results context
        tool_results = context_data.get("tool_results", [])
        if tool_results:
            base_prompt += f" I have executed {len(tool_results)} tool(s) to gather information."
        
        # Add RAG context
        rag_context = context_data.get("rag_context", [])
        if rag_context:
            base_prompt += f" I have relevant knowledge from {len(rag_context)} document(s) to help answer."
            
            # Include actual RAG content in prompt
            base_prompt += "\n\nRelevant information:\n"
            for i, doc in enumerate(rag_context[:3]):  # Limit to top 3 documents
                content = doc.get("content", "")[:500]  # Truncate long content
                base_prompt += f"\n{i+1}. {content}\n"
        
        base_prompt += "\nPlease provide a helpful, accurate, and concise response."
        
        return base_prompt
    
    async def _update_conversation(self, state: ConversationState) -> ConversationState:
        """Update conversation history."""
        try:
            conversation_id = state["conversation_id"]
            
            # Add user message to conversation
            user_message = state["messages"][-2]  # Second to last (assistant is last)
            await self.conversation_manager.add_message(
                conversation_id, user_message
            )
            
            # Add assistant message to conversation
            assistant_message = state["messages"][-1]
            await self.conversation_manager.add_message(
                conversation_id, assistant_message
            )
            
            state["reasoning"].append("Updated conversation history")
            return state
            
        except Exception as e:
            logger.error("Conversation update failed", error=str(e))
            state["reasoning"].append(f"Conversation update error: {str(e)}")
            return state
    
    # Helper methods
    async def _execute_workflow(self, initial_state: ConversationState) -> ConversationState:
        """Execute the workflow graph."""
        try:
            result = await self.compiled_workflow.ainvoke(initial_state)
            return result
        except Exception as e:
            logger.error("Workflow execution failed", error=str(e))
            raise
    
    async def _execute_workflow_stream(
        self, 
        initial_state: ConversationState
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute workflow with streaming updates."""
        try:
            async for chunk in self.compiled_workflow.astream(initial_state):
                yield {
                    "type": "workflow_update",
                    "data": chunk,
                    "timestamp": time.time(),
                }
        except Exception as e:
            logger.error("Streaming workflow execution failed", error=str(e))
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": time.time(),
            }
    
    def _select_agent_type(self, intent: Optional[str], entities: List[Dict]) -> AgentType:
        """Select appropriate agent type based on intent and entities."""
        if not intent:
            return AgentType.GENERAL_ASSISTANT
        
        # CRM-related intents
        crm_intents = ["create_contact", "update_contact", "search_contact", "schedule_meeting"]
        if intent in crm_intents:
            return AgentType.CRM_AGENT
        
        # ERP-related intents
        erp_intents = ["create_order", "update_order", "search_order", "get_inventory", "update_inventory"]
        if intent in erp_intents:
            return AgentType.ERP_AGENT
        
        # Check entities for business context
        business_entities = ["ORGANIZATION", "PRODUCT", "MONEY"]
        if any(e["label"] in business_entities for e in entities):
            return AgentType.TASK_COORDINATOR
        
        return AgentType.GENERAL_ASSISTANT
    
    def _categorize_intent(self, intent: Optional[str]) -> str:
        """Categorize intent for context analysis."""
        if not intent:
            return "unknown"
        
        categories = {
            "create": ["create_contact", "create_order", "create_task"],
            "update": ["update_contact", "update_order", "update_inventory"],
            "search": ["search_contact", "search_order", "search_product"],
            "report": ["generate_report", "get_analytics"],
            "schedule": ["schedule_meeting", "set_reminder"],
        }
        
        for category, intents in categories.items():
            if intent in intents:
                return category
        
        return "general"
    
    def _select_crm_tools(self, intent: str, entities: List[Dict]) -> List[Dict]:
        """Select CRM tools based on intent and entities."""
        tools = []
        
        if intent == "create_contact":
            tools.append({"name": "create_crm_contact", "parameters": self._extract_contact_params(entities)})
        elif intent == "search_contact":
            tools.append({"name": "search_crm_contacts", "parameters": self._extract_search_params(entities)})
        elif intent == "schedule_meeting":
            tools.append({"name": "schedule_crm_meeting", "parameters": self._extract_meeting_params(entities)})
        
        return tools
    
    def _select_erp_tools(self, intent: str, entities: List[Dict]) -> List[Dict]:
        """Select ERP tools based on intent and entities."""
        tools = []
        
        if intent == "create_order":
            tools.append({"name": "create_erp_order", "parameters": self._extract_order_params(entities)})
        elif intent == "get_inventory":
            tools.append({"name": "get_erp_inventory", "parameters": self._extract_inventory_params(entities)})
        elif intent == "generate_report":
            tools.append({"name": "generate_erp_report", "parameters": self._extract_report_params(entities)})
        
        return tools
    
    def _select_general_tools(self, intent: str, entities: List[Dict]) -> List[Dict]:
        """Select general tools."""
        tools = []
        
        # Add general utility tools as needed
        if any(e["label"] == "DATE" for e in entities):
            tools.append({"name": "get_date_info", "parameters": {}})
        
        return tools
    
    def _extract_contact_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract contact parameters from entities."""
        params = {}
        
        for entity in entities:
            if entity["label"] == "PERSON":
                params["name"] = entity["text"]
            elif entity["label"] == "EMAIL":
                params["email"] = entity["text"]
            elif entity["label"] == "PHONE":
                params["phone"] = entity["text"]
            elif entity["label"] == "ORGANIZATION":
                params["company"] = entity["text"]
        
        return params
    
    def _extract_search_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract search parameters from entities."""
        params = {"query": ""}
        
        for entity in entities:
            if entity["label"] in ["PERSON", "ORGANIZATION"]:
                params["query"] = entity["text"]
                break
        
        return params
    
    def _extract_meeting_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract meeting parameters from entities."""
        params = {}
        
        for entity in entities:
            if entity["label"] == "DATE":
                params["date"] = entity["text"]
            elif entity["label"] == "TIME":
                params["time"] = entity["text"]
            elif entity["label"] == "PERSON":
                params["attendee"] = entity["text"]
        
        return params
    
    def _extract_order_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract order parameters from entities."""
        params = {}
        
        for entity in entities:
            if entity["label"] == "PRODUCT":
                params["product"] = entity["text"]
            elif entity["label"] == "QUANTITY":
                params["quantity"] = entity["text"]
            elif entity["label"] == "MONEY":
                params["amount"] = entity["text"]
        
        return params
    
    def _extract_inventory_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract inventory parameters from entities."""
        params = {}
        
        for entity in entities:
            if entity["label"] == "PRODUCT":
                params["product"] = entity["text"]
        
        return params
    
    def _extract_report_params(self, entities: List[Dict]) -> Dict[str, Any]:
        """Extract report parameters from entities."""
        params = {"type": "general"}
        
        for entity in entities:
            if entity["label"] == "DATE":
                params["date_range"] = entity["text"]
        
        return params
    
    def _extract_response_from_messages(self, messages: List[Dict]) -> str:
        """Extract the assistant's response from messages."""
        for message in reversed(messages):
            if message.get("role") == "assistant":
                return message.get("content", "")
        
        return "I apologize, but I couldn't generate a response."
    
    def _update_stats(self, processing_time: float) -> None:
        """Update processing statistics."""
        # Update average processing time using exponential moving average
        alpha = 0.1
        self.avg_processing_time = (
            alpha * processing_time + (1 - alpha) * self.avg_processing_time
        )
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_inference("langgraph_orchestration", processing_time)
    
    # Agent implementations (simplified)
    def _create_crm_agent(self):
        """Create CRM specialized agent."""
        return SimpleAgent("CRM Agent", "I help with customer relationship management tasks.")
    
    def _create_erp_agent(self):
        """Create ERP specialized agent."""
        return SimpleAgent("ERP Agent", "I help with enterprise resource planning tasks.")
    
    def _create_general_assistant(self):
        """Create general assistant agent.""" 
        return SimpleAgent("General Assistant", "I'm a general-purpose AI assistant.")
    
    def _create_task_coordinator(self):
        """Create task coordinator agent."""
        return SimpleAgent("Task Coordinator", "I help coordinate and manage tasks across different systems.")


class SimpleAgent:
    """Enhanced agent for response generation."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def generate_response(self, context: Dict[str, Any]) -> str:
        """Generate response based on context."""
        intent = context.get("intent")
        tool_results = context.get("tool_results", [])
        rag_context = context.get("rag_context", [])
        user_message = context.get("user_message", "")
        routing_decision = context.get("routing_decision")
        
        # Handle tool results
        if tool_results:
            successful_tools = [r for r in tool_results if r.get("success")]
            failed_tools = [r for r in tool_results if not r.get("success")]
            
            response_parts = []
            
            if successful_tools:
                response_parts.append("I've successfully completed the following actions:")
                for result in successful_tools:
                    tool_name = result.get("tool_name", "unknown")
                    response_parts.append(f"- {tool_name.replace('_', ' ').title()}")
            
            if failed_tools:
                response_parts.append("However, I encountered issues with:")
                for result in failed_tools:
                    tool_name = result.get("tool_name", "unknown")
                    response_parts.append(f"- {tool_name.replace('_', ' ').title()}")
            
            return " ".join(response_parts) if response_parts else "I've processed your request."
        
        # Handle RAG-based responses
        elif rag_context:
            if len(rag_context) > 0:
                return "Based on the available information, I can help you with that. Let me provide you with the relevant details."
            else:
                return "I searched for relevant information but couldn't find specific details. Could you provide more context?"
        
        # Handle direct responses
        else:
            if intent == "greeting":
                return f"Hello! I'm {self.name}. {self.description} How can I assist you today?"
            elif intent == "help":
                return f"I'd be happy to help! As {self.name}, I can assist with various tasks. What would you like to do?"
            elif intent:
                action = intent.replace('_', ' ')
                return f"I understand you want to {action}. Let me help you with that. What specific details do you need?"
            else:
                return f"I'm {self.name} and I'm here to help. Could you please tell me what you'd like to accomplish?"