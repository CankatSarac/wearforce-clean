"""Comprehensive tool dispatcher for CRM/ERP operations with HTTP integration.

Features:
- HTTP-based CRM/ERP API integration
- Tool registry and discovery
- Authentication and security
- Rate limiting and retries
- Response caching
- Error handling and fallbacks
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx
import structlog
from shared.monitoring import get_metrics
from shared.exceptions import ValidationError, ServiceUnavailableError
from shared.utils import generate_uuid

logger = structlog.get_logger(__name__)


@dataclass
class ToolDefinition:
    """Enhanced tool definition with metadata."""
    name: str
    description: str
    service_type: str  # crm, erp, general
    endpoint: str
    method: str = "POST"
    parameters_schema: Dict[str, Any] = None
    required_parameters: List[str] = None
    authentication: Optional[Dict[str, str]] = None
    timeout: int = 30
    retry_count: int = 3
    cache_ttl: int = 0  # seconds, 0 = no cache
    rate_limit_per_minute: int = 100
    
    def __post_init__(self):
        if self.parameters_schema is None:
            self.parameters_schema = {}
        if self.required_parameters is None:
            self.required_parameters = []


class ToolCache:
    """Simple in-memory cache for tool results."""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached result."""
        if key in self.cache:
            entry = self.cache[key]
            if entry['expires_at'] > time.time():
                return entry['data']
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, data: Any, ttl: int):
        """Cache result."""
        if ttl <= 0:
            return
        
        # Simple LRU eviction
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['created_at'])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'data': data,
            'created_at': time.time(),
            'expires_at': time.time() + ttl
        }
    
    def clear(self):
        """Clear all cached data."""
        self.cache.clear()


