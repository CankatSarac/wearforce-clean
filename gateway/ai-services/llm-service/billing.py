"""
Token usage tracking and billing for LLM services.

Features:
- Per-model token counting and cost calculation
- User/API key based usage tracking
- Daily/monthly usage limits
- Cost optimization recommendations
- Usage analytics and reporting
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import structlog
from shared.database import RedisManager
from shared.monitoring import get_metrics

logger = structlog.get_logger(__name__)


@dataclass
class TokenPricing:
    """Token pricing configuration for a model."""
    model_name: str
    input_price_per_token: Decimal
    output_price_per_token: Decimal
    currency: str = "USD"


@dataclass
class UsageRecord:
    """Individual usage record."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_cost: Decimal = Decimal('0')
    output_cost: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    timestamp: float = field(default_factory=time.time)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageSummary:
    """Usage summary for a time period."""
    user_id: Optional[str]
    api_key: Optional[str]
    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: Decimal = Decimal('0')
    model_usage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    daily_costs: List[Decimal] = field(default_factory=list)


class BillingTracker:
    """Tracks token usage and calculates billing costs."""
    
    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
        self.pricing_config = self._get_default_pricing()
        self._usage_cache: Dict[str, List[UsageRecord]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_flush = time.time()
    
    def _get_default_pricing(self) -> Dict[str, TokenPricing]:
        """Get default pricing configuration."""
        return {
            "gpt-oss-20b": TokenPricing(
                model_name="gpt-oss-20b",
                input_price_per_token=Decimal('0.0001'),  # $0.0001 per input token
                output_price_per_token=Decimal('0.0002'),  # $0.0002 per output token
            ),
            "gpt-oss-120b": TokenPricing(
                model_name="gpt-oss-120b", 
                input_price_per_token=Decimal('0.0005'),  # $0.0005 per input token
                output_price_per_token=Decimal('0.001'),   # $0.001 per output token
            ),
        }
    
    async def track_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageRecord:
        """Track token usage for billing."""
        pricing = self.pricing_config.get(model_name)
        if not pricing:
            logger.warning(f"No pricing config found for model {model_name}")
            pricing = TokenPricing(
                model_name=model_name,
                input_price_per_token=Decimal('0'),
                output_price_per_token=Decimal('0'),
            )
        
        # Calculate costs
        input_cost = Decimal(prompt_tokens) * pricing.input_price_per_token
        output_cost = Decimal(completion_tokens) * pricing.output_price_per_token
        total_cost = input_cost + output_cost
        
        # Create usage record
        record = UsageRecord(
            user_id=user_id,
            api_key=api_key,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            session_id=session_id,
            metadata=metadata or {},
        )
        
        # Store usage record
        await self._store_usage_record(record)
        
        # Check usage limits
        await self._check_usage_limits(user_id, api_key, total_cost)
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.inference_tokens_processed.labels(
                model=model_name,
                service="llm-service",
                type="input",
            ).inc(prompt_tokens)
            
            metrics.inference_tokens_processed.labels(
                model=model_name,
                service="llm-service", 
                type="output",
            ).inc(completion_tokens)
        
        logger.debug(
            "Usage tracked",
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=float(total_cost),
            user_id=user_id,
        )
        
        return record
    
    async def get_usage_summary(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> UsageSummary:
        """Get usage summary for a user or API key."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)  # Last 30 days
        if not end_date:
            end_date = datetime.utcnow()
        
        # Get usage records
        records = await self._get_usage_records(
            user_id=user_id,
            api_key=api_key,
            start_time=start_date.timestamp(),
            end_time=end_date.timestamp(),
        )
        
        # Create summary
        summary = UsageSummary(
            user_id=user_id,
            api_key=api_key,
            period_start=start_date,
            period_end=end_date,
        )
        
        # Aggregate usage data
        model_stats = {}
        daily_costs = {}
        
        for record in records:
            summary.total_requests += 1
            summary.total_prompt_tokens += record.prompt_tokens
            summary.total_completion_tokens += record.completion_tokens
            summary.total_tokens += record.total_tokens
            summary.total_cost += record.total_cost
            
            # Model-specific stats
            model = record.model_name
            if model not in model_stats:
                model_stats[model] = {
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": Decimal('0'),
                }
            
            model_stats[model]["requests"] += 1
            model_stats[model]["prompt_tokens"] += record.prompt_tokens
            model_stats[model]["completion_tokens"] += record.completion_tokens
            model_stats[model]["total_tokens"] += record.total_tokens
            model_stats[model]["cost"] += record.total_cost
            
            # Daily costs
            date_key = datetime.fromtimestamp(record.timestamp).date().isoformat()
            if date_key not in daily_costs:
                daily_costs[date_key] = Decimal('0')
            daily_costs[date_key] += record.total_cost
        
        summary.model_usage = model_stats
        summary.daily_costs = list(daily_costs.values())
        
        return summary
    
    async def get_current_usage(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get current month usage."""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        summary = await self.get_usage_summary(
            user_id=user_id,
            api_key=api_key,
            start_date=month_start,
            end_date=now,
        )
        
        return {
            "current_month": {
                "requests": summary.total_requests,
                "tokens": summary.total_tokens,
                "cost": float(summary.total_cost),
            },
            "models": {
                model: {
                    "requests": stats["requests"],
                    "tokens": stats["total_tokens"],
                    "cost": float(stats["cost"]),
                }
                for model, stats in summary.model_usage.items()
            },
        }
    
    async def set_usage_limit(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        monthly_limit: Optional[Decimal] = None,
        daily_limit: Optional[Decimal] = None,
    ) -> None:
        """Set usage limits for a user or API key."""
        key = self._get_limit_key(user_id, api_key)
        
        limits = {}
        if monthly_limit is not None:
            limits["monthly"] = float(monthly_limit)
        if daily_limit is not None:
            limits["daily"] = float(daily_limit)
        
        if limits:
            import json
            await self.redis_manager.set(
                f"limits:{key}",
                json.dumps(limits),
                ex=86400 * 31,  # 31 days
            )
    
    async def get_usage_limits(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Optional[Decimal]]:
        """Get usage limits for a user or API key."""
        key = self._get_limit_key(user_id, api_key)
        
        limits_data = await self.redis_manager.get(f"limits:{key}")
        if not limits_data:
            return {"monthly": None, "daily": None}
        
        try:
            import json
            limits = json.loads(limits_data)
            return {
                "monthly": Decimal(str(limits.get("monthly"))) if limits.get("monthly") else None,
                "daily": Decimal(str(limits.get("daily"))) if limits.get("daily") else None,
            }
        except (json.JSONDecodeError, ValueError):
            return {"monthly": None, "daily": None}
    
    async def get_cost_optimization_recommendations(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        summary = await self.get_usage_summary(user_id=user_id, api_key=api_key)
        recommendations = []
        
        # Check for expensive model usage
        total_cost = summary.total_cost
        if total_cost > Decimal('100'):  # $100 threshold
            for model, stats in summary.model_usage.items():
                model_cost_ratio = stats["cost"] / total_cost
                if model_cost_ratio > Decimal('0.8'):  # 80% of costs
                    recommendations.append({
                        "type": "model_optimization",
                        "title": f"Consider using a smaller model than {model}",
                        "description": f"{model} accounts for {model_cost_ratio:.1%} of your costs",
                        "potential_savings": float(stats["cost"] * Decimal('0.3')),
                        "priority": "high" if model_cost_ratio > Decimal('0.9') else "medium",
                    })
        
        # Check for high token usage patterns
        avg_tokens_per_request = summary.total_tokens / max(summary.total_requests, 1)
        if avg_tokens_per_request > 2000:
            recommendations.append({
                "type": "token_optimization",
                "title": "Consider reducing prompt length",
                "description": f"Average {avg_tokens_per_request:.0f} tokens per request",
                "potential_savings": float(total_cost * Decimal('0.2')),
                "priority": "medium",
            })
        
        # Check for batch processing opportunities
        if summary.total_requests > 1000:
            recommendations.append({
                "type": "batching",
                "title": "Use batch processing for better efficiency",
                "description": "Batch multiple requests to reduce overhead",
                "potential_savings": float(total_cost * Decimal('0.15')),
                "priority": "low",
            })
        
        return recommendations
    
    async def export_usage_data(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Export usage data in specified format."""
        records = await self._get_usage_records(
            user_id=user_id,
            api_key=api_key,
            start_time=start_date.timestamp() if start_date else None,
            end_time=end_date.timestamp() if end_date else None,
        )
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "api_key": api_key,
            "records": [],
        }
        
        for record in records:
            export_data["records"].append({
                "id": record.id,
                "model_name": record.model_name,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "total_tokens": record.total_tokens,
                "input_cost": float(record.input_cost),
                "output_cost": float(record.output_cost),
                "total_cost": float(record.total_cost),
                "timestamp": record.timestamp,
                "session_id": record.session_id,
                "metadata": record.metadata,
            })
        
        return export_data
    
    async def _store_usage_record(self, record: UsageRecord) -> None:
        """Store usage record in Redis."""
        try:
            # Store individual record
            record_key = f"usage:{record.id}"
            record_data = {
                "user_id": record.user_id,
                "api_key": record.api_key,
                "model_name": record.model_name,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "total_tokens": record.total_tokens,
                "input_cost": float(record.input_cost),
                "output_cost": float(record.output_cost),
                "total_cost": float(record.total_cost),
                "timestamp": record.timestamp,
                "session_id": record.session_id,
                "metadata": record.metadata,
            }
            
            import json
            await self.redis_manager.set(
                record_key,
                json.dumps(record_data, default=str),
                ex=86400 * 90,  # 90 days retention
            )
            
            # Add to user/API key usage list
            user_key = self._get_user_key(record.user_id, record.api_key)
            await self.redis_manager.lpush(f"user_usage:{user_key}", record.id)
            await self.redis_manager.expire(f"user_usage:{user_key}", 86400 * 90)
            
            # Add to daily usage summary
            date_key = datetime.fromtimestamp(record.timestamp).date().isoformat()
            daily_key = f"daily_usage:{user_key}:{date_key}"
            current_data = await self.redis_manager.get(daily_key)
            
            if current_data:
                daily_data = json.loads(current_data)
            else:
                daily_data = {
                    "requests": 0,
                    "tokens": 0,
                    "cost": 0.0,
                }
            
            daily_data["requests"] += 1
            daily_data["tokens"] += record.total_tokens
            daily_data["cost"] += float(record.total_cost)
            
            await self.redis_manager.set(
                daily_key,
                json.dumps(daily_data),
                ex=86400 * 90,
            )
            
        except Exception as e:
            logger.error("Failed to store usage record", error=str(e))
    
    async def _get_usage_records(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 10000,
    ) -> List[UsageRecord]:
        """Get usage records from Redis."""
        try:
            user_key = self._get_user_key(user_id, api_key)
            record_ids = await self.redis_manager.lrange(f"user_usage:{user_key}", 0, limit - 1)
            
            records = []
            for record_id in record_ids:
                record_data = await self.redis_manager.get(f"usage:{record_id}")
                if not record_data:
                    continue
                
                try:
                    import json
                    data = json.loads(record_data)
                    
                    # Filter by time range
                    if start_time and data["timestamp"] < start_time:
                        continue
                    if end_time and data["timestamp"] > end_time:
                        continue
                    
                    record = UsageRecord(
                        id=record_id,
                        user_id=data.get("user_id"),
                        api_key=data.get("api_key"),
                        model_name=data["model_name"],
                        prompt_tokens=data["prompt_tokens"],
                        completion_tokens=data["completion_tokens"],
                        total_tokens=data["total_tokens"],
                        input_cost=Decimal(str(data["input_cost"])),
                        output_cost=Decimal(str(data["output_cost"])),
                        total_cost=Decimal(str(data["total_cost"])),
                        timestamp=data["timestamp"],
                        session_id=data.get("session_id"),
                        metadata=data.get("metadata", {}),
                    )
                    records.append(record)
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse usage record {record_id}", error=str(e))
                    continue
            
            return records
            
        except Exception as e:
            logger.error("Failed to get usage records", error=str(e))
            return []
    
    async def _check_usage_limits(
        self,
        user_id: Optional[str],
        api_key: Optional[str],
        current_cost: Decimal,
    ) -> None:
        """Check if usage limits are exceeded."""
        limits = await self.get_usage_limits(user_id=user_id, api_key=api_key)
        
        # Check daily limit
        if limits["daily"]:
            today = datetime.utcnow().date().isoformat()
            user_key = self._get_user_key(user_id, api_key)
            daily_data = await self.redis_manager.get(f"daily_usage:{user_key}:{today}")
            
            daily_cost = Decimal('0')
            if daily_data:
                import json
                daily_cost = Decimal(str(json.loads(daily_data)["cost"]))
            
            if daily_cost + current_cost > limits["daily"]:
                logger.warning(
                    "Daily usage limit exceeded",
                    user_id=user_id,
                    current_cost=float(daily_cost + current_cost),
                    limit=float(limits["daily"]),
                )
        
        # Check monthly limit
        if limits["monthly"]:
            summary = await self.get_usage_summary(user_id=user_id, api_key=api_key)
            if summary.total_cost + current_cost > limits["monthly"]:
                logger.warning(
                    "Monthly usage limit exceeded",
                    user_id=user_id,
                    current_cost=float(summary.total_cost + current_cost),
                    limit=float(limits["monthly"]),
                )
    
    def _get_user_key(self, user_id: Optional[str], api_key: Optional[str]) -> str:
        """Get user key for Redis."""
        if user_id:
            return f"user:{user_id}"
        elif api_key:
            return f"api_key:{api_key}"
        else:
            return "anonymous"
    
    def _get_limit_key(self, user_id: Optional[str], api_key: Optional[str]) -> str:
        """Get limit key for Redis."""
        return self._get_user_key(user_id, api_key)