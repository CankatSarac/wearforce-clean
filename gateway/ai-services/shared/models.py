"""Shared Pydantic models for AI services."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ResponseStatus(str, Enum):
    """Response status enumeration."""
    
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class HealthStatus(str, Enum):
    """Health status enumeration."""
    
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class AudioFormat(str, Enum):
    """Supported audio formats."""
    
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"
    WEBM = "webm"


class Language(str, Enum):
    """Supported languages."""
    
    ENGLISH = "en"
    TURKISH = "tr"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    JAPANESE = "ja"
    KOREAN = "ko"
    CHINESE = "zh"
    ARABIC = "ar"


class MessageRole(str, Enum):
    """Message role in conversation."""
    
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"


class VectorSearchType(str, Enum):
    """Vector search types."""
    
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


# Base Response Models
class BaseResponse(BaseModel):
    """Base response model."""
    
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ErrorResponse(BaseResponse):
    """Error response model."""
    
    status: ResponseStatus = ResponseStatus.ERROR
    error_code: str
    details: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: HealthStatus
    service: str
    version: str = "1.0.0"
    checks: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# STT Models
class STTRequest(BaseModel):
    """Speech-to-text request."""
    
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio data")
    audio_url: Optional[str] = Field(None, description="URL to audio file")
    format: AudioFormat = AudioFormat.WAV
    language: Optional[Language] = None
    model: str = "base.en"
    temperature: float = Field(0.0, ge=0.0, le=1.0)
    enable_vad: bool = True
    return_timestamps: bool = False
    return_word_level_timestamps: bool = False
    
    @validator("audio_data", "audio_url")
    def validate_audio_source(cls, v, values):
        """Ensure at least one audio source is provided."""
        if not v and not values.get("audio_data") and not values.get("audio_url"):
            raise ValueError("Either audio_data or audio_url must be provided")
        return v


class STTSegment(BaseModel):
    """STT segment with timestamp."""
    
    text: str
    start: float
    end: float
    confidence: Optional[float] = None


class STTWord(BaseModel):
    """STT word-level result."""
    
    word: str
    start: float
    end: float
    confidence: float


class STTResponse(BaseResponse):
    """Speech-to-text response."""
    
    text: str
    language: Optional[Language] = None
    confidence: Optional[float] = None
    duration: Optional[float] = None
    segments: List[STTSegment] = Field(default_factory=list)
    words: List[STTWord] = Field(default_factory=list)
    processing_time: float


class StreamSTTChunk(BaseModel):
    """Streaming STT chunk."""
    
    text: str
    is_partial: bool = True
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# TTS Models  
class TTSRequest(BaseModel):
    """Text-to-speech request."""
    
    text: str = Field(..., max_length=5000)
    voice: str = "en_US-lessac-high"
    language: Language = Language.ENGLISH
    speed: float = Field(1.0, ge=0.1, le=3.0)
    pitch: float = Field(1.0, ge=0.1, le=2.0)
    volume: float = Field(1.0, ge=0.1, le=2.0)
    format: AudioFormat = AudioFormat.WAV
    sample_rate: int = Field(22050, ge=8000, le=48000)
    enable_streaming: bool = False


class TTSResponse(BaseResponse):
    """Text-to-speech response."""
    
    audio_data: str = Field(..., description="Base64 encoded audio")
    audio_url: Optional[str] = None
    format: AudioFormat
    sample_rate: int
    duration: float
    processing_time: float


class VoiceInfo(BaseModel):
    """Voice information."""
    
    id: str
    name: str
    language: Language
    gender: str
    description: Optional[str] = None
    sample_rate: int = 22050
    is_custom: bool = False


class VoicesResponse(BaseResponse):
    """Available voices response."""
    
    voices: List[VoiceInfo]


# LLM Models
class ChatMessage(BaseModel):
    """Chat message."""
    
    role: MessageRole
    content: str
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Chat completion request (OpenAI compatible)."""
    
    model: str
    messages: List[ChatMessage]
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(0.0, ge=-2.0, le=2.0)
    stop: Optional[Union[str, List[str]]] = None
    stream: bool = False
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None


class ChatChoice(BaseModel):
    """Chat completion choice."""
    
    index: int
    message: ChatMessage
    finish_reason: str


class TokenUsage(BaseModel):
    """Token usage statistics."""
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseResponse):
    """Chat completion response."""
    
    model: str
    choices: List[ChatChoice]
    usage: TokenUsage
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))


