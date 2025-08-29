import httpx
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class HTTPConnectionPool:
    """
    Singleton HTTP connection pool for better performance
    """
    _instance: Optional['HTTPConnectionPool'] = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client with connection pooling"""
        if self._client is None or self._client.is_closed:
            # Configure connection limits for better performance
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )
            
            # Configure timeout for external API calls
            timeout = httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=10.0,
                pool=5.0
            )
            
            self._client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=True,  # Enable HTTP/2 for better performance
                follow_redirects=True
            )
            logger.info("HTTP connection pool initialized")
        
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("HTTP connection pool closed")

# Global instance
http_pool = HTTPConnectionPool()

async def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client"""
    return await http_pool.get_client()

async def close_http_pool():
    """Close the HTTP connection pool"""
    await http_pool.close()