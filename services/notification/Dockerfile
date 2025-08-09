# Notification Service Dockerfile
FROM ../ as base

# Set service-specific environment variables
ENV SERVICE_NAME=notification
ENV SERVICE_PORT=8003

# Health check specific to Notification service
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Expose Notification service port
EXPOSE 8003

# Run Notification service
CMD ["python", "-m", "uvicorn", "notification.main:app", "--host", "0.0.0.0", "--port", "8003"]