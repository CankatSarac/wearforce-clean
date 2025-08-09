import asyncio
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from ..shared.config import ERPSettings
from ..shared.database import init_database
from ..shared.events import init_events
from ..shared.auth import init_auth
from ..shared.middleware import setup_middleware
from ..shared.exceptions import WearForceException, exception_handler
from .api import router

# Configure structured logging
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
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global settings
settings = ERPSettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting ERP service", version="1.0.0", port=settings.port)
    
    try:
        # Initialize database
        db = init_database(settings.database)
        await db.create_tables()
        logger.info("Database initialized")
        
        # Initialize events
        event_publisher = init_events(settings.nats.servers)
        await event_publisher.connect()
        logger.info("Event publisher connected")
        
        # Initialize auth
        init_auth(settings.secret_key)
        logger.info("Authentication initialized")
        
        logger.info("ERP service started successfully")
        
    except Exception as e:
        logger.error("Failed to start ERP service", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down ERP service")
    try:
        # Close event publisher
        if 'event_publisher' in locals():
            await event_publisher.disconnect()
        
        # Close database
        if 'db' in locals():
            await db.close()
        
        logger.info("ERP service shut down successfully")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title="WearForce ERP Service",
    description="Enterprise Resource Planning API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://api.wearforce-clean.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup middleware
setup_middleware(app)

# Include API router
app.include_router(router)

# Exception handlers
@app.exception_handler(WearForceException)
async def wearforce-clean_exception_handler(request, exc):
    return exception_handler(exc)


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "erp-service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else None
    }


def main():
    """Run the ERP service."""
    uvicorn.run(
        "services.erp.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug,
    )


if __name__ == "__main__":
    main()