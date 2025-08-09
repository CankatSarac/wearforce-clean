"""Configuration management for AI services."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field, validator


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    host: str = Field(default="localhost", env="DB_HOST")
    port: int = Field(default=5432, env="DB_PORT")
    user: str = Field(default="postgres", env="DB_USER")
    password: str = Field(default="", env="DB_PASSWORD")
    database: str = Field(default="wearforce", env="DB_NAME")
    
    @property
    def url(self) -> str:
        """Get database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseSettings):
    """Redis configuration."""
    
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    db: int = Field(default=0, env="REDIS_DB")
    max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    
    @property
    def url(self) -> str:
        """Get Redis URL."""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class QdrantConfig(BaseSettings):
    """Qdrant vector database configuration."""
    
    host: str = Field(default="localhost", env="QDRANT_HOST")
    port: int = Field(default=6333, env="QDRANT_PORT")
    api_key: Optional[str] = Field(default=None, env="QDRANT_API_KEY")
    collection_name: str = Field(default="wearforce_docs", env="QDRANT_COLLECTION")
    embedding_dim: int = Field(default=384, env="EMBEDDING_DIM")
    
    @property
    def url(self) -> str:
        """Get Qdrant URL."""
        return f"http://{self.host}:{self.port}"


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    
    level: str = Field(default="INFO", env="LOG_LEVEL")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    structured: bool = Field(default=True, env="LOG_STRUCTURED")
    
    @validator("level")
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()


class ModelConfig(BaseSettings):
    """Model configuration."""
    
    # LLM settings
    llm_model_path: str = Field(default="models/gpt-oss-20b", env="LLM_MODEL_PATH")
    llm_max_tokens: int = Field(default=4096, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    llm_gpu_memory_utilization: float = Field(default=0.9, env="LLM_GPU_MEMORY")
    
    # Embedding model
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", env="EMBEDDING_MODEL")
    
    # Whisper settings
    whisper_model: str = Field(default="base.en", env="WHISPER_MODEL")
    whisper_device: str = Field(default="cuda", env="WHISPER_DEVICE")
    
    # TTS settings
    tts_model_path: str = Field(default="models/piper", env="TTS_MODEL_PATH")
    tts_sample_rate: int = Field(default=22050, env="TTS_SAMPLE_RATE")


class ServiceConfig(BaseSettings):
    """Base service configuration."""
    
    name: str = Field(..., env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(..., env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # CORS settings
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # Health check
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    # Monitoring
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    metrics_port: int = Field(default=8000, env="METRICS_PORT")
    
    class Config:
        """Pydantic config."""
        env_file = ".env"


class STTServiceConfig(ServiceConfig):
    """STT Service specific configuration."""
    
    name: str = Field(default="stt-service", env="SERVICE_NAME")
    port: int = Field(default=8001, env="PORT")
    
    # Audio processing
    max_audio_size: int = Field(default=10 * 1024 * 1024, env="MAX_AUDIO_SIZE")  # 10MB
    supported_formats: List[str] = Field(
        default=["wav", "mp3", "m4a", "flac", "ogg"],
        env="SUPPORTED_AUDIO_FORMATS"
    )
    
    # Whisper settings
    whisper_model_size: str = Field(default="base.en", env="WHISPER_MODEL_SIZE")
    whisper_compute_type: str = Field(default="float16", env="WHISPER_COMPUTE_TYPE")
    whisper_threads: int = Field(default=4, env="WHISPER_THREADS")


class TTSServiceConfig(ServiceConfig):
    """TTS Service specific configuration."""
    
    name: str = Field(default="tts-service", env="SERVICE_NAME")
    port: int = Field(default=8002, env="PORT")
    
    # TTS settings
    default_voice: str = Field(default="en_US-lessac-high", env="DEFAULT_VOICE")
    max_text_length: int = Field(default=5000, env="MAX_TEXT_LENGTH")
    audio_format: str = Field(default="wav", env="AUDIO_FORMAT")
    sample_rate: int = Field(default=22050, env="SAMPLE_RATE")


class NLUServiceConfig(ServiceConfig):
    """NLU Service specific configuration."""
    
    name: str = Field(default="nlu-service", env="SERVICE_NAME")
    port: int = Field(default=8003, env="PORT")
    
    # Agent settings
    max_conversation_history: int = Field(default=50, env="MAX_CONVERSATION_HISTORY")
    conversation_ttl: int = Field(default=3600, env="CONVERSATION_TTL")  # 1 hour
    
    # Tool settings
    crm_api_url: str = Field(default="http://localhost:3000/api", env="CRM_API_URL")
    erp_api_url: str = Field(default="http://localhost:3001/api", env="ERP_API_URL")


class LLMServiceConfig(ServiceConfig):
    """LLM Service specific configuration."""
    
    name: str = Field(default="llm-service", env="SERVICE_NAME")
    port: int = Field(default=8004, env="PORT")
    
    # vLLM settings
    tensor_parallel_size: int = Field(default=1, env="TENSOR_PARALLEL_SIZE")
    max_num_seqs: int = Field(default=256, env="MAX_NUM_SEQS")
    max_model_len: int = Field(default=4096, env="MAX_MODEL_LEN")
    swap_space: int = Field(default=4, env="SWAP_SPACE")
    
    # Request batching
    batch_size: int = Field(default=32, env="BATCH_SIZE")
    batch_timeout: float = Field(default=0.1, env="BATCH_TIMEOUT")


class RAGServiceConfig(ServiceConfig):
    """RAG Service specific configuration."""
    
    name: str = Field(default="rag-service", env="SERVICE_NAME")
    port: int = Field(default=8005, env="PORT")
    
    # RAG settings
    chunk_size: int = Field(default=512, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="CHUNK_OVERLAP")
    top_k: int = Field(default=5, env="TOP_K")
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")
    
    # Hybrid search weights
    dense_weight: float = Field(default=0.7, env="DENSE_WEIGHT")
    sparse_weight: float = Field(default=0.3, env="SPARSE_WEIGHT")


class AppConfig(BaseSettings):
    """Application configuration."""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Components
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid environment: {v}")
        return v.lower()
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_nested_delimiter = "__"


@lru_cache()
def get_config() -> AppConfig:
    """Get application configuration (cached)."""
    return AppConfig()


@lru_cache()
def get_service_config(service_name: str) -> ServiceConfig:
    """Get service-specific configuration."""
    config_map = {
        "stt": STTServiceConfig,
        "tts": TTSServiceConfig,
        "nlu": NLUServiceConfig,
        "llm": LLMServiceConfig,
        "rag": RAGServiceConfig,
    }
    
    config_class = config_map.get(service_name, ServiceConfig)
    return config_class()


def setup_logging(config: LoggingConfig) -> None:
    """Setup logging configuration."""
    import structlog
    
    if config.structured:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    logging.basicConfig(
        level=getattr(logging, config.level),
        format=config.format,
        handlers=[logging.StreamHandler()],
    )