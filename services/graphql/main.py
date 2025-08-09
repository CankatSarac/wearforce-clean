from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from ..shared.config import get_graphql_settings
from ..shared.middleware import setup_middleware
from .schema import schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    yield
    
    # Cleanup
    # Close any HTTP clients in resolvers if needed
    pass


def create_graphql_app() -> FastAPI:
    """Create GraphQL gateway FastAPI application."""
    settings = get_graphql_settings()
    
    app = FastAPI(
        title="WearForce GraphQL Gateway",
        description="Unified GraphQL API gateway for WearForce CRM/ERP platform",
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
    
    # Create GraphQL router
    graphql_app = GraphQLRouter(
        schema,
        graphiql=settings.debug,  # Enable GraphiQL in development
        path="/graphql"
    )
    
    # Include GraphQL router
    app.include_router(graphql_app, prefix="/graphql")
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "graphql-gateway"}
    
    # Service info endpoint
    @app.get("/")
    async def service_info():
        """Service information."""
        return {
            "service": "WearForce GraphQL Gateway",
            "version": "1.0.0",
            "graphql_endpoint": "/graphql",
            "graphiql_enabled": settings.debug,
            "services": {
                "crm": settings.crm_service_url,
                "erp": settings.erp_service_url,
                "notification": settings.notification_service_url
            }
        }
    
    return app


app = create_graphql_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_graphql_settings()
    
    uvicorn.run(
        "graphql.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )