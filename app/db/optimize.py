# app/db/optimize.py
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from app.core.config import settings
import logging
import os

logger = logging.getLogger(__name__)

def _is_sqlite(engine) -> bool:
    return engine.dialect.name == "sqlite"

def _table_exists(engine, table_name: str) -> bool:
    try:
        return inspect(engine).has_table(table_name)
    except Exception:
        # Fallback for SQLite if inspector has issues
        if _is_sqlite(engine):
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
                    {"n": table_name},
                ).fetchone()
                return row is not None
        return False

def _safe_exec(conn, sql: str) -> None:
    try:
        conn.execute(text(sql))
    except (OperationalError, ProgrammingError) as e:
        logger.debug("Skipping/ignoring statement due to error: %s | SQL: %s", e, sql)

def optimize_database():
    """
    Optimize the database safely:
      - For SQLite: apply useful PRAGMAs (non-fatal if not supported) and create indexes.
      - Create indexes only if their tables already exist.
      - Never fail the app if an index/table is missing.
    """
    # Prefer env var override if present
    db_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)

    engine = create_engine(
        db_url,
        connect_args=(
            {"check_same_thread": False, "timeout": 30}
            if db_url.startswith("sqlite")
            else {}
        ),
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
        future=True,
    )

    try:
        with engine.begin() as conn:
            # ---------- Engine-specific tuning ----------
            if _is_sqlite(engine):
                # These PRAGMAs are safe to attempt; failures are logged and ignored
                _safe_exec(conn, "PRAGMA journal_mode=WAL;")          # better concurrency
                _safe_exec(conn, "PRAGMA synchronous=NORMAL;")         # durability/perf balance
                _safe_exec(conn, "PRAGMA mmap_size=30000000000;")      # 30GB; ignored if unsupported
                _safe_exec(conn, "PRAGMA cache_size=20000;")           # ~80MB if 4KB pages
                _safe_exec(conn, "PRAGMA foreign_keys=ON;")
                _safe_exec(conn, "PRAGMA busy_timeout=30000;")         # 30s
                _safe_exec(conn, "PRAGMA automatic_index=ON;")
                _safe_exec(conn, "PRAGMA temp_store=MEMORY;")
                _safe_exec(conn, "PRAGMA page_size=4096;")             # note: requires VACUUM to take effect

            # ---------- Conditional indexes ----------
            idx_statements = [
                # table_name, create_index_sql
                (
                    "image_searches",
                    """
                    CREATE INDEX IF NOT EXISTS idx_image_searches_recent
                    ON image_searches (search_time DESC, id DESC)
                    """,
                ),
                (
                    "search_results",
                    """
                    CREATE INDEX IF NOT EXISTS idx_search_results_search_price
                    ON search_results (search_id, price)
                    """,
                ),
                (
                    "search_results",
                    """
                    -- partial index helps when brand is frequently NULL
                    CREATE INDEX IF NOT EXISTS idx_search_results_brand
                    ON search_results (brand)
                    WHERE brand IS NOT NULL
                    """,
                ),
                (
                    "search_results",
                    """
                    CREATE INDEX IF NOT EXISTS idx_search_results_composite
                    ON search_results (search_id, brand, price)
                    """,
                ),
            ]

            created_any = False
            for table_name, sql in idx_statements:
                if _table_exists(engine, table_name):
                    _safe_exec(conn, sql)
                    created_any = True
                else:
                    logger.info("Skipping index creation: table '%s' not found.", table_name)

            if created_any:
                logger.info("Index ensure step completed.")

            # ---------- Planner stats ----------
            # ANALYZE works on SQLite and Postgres; harmless if already analyzed.
            _safe_exec(conn, "ANALYZE;")
            if _is_sqlite(engine):
                _safe_exec(conn, "PRAGMA optimize;")

        logger.info("Database optimization completed successfully.")

    finally:
        # Free pooled connections
        engine.dispose()

if __name__ == "__main__":
    optimize_database()
