"""
Database initialization script
Creates all tables in the PostgreSQL database
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import init_db, engine
from app.models.database import Base, AsinBank, OASourcing, PurchaseTracker


def main():
    """Initialize database tables"""
    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)
    print(f"\nDatabase URL: {engine.url}")
    
    try:
        # Create all tables
        print("\nCreating database tables...")
        init_db()
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("\n✓ Successfully created the following tables:")
        for table in tables:
            print(f"  - {table}")
        
        print("\n" + "=" * 60)
        print("Database initialization completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error initializing database: {e}")
        raise


if __name__ == '__main__':
    main()


