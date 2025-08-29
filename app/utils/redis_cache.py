import json
import functools
import time
import os
import sys
from typing import Any, Callable, Dict, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if Redis is available
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"

# Initialize Redis client if enabled
redis_client = None
if REDIS_ENABLED:
    try:
        # Try to import Redis - this might fail if the package is not installed
        try:
            import redis
        except ImportError:
            logger.warning("Redis package not installed, falling back to in-memory cache")
            REDIS_ENABLED = False
        
        # If Redis is available, try to connect
        if REDIS_ENABLED:
            try:
                redis_client = redis.from_url(REDIS_URL)
                redis_client.ping()  # Test connection
                logger.info("Redis cache enabled")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {str(e)}")
                logger.warning("Falling back to in-memory cache")
                redis_client = None
                REDIS_ENABLED = False
    except Exception as e:
        logger.warning(f"Error initializing Redis: {str(e)}")
        logger.warning("Falling back to in-memory cache")
        redis_client = None
        REDIS_ENABLED = False

# In-memory cache as fallback
_memory_cache: Dict[str, Dict[str, Any]] = {}

def redis_cache(ttl: int = 3600):
    """
    Cache decorator that uses Redis if available, otherwise falls back to in-memory cache
    
    Args:
        ttl: Time to live in seconds (default: 1 hour)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Create a cache key from function name and arguments
                # Use a simpler key format to avoid potential encoding issues
                key = f"{func.__name__}:{hash(str(args))}{hash(str(kwargs))}"
                
                # Try to get from cache
                if REDIS_ENABLED and redis_client:
                    try:
                        cached_data = redis_client.get(key)
                        if cached_data:
                            logger.info(f"Redis cache hit for {func.__name__}")
                            return json.loads(cached_data)
                    except Exception as e:
                        logger.warning(f"Error retrieving from Redis cache: {str(e)}")
                elif key in _memory_cache:
                    entry = _memory_cache[key]
                    if time.time() - entry["timestamp"] < ttl:
                        logger.info(f"Memory cache hit for {func.__name__}")
                        return entry["result"]
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Cache the result
                try:
                    if REDIS_ENABLED and redis_client:
                        try:
                            # Try to serialize the result
                            serialized = json.dumps(result)
                            redis_client.setex(key, ttl, serialized)
                        except (TypeError, json.JSONDecodeError) as e:
                            logger.warning(f"Could not serialize result for Redis: {str(e)}")
                    else:
                        _memory_cache[key] = {
                            "result": result,
                            "timestamp": time.time()
                        }
                        
                        # Clean up old entries if memory cache gets too large
                        if len(_memory_cache) > 1000:  # Arbitrary limit
                            now = time.time()
                            expired_keys = [k for k, v in _memory_cache.items() 
                                          if now - v["timestamp"] > ttl]
                            for k in expired_keys[:100]:  # Remove oldest 100 entries
                                _memory_cache.pop(k, None)
                                
                except Exception as e:
                    logger.error(f"Error caching result: {str(e)}")
                
                return result
            except Exception as e:
                logger.error(f"Unexpected error in cache decorator: {str(e)}")
                # Fall back to calling the original function
                return await func(*args, **kwargs)
                
        return wrapper
    return decorator

def clear_cache():
    """
    Clear the cache
    """
    if REDIS_ENABLED and redis_client:
        redis_client.flushdb()
        logger.info("Redis cache cleared")
    else:
        global _memory_cache
        _memory_cache = {}
        logger.info("Memory cache cleared")