class StreamChatChunk(BaseModel):
    """Streaming chat chunk."""
    
    id: str
    model: str
    choices: List[Dict[str, Any]]
    created: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp()))


# RAG Models
class Document(BaseModel):
    """Document model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentChunk(BaseModel):
    """Document chunk for vectorization."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None


class VectorSearchRequest(BaseModel):
    """Vector search request."""
    
    query: str
    collection: Optional[str] = None
    top_k: int = Field(5, ge=1, le=100)
    search_type: VectorSearchType = VectorSearchType.HYBRID
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None
    include_metadata: bool = True


class SearchResult(BaseModel):
    """Search result."""
    
    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None


class VectorSearchResponse(BaseResponse):
    """Vector search response."""
    
    query: str
    results: List[SearchResult]
    total_results: int
    processing_time: float


class RAGRequest(BaseModel):
    """RAG (Retrieval-Augmented Generation) request."""
    
    question: str
    collection: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)
    include_sources: bool = True
    model: str = "gpt-oss-20b"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=4096)


class RAGResponse(BaseResponse):
    """RAG response."""
    
    question: str
    answer: str
    sources: List[SearchResult] = Field(default_factory=list)
    confidence: Optional[float] = None
    model_used: str
    processing_time: float


# NLU Models
class Intent(BaseModel):
    """Intent classification result."""
    
    name: str
    confidence: float
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """Named entity."""
    
    text: str
    label: str
    start: int
    end: int
    confidence: float


class NLURequest(BaseModel):
    """Natural Language Understanding request."""
    
    text: str
    language: Language = Language.ENGLISH
    conversation_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    extract_entities: bool = True
    classify_intent: bool = True


class NLUResponse(BaseResponse):
    """NLU response."""
    
    text: str
    language: Language
    intent: Optional[Intent] = None
    entities: List[Entity] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    processing_time: float


class ConversationMessage(BaseModel):
    """Conversation message."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Conversation(BaseModel):
    """Conversation model."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    messages: List[ConversationMessage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True


class AgentAction(BaseModel):
    """Agent action."""
    
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    tool_name: Optional[str] = None
    reasoning: Optional[str] = None


class AgentResponse(BaseResponse):
    """Agent response."""
    
    conversation_id: str
    actions: List[AgentAction] = Field(default_factory=list)
    response: str
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    processing_time: float


# Tool Integration Models
class ToolDefinition(BaseModel):
    """Tool definition for agents."""
    
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str] = Field(default_factory=list)
    service_url: str
    authentication: Optional[Dict[str, str]] = None


class ToolCall(BaseModel):
    """Tool call request."""
    
    tool_name: str
    parameters: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class ToolResult(BaseModel):
    """Tool execution result."""
    
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float


# Batch Processing Models
class BatchRequest(BaseModel):
    """Batch processing request."""
    
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requests: List[Dict[str, Any]]
    priority: int = Field(0, ge=0, le=10)
    timeout: Optional[int] = None


class BatchResponse(BaseResponse):
    """Batch processing response."""
    
    batch_id: str
    results: List[Dict[str, Any]]
    completed: int
    failed: int
    processing_time: float


# Metrics Models
class ServiceMetrics(BaseModel):
    """Service metrics."""
    
    service_name: str
    requests_per_second: float
    average_response_time: float
    error_rate: float
    active_connections: int
    memory_usage: float
    cpu_usage: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ModelMetrics(BaseModel):
    """Model-specific metrics."""
    
    model_name: str
    inference_count: int
    average_inference_time: float
    tokens_processed: int
    gpu_memory_usage: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# WebSocket Models
class WebSocketMessage(BaseModel):
    """WebSocket message."""
    
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None


class WebSocketResponse(BaseModel):
    """WebSocket response."""
    
    type: str
    data: Dict[str, Any]
    status: ResponseStatus = ResponseStatus.SUCCESS
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Configuration Models
class ModelConfig(BaseModel):
    """Model configuration."""
    
    name: str
    path: str
    type: str  # llm, embedding, stt, tts
    device: str = "cuda"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    is_loaded: bool = False
    load_time: Optional[datetime] = None


class ServiceInfo(BaseModel):
    """Service information."""
    
    name: str
    version: str
    description: str
    endpoints: List[str]
    models: List[ModelConfig] = Field(default_factory=list)
    status: HealthStatus = HealthStatus.HEALTHY
    uptime: Optional[float] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)