"""
Authentication dependencies for FastAPI endpoints.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.database import User

logger = logging.getLogger(__name__)

# Import ACTIVE_TOKENS from auth_api
# This is a shared state for token management
from app.api.auth_api import ACTIVE_TOKENS


def authenticate_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> dict:
    """
    Authenticate user based on Bearer token.
    Returns user information including role.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    
    # Check if token exists and is valid
    token_info = ACTIVE_TOKENS.get(token)
    if not token_info:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Check if token is expired
    from datetime import datetime
    if token_info["expires"] < datetime.now():
        del ACTIVE_TOKENS[token]
        raise HTTPException(status_code=401, detail="Token expired")
    
    # Get full user info from database
    user_id = token_info["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
    }


def authenticate_admin(
    current_user: dict = Depends(authenticate_user)
) -> dict:
    """
    Authenticate admin user.
    Requires user to have 'admin' role.
    """
    if current_user.get("role_name") != "admin":
        logger.warning(
            f"User {current_user.get('username')} attempted to access admin endpoint"
        )
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    
    return current_user


