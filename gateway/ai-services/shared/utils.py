"""Utility functions for AI services."""

import asyncio
import hashlib
import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .exceptions import ExternalServiceError


logger = structlog.get_logger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def generate_id(prefix: str = "", suffix: str = "") -> str:
    """Generate unique ID with optional prefix and suffix."""
    timestamp = str(int(time.time() * 1000000))  # microseconds
    return f"{prefix}{timestamp}{suffix}"


def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Generate hash of text."""
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode("utf-8"))
    return hash_obj.hexdigest()


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    min_chunk_size: int = 100,
) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [{"text": text, "start": 0, "end": len(text)}]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # If this is not the last chunk, try to break at word boundary
        if end < len(text):
            # Look for the last space within the chunk
            last_space = text.rfind(" ", start, end)
            if last_space > start + min_chunk_size:
                end = last_space
        
        chunk_text = text[start:end].strip()
        if len(chunk_text) >= min_chunk_size or start == 0:
            chunks.append({
                "text": chunk_text,
                "start": start,
                "end": end,
            })
        
        # Move start position with overlap
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations."""
    import re
    
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")
    
    # Limit length
    if len(filename) > 255:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_len = 255 - len(ext)
        filename = name[:max_name_len] + ext
    
    return filename or "untitled"


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration to human readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def retry_with_exponential_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Decorator for retrying functions with exponential backoff."""
    def decorator(func: F) -> F:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(exceptions),
            reraise=True,
        )
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(exceptions),
            reraise=True,
        )
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def safe_execute(
    func: Callable[..., T],
    *args,
    error_message: str = "Operation failed",
    default_value: Optional[T] = None,
    log_errors: bool = True,
    **kwargs,
) -> Optional[T]:
    """Safely execute a function and handle errors."""
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(
                error_message,
                error=str(e),
                function=func.__name__,
                exc_info=True,
            )
        return default_value


def validate_audio_format(format_str: str, supported_formats: List[str]) -> bool:
    """Validate audio format."""
    return format_str.lower() in [f.lower() for f in supported_formats]


def validate_text_length(text: str, max_length: int) -> bool:
    """Validate text length."""
    return len(text) <= max_length


def extract_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract file information."""
    path = Path(file_path)
    
    return {
        "name": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "size": path.stat().st_size if path.exists() else 0,
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "absolute_path": str(path.absolute()),
    }


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def filter_dict(
    data: Dict[str, Any],
    include_keys: Optional[List[str]] = None,
    exclude_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Filter dictionary keys."""
    if include_keys:
        return {k: v for k, v in data.items() if k in include_keys}
    elif exclude_keys:
        return {k: v for k, v in data.items() if k not in exclude_keys}
    else:
        return data.copy()


def flatten_dict(
    data: Dict[str, Any],
    separator: str = ".",
    prefix: str = "",
) -> Dict[str, Any]:
    """Flatten nested dictionary."""
    result = {}
    
    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key
        
        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = value
    
    return result


def batch_items(items: List[T], batch_size: int) -> List[List[T]]:
    """Split items into batches."""
    return [
        items[i : i + batch_size]
        for i in range(0, len(items), batch_size)
    ]


async def run_in_executor(
    func: Callable[..., T],
    *args,
    executor=None,
    **kwargs,
) -> T:
    """Run sync function in executor."""
    loop = asyncio.get_event_loop()
    
    def wrapped_func():
        return func(*args, **kwargs)
    
    return await loop.run_in_executor(executor, wrapped_func)


class AsyncLRUCache:
    """Async LRU cache implementation."""
    
    def __init__(self, max_size: int = 128, ttl: Optional[int] = None) -> None:
        """Initialize cache."""
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            # Check TTL
            if self.ttl and time.time() - entry["timestamp"] > self.ttl:
                del self.cache[key]
                del self.access_times[key]
                return None
            
            # Update access time
            self.access_times[key] = time.time()
            return entry["value"]
    
    async def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        async with self._lock:
            current_time = time.time()
            
            # If cache is full, remove least recently used item
            if len(self.cache) >= self.max_size and key not in self.cache:
                lru_key = min(self.access_times.keys(), key=self.access_times.get)
                del self.cache[lru_key]
                del self.access_times[lru_key]
            
            self.cache[key] = {
                "value": value,
                "timestamp": current_time,
            }
            self.access_times[key] = current_time
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.access_times[key]
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.access_times.clear()
    
    async def size(self) -> int:
        """Get cache size."""
        return len(self.cache)


# Audio Processing Utilities
def encode_audio_base64(audio_data: bytes) -> str:
    """Encode audio data to base64 string."""
    import base64
    return base64.b64encode(audio_data).decode('utf-8')


def decode_audio_base64(encoded_data: str) -> bytes:
    """Decode base64 audio data."""
    import base64
    return base64.b64decode(encoded_data)


def validate_audio_data(audio_data: bytes, max_size: int = 10 * 1024 * 1024) -> bool:
    """Validate audio data size and basic format."""
    if len(audio_data) > max_size:
        return False
    
    # Check for common audio file signatures
    wav_header = b'RIFF'
    mp3_header = b'\xff\xfb'
    flac_header = b'fLaC'
    ogg_header = b'OggS'
    
    return (
        audio_data.startswith(wav_header) or
        audio_data.startswith(mp3_header) or
        audio_data.startswith(flac_header) or
        audio_data.startswith(ogg_header) or
        len(audio_data) > 0  # Allow other formats
    )


def get_audio_info(audio_data: bytes) -> Dict[str, Any]:
    """Get basic audio information from bytes."""
    info = {
        "size": len(audio_data),
        "format": "unknown",
        "is_valid": validate_audio_data(audio_data),
    }
    
    # Detect format from header
    if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:20]:
        info["format"] = "wav"
    elif audio_data.startswith(b'\xff\xfb') or audio_data.startswith(b'ID3'):
        info["format"] = "mp3"
    elif audio_data.startswith(b'fLaC'):
        info["format"] = "flac"
    elif audio_data.startswith(b'OggS'):
        info["format"] = "ogg"
    
    return info


# Text Processing Utilities
def preprocess_text_for_tts(text: str) -> str:
    """Preprocess text for better TTS output."""
    import re
    
    # Expand common abbreviations
    abbreviations = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Miss',
        r'\bProf\.': 'Professor',
        r'\bSt\.': 'Street',
        r'\bAve\.': 'Avenue',
        r'\bBlvd\.': 'Boulevard',
        r'\bRd\.': 'Road',
        r'\betc\.': 'etcetera',
        r'\bi\.e\.': 'that is',
        r'\be\.g\.': 'for example',
        r'\bvs\.': 'versus',
        r'\bUSA\b': 'United States of America',
        r'\bUK\b': 'United Kingdom',
        r'\bAI\b': 'Artificial Intelligence',
        r'\bAPI\b': 'Application Programming Interface',
    }
    
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Handle numbers and dates
    text = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', r'\1 \2 \3', text)  # Dates
    text = re.sub(r'\b(\d+)%\b', r'\1 percent', text)  # Percentages
    text = re.sub(r'\$(\d+)\b', r'\1 dollars', text)  # Currency
    
    # Clean up formatting
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces
    text = re.sub(r'([.!?])\1+', r'\1', text)  # Multiple punctuation
    
    return text.strip()


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Basic entity extraction (email, phone, URLs)."""
    import re
    
    entities = {
        "emails": [],
        "phones": [],
        "urls": [],
        "numbers": [],
        "dates": [],
    }
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    entities["emails"] = re.findall(email_pattern, text)
    
    # Phone pattern (simple)
    phone_pattern = r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
    entities["phones"] = re.findall(phone_pattern, text)
    
    # URL pattern
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    entities["urls"] = re.findall(url_pattern, text)
    
    # Number pattern
    number_pattern = r'\b\d+(?:\.\d+)?\b'
    entities["numbers"] = re.findall(number_pattern, text)
    
    # Date pattern (basic)
    date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
    entities["dates"] = re.findall(date_pattern, text)
    
    return entities


def split_text_into_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    import re
    # Simple sentence splitting
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]


