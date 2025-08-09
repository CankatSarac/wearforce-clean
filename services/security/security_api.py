"""
Security scanning API for WearForce platform.

This module provides REST API endpoints for triggering security scans,
retrieving results, and managing vulnerability data.
"""

import asyncio
import os
import redis.asyncio as redis
from datetime import datetime
from typing import Dict, List, Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from vulnerability_scanner import (
    VulnerabilityManager, VulnerabilitySeverity, ScanType, ScanResult
)

# Configure logging
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

# Pydantic models for API
class ScanRequest(BaseModel):
    scan_type: str = Field(..., description="Type of scan: dependency, container, code, infrastructure")
    target: str = Field(..., description="Target to scan")
    options: Dict = Field(default_factory=dict, description="Additional scan options")

class ComprehensiveScanRequest(BaseModel):
    requirements_file: Optional[str] = Field(None, description="Path to requirements file")
    container_images: Optional[List[List[str]]] = Field(None, description="List of [image, tag] pairs")
    source_path: Optional[str] = Field(None, description="Path to source code")
    infrastructure_targets: Optional[List[str]] = Field(None, description="Infrastructure targets to scan")

class VulnerabilityResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    cvss_score: Optional[float]
    cve_id: Optional[str]
    affected_package: Optional[str]
    affected_version: Optional[str]
    fixed_version: Optional[str]
    references: List[str]
    discovered_at: str
    scan_type: Optional[str]
    file_path: Optional[str]
    line_number: Optional[int]

class ScanResultResponse(BaseModel):
    scan_id: str
    scan_type: str
    target: str
    started_at: str
    completed_at: Optional[str]
    status: str
    duration_seconds: Optional[float]
    vulnerability_counts: Dict[str, int]
    total_vulnerabilities: int
    vulnerabilities: List[VulnerabilityResponse]
    error: Optional[str]
    metadata: Dict

# Global variables
app = FastAPI(
    title="WearForce Security Scanner API",
    description="Security vulnerability scanning and management API",
    version="1.0.0"
)

vuln_manager: Optional[VulnerabilityManager] = None
redis_client: Optional[redis.Redis] = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_vuln_manager() -> VulnerabilityManager:
    """Dependency injection for vulnerability manager."""
    global vuln_manager
    if vuln_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vulnerability manager not initialized"
        )
    return vuln_manager

async def get_redis_client() -> redis.Redis:
    """Dependency injection for Redis client."""
    global redis_client
    if redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client not initialized"
        )
    return redis_client

# API endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        return {"status": "ready", "timestamp": datetime.now().isoformat()}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )

@app.post("/scans/dependency", response_model=Dict[str, str])
async def scan_dependencies(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Trigger dependency vulnerability scan."""
    try:
        if not os.path.exists(request.target):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requirements file not found: {request.target}"
            )
        
        # Start scan in background
        task = asyncio.create_task(vuln_manager.scan_dependencies(request.target))
        
        # Return immediately with scan ID
        scan_id = f"dep-{int(datetime.now().timestamp())}"
        
        logger.info("Dependency scan started", 
                   scan_id=scan_id, target=request.target)
        
        return {"scan_id": scan_id, "status": "started", "message": "Dependency scan initiated"}
        
    except Exception as e:
        logger.error("Failed to start dependency scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan: {str(e)}"
        )

@app.post("/scans/container", response_model=Dict[str, str])
async def scan_containers(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Trigger container vulnerability scan."""
    try:
        # Parse container images from target (format: "image1:tag1,image2:tag2")
        image_pairs = []
        for image_spec in request.target.split(','):
            if ':' in image_spec:
                image, tag = image_spec.strip().split(':', 1)
                image_pairs.append((image, tag))
            else:
                image_pairs.append((image_spec.strip(), 'latest'))
        
        # Start scan in background
        task = asyncio.create_task(vuln_manager.scan_container_images(image_pairs))
        
        scan_id = f"container-{int(datetime.now().timestamp())}"
        
        logger.info("Container scan started", 
                   scan_id=scan_id, images=len(image_pairs))
        
        return {"scan_id": scan_id, "status": "started", "message": "Container scan initiated"}
        
    except Exception as e:
        logger.error("Failed to start container scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan: {str(e)}"
        )

@app.post("/scans/code", response_model=Dict[str, str])
async def scan_code(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Trigger source code security scan."""
    try:
        if not os.path.exists(request.target):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source path not found: {request.target}"
            )
        
        # Start scan in background
        task = asyncio.create_task(vuln_manager.scan_source_code(request.target))
        
        scan_id = f"code-{int(datetime.now().timestamp())}"
        
        logger.info("Code scan started", 
                   scan_id=scan_id, target=request.target)
        
        return {"scan_id": scan_id, "status": "started", "message": "Code scan initiated"}
        
    except Exception as e:
        logger.error("Failed to start code scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan: {str(e)}"
        )

@app.post("/scans/infrastructure", response_model=Dict[str, str])
async def scan_infrastructure(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Trigger infrastructure security scan."""
    try:
        # Parse targets (format: "target1,target2,target3")
        targets = [target.strip() for target in request.target.split(',')]
        
        # Start scan in background
        task = asyncio.create_task(vuln_manager.scan_infrastructure(targets))
        
        scan_id = f"infra-{int(datetime.now().timestamp())}"
        
        logger.info("Infrastructure scan started", 
                   scan_id=scan_id, targets=len(targets))
        
        return {"scan_id": scan_id, "status": "started", "message": "Infrastructure scan initiated"}
        
    except Exception as e:
        logger.error("Failed to start infrastructure scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan: {str(e)}"
        )

@app.post("/scans/comprehensive", response_model=Dict[str, str])
async def scan_comprehensive(
    request: ComprehensiveScanRequest,
    background_tasks: BackgroundTasks,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Trigger comprehensive security scan."""
    try:
        scan_config = {}
        
        if request.requirements_file:
            scan_config["requirements_file"] = request.requirements_file
        
        if request.container_images:
            # Convert list of lists to list of tuples
            scan_config["container_images"] = [tuple(img) for img in request.container_images]
        
        if request.source_path:
            scan_config["source_path"] = request.source_path
        
        if request.infrastructure_targets:
            scan_config["infrastructure_targets"] = request.infrastructure_targets
        
        if not scan_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one scan target must be specified"
            )
        
        # Start comprehensive scan in background
        task = asyncio.create_task(vuln_manager.run_comprehensive_scan(scan_config))
        
        scan_id = f"comprehensive-{int(datetime.now().timestamp())}"
        
        logger.info("Comprehensive scan started", 
                   scan_id=scan_id, config=scan_config)
        
        return {"scan_id": scan_id, "status": "started", "message": "Comprehensive scan initiated"}
        
    except Exception as e:
        logger.error("Failed to start comprehensive scan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scan: {str(e)}"
        )

@app.get("/scans/{scan_id}", response_model=ScanResultResponse)
async def get_scan_result(
    scan_id: str,
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Get scan result by ID."""
    try:
        scan_result = await vuln_manager.get_scan_result(scan_id)
        
        if not scan_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan result not found: {scan_id}"
            )
        
        # Convert to response model
        vulnerabilities = []
        for vuln in scan_result.vulnerabilities:
            vuln_response = VulnerabilityResponse(
                id=vuln.id,
                title=vuln.title,
                description=vuln.description,
                severity=vuln.severity.value,
                cvss_score=vuln.cvss_score,
                cve_id=vuln.cve_id,
                affected_package=vuln.affected_package,
                affected_version=vuln.affected_version,
                fixed_version=vuln.fixed_version,
                references=vuln.references,
                discovered_at=vuln.discovered_at.isoformat(),
                scan_type=vuln.scan_type.value if vuln.scan_type else None,
                file_path=vuln.file_path,
                line_number=vuln.line_number
            )
            vulnerabilities.append(vuln_response)
        
        response = ScanResultResponse(
            scan_id=scan_result.scan_id,
            scan_type=scan_result.scan_type.value,
            target=scan_result.target,
            started_at=scan_result.started_at.isoformat(),
            completed_at=scan_result.completed_at.isoformat() if scan_result.completed_at else None,
            status=scan_result.status,
            duration_seconds=scan_result.duration_seconds,
            vulnerability_counts=scan_result.vulnerability_counts,
            total_vulnerabilities=len(scan_result.vulnerabilities),
            vulnerabilities=vulnerabilities,
            error=scan_result.error,
            metadata=scan_result.metadata
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scan result", scan_id=scan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scan result: {str(e)}"
        )

@app.get("/scans")
async def list_scans(
    limit: int = 10,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """List recent scans."""
    try:
        # Get recent scan IDs from Redis
        scan_ids = await redis_client.zrevrange("scan_history", 0, limit - 1)
        
        scans = []
        for scan_id in scan_ids:
            result_data = await redis_client.get(f"scan_result:{scan_id}")
            if result_data:
                import json
                data = json.loads(result_data)
                scans.append({
                    "scan_id": data["scan_id"],
                    "scan_type": data["scan_type"],
                    "target": data["target"],
                    "status": data["status"],
                    "started_at": data["started_at"],
                    "completed_at": data["completed_at"],
                    "total_vulnerabilities": data["total_vulnerabilities"],
                    "vulnerability_counts": data["vulnerability_counts"]
                })
        
        return {"scans": scans}
        
    except Exception as e:
        logger.error("Failed to list scans", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scans: {str(e)}"
        )

@app.get("/security/summary")
async def get_security_summary(
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get security summary and metrics."""
    try:
        # Get cached summary
        summary_data = await redis_client.get("security_summary")
        
        if summary_data:
            import json
            summary = json.loads(summary_data)
        else:
            summary = {"message": "No recent security scans available"}
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get security summary", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security summary: {str(e)}"
        )

@app.get("/security/metrics")
async def get_security_metrics(
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Get security metrics for monitoring."""
    try:
        metrics = await vuln_manager.get_security_metrics()
        return metrics
        
    except Exception as e:
        logger.error("Failed to get security metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security metrics: {str(e)}"
        )

@app.delete("/scans/{scan_id}")
async def delete_scan_result(
    scan_id: str,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Delete scan result."""
    try:
        # Delete scan result and vulnerabilities
        await redis_client.delete(f"scan_result:{scan_id}")
        await redis_client.delete(f"scan_vulnerabilities:{scan_id}")
        
        # Remove from scan history
        await redis_client.zrem("scan_history", scan_id)
        
        logger.info("Scan result deleted", scan_id=scan_id)
        
        return {"message": "Scan result deleted successfully"}
        
    except Exception as e:
        logger.error("Failed to delete scan result", scan_id=scan_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scan result: {str(e)}"
        )

# Metrics endpoint for Prometheus
@app.get("/metrics")
async def get_prometheus_metrics(
    vuln_manager: VulnerabilityManager = Depends(get_vuln_manager)
):
    """Prometheus metrics endpoint."""
    try:
        metrics = await vuln_manager.get_security_metrics()
        
        # Convert to Prometheus format
        prometheus_metrics = []
        
        prometheus_metrics.append(f"# HELP security_scans_total Total number of security scans")
        prometheus_metrics.append(f"# TYPE security_scans_total counter")
        prometheus_metrics.append(f"security_scans_total {metrics.get('recent_scans', 0)}")
        
        prometheus_metrics.append(f"# HELP security_scan_success_rate Security scan success rate")
        prometheus_metrics.append(f"# TYPE security_scan_success_rate gauge")
        prometheus_metrics.append(f"security_scan_success_rate {metrics.get('scan_success_rate', 0)}")
        
        prometheus_metrics.append(f"# HELP security_vulnerabilities_critical Critical vulnerabilities found")
        prometheus_metrics.append(f"# TYPE security_vulnerabilities_critical gauge")
        prometheus_metrics.append(f"security_vulnerabilities_critical {metrics.get('critical_vulnerabilities', 0)}")
        
        prometheus_metrics.append(f"# HELP security_vulnerabilities_high High severity vulnerabilities found")
        prometheus_metrics.append(f"# TYPE security_vulnerabilities_high gauge")
        prometheus_metrics.append(f"security_vulnerabilities_high {metrics.get('high_vulnerabilities', 0)}")
        
        return "\n".join(prometheus_metrics)
        
    except Exception as e:
        logger.error("Failed to generate Prometheus metrics", error=str(e))
        return "# Error generating metrics"

# Application startup and shutdown
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global vuln_manager, redis_client
    
    try:
        # Initialize Redis client
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url)
        
        # Test Redis connection
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # Initialize vulnerability manager
        vuln_manager = VulnerabilityManager(redis_client)
        
        logger.info("Security Scanner API started successfully")
        
    except Exception as e:
        logger.error("Failed to start Security Scanner API", error=str(e))
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    global redis_client
    
    try:
        if redis_client:
            await redis_client.close()
        
        logger.info("Security Scanner API shutdown completed")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

# Main function
def main():
    """Run the Security Scanner API."""
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "security_api:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()