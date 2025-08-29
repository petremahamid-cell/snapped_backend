from sqlalchemy import create_engine, text
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def optimize_database():
    """
    Optimize the SQLite database for better performance
    """
    engine = create_engine(
        settings.DATABASE_URL, 
        connect_args={
            "check_same_thread": False,
            "timeout": 30  # 30 second timeout for database operations
        },
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections every hour
        echo=False  # Set to True for SQL debugging
    )
    
    with engine.connect() as conn:
        # Enable WAL mode for better concurrency
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        
        # Set synchronous mode to NORMAL for better performance
        conn.execute(text("PRAGMA synchronous=NORMAL;"))
        
        # Enable memory-mapped I/O for the database file (30GB limit)
        conn.execute(text("PRAGMA mmap_size=30000000000;"))
        
        # Set cache size to 20000 pages (about 80MB)
        conn.execute(text("PRAGMA cache_size=20000;"))
        
        # Enable foreign key constraints
        conn.execute(text("PRAGMA foreign_keys=ON;"))
        
        # Set busy timeout to 30 seconds
        conn.execute(text("PRAGMA busy_timeout=30000;"))
        
        # Enable automatic index creation
        conn.execute(text("PRAGMA automatic_index=ON;"))
        
        # Set temp store to memory for better performance
        conn.execute(text("PRAGMA temp_store=MEMORY;"))
        
        # Optimize page size for better I/O
        conn.execute(text("PRAGMA page_size=4096;"))
        
        # Create additional indexes for better query performance
        try:
            # Index for recent searches
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_image_searches_recent 
                ON image_searches(search_time DESC, id DESC);
            """))
            
            # Index for search results by search_id and price
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_results_search_price 
                ON search_results(search_id, price);
            """))
            
            # Index for search results by brand
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_results_brand 
                ON search_results(brand) WHERE brand IS NOT NULL;
            """))
            
            # Composite index for filtering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_results_composite 
                ON search_results(search_id, brand, price);
            """))
            
            logger.info("Additional database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Some indexes may already exist: {e}")
        
        # Analyze the database to optimize query planning
        conn.execute(text("ANALYZE;"))
        
        # Update statistics for better query optimization
        conn.execute(text("PRAGMA optimize;"))
    
    logger.info("Database optimized successfully.")

if __name__ == "__main__":
    optimize_database()