def count_tokens_estimate(text: str) -> int:
    """Estimate token count (rough approximation)."""
    # Very rough estimate: ~4 characters per token on average for English
    return max(1, len(text) // 4)


def chunk_text_by_tokens(
    text: str,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
) -> List[str]:
    """Chunk text by estimated token count."""
    sentences = split_text_into_sentences(text)
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = count_tokens_estimate(sentence)
        
        if current_tokens + sentence_tokens > max_tokens and current_chunk:
            # Finish current chunk
            chunks.append(' '.join(current_chunk))
            
            # Start new chunk with overlap
            if overlap_tokens > 0 and len(current_chunk) > 1:
                overlap_text = ' '.join(current_chunk[-2:])
                current_chunk = [overlap_text, sentence]
                current_tokens = count_tokens_estimate(overlap_text) + sentence_tokens
            else:
                current_chunk = [sentence]
                current_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens
    
    # Add final chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


class BatchProcessor:
    """Utility for processing items in batches with concurrency control."""
    
    def __init__(self, batch_size: int = 10, max_workers: int = 5):
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    async def process_batch(
        self,
        items: List[Any],
        process_func: Callable,
        semaphore: asyncio.Semaphore,
    ) -> List[Any]:
        """Process a batch of items."""
        async with semaphore:
            tasks = []
            for item in items:
                if asyncio.iscoroutinefunction(process_func):
                    tasks.append(process_func(item))
                else:
                    tasks.append(run_in_executor(process_func, item))
            return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def process_all(
        self,
        items: List[Any],
        process_func: Callable,
    ) -> List[Any]:
        """Process all items in batches with concurrency control."""
        semaphore = asyncio.Semaphore(self.max_workers)
        batches = batch_items(items, self.batch_size)
        
        all_results = []
        for batch in batches:
            results = await self.process_batch(batch, process_func, semaphore)
            all_results.extend(results)
        
        return all_results


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, rate: float, capacity: int = None):
        self.rate = rate  # tokens per second
        self.capacity = capacity or int(rate)  # bucket capacity
        self.tokens = self.capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Acquire tokens from the bucket."""
        async with self._lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def wait_for_tokens(self, tokens: int = 1) -> None:
        """Wait until tokens are available."""
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)


class AsyncTimer:
    """Async context manager for timing operations."""
    
    def __init__(self, operation_name: str = "operation"):
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.elapsed: float = 0.0
    
    async def __aenter__(self):
        """Enter the timer context."""
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the timer context."""
        self.end_time = time.time()
        if self.start_time is not None:
            self.elapsed = self.end_time - self.start_time
        
        logger.debug(
            "Operation completed",
            operation=self.operation_name,
            elapsed_seconds=self.elapsed,
            elapsed_ms=self.elapsed * 1000,
        )


def get_mime_type_from_extension(file_extension: str) -> str:
    """Get MIME type from file extension."""
    mime_types = {
        # Audio formats
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'flac': 'audio/flac',
        'm4a': 'audio/mp4',
        'aac': 'audio/aac',
        'ogg': 'audio/ogg',
        'webm': 'audio/webm',
        
        # Image formats
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'bmp': 'image/bmp',
        'svg': 'image/svg+xml',
        
        # Document formats
        'pdf': 'application/pdf',
        'txt': 'text/plain',
        'json': 'application/json',
        'xml': 'application/xml',
        'csv': 'text/csv',
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
    }
    
    return mime_types.get(file_extension.lower().lstrip('.'), 'application/octet-stream')


def clean_and_validate_text(
    text: str,
    max_length: Optional[int] = None,
    min_length: int = 1,
    remove_special_chars: bool = False,
) -> str:
    """Clean and validate text input."""
    import re
    
    # Basic cleaning
    text = text.strip()
    
    # Remove or normalize special characters if requested
    if remove_special_chars:
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Check length constraints
    if len(text) < min_length:
        raise ValueError(f"Text must be at least {min_length} characters long")
    
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return text