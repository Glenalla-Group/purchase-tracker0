#!/usr/bin/env python3
"""
Standalone script to run Playwright automation
This runs in a separate process to avoid server context issues
"""

import json
import sys
import os
import logging

# Add backend directory to Python path so we can import app module
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Change to backend directory so pydantic-settings can find .env files
os.chdir(backend_dir)

from app.services.prepworx_automation import process_inbound_creation

# Configure logging to output to stderr (so it's captured separately from JSON stdout)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Send logs to stderr so they don't interfere with JSON stdout
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # Read JSON data from stdin
        data = json.load(sys.stdin)
        purchase_records = data.get("purchase_records", [])
        headless = data.get("headless", True)
        
        logger.info(f"Starting automation for {len(purchase_records)} records (headless={headless})")
        
        # Run automation
        result = process_inbound_creation(purchase_records, headless=headless)
        
        # Output JSON result
        print(json.dumps(result))
        sys.exit(0 if result.get("success", False) else 1)
        
    except Exception as e:
        logger.error(f"Error in automation runner: {e}", exc_info=True)
        error_result = {
            "success": False,
            "error": str(e),
            "total_records": 0,
            "processed_by_address": {},
            "errors": [str(e)]
        }
        print(json.dumps(error_result))
        sys.exit(1)

