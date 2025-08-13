"""
FastAPI web application for unified GA4 and GSC dashboard
"""
import os
import sys
from pathlib import Path

# Add repository root to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import uuid
import shutil
from typing import Dict, Any
import asyncio

from core.query_models import QueryRequest, QueryResponse, MetaInfo
from core.cache import UnifiedCache
from data_providers import DataProviderRegistry
from routes import query, presets, meta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="GA4 & GSC Unified Dashboard",
    description="Unified web dashboard for Google Analytics 4 and Search Console data",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core components
cache = UnifiedCache()
data_registry = DataProviderRegistry()

# Store for active queries
active_queries: Dict[str, Dict[str, Any]] = {}

# Mount static files
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")

# Include routers
app.include_router(query.router, prefix="/api", tags=["queries"])
app.include_router(presets.router, prefix="/api", tags=["presets"])
app.include_router(meta.router, prefix="/api", tags=["metadata"])

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main dashboard page"""
    try:
        frontend_path = Path(__file__).parent.parent / "frontend"
        with open(frontend_path / "index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GA4 & GSC Dashboard</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .error { background: #ffebee; padding: 20px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>GA4 & GSC Unified Dashboard</h1>
                <div class="error">
                    <h3>Frontend Not Found</h3>
                    <p>The frontend files are not yet available. The API is running at <a href="/docs">/docs</a></p>
                </div>
            </div>
        </body>
        </html>
        """)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "cache_stats": cache.get_cache_stats()
    }

@app.post("/api/upload-credentials")
async def upload_credentials(file: UploadFile = File(...)):
    """Upload Google credentials file"""
    try:
        # Validate file type
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="File must be a JSON file")
        
        # Read and validate content
        content = await file.read()
        try:
            import json
            creds_data = json.loads(content)
            
            # Basic validation for Google credentials
            if not ('installed' in creds_data or 'web' in creds_data):
                raise HTTPException(status_code=400, detail="Invalid Google credentials format")
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")
        
        # Save to the repository root (where other files expect it)
        target_path = repo_root / "client_secrets.json"
        
        # Write the file
        with open(target_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Credentials uploaded successfully to {target_path}")
        
        return {
            "status": "success",
            "message": "Credentials uploaded successfully",
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading credentials: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading credentials: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    logger.info("Starting GA4 & GSC Unified Dashboard")
    logger.info("Cache initialized")
    logger.info("Data providers registered: %s", data_registry.list_sources())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down GA4 & GSC Unified Dashboard")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        log_level="info"
    )