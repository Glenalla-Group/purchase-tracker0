"""
Initialize database tables
Run this script to create all tables in the database
"""

from app.config.database import init_db, engine
from app.models.database import Base
from sqlalchemy import text

def main():
    print("=" * 60)
    print("DATABASE INITIALIZATION")
    print("=" * 60)
    
    # Test connection
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        print("[OK] Database connection successful!")
    except Exception as e:
        print(f"[ERROR] Cannot connect to database: {e}")
        return
    
    # Create all tables
    try:
        print("\n[INFO] Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("[OK] All tables created successfully!")
        
        # Show created tables
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = result.fetchall()
            
            if tables:
                print(f"\n[INFO] Found {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("\n[WARNING] No tables found!")
        
        print("\n" + "=" * 60)
        print("DATABASE INITIALIZATION COMPLETE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to create tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()






