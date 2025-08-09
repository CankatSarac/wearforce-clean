from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/wearforce-clean")
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    echo: bool = Field(default=False)


class RedisSettings(BaseSettings):
    url: str = Field(default="redis://localhost:6379/0")
    max_connections: int = Field(default=50)


class NATSSettings(BaseSettings):
    servers: list[str] = Field(default=["nats://localhost:4222"])
    max_reconnect_attempts: int = Field(default=60)
    reconnect_time_wait: int = Field(default=2)


class BaseServiceSettings(BaseSettings):
    service_name: str
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-this")
    access_token_expire_minutes: int = Field(default=30)
    
    # Database
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    # Redis
    redis: RedisSettings = Field(default_factory=RedisSettings)
    
    # NATS
    nats: NATSSettings = Field(default_factory=NATSSettings)
    
    # Logging
    log_level: str = Field(default="INFO")
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


class CRMSettings(BaseServiceSettings):
    service_name: str = "crm-service"
    port: int = Field(default=8001)


class ERPSettings(BaseServiceSettings):
    service_name: str = "erp-service"
    port: int = Field(default=8002)


class NotificationSettings(BaseServiceSettings):
    service_name: str = "notification-service"
    port: int = Field(default=8003)
    
    # Email settings (SMTP)
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_use_tls: bool = Field(default=True)
    
    # SMS settings (Twilio)
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_from_number: str = Field(default="")
    
    # Push notification settings (Firebase)
    firebase_service_account_path: str = Field(default="")
    
    # Provider configuration
    use_dummy_providers: bool = Field(default=True)
    
    # Queue configuration
    notification_queue_name: str = Field(default="notifications")
    webhook_queue_name: str = Field(default="webhooks")


class GraphQLSettings(BaseServiceSettings):
    service_name: str = "graphql-gateway"
    port: int = Field(default=8004)
    
    # Service endpoints
    crm_service_url: str = Field(default="http://localhost:8001")
    erp_service_url: str = Field(default="http://localhost:8002")
    notification_service_url: str = Field(default="http://localhost:8003")


# Utility functions to get settings
def get_settings() -> BaseServiceSettings:
    """Get base service settings."""
    return BaseServiceSettings(service_name="wearforce-clean-services")


def get_crm_settings() -> CRMSettings:
    """Get CRM service settings."""
    return CRMSettings()


def get_erp_settings() -> ERPSettings:
    """Get ERP service settings."""
    return ERPSettings()


def get_notification_settings() -> NotificationSettings:
    """Get notification service settings."""
    return NotificationSettings()


def get_graphql_settings() -> GraphQLSettings:
    """Get GraphQL gateway settings."""
    return GraphQLSettings()