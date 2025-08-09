# GraphQL Gateway Dockerfile
FROM ../ as base

# Set service-specific environment variables
ENV SERVICE_NAME=graphql
ENV SERVICE_PORT=8000

# Health check specific to GraphQL service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose GraphQL service port
EXPOSE 8000

# Run GraphQL service
CMD ["python", "-m", "uvicorn", "graphql.main:app", "--host", "0.0.0.0", "--port", "8000"]