# CRM Service Dockerfile
FROM ../ as base

# Set service-specific environment variables
ENV SERVICE_NAME=crm
ENV SERVICE_PORT=8001

# Health check specific to CRM service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose CRM service port
EXPOSE 8001

# Run CRM service
CMD ["python", "-m", "uvicorn", "crm.main:app", "--host", "0.0.0.0", "--port", "8001"]