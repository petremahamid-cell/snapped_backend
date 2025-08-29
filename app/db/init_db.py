import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.core.config import settings

logger = logging.getLogger(__name__)

async def init_db():
    """
    Initialize the database by creating all tables
    """
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        logger.info(f"Created uploads directory: {settings.UPLOAD_FOLDER}")
        
        # Create static directory if it doesn't exist
        os.makedirs(settings.STATIC_FOLDER, exist_ok=True)
        logger.info(f"Created static directory: {settings.STATIC_FOLDER}")
        
        # Create engine
        engine = create_engine(
            settings.DATABASE_URL, connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create a session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Add any initial data here if needed
            pass
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    print("Database initialized successfully.")