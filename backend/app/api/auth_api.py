"""
Authentication API endpoints with database integration.
Full authentication system with user signup, signin, role management,
password reset, and Google OAuth.
"""

import logging
import uuid
import secrets
import httpx
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.config.database import get_db
from app.models.database import User, UserRole, PasswordResetToken
from app.utils.password import hash_password, verify_password
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SignInRequest(BaseModel):
    """Sign in request with email and password"""
    email: str
    password: str


class SignUpRequest(BaseModel):
    """Sign up request with user details"""
    username: str
    email: EmailStr
    password: str
    
    @validator('username')
    def username_must_be_valid(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 100:
            raise ValueError('Username must be less than 100 characters')
        return v
    
    @validator('password')
    def password_must_be_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


class UserInfoResponse(BaseModel):
    """User information response"""
    id: int
    username: str
    email: str
    role: dict
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class SignInResponse(BaseModel):
    """Sign in response with user info and tokens"""
    status: int = 200
    message: str = ""
    data: dict


class ForgotPasswordRequest(BaseModel):
    """Forgot password request with email"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request with token and new password"""
    token: str
    new_password: str
    
    @validator('new_password')
    def password_must_be_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v


# ============================================================================
# TOKEN STORAGE (In-memory for now - use Redis in production)
# ============================================================================

ACTIVE_TOKENS = {}


def generate_token() -> str:
    """Generate a random UUID token."""
    return str(uuid.uuid4())


def create_user_token(user_id: int, username: str) -> tuple[str, str]:
    """
    Create access and refresh tokens for a user.
    
    Args:
        user_id: User ID
        username: Username
        
    Returns:
        Tuple of (access_token, refresh_token)
    """
    access_token = generate_token()
    refresh_token = generate_token()
    
    # Store tokens with expiry (1 hour for access, 7 days for refresh)
    ACTIVE_TOKENS[access_token] = {
        "user_id": user_id,
        "username": username,
        "type": "access",
        "expires": datetime.now() + timedelta(hours=1)
    }
    ACTIVE_TOKENS[refresh_token] = {
        "user_id": user_id,
        "username": username,
        "type": "refresh",
        "expires": datetime.now() + timedelta(days=7)
    }
    
    return access_token, refresh_token


def format_user_response(user: User) -> dict:
    """
    Format user object for API response.
    
    Args:
        user: User model instance
        
    Returns:
        Dictionary with user info (excluding password)
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user.username}",
        "roles": [{
            "id": user.role.id,
            "name": user.role.name,
            "label": user.role.name.capitalize()
        }],
        "permissions": [
            {"id": "1", "name": "dashboard", "label": "Dashboard"},
            {"id": "2", "name": "purchases", "label": "Purchases"},
            {"id": "3", "name": "retailers", "label": "Retailers"},
            {"id": "4", "name": "checkin", "label": "Check-in"},
        ] if user.role.name == "admin" else [
            {"id": "1", "name": "dashboard", "label": "Dashboard"},
            {"id": "2", "name": "purchases", "label": "Purchases"},
        ],
        "menu": [
            {
                "id": "1",
                "name": "Dashboard",
                "path": "/workbench",
                "component": "WorkbenchPage",
            },
        ],
    }


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post("/signup")
async def signup(request: SignUpRequest, db: Session = Depends(get_db)):
    """
    Sign up endpoint - Create a new user account.
    
    Creates a new user with 'user' role by default.
    Password is hashed using bcrypt before storage.
    """
    logger.info(f"Signup attempt for username: {request.username}")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        logger.warning(f"Username already exists: {request.username}")
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        logger.warning(f"Email already exists: {request.email}")
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )
    
    # Get 'user' role (default role for new signups)
    user_role = db.query(UserRole).filter(UserRole.name == "user").first()
    if not user_role:
        logger.error("User role not found in database")
        raise HTTPException(
            status_code=500,
            detail="User role not configured. Please run database seed script."
        )
    
    # Hash password
    hashed_password = hash_password(request.password)
    
    # Create new user
    new_user = User(
        username=request.username,
        email=request.email,
        password=hashed_password,
        role_id=user_role.id,
        is_active=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate tokens
    access_token, refresh_token = create_user_token(new_user.id, new_user.username)
    
    # Format user info for response
    user_info = format_user_response(new_user)
    
    logger.info(f"User {request.username} signed up successfully")
    
    return SignInResponse(
        status=200,
        message="Signup successful",
        data={
            "user": user_info,
            "accessToken": access_token,
            "refreshToken": refresh_token,
        }
    )


@router.post("/signin")
async def signin(request: SignInRequest, db: Session = Depends(get_db)):
    """
    Sign in endpoint - Authenticate user and return tokens.
    
    Accepts email for login.
    Returns user info and access/refresh tokens.
    """
    logger.info(f"Login attempt for email: {request.email}")
    
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user:
        logger.warning(f"User not found: {request.email}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        logger.warning(f"Inactive user tried to login: {request.email}")
        raise HTTPException(
            status_code=401,
            detail="Account is inactive. Please contact administrator."
        )
    
    # Verify password
    if not verify_password(request.password, user.password):
        logger.warning(f"Invalid password for user: {request.email}")
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token, refresh_token = create_user_token(user.id, user.username)
    
    # Format user info for response
    user_info = format_user_response(user)
    
    logger.info(f"User {request.email} logged in successfully")
    
    return SignInResponse(
        status=200,
        message="Login successful",
        data={
            "user": user_info,
            "accessToken": access_token,
            "refreshToken": refresh_token,
        }
    )


@router.get("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout endpoint - Invalidate the current access token.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        if token in ACTIVE_TOKENS:
            username = ACTIVE_TOKENS[token].get("username")
            del ACTIVE_TOKENS[token]
            logger.info(f"User {username} logged out")
            return {"status": 200, "message": "Logout successful"}
    
    return {"status": 200, "message": "Logout successful"}


@router.post("/refresh")
async def refresh_token(authorization: Optional[str] = Header(None)):
    """
    Refresh token endpoint - Get a new access token using refresh token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")
    
    refresh_token = authorization.replace("Bearer ", "")
    
    # Check if refresh token exists and is valid
    token_info = ACTIVE_TOKENS.get(refresh_token)
    if not token_info or token_info["type"] != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    if token_info["expires"] < datetime.now():
        del ACTIVE_TOKENS[refresh_token]
        raise HTTPException(status_code=401, detail="Refresh token expired")
    
    # Generate new access token
    user_id = token_info["user_id"]
    username = token_info["username"]
    new_access_token = generate_token()
    ACTIVE_TOKENS[new_access_token] = {
        "user_id": user_id,
        "username": username,
        "type": "access",
        "expires": datetime.now() + timedelta(hours=1)
    }
    
    logger.info(f"Token refreshed for user: {username}")
    
    return {
        "status": 200,
        "message": "Token refreshed",
        "data": {
            "accessToken": new_access_token,
            "refreshToken": refresh_token,
        }
    }


@router.get("/user/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Get user information by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_info = format_user_response(user)
    
    return {"status": 200, "data": user_info}


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset email.
    
    Sends an email with a password reset token if the user exists.
    Always returns success to prevent email enumeration.
    """
    logger.info(f"Password reset requested for email: {request.email}")
    
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    
    if user:
        # Check if user uses OAuth (no password to reset)
        if user.oauth_provider:
            logger.warning(f"Password reset requested for OAuth user: {request.email}")
            # Still return success to prevent enumeration
            return {
                "status": 200,
                "message": "If an account exists with this email, a password reset link will be sent."
            }
        
        # Generate a secure random token
        reset_token = secrets.token_urlsafe(32)
        
        # Create token expiry (1 hour from now)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).update({"used": True})
        
        # Create new reset token
        new_token = PasswordResetToken(
            user_id=user.id,
            token=reset_token,
            expires_at=expires_at
        )
        db.add(new_token)
        db.commit()
        
        # Send password reset email
        settings = get_settings()
        email_service = EmailService()
        
        try:
            email_sent = email_service.send_password_reset_email(
                to_email=user.email,
                username=user.username,
                reset_token=reset_token,
                frontend_url=settings.frontend_url
            )
            
            if email_sent:
                logger.info(f"Password reset email sent to {user.email}")
            else:
                logger.error(f"Failed to send password reset email to {user.email}")
        except Exception as e:
            logger.error(f"Error sending password reset email: {e}", exc_info=True)
    else:
        logger.info(f"Password reset requested for non-existent email: {request.email}")
    
    # Always return success to prevent email enumeration
    return {
        "status": 200,
        "message": "If an account exists with this email, a password reset link will be sent."
    }


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using a valid reset token.
    
    Validates the token and updates the user's password.
    """
    logger.info("Password reset attempt with token")
    
    # Find the token
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check if token has been used
    if token_record.used:
        raise HTTPException(status_code=400, detail="This reset token has already been used")
    
    # Check if token has expired
    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset token has expired")
    
    # Get the user
    user = db.query(User).filter(User.id == token_record.user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Hash the new password
    hashed_password = hash_password(request.new_password)
    
    # Update user password
    user.password = hashed_password
    user.updated_at = datetime.utcnow()
    
    # Mark token as used
    token_record.used = True
    
    db.commit()
    
    logger.info(f"Password reset successful for user: {user.email}")
    
    return {
        "status": 200,
        "message": "Password has been reset successfully. You can now login with your new password."
    }


@router.get("/google/login")
async def google_login():
    """
    Initiate Google OAuth login flow.
    
    Redirects user to Google's OAuth consent page.
    """
    settings = get_settings()
    
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured. Please set GOOGLE_OAUTH_CLIENT_ID."
        )
    
    # Build Google OAuth URL
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.google_oauth_client_id}&"
        f"redirect_uri={settings.google_oauth_redirect_uri}&"
        f"response_type=code&"
        f"scope=openid email profile&"
        f"access_type=offline&"
        f"prompt=consent"
    )
    
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback.
    
    Exchanges authorization code for tokens and creates/logs in user.
    """
    settings = get_settings()
    
    try:
        # Exchange authorization code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            # Get user info from Google
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_info_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info from Google")
            
            google_user = user_info_response.json()
            google_id = google_user.get("id")
            email = google_user.get("email")
            name = google_user.get("name", email.split("@")[0])
            
            # Check if user exists by Google ID
            user = db.query(User).filter(User.google_id == google_id).first()
            
            if not user:
                # Check if user exists by email
                user = db.query(User).filter(User.email == email).first()
                
                if user:
                    # Link Google account to existing user
                    user.google_id = google_id
                    user.oauth_provider = "google"
                else:
                    # Create new user
                    user_role = db.query(UserRole).filter(UserRole.name == "user").first()
                    if not user_role:
                        raise HTTPException(
                            status_code=500,
                            detail="User role not configured"
                        )
                    
                    user = User(
                        username=name,
                        email=email,
                        google_id=google_id,
                        oauth_provider="google",
                        password=None,  # No password for OAuth users
                        role_id=user_role.id,
                        is_active=True
                    )
                    db.add(user)
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
            # Generate tokens
            access_token_jwt, refresh_token_jwt = create_user_token(user.id, user.username)
            
            # Format user info for response
            user_info = format_user_response(user)
            
            logger.info(f"User {email} logged in via Google OAuth")
            
            # Redirect to frontend with tokens
            redirect_url = (
                f"{settings.frontend_url}/auth/callback?"
                f"accessToken={access_token_jwt}&"
                f"refreshToken={refresh_token_jwt}"
            )
            
            return RedirectResponse(url=redirect_url)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Google OAuth callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed")