class RateLimiter:
    """Rate limiter for tool execution."""
    
    def __init__(self):
        self.call_counts: Dict[str, List[float]] = {}
    
    def can_execute(self, tool_name: str, rate_limit: int) -> bool:
        """Check if tool can be executed within rate limit."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old entries
        if tool_name in self.call_counts:
            self.call_counts[tool_name] = [
                timestamp for timestamp in self.call_counts[tool_name]
                if timestamp > minute_ago
            ]
        else:
            self.call_counts[tool_name] = []
        
        return len(self.call_counts[tool_name]) < rate_limit
    
    def record_call(self, tool_name: str):
        """Record a tool call."""
        if tool_name not in self.call_counts:
            self.call_counts[tool_name] = []
        self.call_counts[tool_name].append(time.time())


class ToolDispatcher:
    """Enhanced tool dispatcher with comprehensive HTTP integration."""
    
    def __init__(
        self, 
        crm_api_url: str,
        erp_api_url: str,
        default_timeout: int = 30,
        max_concurrent_requests: int = 10
    ):
        self.crm_api_url = crm_api_url.rstrip('/')
        self.erp_api_url = erp_api_url.rstrip('/')
        self.default_timeout = default_timeout
        self.max_concurrent_requests = max_concurrent_requests
        
        # Tool registry
        self.tools: Dict[str, ToolDefinition] = {}
        
        # HTTP client for API calls
        self.http_client = None
        
        # Cache and rate limiting
        self.cache = ToolCache()
        self.rate_limiter = RateLimiter()
        
        # Semaphore for concurrent request limiting
        self.request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Statistics
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.cached_hits = 0
        self.rate_limited_calls = 0
        
        # Tool execution history
        self.execution_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        
    async def initialize(self):
        """Initialize the tool dispatcher."""
        logger.info("Initializing tool dispatcher")
        
        try:
            # Initialize HTTP client with connection pooling
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.default_timeout),
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=20
                ),
                headers={
                    "User-Agent": "WearForce-NLU-Service/1.0",
                    "Content-Type": "application/json"
                }
            )
            
            # Register default tools
            await self._register_default_tools()
            
            logger.info(f"Tool dispatcher initialized with {len(self.tools)} tools")
            
        except Exception as e:
            logger.error("Failed to initialize tool dispatcher", error=str(e))
            raise
    
    async def close(self):
        """Close the tool dispatcher and cleanup resources."""
        logger.info("Closing tool dispatcher")
        
        if self.http_client:
            await self.http_client.aclose()
        
        self.cache.clear()
        logger.info("Tool dispatcher closed")
    
    def register_tool(self, tool: ToolDefinition):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.service_type})")
    
    def unregister_tool(self, tool_name: str):
        """Unregister a tool."""
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a tool with comprehensive error handling and features."""
        start_time = time.time()
        execution_id = generate_uuid()
        
        try:
            # Validate tool exists
            if tool_name not in self.tools:
                raise ValidationError(f"Tool '{tool_name}' not found")
            
            tool = self.tools[tool_name]
            
            # Check rate limiting
            if not self.rate_limiter.can_execute(tool_name, tool.rate_limit_per_minute):
                self.rate_limited_calls += 1
                raise ServiceUnavailableError(
                    f"Rate limit exceeded for tool '{tool_name}' "
                    f"({tool.rate_limit_per_minute} calls/minute)"
                )
            
            # Validate parameters
            self._validate_parameters(tool, parameters)
            
            # Check cache first
            cache_key = self._generate_cache_key(tool_name, parameters)
            cached_result = self.cache.get(cache_key)
            if cached_result:
                self.cached_hits += 1
                logger.debug(f"Cache hit for tool {tool_name}")
                return cached_result
            
            # Record rate limit call
            self.rate_limiter.record_call(tool_name)
            
            # Execute tool with semaphore for concurrency control
            async with self.request_semaphore:
                result = await self._execute_tool_request(tool, parameters, context, execution_id)
            
            # Cache result if applicable
            if tool.cache_ttl > 0:
                self.cache.set(cache_key, result, tool.cache_ttl)
            
            # Record successful execution
            self.total_executions += 1
            self.successful_executions += 1
            
            execution_time = time.time() - start_time
            
            # Record execution history
            self._record_execution(tool_name, parameters, result, execution_time, True, execution_id)
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_inference("tool_execution", execution_time)
                metrics.record_counter("tool_executions_success", "nlu_service", {"tool": tool_name})
            
            logger.info(
                f"Tool executed successfully: {tool_name}",
                execution_id=execution_id,
                execution_time=execution_time
            )
            
            return result
            
        except Exception as e:
            self.total_executions += 1
            self.failed_executions += 1
            
            execution_time = time.time() - start_time
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time
            }
            
            # Record failed execution
            self._record_execution(tool_name, parameters, error_result, execution_time, False, execution_id)
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_counter("tool_executions_failed", "nlu_service", {"tool": tool_name})
            
            logger.error(
                f"Tool execution failed: {tool_name}",
                error=str(e),
                execution_id=execution_id,
                execution_time=execution_time
            )
            
            raise
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools with their definitions."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "service_type": tool.service_type,
                "parameters_schema": tool.parameters_schema,
                "required_parameters": tool.required_parameters,
                "rate_limit_per_minute": tool.rate_limit_per_minute,
                "cache_ttl": tool.cache_ttl,
            }
            for tool in self.tools.values()
        ]
    
    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self.tools.get(tool_name)
    
    async def health_check(self) -> bool:
        """Check tool dispatcher health."""
        try:
            # Check if HTTP client is available
            if not self.http_client:
                return False
            
            # Try a simple health check to CRM and ERP services
            health_checks = []
            
            # CRM health check
            try:
                response = await self.http_client.get(f"{self.crm_api_url}/health", timeout=5.0)
                health_checks.append(response.status_code == 200)
            except:
                health_checks.append(False)
            
            # ERP health check  
            try:
                response = await self.http_client.get(f"{self.erp_api_url}/health", timeout=5.0)
                health_checks.append(response.status_code == 200)
            except:
                health_checks.append(False)
            
            # Return True if at least one service is healthy
            return any(health_checks)
            
        except Exception:
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get tool dispatcher statistics."""
        return {
            "total_tools": len(self.tools),
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.successful_executions / max(self.total_executions, 1),
            "cached_hits": self.cached_hits,
            "rate_limited_calls": self.rate_limited_calls,
            "cache_size": len(self.cache.cache),
            "execution_history_size": len(self.execution_history),
        }
    
    async def get_tool_stats(self, tool_name: str) -> Dict[str, Any]:
        """Get statistics for a specific tool."""
        tool_executions = [
            exec_record for exec_record in self.execution_history
            if exec_record["tool_name"] == tool_name
        ]
        
        if not tool_executions:
            return {"tool_name": tool_name, "executions": 0}
        
        successful = sum(1 for exec_record in tool_executions if exec_record["success"])
        total = len(tool_executions)
        avg_time = sum(exec_record["execution_time"] for exec_record in tool_executions) / total
        
        return {
            "tool_name": tool_name,
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": total - successful,
            "success_rate": successful / total,
            "average_execution_time": avg_time,
            "last_execution": max(exec_record["timestamp"] for exec_record in tool_executions)
        }
    
    # Private methods
    async def _register_default_tools(self):
        """Register default CRM and ERP tools."""
        
        # CRM Tools
        crm_tools = [
            ToolDefinition(
                name="create_crm_contact",
                description="Create a new contact in CRM system",
                service_type="crm",
                endpoint=f"{self.crm_api_url}/contacts",
                method="POST",
                parameters_schema={
                    "name": {"type": "string", "required": True},
                    "email": {"type": "string", "required": False},
                    "phone": {"type": "string", "required": False},
                    "company": {"type": "string", "required": False},
                    "notes": {"type": "string", "required": False}
                },
                required_parameters=["name"],
                timeout=30,
                retry_count=3,
                rate_limit_per_minute=60
            ),
            
            ToolDefinition(
                name="search_crm_contacts",
                description="Search for contacts in CRM system",
                service_type="crm",
                endpoint=f"{self.crm_api_url}/contacts/search",
                method="GET",
                parameters_schema={
                    "query": {"type": "string", "required": True},
                    "limit": {"type": "integer", "required": False, "default": 10},
                    "fields": {"type": "array", "required": False}
                },
                required_parameters=["query"],
                cache_ttl=300,  # 5 minutes
                rate_limit_per_minute=120
            ),
            
            ToolDefinition(
                name="update_crm_contact",
                description="Update an existing contact in CRM system",
                service_type="crm",
                endpoint=f"{self.crm_api_url}/contacts/{{contact_id}}",
                method="PUT",
                parameters_schema={
                    "contact_id": {"type": "string", "required": True},
                    "name": {"type": "string", "required": False},
                    "email": {"type": "string", "required": False},
                    "phone": {"type": "string", "required": False},
                    "company": {"type": "string", "required": False},
                    "notes": {"type": "string", "required": False}
                },
                required_parameters=["contact_id"],
                rate_limit_per_minute=60
            ),
            
            ToolDefinition(
                name="schedule_crm_meeting",
                description="Schedule a meeting in CRM system",
                service_type="crm",
                endpoint=f"{self.crm_api_url}/meetings",
                method="POST",
                parameters_schema={
                    "title": {"type": "string", "required": True},
                    "attendees": {"type": "array", "required": True},
                    "start_time": {"type": "string", "required": True},
                    "end_time": {"type": "string", "required": True},
                    "location": {"type": "string", "required": False},
                    "description": {"type": "string", "required": False}
                },
                required_parameters=["title", "attendees", "start_time", "end_time"],
                rate_limit_per_minute=30
            )
        ]
        
        # ERP Tools
        erp_tools = [
            ToolDefinition(
                name="create_erp_order",
                description="Create a new order in ERP system",
                service_type="erp",
                endpoint=f"{self.erp_api_url}/orders",
                method="POST",
                parameters_schema={
                    "customer_id": {"type": "string", "required": True},
                    "items": {"type": "array", "required": True},
                    "order_date": {"type": "string", "required": False},
                    "delivery_date": {"type": "string", "required": False},
                    "notes": {"type": "string", "required": False}
                },
                required_parameters=["customer_id", "items"],
                rate_limit_per_minute=60
            ),
            
            ToolDefinition(
                name="search_erp_orders",
                description="Search for orders in ERP system",
                service_type="erp",
                endpoint=f"{self.erp_api_url}/orders/search",
                method="GET",
                parameters_schema={
                    "query": {"type": "string", "required": False},
                    "customer_id": {"type": "string", "required": False},
                    "status": {"type": "string", "required": False},
                    "start_date": {"type": "string", "required": False},
                    "end_date": {"type": "string", "required": False},
                    "limit": {"type": "integer", "required": False, "default": 10}
                },
                cache_ttl=60,  # 1 minute
                rate_limit_per_minute=120
            ),
            
            ToolDefinition(
                name="get_erp_inventory",
                description="Get inventory information from ERP system",
                service_type="erp",
                endpoint=f"{self.erp_api_url}/inventory",
                method="GET",
                parameters_schema={
                    "product_id": {"type": "string", "required": False},
                    "product_name": {"type": "string", "required": False},
                    "category": {"type": "string", "required": False},
                    "low_stock_only": {"type": "boolean", "required": False}
                },
                cache_ttl=300,  # 5 minutes
                rate_limit_per_minute=100
            ),
            
            ToolDefinition(
                name="update_erp_inventory",
                description="Update inventory quantities in ERP system",
                service_type="erp",
                endpoint=f"{self.erp_api_url}/inventory/{{product_id}}",
                method="PUT",
                parameters_schema={
                    "product_id": {"type": "string", "required": True},
                    "quantity": {"type": "integer", "required": True},
                    "operation": {"type": "string", "required": False, "enum": ["set", "add", "subtract"]},
                    "reason": {"type": "string", "required": False}
                },
                required_parameters=["product_id", "quantity"],
                rate_limit_per_minute=60
            ),
            
            ToolDefinition(
                name="generate_erp_report",
                description="Generate reports from ERP system",
                service_type="erp",
                endpoint=f"{self.erp_api_url}/reports/generate",
                method="POST",
                parameters_schema={
                    "report_type": {"type": "string", "required": True, "enum": ["sales", "inventory", "financial"]},
                    "start_date": {"type": "string", "required": True},
                    "end_date": {"type": "string", "required": True},
                    "format": {"type": "string", "required": False, "enum": ["json", "csv", "pdf"], "default": "json"},
                    "filters": {"type": "object", "required": False}
                },
                required_parameters=["report_type", "start_date", "end_date"],
                timeout=60,  # Reports may take longer
                rate_limit_per_minute=10
            )
        ]
        
        # Register all tools
        for tool in crm_tools + erp_tools:
            self.register_tool(tool)
    
    def _validate_parameters(self, tool: ToolDefinition, parameters: Dict[str, Any]):
        """Validate tool parameters against schema."""
        # Check required parameters
        for required_param in tool.required_parameters:
            if required_param not in parameters:
                raise ValidationError(f"Required parameter '{required_param}' missing for tool '{tool.name}'")
        
        # Basic type validation (could be enhanced with jsonschema)
        for param_name, param_value in parameters.items():
            if param_name in tool.parameters_schema:
                schema = tool.parameters_schema[param_name]
                expected_type = schema.get("type")
                
                if expected_type == "string" and not isinstance(param_value, str):
                    raise ValidationError(f"Parameter '{param_name}' should be string, got {type(param_value)}")
                elif expected_type == "integer" and not isinstance(param_value, int):
                    raise ValidationError(f"Parameter '{param_name}' should be integer, got {type(param_value)}")
                elif expected_type == "boolean" and not isinstance(param_value, bool):
                    raise ValidationError(f"Parameter '{param_name}' should be boolean, got {type(param_value)}")
                elif expected_type == "array" and not isinstance(param_value, list):
                    raise ValidationError(f"Parameter '{param_name}' should be array, got {type(param_value)}")
                elif expected_type == "object" and not isinstance(param_value, dict):
                    raise ValidationError(f"Parameter '{param_name}' should be object, got {type(param_value)}")
    
    def _generate_cache_key(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Generate cache key for tool execution."""
        param_str = json.dumps(parameters, sort_keys=True)
        return f"{tool_name}:{hash(param_str)}"
    
    async def _execute_tool_request(
        self, 
        tool: ToolDefinition, 
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        execution_id: str
    ) -> Dict[str, Any]:
        """Execute the actual HTTP request to the tool endpoint."""
        
        # Prepare URL (handle path parameters)
        url = tool.endpoint
        path_params = {}
        
        # Extract path parameters (e.g., {contact_id})
        import re
        path_param_pattern = r'\{(\w+)\}'
        path_param_matches = re.findall(path_param_pattern, url)
        
        for param_name in path_param_matches:
            if param_name in parameters:
                path_params[param_name] = parameters[param_name]
                url = url.replace(f"{{{param_name}}}", str(parameters[param_name]))
                # Remove from parameters to avoid sending in body/query
                del parameters[param_name]
        
        # Prepare request data
        request_kwargs = {
            "timeout": tool.timeout,
            "headers": {
                "X-Execution-ID": execution_id,
                "X-Tool-Name": tool.name
            }
        }
        
        # Add authentication if configured
        if tool.authentication:
            auth_type = tool.authentication.get("type")
            if auth_type == "bearer":
                request_kwargs["headers"]["Authorization"] = f"Bearer {tool.authentication['token']}"
            elif auth_type == "api_key":
                request_kwargs["headers"]["X-API-Key"] = tool.authentication["key"]
        
        # Prepare request based on method
        if tool.method.upper() in ["GET", "DELETE"]:
            # Send parameters as query params
            request_kwargs["params"] = parameters
        else:
            # Send parameters as JSON body
            request_kwargs["json"] = parameters
        
        # Execute with retries
        last_exception = None
        for attempt in range(tool.retry_count):
            try:
                response = await self.http_client.request(
                    method=tool.method.upper(),
                    url=url,
                    **request_kwargs
                )
                
                # Handle response
                if response.status_code >= 400:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    if response.status_code >= 500 and attempt < tool.retry_count - 1:
                        # Retry on server errors
                        logger.warning(f"Server error, retrying ({attempt + 1}/{tool.retry_count}): {error_msg}")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise ServiceUnavailableError(f"Tool '{tool.name}' failed: {error_msg}")
                
                # Parse response
                try:
                    result_data = response.json()
                except:
                    result_data = {"response": response.text}
                
                # Return successful result
                return {
                    "success": True,
                    "data": result_data,
                    "status_code": response.status_code,
                    "execution_time": 0,  # Will be set by caller
                    "tool_name": tool.name,
                    "execution_id": execution_id
                }
                
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < tool.retry_count - 1:
                    logger.warning(f"Request timeout, retrying ({attempt + 1}/{tool.retry_count})")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ServiceUnavailableError(f"Tool '{tool.name}' timed out after {tool.retry_count} attempts")
            
            except Exception as e:
                last_exception = e
                if attempt < tool.retry_count - 1:
                    logger.warning(f"Request failed, retrying ({attempt + 1}/{tool.retry_count}): {str(e)}")
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ServiceUnavailableError(f"Tool '{tool.name}' failed after {tool.retry_count} attempts: {str(e)}")
        
        # Should not reach here, but just in case
        raise ServiceUnavailableError(f"Tool '{tool.name}' failed: {str(last_exception)}")
    
    def _record_execution(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any], 
        result: Dict[str, Any], 
        execution_time: float, 
        success: bool,
        execution_id: str
    ):
        """Record tool execution in history."""
        execution_record = {
            "execution_id": execution_id,
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "execution_time": execution_time,
            "success": success,
            "timestamp": time.time()
        }
        
        self.execution_history.append(execution_record)
        
        # Keep history size manageable
        if len(self.execution_history) > self.max_history_size:
            self.execution_history = self.execution_history[-self.max_history_size//2:]