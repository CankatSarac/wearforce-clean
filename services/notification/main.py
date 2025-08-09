from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..shared.config import get_settings
from ..shared.database import get_database, init_database
from ..shared.middleware import setup_middleware
from ..shared.events import get_event_publisher
from .api import router
from .providers import NotificationProviderFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()
    
    # Initialize database
    await init_database()
    
    # Initialize event publisher
    event_publisher = get_event_publisher()
    await event_publisher.connect()
    
    yield
    
    # Cleanup
    database = get_database()
    await database.close()
    
    await event_publisher.disconnect()


def create_notification_app() -> FastAPI:
    """Create notification service FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="WearForce Notification Service",
        description="Notification and messaging service for WearForce CRM/ERP platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup common middleware
    setup_middleware(app)
    
    # Include API router
    app.include_router(router)
    
    return app


app = create_notification_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "notification.main:app",
        host="0.0.0.0",
        port=settings.notification_service_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )