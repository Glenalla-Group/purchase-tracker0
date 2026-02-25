"""
Admin API endpoints for user management.
Admin-only endpoints for managing user accounts, roles, and permissions.
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config.database import get_db
from app.models.database import User, UserRole
from app.utils.password import hash_password
from app.utils.auth_dependencies import authenticate_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class UserResponse(BaseModel):
    """User response model"""
    id: int
    username: str
    email: str
    role_id: int
    role_name: str
    is_active: bool
    oauth_provider: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UpdateUserRoleRequest(BaseModel):
    """Request to update user role"""
    role_id: int


class UpdateUserStatusRequest(BaseModel):
    """Request to update user active status"""
    is_active: bool


class CreateUserRequest(BaseModel):
    """Request to create a new user"""
    username: str
    email: EmailStr
    password: str
    role_id: int
    is_active: bool = True


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_user_for_admin(user: User) -> dict:
    """Format user object for admin response"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else "unknown",
        "is_active": user.is_active,
        "oauth_provider": user.oauth_provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    List all users with optional filtering.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} listing users")
    
    query = db.query(User)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    if role_id is not None:
        query = query.filter(User.role_id == role_id)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    return {
        "status": 200,
        "data": {
            "users": [format_user_for_admin(user) for user in users],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific user.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} retrieving user {user_id}")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "status": 200,
        "data": format_user_for_admin(user)
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UpdateUserRoleRequest,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Update a user's role.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} updating role for user {user_id}")
    
    # Get the user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify the role exists
    role = db.query(UserRole).filter(UserRole.id == request.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent admin from changing their own role
    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot change your own role"
        )
    
    # Update the role
    user.role_id = request.role_id
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"User {user_id} role updated to {role.name}")
    
    return {
        "status": 200,
        "message": "User role updated successfully",
        "data": format_user_for_admin(user)
    }


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Activate or deactivate a user account.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} updating status for user {user_id}")
    
    # Get the user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deactivating themselves
    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot change your own status"
        )
    
    # Update the status
    user.is_active = request.is_active
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    status_text = "activated" if request.is_active else "deactivated"
    logger.info(f"User {user_id} {status_text}")
    
    return {
        "status": 200,
        "message": f"User {status_text} successfully",
        "data": format_user_for_admin(user)
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a user account permanently.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} deleting user {user_id}")
    
    # Get the user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if user.id == current_user["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    # Delete the user
    username = user.username
    db.delete(user)
    db.commit()
    
    logger.info(f"User {user_id} ({username}) deleted")
    
    return {
        "status": 200,
        "message": "User deleted successfully"
    }


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new user account.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} creating new user")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )
    
    # Verify the role exists
    role = db.query(UserRole).filter(UserRole.id == request.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create new user
    new_user = User(
        username=request.username,
        email=request.email,
        password=hashed_password,
        role_id=request.role_id,
        is_active=request.is_active,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"New user created: {new_user.username} (ID: {new_user.id})")
    
    return {
        "status": 201,
        "message": "User created successfully",
        "data": format_user_for_admin(new_user)
    }


@router.get("/roles")
async def list_roles(
    current_user: dict = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    List all available roles.
    Admin only endpoint.
    """
    logger.info(f"Admin {current_user['username']} listing roles")
    
    roles = db.query(UserRole).all()
    
    return {
        "status": 200,
        "data": [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
            }
            for role in roles
        ]
    }

