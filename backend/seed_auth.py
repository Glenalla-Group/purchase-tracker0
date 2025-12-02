"""
Seed script for authentication tables.

This script:
1. Creates default user roles (admin, user)
2. Creates a default admin user
3. Can be run multiple times safely (checks for existing data)

Usage:
    python seed_auth.py
"""

import sys
from sqlalchemy.orm import Session

from app.config.database import SessionLocal, test_connection
from app.models.database import User, UserRole
from app.utils.password import hash_password


def seed_roles(db: Session) -> dict:
    """
    Seed default user roles.
    
    Returns:
        Dictionary mapping role names to role IDs
    """
    print("\n📋 Seeding user roles...")
    
    roles_data = [
        {"name": "admin", "description": "Administrator with full access to all features"},
        {"name": "user", "description": "Regular user with limited access"},
    ]
    
    role_ids = {}
    
    for role_data in roles_data:
        # Check if role already exists
        existing_role = db.query(UserRole).filter(UserRole.name == role_data["name"]).first()
        
        if existing_role:
            print(f"   ℹ️  Role '{role_data['name']}' already exists (ID: {existing_role.id})")
            role_ids[role_data["name"]] = existing_role.id
        else:
            # Create new role
            new_role = UserRole(
                name=role_data["name"],
                description=role_data["description"]
            )
            db.add(new_role)
            db.commit()
            db.refresh(new_role)
            print(f"   ✅ Created role '{role_data['name']}' (ID: {new_role.id})")
            role_ids[role_data["name"]] = new_role.id
    
    return role_ids


def seed_admin_user(db: Session, admin_role_id: int):
    """
    Seed default admin user.
    """
    print("\n👤 Seeding admin user...")
    
    admin_data = {
        "username": "admin",
        "email": "admin@ponderosacommerce.com",
        "password": "demo1234",  # Will be hashed
    }
    
    # Check if admin user already exists
    existing_user = db.query(User).filter(User.username == admin_data["username"]).first()
    
    if existing_user:
        print(f"   ℹ️  Admin user '{admin_data['username']}' already exists (ID: {existing_user.id})")
        print(f"   📧 Email: {existing_user.email}")
        return
    
    # Create admin user
    hashed_password = hash_password(admin_data["password"])
    
    new_user = User(
        username=admin_data["username"],
        email=admin_data["email"],
        password=hashed_password,
        role_id=admin_role_id,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print(f"   ✅ Created admin user '{admin_data['username']}' (ID: {new_user.id})")
    print(f"   📧 Email: {admin_data['email']}")
    print(f"   🔑 Password: {admin_data['password']}")


def seed_test_user(db: Session, user_role_id: int):
    """
    Seed test regular user.
    """
    print("\n👤 Seeding test user...")
    
    user_data = {
        "username": "user",
        "email": "user@ponderosacommerce.com",
        "password": "demo1234",  # Will be hashed
    }
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.username == user_data["username"]).first()
    
    if existing_user:
        print(f"   ℹ️  Test user '{user_data['username']}' already exists (ID: {existing_user.id})")
        print(f"   📧 Email: {existing_user.email}")
        return
    
    # Create test user
    hashed_password = hash_password(user_data["password"])
    
    new_user = User(
        username=user_data["username"],
        email=user_data["email"],
        password=hashed_password,
        role_id=user_role_id,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print(f"   ✅ Created test user '{user_data['username']}' (ID: {new_user.id})")
    print(f"   📧 Email: {user_data['email']}")
    print(f"   🔑 Password: {user_data['password']}")


def main():
    """Main seed function."""
    print("=" * 70)
    print("🌱 Authentication Seed Script")
    print("=" * 70)
    
    # Test database connection
    print("\n🔌 Testing database connection...")
    if not test_connection():
        print("\n❌ Failed to connect to database. Please check your DATABASE_URL in .env")
        sys.exit(1)
    
    print("✅ Database connection successful!")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Seed roles
        role_ids = seed_roles(db)
        
        # Seed admin user
        if "admin" in role_ids:
            seed_admin_user(db, role_ids["admin"])
        
        # Seed test user
        if "user" in role_ids:
            seed_test_user(db, role_ids["user"])
        
        print("\n" + "=" * 70)
        print("✅ Authentication seed completed successfully!")
        print("=" * 70)
        print("\n📝 Default Credentials:")
        print("   Admin - Username: admin, Password: demo1234")
        print("   User  - Username: user,  Password: demo1234")
        print("\n⚠️  Remember to change these passwords in production!")
        print("=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()


