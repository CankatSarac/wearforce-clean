import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
import re
import json
from pydantic import BaseModel

import structlog

logger = structlog.get_logger()


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append('_')
        result.append(char.lower())
    return ''.join(result)


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])


def paginate_query_params(
    skip: int = 0,
    limit: int = 100,
    max_limit: int = 1000
) -> tuple[int, int]:
    """Validate and normalize pagination parameters."""
    skip = max(0, skip)
    limit = min(max(1, limit), max_limit)
    return skip, limit


class PaginatedResponse(BaseModel):
    """Standard paginated response model."""
    items: List[Any]
    total: int
    skip: int
    limit: int
    has_more: bool
    
    @classmethod
    def create(
        cls,
        items: List[Any],
        total: int,
        skip: int,
        limit: int
    ) -> "PaginatedResponse":
        """Create a paginated response."""
        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + limit) < total
        )


class FilterParams(BaseModel):
    """Base class for filter parameters."""
    search: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"
    
    def get_sort_order(self) -> str:
        """Get normalized sort order."""
        return "desc" if self.sort_order and self.sort_order.lower() == "desc" else "asc"


def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def clean_dict(data: Dict[str, Any], remove_none: bool = True) -> Dict[str, Any]:
    """Clean dictionary by removing None values and empty strings."""
    cleaned = {}
    for key, value in data.items():
        if remove_none and value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        if isinstance(value, dict):
            cleaned_nested = clean_dict(value, remove_none)
            if cleaned_nested:
                cleaned[key] = cleaned_nested
        else:
            cleaned[key] = value
    return cleaned


def generate_short_id(length: int = 8) -> str:
    """Generate a short random ID."""
    return str(uuid.uuid4()).replace('-', '')[:length]


def generate_hash(data: str, algorithm: str = 'sha256') -> str:
    """Generate a hash of the given data."""
    if algorithm == 'sha256':
        return hashlib.sha256(data.encode()).hexdigest()
    elif algorithm == 'md5':
        return hashlib.md5(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format (basic validation)."""
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone)
    # Check if it's between 10 and 15 digits
    return len(cleaned) >= 10 and len(cleaned) <= 15


def sanitize_string(value: str, max_length: int = None) -> str:
    """Sanitize string input."""
    if not value:
        return ""
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1F\x7F]', '', value)
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def format_currency(amount: Union[int, float, Decimal], currency: str = 'USD') -> str:
    """Format currency amount."""
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    
    if currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    elif currency == 'GBP':
        return f"£{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def parse_sort_params(sort_param: str) -> List[Dict[str, str]]:
    """Parse sort parameter string into list of sort criteria.
    
    Example: "name:asc,created_at:desc" -> [{"field": "name", "direction": "asc"}, ...]
    """
    if not sort_param:
        return []
    
    sorts = []
    for item in sort_param.split(','):
        item = item.strip()
        if ':' in item:
            field, direction = item.split(':', 1)
            direction = direction.lower()
            if direction not in ['asc', 'desc']:
                direction = 'asc'
        else:
            field = item
            direction = 'asc'
        
        sorts.append({"field": field.strip(), "direction": direction})
    
    return sorts


def parse_filter_params(filter_param: str) -> Dict[str, Any]:
    """Parse filter parameter string into dictionary.
    
    Example: "status:active,category:electronics" -> {"status": "active", "category": "electronics"}
    """
    if not filter_param:
        return {}
    
    filters = {}
    for item in filter_param.split(','):
        item = item.strip()
        if ':' in item:
            key, value = item.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Try to parse as JSON for complex values
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # Keep as string
                pass
            
            filters[key] = value
    
    return filters


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely parse JSON string, returning default on error."""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def calculate_pagination_info(total_count: int, page: int, page_size: int) -> Dict[str, Any]:
    """Calculate pagination information."""
    total_pages = (total_count + page_size - 1) // page_size
    has_next = page < total_pages
    has_previous = page > 1
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous,
        "start_index": (page - 1) * page_size + 1 if total_count > 0 else 0,
        "end_index": min(page * page_size, total_count)
    }


def mask_sensitive_data(data: Dict[str, Any], sensitive_fields: List[str] = None) -> Dict[str, Any]:
    """Mask sensitive fields in dictionary for logging."""
    if sensitive_fields is None:
        sensitive_fields = [
            'password', 'token', 'secret', 'key', 'credential', 
            'auth', 'bearer', 'session', 'cookie'
        ]
    
    masked_data = data.copy()
    
    for key, value in masked_data.items():
        key_lower = key.lower()
        if any(field in key_lower for field in sensitive_fields):
            masked_data[key] = "***MASKED***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_fields)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            masked_data[key] = [mask_sensitive_data(item, sensitive_fields) for item in value]
    
    return masked_data


class BusinessRules:
    """Common business rule validations."""
    
    @staticmethod
    def validate_lead_score(score: int) -> bool:
        """Validate lead score is within valid range."""
        return 0 <= score <= 100
    
    @staticmethod
    def validate_discount_percentage(discount: float) -> bool:
        """Validate discount percentage is within valid range."""
        return 0 <= discount <= 100
    
    @staticmethod
    def validate_quantity(quantity: int) -> bool:
        """Validate quantity is positive."""
        return quantity > 0
    
    @staticmethod
    def validate_price(price: Union[int, float, Decimal]) -> bool:
        """Validate price is non-negative."""
        if isinstance(price, (int, float)):
            price = Decimal(str(price))
        return price >= 0
    
    @staticmethod
    def validate_stock_level(stock: int, min_stock: int = 0) -> bool:
        """Validate stock level."""
        return stock >= min_stock
    
    @staticmethod
    def is_business_hours(dt: datetime = None) -> bool:
        """Check if datetime is within business hours (9 AM - 5 PM, Mon-Fri UTC)."""
        if dt is None:
            dt = utc_now()
        
        # Monday is 0, Sunday is 6
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        
        return 9 <= dt.hour < 17


class DataTransformers:
    """Data transformation utilities."""
    
    @staticmethod
    def normalize_phone_number(phone: str) -> str:
        """Normalize phone number format."""
        # Remove all non-digit characters
        digits_only = re.sub(r'[^\d]', '', phone)
        
        # Add country code if missing (assuming US)
        if len(digits_only) == 10:
            digits_only = '1' + digits_only
        
        # Format as +1 (XXX) XXX-XXXX
        if len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
        
        return phone  # Return original if can't normalize
    
    @staticmethod
    def extract_domain_from_email(email: str) -> str:
        """Extract domain from email address."""
        if '@' in email:
            return email.split('@')[1].lower()
        return ""
    
    @staticmethod
    def format_address(address_parts: Dict[str, str]) -> str:
        """Format address parts into a single string."""
        parts = []
        
        if address_parts.get('street'):
            parts.append(address_parts['street'])
        if address_parts.get('city'):
            parts.append(address_parts['city'])
        if address_parts.get('state'):
            parts.append(address_parts['state'])
        if address_parts.get('postal_code'):
            parts.append(address_parts['postal_code'])
        if address_parts.get('country'):
            parts.append(address_parts['country'])
        
        return ', '.join(parts)