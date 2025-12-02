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
from app.api.purchase_tracker_api import router as purchase_tracker_router
from app.api.retailers_api import router as retailers_router
from app.api.checkin_api import router as checkin_router
from app.api.retailer_orders_api import router as retailer_orders_router
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
    logger.info("Starting Purchase Tracker Backend...")
    settings = get_settings()
    logger.info(f"Environment: {'Development' if settings.debug else 'Production'}")
    logger.info(f"Version: {__version__}")
    
    # Test database connection
    from app.config.database import test_connection
    test_connection()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Purchase Tracker Backend...")


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
import os

# Auth API (always enabled - required for frontend login)
app.include_router(auth_router, tags=["Authentication"])
logger.info("✅ Authentication API enabled")

# Purchase Tracker API (main business logic)
if os.getenv('ENABLE_PURCHASE_TRACKER_API', 'true').lower() == 'true':
    app.include_router(purchase_tracker_router, tags=["Purchase Tracker"])
    logger.info("✅ Purchase Tracker API enabled")
else:
    logger.info("⚠️  Purchase Tracker API disabled")

# Retailers API
if os.getenv('ENABLE_RETAILERS_API', 'true').lower() == 'true':
    app.include_router(retailers_router, tags=["Retailers"])
    logger.info("✅ Retailers API enabled")
else:
    logger.info("⚠️  Retailers API disabled (set ENABLE_RETAILERS_API=true to enable)")

# Checkin API
if os.getenv('ENABLE_CHECKIN_API', 'true').lower() == 'true':
    app.include_router(checkin_router, tags=["Checkin"])
    logger.info("✅ Checkin API enabled")
else:
    logger.info("⚠️  Checkin API disabled (set ENABLE_CHECKIN_API=true to enable)")

# Retailer Orders API (process order confirmation emails)
if os.getenv('ENABLE_RETAILER_ORDERS_API', 'true').lower() == 'true':
    app.include_router(retailer_orders_router, tags=["Retailer Orders"])
    logger.info("✅ Retailer Orders API enabled")
else:
    logger.info("⚠️  Retailer Orders API disabled (set ENABLE_RETAILER_ORDERS_API=true to enable)")

# Gmail Watch Webhook (email notifications)
if os.getenv('ENABLE_GMAIL_WATCH', 'true').lower() == 'true':
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


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
