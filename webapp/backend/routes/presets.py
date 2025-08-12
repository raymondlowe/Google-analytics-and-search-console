"""
Preset query routes
"""
from fastapi import APIRouter, HTTPException
import json
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

from core.query_models import PresetQuery, QueryRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to presets directory
PRESETS_DIR = os.path.join(Path(__file__).parent.parent.parent, "presets")


def load_preset_file(filename: str) -> PresetQuery:
    """Load a preset from JSON file"""
    filepath = os.path.join(PRESETS_DIR, filename)
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return PresetQuery(**data)
    except Exception as e:
        logger.error(f"Error loading preset {filename}: {e}")
        raise


def save_preset_file(preset: PresetQuery) -> None:
    """Save a preset to JSON file"""
    os.makedirs(PRESETS_DIR, exist_ok=True)
    filepath = os.path.join(PRESETS_DIR, f"{preset.id}.json")
    try:
        with open(filepath, 'w') as f:
            json.dump(preset.dict(), f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving preset {preset.id}: {e}")
        raise


def list_preset_files() -> List[str]:
    """List all preset JSON files"""
    if not os.path.exists(PRESETS_DIR):
        return []
    
    return [f for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]


@router.get("/presets", response_model=List[PresetQuery])
async def get_presets():
    """Get all available preset queries"""
    presets = []
    
    for filename in list_preset_files():
        try:
            preset = load_preset_file(filename)
            presets.append(preset)
        except Exception as e:
            logger.warning(f"Skipping invalid preset file {filename}: {e}")
    
    # If no presets exist, return default ones
    if not presets:
        presets = get_default_presets()
        # Save default presets
        for preset in presets:
            try:
                save_preset_file(preset)
            except Exception as e:
                logger.warning(f"Could not save default preset {preset.id}: {e}")
    
    return presets


@router.get("/presets/{preset_id}", response_model=PresetQuery)
async def get_preset(preset_id: str):
    """Get a specific preset query"""
    filename = f"{preset_id}.json"
    
    if filename not in list_preset_files():
        raise HTTPException(status_code=404, detail="Preset not found")
    
    try:
        return load_preset_file(filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading preset: {e}")


@router.post("/presets", response_model=PresetQuery)
async def create_preset(preset: PresetQuery):
    """Create a new preset query"""
    # Check if preset already exists
    filename = f"{preset.id}.json"
    if filename in list_preset_files():
        raise HTTPException(status_code=409, detail="Preset with this ID already exists")
    
    try:
        save_preset_file(preset)
        return preset
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving preset: {e}")


@router.put("/presets/{preset_id}", response_model=PresetQuery)
async def update_preset(preset_id: str, preset: PresetQuery):
    """Update an existing preset query"""
    filename = f"{preset_id}.json"
    
    if filename not in list_preset_files():
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Ensure the ID matches
    preset.id = preset_id
    
    try:
        save_preset_file(preset)
        return preset
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating preset: {e}")


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    """Delete a preset query"""
    filename = f"{preset_id}.json"
    filepath = os.path.join(PRESETS_DIR, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Preset not found")
    
    try:
        os.remove(filepath)
        return {"message": "Preset deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting preset: {e}")


def get_default_presets() -> List[PresetQuery]:
    """Get default preset queries"""
    from datetime import date, timedelta
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    return [
        PresetQuery(
            id="traffic_vs_revenue",
            name="Traffic vs Revenue Analysis",
            description="Compare page views and ad revenue across all GA4 properties",
            category="revenue",
            query=QueryRequest(
                start_date=week_ago,
                end_date=today,
                sources=["ga4"],
                dimensions=["pagePath", "hostname"],
                metrics=["screenPageViews", "totalAdRevenue", "sessions"],
                sort=[{"field": "totalAdRevenue", "order": "desc"}],
                limit=100
            )
        ),
        PresetQuery(
            id="high_impressions_low_position",
            name="High Impressions, Low Position Pages",
            description="Find GSC pages with high impressions but poor ranking positions",
            category="seo",
            query=QueryRequest(
                start_date=week_ago,
                end_date=today,
                sources=["gsc"],
                dimensions=["page", "query"],
                metrics=["impressions", "position", "clicks", "ctr"],
                sort=[{"field": "impressions", "order": "desc"}],
                limit=100
            )
        ),
        PresetQuery(
            id="multi_source_overview",
            name="Multi-Source Overview",
            description="Combined GA4 and GSC data for comprehensive site analysis",
            category="overview",
            query=QueryRequest(
                start_date=week_ago,
                end_date=today,
                sources=["ga4", "gsc"],
                dimensions=["pagePath", "page"],
                metrics=["screenPageViews", "sessions", "impressions", "clicks"],
                sort=[{"field": "screenPageViews", "order": "desc"}],
                limit=50
            )
        ),
        PresetQuery(
            id="top_content_by_device",
            name="Top Content by Device",
            description="Analyze content performance across different device types",
            category="content",
            query=QueryRequest(
                start_date=week_ago,
                end_date=today,
                sources=["ga4"],
                dimensions=["pagePath", "deviceCategory"],
                metrics=["screenPageViews", "sessions", "userEngagementDuration"],
                sort=[{"field": "screenPageViews", "order": "desc"}],
                limit=100
            )
        )
    ]