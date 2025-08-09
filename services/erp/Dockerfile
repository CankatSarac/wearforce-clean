# ERP Service Dockerfile
FROM ../ as base

# Set service-specific environment variables
ENV SERVICE_NAME=erp
ENV SERVICE_PORT=8002

# Health check specific to ERP service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Expose ERP service port
EXPOSE 8002

# Run ERP service
CMD ["python", "-m", "uvicorn", "erp.main:app", "--host", "0.0.0.0", "--port", "8002"]