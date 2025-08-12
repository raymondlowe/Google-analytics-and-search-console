#!/usr/bin/env python3
"""
Main entry point for the GA4 & GSC Unified Web Dashboard
Usage: uv run webfrontend.py
"""
import os
import sys
import uvicorn
from pathlib import Path

# Add the repository root to Python path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

# Import the app from the backend
sys.path.insert(0, str(repo_root / "webapp" / "backend"))

if __name__ == "__main__":
    print("Starting GA4 & GSC Unified Dashboard...")
    print("Dashboard will be available at: http://127.0.0.1:8000")
    print("API documentation available at: http://127.0.0.1:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    
    # Change to the backend directory
    os.chdir(repo_root / "webapp" / "backend")
    
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # Disable reload to avoid issues
        log_level="info"
    )