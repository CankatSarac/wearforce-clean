"""
NLU/Agent Router Service - FastAPI app with LangGraph orchestration.

Provides:
- Intent classification and entity extraction
- Multi-agent conversation handling
- Tool dispatcher for CRM/ERP operations
- LangGraph workflow orchestration
- Redis-based conversation history
- Function calling and tool execution
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse

from shared.config import NLUServiceConfig, get_config, setup_logging
from shared.database import RedisManager, ConversationStore
from shared.exceptions import ValidationError, ServiceUnavailableError
from shared.middleware import setup_middleware
from shared.models import (
    NLURequest,
    NLUResponse,
    AgentResponse,
    ConversationMessage,
    Conversation,
    HealthResponse,
    HealthStatus,
    MessageRole,
    Intent,
    Entity,
    AgentAction,
)
from shared.monitoring import init_metrics, get_metrics, health_checker, metrics_endpoint
from shared.utils import generate_uuid

from .langgraph_orchestrator import LangGraphOrchestrator
from .intent_classifier import IntentClassifier
from .entity_extractor import EntityExtractor
from .tool_dispatcher import ToolDispatcher
from .conversation_manager import ConversationManager

logger = structlog.get_logger(__name__)


# Global managers
orchestrator: Optional[LangGraphOrchestrator] = None
intent_classifier: Optional[IntentClassifier] = None
entity_extractor: Optional[EntityExtractor] = None
tool_dispatcher: Optional[ToolDispatcher] = None
conversation_manager: Optional[ConversationManager] = None
redis_manager: Optional[RedisManager] = None
conversation_store: Optional[ConversationStore] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle."""
    global orchestrator, intent_classifier, entity_extractor, tool_dispatcher
    global conversation_manager, redis_manager, conversation_store
    
    config = get_config()
    nlu_config = NLUServiceConfig()
    
    try:
        logger.info("Starting NLU/Agent Router Service", service=nlu_config.name)
        
        # Initialize Redis
        redis_manager = RedisManager(config.redis)
        await redis_manager.health_check()
        logger.info("Redis connection established")
        
        # Initialize conversation store
        conversation_store = ConversationStore(
            redis_manager, 
            ttl=nlu_config.conversation_ttl
        )
        
        # Initialize intent classifier
        intent_classifier = IntentClassifier()
        await intent_classifier.initialize()
        logger.info("Intent classifier initialized")
        
        # Initialize entity extractor
        entity_extractor = EntityExtractor()
        await entity_extractor.initialize()
        logger.info("Entity extractor initialized")
        
        # Initialize tool dispatcher
        tool_dispatcher = ToolDispatcher(
            crm_api_url=nlu_config.crm_api_url,
            erp_api_url=nlu_config.erp_api_url,
        )
        await tool_dispatcher.initialize()
        logger.info("Tool dispatcher initialized")
        
        # Initialize conversation manager
        conversation_manager = ConversationManager(
            conversation_store=conversation_store,
            max_history=nlu_config.max_conversation_history,
        )
        
        # Initialize LangGraph orchestrator
        orchestrator = LangGraphOrchestrator(
            intent_classifier=intent_classifier,
            entity_extractor=entity_extractor,
            tool_dispatcher=tool_dispatcher,
            conversation_manager=conversation_manager,
        )
        await orchestrator.initialize()
        logger.info("LangGraph orchestrator initialized")
        
        # Setup health checks
        health_checker.add_check("redis", redis_manager.health_check)
        health_checker.add_check("orchestrator", orchestrator.health_check)
        health_checker.add_check("tool_dispatcher", tool_dispatcher.health_check)
        
        logger.info("NLU/Agent Router Service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start NLU service", error=str(e))
        raise
    finally:
        logger.info("Shutting down NLU/Agent Router Service")
        
        # Cleanup resources
        if orchestrator:
            await orchestrator.close()
        if tool_dispatcher:
            await tool_dispatcher.close()
        if redis_manager:
            await redis_manager.close()


# Create FastAPI app
config = get_config()
nlu_config = NLUServiceConfig()

