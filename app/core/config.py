from typing import Optional, List, Set
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class Settings:
    def __init__(self):
        # API settings
        self.API_V1_STR: str = "/api/v1"
        self.PROJECT_NAME: str = "Snapped AI"
        
        # Environment
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
        
        # SerpAPI settings
        self.SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
        self.MAX_SIMILAR_PRODUCTS: int = int(os.getenv("MAX_SIMILAR_PRODUCTS", "30"))
        self.STORE_RAW_DATA: bool = os.getenv("STORE_RAW_DATA", "false").lower() == "true"
        
        # Database settings
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
        self.DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
        self.DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
        
        # Redis settings
        self.REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # CORS settings
        cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "*")
        if cors_origins == "*":
            self.BACKEND_CORS_ORIGINS: List[str] = ["*"]
        else:
            self.BACKEND_CORS_ORIGINS: List[str] = [origin.strip() for origin in cors_origins.split(",")]
        
        # Upload settings
        self.UPLOAD_FOLDER: str = "app/static/uploads"
        self.STATIC_FOLDER: str = "app/static"
        self.ALLOWED_EXTENSIONS: Set[str] = {"png", "jpg", "jpeg", "gif", "webp"}
        self.MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "16777216"))  # 16MB
        
        # Cloudinary settings
        self.USE_CLOUDINARY: bool = os.getenv("USE_CLOUDINARY", "false").lower() == "true"
        self.CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
        self.CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
        self.CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
        self.SAVE_LOCAL_COPY: bool = os.getenv("SAVE_LOCAL_COPY", "true").lower() == "true"
        self.REQUIRE_CLOUDINARY: bool = os.getenv("REQUIRE_CLOUDINARY", "false").lower() == "true"
        
        # Server settings
        self.HOST: str = os.getenv("HOST", "127.0.0.1")
        self.PORT: int = int(os.getenv("PORT", "12000"))
        self.WORKERS: int = int(os.getenv("WORKERS", "4"))
        # Public base URL used to build absolute URLs for external services (e.g., SerpAPI)
        self.PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")
        
        # Performance settings
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
        self.THREAD_POOL_SIZE: int = int(os.getenv("THREAD_POOL_SIZE", "4"))
        
        # Rate limiting
        self.RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour
        
        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE: str = os.getenv("LOG_FILE", "app.log")
        
        # Security
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

settings = Settings()