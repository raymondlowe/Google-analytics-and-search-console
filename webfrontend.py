#!/usr/bin/env python3
"""
Main entry point for the GA4 & GSC Unified Web Dashboard
Usage: uv run webfrontend.py [options]
"""
import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add the repository root to Python path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

# Import the app from the backend
sys.path.insert(0, str(repo_root / "webapp" / "backend"))

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="GA4 & GSC Unified Web Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run webfrontend.py                    # Start with default settings
  uv run webfrontend.py --host 0.0.0.0    # Listen on all interfaces
  uv run webfrontend.py --port 9000       # Use custom port
  uv run webfrontend.py --debug            # Enable debug mode
  uv run webfrontend.py --config config/  # Use custom config directory
        """
    )
    
    parser.add_argument(
        "--host", 
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug mode with detailed logging"
    )
    
    parser.add_argument(
        "--config",
        default="config",
        help="Path to configuration directory (default: config)"
    )
    
    parser.add_argument(
        "--client-secrets",
        default="client_secrets.json",
        help="Path to Google client secrets file (default: client_secrets.json)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level (default: info)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Set environment variables for the app
    if args.debug:
        os.environ["DEBUG_MODE"] = "true"
        log_level = "debug"
    else:
        log_level = args.log_level
    
    os.environ["CLIENT_SECRETS_PATH"] = args.client_secrets
    os.environ["CONFIG_PATH"] = args.config
    
    print("Starting GA4 & GSC Unified Dashboard...")
    print(f"Dashboard will be available at: http://{args.host}:{args.port}")
    print(f"API documentation available at: http://{args.host}:{args.port}/docs")
    if args.debug:
        print("Debug mode: ENABLED")
    print(f"Log level: {log_level.upper()}")
    print(f"Client secrets: {args.client_secrets}")
    print(f"Config directory: {args.config}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Environment variables:")
    for k, v in os.environ.items():
        if k in ["DEBUG_MODE", "CLIENT_SECRETS_PATH", "CONFIG_PATH"]:
            print(f"  {k}: {v}")
    print("\nPress Ctrl+C to stop the server")
    
    # Change to the backend directory
    os.chdir(repo_root / "webapp" / "backend")
    print(f"Changed working directory to: {os.getcwd()}")
    print("Starting Uvicorn with access log enabled and debug logging...")
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=log_level,
        access_log=True
    )