app = FastAPI(
    title="WearForce NLU/Agent Router Service",
    description="Natural Language Understanding and Agent orchestration service",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup logging and metrics
setup_logging(config.logging)
init_metrics(nlu_config.name)

# Setup middleware
setup_middleware(
    app,
    service_name=nlu_config.name,
    cors_origins=nlu_config.cors_origins,
    requests_per_minute=nlu_config.rate_limit_per_minute,
    enable_gzip=True,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    checks = await health_checker.check_health()
    
    status = HealthStatus.HEALTHY
    if checks["status"] != "healthy":
        status = HealthStatus.UNHEALTHY
    
    return HealthResponse(
        status=status,
        service=nlu_config.name,
        checks=checks,
    )


@app.get("/metrics")
async def get_metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return metrics_endpoint()


@app.post("/nlu", response_model=NLUResponse)
async def process_nlu(request: NLURequest) -> NLUResponse:
    """Process Natural Language Understanding request."""
    if not intent_classifier or not entity_extractor:
        raise ServiceUnavailableError("NLU components not initialized")
    
    start_time = time.time()
    
    try:
        # Classify intent
        intent = None
        if request.classify_intent:
            intent = await intent_classifier.classify(request.text, request.language)
        
        # Extract entities
        entities = []
        if request.extract_entities:
            entities = await entity_extractor.extract(request.text, request.language)
        
        processing_time = time.time() - start_time
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_inference("nlu", processing_time)
        
        return NLUResponse(
            text=request.text,
            language=request.language,
            intent=intent,
            entities=entities,
            conversation_id=request.conversation_id,
            processing_time=processing_time,
        )
        
    except Exception as e:
        logger.error("NLU processing failed", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("nlu_processing", "nlu_service")
        raise


@app.post("/agent", response_model=AgentResponse)
async def process_agent_request(
    request: Dict,
    background_tasks: BackgroundTasks,
) -> AgentResponse:
    """Process agent request with LangGraph orchestration."""
    if not orchestrator:
        raise ServiceUnavailableError("Agent orchestrator not initialized")
    
    start_time = time.time()
    
    try:
        # Extract request parameters
        text = request.get("text", "")
        conversation_id = request.get("conversation_id", generate_uuid())
        user_id = request.get("user_id")
        context = request.get("context", {})
        
        if not text:
            raise ValidationError("Text is required")
        
        # Process with LangGraph orchestrator
        result = await orchestrator.process_request(
            text=text,
            conversation_id=conversation_id,
            user_id=user_id,
            context=context,
        )
        
        processing_time = time.time() - start_time
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_inference("agent", processing_time)
        
        return AgentResponse(
            conversation_id=conversation_id,
            actions=result.get("actions", []),
            response=result.get("response", ""),
            reasoning=result.get("reasoning"),
            confidence=result.get("confidence"),
            processing_time=processing_time,
        )
        
    except Exception as e:
        logger.error("Agent processing failed", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("agent_processing", "nlu_service")
        raise


@app.post("/agent/stream")
async def process_agent_stream(request: Dict) -> StreamingResponse:
    """Process agent request with streaming response."""
    if not orchestrator:
        raise ServiceUnavailableError("Agent orchestrator not initialized")
    
    return StreamingResponse(
        _stream_agent_response(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _stream_agent_response(request: Dict) -> AsyncGenerator[str, None]:
    """Stream agent response."""
    try:
        text = request.get("text", "")
        conversation_id = request.get("conversation_id", generate_uuid())
        user_id = request.get("user_id")
        context = request.get("context", {})
        
        async for chunk in orchestrator.process_request_stream(
            text=text,
            conversation_id=conversation_id,
            user_id=user_id,
            context=context,
        ):
            yield f"data: {chunk}\n\n"
        
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error("Agent streaming failed", error=str(e))
        error_chunk = {
            "error": {
                "message": "Agent processing failed",
                "type": "processing_error",
            }
        }
        yield f"data: {error_chunk}\n\n"


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict:
    """Get conversation history."""
    if not conversation_store:
        raise ServiceUnavailableError("Conversation store not initialized")
    
    conversation = await conversation_store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@app.post("/conversations/{conversation_id}/messages")
async def add_conversation_message(
    conversation_id: str,
    message: Dict,
) -> Dict:
    """Add message to conversation."""
    if not conversation_store:
        raise ServiceUnavailableError("Conversation store not initialized")
    
    # Create conversation message
    conv_message = {
        "role": message.get("role", "user"),
        "content": message.get("content", ""),
        "timestamp": time.time(),
        "metadata": message.get("metadata", {}),
    }
    
    await conversation_store.add_message(conversation_id, conv_message)
    
    return {"status": "message_added", "conversation_id": conversation_id}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict:
    """Delete conversation."""
    if not conversation_store:
        raise ServiceUnavailableError("Conversation store not initialized")
    
    await conversation_store.delete_conversation(conversation_id)
    
    return {"status": "conversation_deleted", "conversation_id": conversation_id}


@app.get("/tools")
async def list_tools() -> Dict:
    """List available tools."""
    if not tool_dispatcher:
        raise ServiceUnavailableError("Tool dispatcher not initialized")
    
    return {
        "tools": tool_dispatcher.list_tools(),
    }


@app.post("/tools/execute")
async def execute_tool(request: Dict) -> Dict:
    """Execute a tool."""
    if not tool_dispatcher:
        raise ServiceUnavailableError("Tool dispatcher not initialized")
    
    tool_name = request.get("tool_name")
    parameters = request.get("parameters", {})
    
    if not tool_name:
        raise ValidationError("Tool name is required")
    
    try:
        result = await tool_dispatcher.execute_tool(tool_name, parameters)
        return {
            "status": "success",
            "result": result,
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}", error=str(e))
        return {
            "status": "error",
            "error": str(e),
        }


@app.get("/intents")
async def list_intents() -> Dict:
    """List available intents."""
    if not intent_classifier:
        raise ServiceUnavailableError("Intent classifier not initialized")
    
    return {
        "intents": intent_classifier.list_intents(),
    }


@app.get("/entities")
async def list_entities() -> Dict:
    """List entity types."""
    if not entity_extractor:
        raise ServiceUnavailableError("Entity extractor not initialized")
    
    return {
        "entity_types": entity_extractor.list_entity_types(),
    }


@app.get("/stats")
async def get_service_stats() -> Dict:
    """Get service statistics."""
    stats = {
        "service": nlu_config.name,
        "uptime": time.time(),
    }
    
    if orchestrator:
        stats["orchestrator"] = await orchestrator.get_stats()
    
    if intent_classifier:
        stats["intent_classifier"] = intent_classifier.get_stats()
    
    if entity_extractor:
        stats["entity_extractor"] = entity_extractor.get_stats()
    
    if tool_dispatcher:
        stats["tool_dispatcher"] = await tool_dispatcher.get_stats()
    
    return stats


if __name__ == "__main__":
    config = NLUServiceConfig()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        log_level="info",
        reload=config.debug,
        access_log=True,
    )