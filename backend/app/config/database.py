from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import os
import logging
from typing import Generator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in environment variables. "
        "Please create a .env file with DATABASE_URL setting. "
        "See .env.example for reference."
    )

# Get additional database settings from environment
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
DB_ECHO = os.getenv('DB_ECHO', 'False').lower() == 'true'

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,           # Number of connections to maintain
    max_overflow=DB_MAX_OVERFLOW,     # Additional connections when pool is full
    pool_timeout=DB_POOL_TIMEOUT,     # Seconds to wait for connection
    pool_recycle=DB_POOL_RECYCLE,     # Recycle connections after this many seconds
    pool_pre_ping=True,                # Verify connections before using
    echo=DB_ECHO                       # Log SQL statements (set to False in production)
)

# Test database connection
def test_connection():
    """Test database connection and log status"""
    try:
        # Try to connect
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        
        # Extract database info from URL (hide password)
        db_url_parts = DATABASE_URL.split('@')
        if len(db_url_parts) > 1:
            db_host = db_url_parts[1].split('/')[0]
            db_name = DATABASE_URL.split('/')[-1].split('?')[0]
            logger.info(f"[DATABASE] PostgreSQL connected successfully!")
            logger.info(f"[DATABASE] Host: {db_host} | Database: {db_name}")
        else:
            logger.info("[DATABASE] PostgreSQL connected successfully!")
        
        return True
    except Exception as e:
        logger.error(f"[DATABASE] Failed to connect to PostgreSQL: {e}")
        return False

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    """
    from app.models.database import Base
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def drop_all_tables():
    """
    Drop all tables - USE WITH CAUTION!
    """
    from app.models.database import Base
    Base.metadata.drop_all(bind=engine)
    print("All database tables dropped!")


