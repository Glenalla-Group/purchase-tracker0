"""
FastAPI application entry point.
"""

# Fix Windows console encoding for emoji support - MUST BE FIRST!
import sys
import os
if sys.platform == 'win32':
    # Force UTF-8 encoding for stdout/stderr on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    # Set environment variables for subprocesses
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, __build_date__
from app.api.auth_api import router as auth_router
from app.api.admin_api import router as admin_router
from app.api.purchase_tracker_api import router as purchase_tracker_router
from app.api.retailers_api import router as retailers_router
from app.api.checkin_api import router as checkin_router
from app.api.retailer_orders_api import router as retailer_orders_router
from app.api.pto_api import router as pto_router
from app.api.holidays_api import router as holidays_router
from app.api.tasks_api import router as tasks_router
from app.api import webhook
from app.config import get_settings

# Configure logging with UTF-8 support
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')  # Explicit UTF-8 for file
    ]
)

# Suppress verbose Google API logs
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("=" * 70)
    logger.info("Starting Purchase Tracker Backend...")
    settings = get_settings()
    logger.info(f"Environment: {settings.environment.capitalize()}")
    logger.info(f"Version: {__version__}")
    logger.info("=" * 70)
    
    # Test database connection
    from app.config.database import test_connection
    test_connection()
    
    # Test Gmail authentication
    logger.info("")
    logger.info("Verifying Gmail API Authentication...")
    try:
        from app.services.gmail_service import GmailService
        gmail_service = GmailService()
        
        # Test the connection with an actual API call
        if gmail_service.test_connection():
            logger.info("✅ Gmail authentication verified successfully")
        else:
            logger.error("❌ Gmail authentication test failed")
            logger.error("   The application will start, but Gmail features may not work")
    except FileNotFoundError as e:
        logger.error("❌ Gmail authentication failed - Credentials not found")
        logger.error(f"   {e}")
        logger.error("   Run: python authenticate.py")
    except Exception as e:
        logger.error("❌ Gmail authentication failed")
        logger.error(f"   Error: {e}")
        logger.error("   The application will start, but Gmail features may not work")
    
    # Start background scheduler for periodic tasks
    # logger.info("Starting background scheduler...")
    try:
        # from app.services.background_scheduler import start_scheduler
        # start_scheduler()
        logger.info("")
    except Exception as e:
        logger.error(f"❌ Failed to start background scheduler: {e}")
        logger.error("   Periodic email processing will not be available")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ Application startup complete")
    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Purchase Tracker Backend...")
    
    # Stop background scheduler
    try:
        from app.services.background_scheduler import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.error(f"Error stopping background scheduler: {e}")


# Create FastAPI application
app = FastAPI(
    title="Purchase Tracker Backend",
    description="Backend service for monitoring Gmail inbox and extracting purchase information",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers based on feature flags
# Get settings for feature flags
settings = get_settings()

# Auth API (always enabled - required for frontend login)
app.include_router(auth_router, tags=["Authentication"])
logger.info("✅ Authentication API enabled")

# Admin API (always enabled - required for user management)
app.include_router(admin_router, tags=["Admin"])
logger.info("✅ Admin API enabled")

# Get settings for feature flags
settings = get_settings()

# Purchase Tracker API (main business logic)
if settings.enable_purchase_tracker_api:
    app.include_router(purchase_tracker_router, tags=["Purchase Tracker"])
    logger.info("✅ Purchase Tracker API enabled")
else:
    logger.info("⚠️  Purchase Tracker API disabled")

# Retailers API
if settings.enable_retailers_api:
    app.include_router(retailers_router, tags=["Retailers"])
    logger.info("✅ Retailers API enabled")
else:
    logger.info("⚠️  Retailers API disabled (set ENABLE_RETAILERS_API=true to enable)")

# Checkin API
if settings.enable_checkin_api:
    app.include_router(checkin_router, tags=["Checkin"])
    logger.info("✅ Checkin API enabled")
else:
    logger.info("⚠️  Checkin API disabled (set ENABLE_CHECKIN_API=true to enable)")

# PTO API
if settings.enable_pto_api:
    app.include_router(pto_router, tags=["PTO"])
    logger.info("✅ PTO API enabled")
else:
    logger.info("⚠️  PTO API disabled (set ENABLE_PTO_API=true to enable)")

# Holidays API
if settings.enable_holidays_api:
    app.include_router(holidays_router, tags=["Holidays"])
    logger.info("✅ Holidays API enabled")
else:
    logger.info("⚠️  Holidays API disabled (set ENABLE_HOLIDAYS_API=true to enable)")

# Tasks API
if settings.enable_tasks_api:
    app.include_router(tasks_router, tags=["Tasks"])
    logger.info("✅ Tasks API enabled")
else:
    logger.info("⚠️  Tasks API disabled (set ENABLE_TASKS_API=true to enable)")

# Retailer Orders API (process order confirmation emails)
if settings.enable_retailer_orders_api:
    app.include_router(retailer_orders_router, tags=["Retailer Orders"])
    logger.info("✅ Retailer Orders API enabled")
else:
    logger.info("⚠️  Retailer Orders API disabled (set ENABLE_RETAILER_ORDERS_API=true to enable)")

# Gmail Watch Webhook (email notifications)
if settings.enable_gmail_watch:
    app.include_router(webhook.router, prefix="/api", tags=["Webhook"])
    logger.info("✅ Gmail Watch enabled")
else:
    logger.info("⚠️  Gmail Watch disabled")


# Health check endpoint
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - Health check"""
    return {
        "status": "ok",
        "message": "Purchase Tracker Backend is running",
        "version": __version__,
        "build_date": __build_date__
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": __version__,
        "build_date": __build_date__
    }


@app.get("/health/gmail", tags=["Health"])
async def gmail_health_check():
    """Gmail authentication health check endpoint"""
    try:
        from app.services.gmail_service import GmailService
        gmail_service = GmailService()
        
        # Test the connection
        if gmail_service.test_connection():
            # Get profile info
            profile = gmail_service.service.users().getProfile(userId='me').execute()
            return {
                "status": "authenticated",
                "email": profile.get('emailAddress', 'Unknown'),
                "messages_total": profile.get('messagesTotal', 0),
                "threads_total": profile.get('threadsTotal', 0)
            }
        else:
            return {
                "status": "error",
                "message": "Gmail API connection test failed"
            }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "message": "Credentials file not found",
            "details": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Gmail authentication failed",
            "details": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )
