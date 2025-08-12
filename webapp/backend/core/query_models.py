"""
Query models for the unified web dashboard
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import date


class QueryRequest(BaseModel):
    """Unified query request model for GA4 and GSC data"""
    start_date: date
    end_date: date
    sources: List[str]  # ["ga4", "gsc"] or subset
    properties: Optional[List[str]] = None  # Property IDs for GA4, domain names for GSC. None = all
    dimensions: List[str]
    metrics: List[str]
    filters: Optional[Dict[str, Any]] = None
    sort: Optional[List[Dict[str, str]]] = None  # [{"field": "metric_name", "order": "desc"}]
    limit: Optional[int] = None
    auth_identifier: str = ""
    debug: bool = False


class QueryResponse(BaseModel):
    """Response model for query results"""
    query_id: str
    status: str  # "running", "completed", "failed"
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    row_count: Optional[int] = None
    cache_hit: bool = False
    execution_time_ms: Optional[float] = None
    sources_queried: List[str] = []


class PresetQuery(BaseModel):
    """Model for preset queries"""
    id: str
    name: str
    description: str
    query: QueryRequest
    category: str = "general"


class MetaInfo(BaseModel):
    """Metadata about available dimensions and metrics"""
    source: str  # "ga4" or "gsc"
    dimensions: List[Dict[str, str]]  # [{"id": "pagePath", "name": "Page Path", "type": "string"}]
    metrics: List[Dict[str, str]]  # [{"id": "screenPageViews", "name": "Screen Page Views", "type": "integer"}]