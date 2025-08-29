import time
import functools
import asyncio
from typing import Callable, Dict, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory cache
_cache: Dict[str, Dict[str, Any]] = {}

def timed_async(func):
    """
    Decorator to measure and log the execution time of async functions
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        logger.info(f"Function {func.__name__} executed in {execution_time:.4f} seconds")
        
        return result
    return wrapper

def async_cache(ttl: int = 3600):
    """
    Simple async cache decorator with time-to-live (TTL) in seconds
    
    Args:
        ttl: Time to live in seconds (default: 1 hour)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check if result is in cache and not expired
            if key in _cache:
                entry = _cache[key]
                if time.time() - entry["timestamp"] < ttl:
                    logger.info(f"Cache hit for {func.__name__}")
                    return entry["result"]
            
            # Execute the function and cache the result
            result = await func(*args, **kwargs)
            _cache[key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
        return wrapper
    return decorator

async def run_in_threadpool(func: Callable, *args, **kwargs) -> Any:
    """
    Run a CPU-bound function in a thread pool to avoid blocking the event loop
    
    Args:
        func: The function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(func, *args, **kwargs)
    )

def clear_cache():
    """
    Clear the in-memory cache
    """
    global _cache
    _cache = {}
    logger.info("Cache cleared")