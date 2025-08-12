"""
Metadata routes for dimensions, metrics, and properties
"""
from fastapi import APIRouter, HTTPException
import logging
from typing import Dict, List, Any

from data_providers import DataProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter()
data_registry = DataProviderRegistry()


@router.get("/meta/sources")
async def get_sources():
    """Get available data sources"""
    return {
        "sources": [
            {"id": "ga4", "name": "Google Analytics 4", "description": "Website analytics data"},
            {"id": "gsc", "name": "Google Search Console", "description": "Search performance data"}
        ]
    }


@router.get("/meta/dimensions")
async def get_dimensions(source: str = None):
    """Get available dimensions for all sources or a specific source"""
    try:
        if source:
            provider = data_registry.get_provider(source)
            if not provider:
                raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
            
            metadata = await provider.get_metadata()
            return {source: metadata["dimensions"]}
        else:
            all_metadata = await data_registry.get_all_metadata()
            return {
                source: meta["dimensions"] 
                for source, meta in all_metadata.items()
            }
    except Exception as e:
        logger.error(f"Error getting dimensions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta/metrics")
async def get_metrics(source: str = None):
    """Get available metrics for all sources or a specific source"""
    try:
        if source:
            provider = data_registry.get_provider(source)
            if not provider:
                raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
            
            metadata = await provider.get_metadata()
            return {source: metadata["metrics"]}
        else:
            all_metadata = await data_registry.get_all_metadata()
            return {
                source: meta["metrics"] 
                for source, meta in all_metadata.items()
            }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta/properties")
async def get_properties(source: str = None, auth_identifier: str = ""):
    """Get available properties/domains for sources"""
    try:
        result = {}
        
        if source:
            provider = data_registry.get_provider(source)
            if not provider:
                raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
            
            if source == "ga4":
                properties = await provider.list_properties(auth_identifier)
                result[source] = properties
            elif source == "gsc":
                domains = await provider.list_domains(auth_identifier)
                result[source] = domains
        else:
            # Get properties for all sources
            for src in data_registry.list_sources():
                provider = data_registry.get_provider(src)
                if src == "ga4":
                    properties = await provider.list_properties(auth_identifier)
                    result[src] = properties
                elif src == "gsc":
                    domains = await provider.list_domains(auth_identifier)
                    result[src] = domains
        
        return result
    except Exception as e:
        logger.error(f"Error getting properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta/all")
async def get_all_metadata(auth_identifier: str = ""):
    """Get all metadata in one call"""
    try:
        # Get dimensions and metrics
        all_metadata = await data_registry.get_all_metadata()
        
        # Get properties for all sources
        properties = {}
        for src in data_registry.list_sources():
            provider = data_registry.get_provider(src)
            if src == "ga4":
                properties[src] = await provider.list_properties(auth_identifier)
            elif src == "gsc":
                properties[src] = await provider.list_domains(auth_identifier)
        
        return {
            "sources": [
                {"id": "ga4", "name": "Google Analytics 4", "description": "Website analytics data"},
                {"id": "gsc", "name": "Google Search Console", "description": "Search performance data"}
            ],
            "dimensions": {src: meta["dimensions"] for src, meta in all_metadata.items()},
            "metrics": {src: meta["metrics"] for src, meta in all_metadata.items()},
            "properties": properties
        }
    except Exception as e:
        logger.error(f"Error getting all metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))