from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
import sys
import time
import logging
import platform
from contextlib import asynccontextmanager
import importlib.metadata

from app.api.api import api_router
from app.core.config import settings
from app.db.base import Base, engine
from app.db.optimize import optimize_database
from app.db.init_db import init_db
from app.utils.connection_pool import close_http_pool

# Check Pydantic version for compatibility
try:
    pydantic_version = importlib.metadata.version("pydantic")
    is_pydantic_v1 = pydantic_version.startswith("1.")
    logger = logging.getLogger(__name__)
    logger.info(f"Using Pydantic version: {pydantic_version}")
    if is_pydantic_v1:
        logger.warning("Using Pydantic v1 - some features may be limited")
except Exception:
    # If we can't determine the version, assume it's compatible
    is_pydantic_v1 = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log"),
    ]
)
logger = logging.getLogger(__name__)

# Log system information
logger.info(f"Python version: {platform.python_version()}")
logger.info(f"Operating System: {platform.system()} {platform.release()}")
logger.info(f"Platform: {platform.platform()}")

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables and optimize
    try:
        logger.info("Initializing database...")
        await init_db()
        optimize_database()
        logger.info("Database initialized successfully.")
        
        # Initialize Cloudinary if enabled
        if settings.USE_CLOUDINARY:
            try:
                import cloudinary
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET,
                    secure=True
                )
                logger.info("Cloudinary initialized successfully")
            except ImportError:
                logger.warning("Cloudinary package not installed. Using local storage instead.")
            except Exception as e:
                logger.error(f"Error initializing Cloudinary: {str(e)}")
                logger.warning("Continuing without Cloudinary. Using local storage instead.")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}", exc_info=True)
        raise
    
    yield
    
    # Shutdown: Clean up resources
    logger.info("Shutting down application...")
    await close_http_pool()

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Add middleware for request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"Request to {request.url.path} processed in {process_time:.4f} seconds")
    return response

# Mount static files
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.STATIC_FOLDER), name="static")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {"message": "Welcome to Snapped AI API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Exception handler for unexpected errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )

if __name__ == "__main__":
    import uvicorn
    
    # Log server startup information
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    logger.info(f"API documentation will be available at http://{settings.HOST}:{settings.PORT}/docs")
    
    # Check if running on Windows
    if platform.system() == "Windows":
        logger.info("Running on Windows - using uvicorn directly")
        uvicorn.run(
            "app.main:app", 
            host=settings.HOST, 
            port=settings.PORT,
            reload=True,
            log_level="info"
        )
    else:
        # For Linux/Mac, uvicorn with workers is recommended
        logger.info("Running on Unix-like system - using uvicorn with workers")
        uvicorn.run(
            "app.main:app", 
            host=settings.HOST, 
            port=settings.PORT,
            reload=True,
            log_level="info"
        )