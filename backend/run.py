"""
Application runner script.

Usage:
    python run.py           # Run with default settings
    python run.py --no-reload  # Disable auto-reload (more stable)
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
    # Set environment variable for all subprocesses (including uvicorn workers)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    
    # Parse command line arguments
    port = settings.port
    reload = settings.debug
    
    args = sys.argv[1:]
    for arg in args:
        if arg == "--no-reload":
            reload = False
            print("Auto-reload disabled (more stable for processing)")
        elif arg.startswith("--"):
            print(f"Unknown option: {arg}")
        else:
            try:
                port = int(arg)
                print(f"Using port {port}")
            except ValueError:
                print(f"Invalid port: {arg}")
    
    print(f"Starting server on {settings.host}:{port}")
    print(f"Auto-reload: {reload}")
    print(f"Access docs at: http://localhost:{port}/docs")
    print()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=port,
        reload=reload,
        log_level=settings.log_level.lower()
    )
