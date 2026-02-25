"""
Subprocess-based Playwright automation
Runs Playwright in a separate process to avoid server context issues
"""

import subprocess
import json
import logging
import os
import sys
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def run_playwright_automation_script(purchase_records: List[Dict[str, Any]], headless: bool = True) -> Dict[str, Any]:
    """
    Run Playwright automation in a subprocess
    
    This avoids issues with Playwright hanging when run directly in the server context
    """
    try:
        # Get the directory of this file and backend root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(os.path.dirname(script_dir))  # Go up from app/services to backend
        automation_script = os.path.join(script_dir, "prepworx_automation_runner.py")
        
        # Prepare data
        data = {
            "purchase_records": purchase_records,
            "headless": headless
        }
        
        logger.info(f"Running Playwright automation in subprocess for {len(purchase_records)} records...")
        logger.info(f"Backend directory: {backend_dir}")
        logger.info(f"Script path: {automation_script}")
        
        # Prepare environment with PYTHONPATH set to backend directory
        env = os.environ.copy()
        pythonpath = env.get('PYTHONPATH', '')
        if pythonpath:
            env['PYTHONPATH'] = f"{backend_dir}:{pythonpath}"
        else:
            env['PYTHONPATH'] = backend_dir
        
        # Run in subprocess with timeout
        # Use Popen to capture both stdout and stderr separately, and stream logs in real-time
        process = subprocess.Popen(
            [sys.executable, automation_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=backend_dir,
            env=env,
            bufsize=1  # Line buffered
        )
        
        # Send input data
        # Increased timeout to 10 minutes (600 seconds) to match frontend timeout
        # Browser automation can take time, especially with multiple records
        try:
            stdout_data, stderr_data = process.communicate(input=json.dumps(data), timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("Selenium automation subprocess timed out after 10 minutes")
            process.kill()
            stdout_data, stderr_data = process.communicate()  # Get any partial output
            return {
                "success": False,
                "error": "Automation timed out",
                "processed": 0,
                "total": len(purchase_records)
            }
        
        # Log all stderr output (where Python logging goes) - ALWAYS log, not just on errors
        if stderr_data:
            logger.info("=== Subprocess Logs (STDERR) ===")
            for line in stderr_data.strip().split('\n'):
                if line.strip():
                    logger.info(f"[SUBPROCESS] {line}")
            logger.info("=== End Subprocess Logs ===")
        
        # Log stdout for debugging
        if stdout_data:
            logger.debug(f"Subprocess STDOUT: {stdout_data[:500]}")
        
        if process.returncode != 0:
            logger.error(f"Subprocess failed with return code {process.returncode}")
            return {
                "success": False,
                "error": f"Subprocess failed: {stderr_data[:500] if stderr_data else 'Unknown error'}",
                "processed": 0,
                "total": len(purchase_records)
            }
        
        # Parse JSON output from stdout
        try:
            output = json.loads(stdout_data)
            logger.info(f"Subprocess completed successfully")
            return output
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse subprocess output: {e}")
            logger.error(f"STDOUT: {stdout_data[:500]}")
            logger.error(f"STDERR: {stderr_data[:500]}")
            return {
                "success": False,
                "error": f"Failed to parse output: {str(e)}",
                "processed": 0,
                "total": len(purchase_records)
            }
    except Exception as e:
        logger.error(f"Error running Playwright subprocess: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "processed": 0,
            "total": len(purchase_records)
        }

