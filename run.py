#!/usr/bin/env python
"""
Run script for Snapped AI application
Simple script to run the FastAPI server
"""

import uvicorn
import os
from app.core.config import settings

def main():
    """Run the FastAPI application"""
    print(f"Starting Snapped AI API server on http://{settings.HOST}:{settings.PORT}")
    print(f"API documentation will be available at http://{settings.HOST}:{settings.PORT}/docs")
    
    # Create uploads directory if it doesn't exist
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()