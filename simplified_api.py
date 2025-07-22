#!/usr/bin/env python3
"""
Simplified REST API for Google Analytics 4 and Search Console Data
Designed for AI/MCP access with minimal required parameters and clear separation.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import uvicorn

# Import our existing modules
import GA4query3
import NewDownloads

app = FastAPI(
    title="GA4 & GSC Simplified API",
    description="Simplified REST API for AI/MCP access to Google Analytics 4 and Search Console data",
    version="1.0.0"
)

# Pydantic models for request/response
class DateRange(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")

class GA4QueryRequest(BaseModel):
    date_range: DateRange
    auth_identifier: str = Field(..., description="Authentication identifier for OAuth tokens")
    property_id: Optional[str] = Field(None, description="GA4 Property ID (leave empty for all properties)")
    dimensions: str = Field("pagePath", description="Comma-separated dimensions")
    metrics: str = Field("screenPageViews", description="Comma-separated metrics")
    filter_expression: Optional[str] = Field(None, description="Filter expression")
    debug: bool = Field(False, description="Enable debug mode")

class GSCQueryRequest(BaseModel):
    date_range: DateRange
    domain: Optional[str] = Field(None, description="Single domain to query (e.g., example.com)")
    auth_identifier: Optional[str] = Field("", description="Authentication identifier for OAuth tokens")
    search_type: str = Field("web", description="Search type: web, image, or video")
    dimensions: str = Field("page", description="Comma-separated dimensions")
    debug: bool = Field(False, description="Enable debug mode")

class UnifiedQueryRequest(BaseModel):
    date_range: DateRange
    domain: Optional[str] = Field(None, description="Single domain to query")
    auth_identifier: str = Field(..., description="Authentication identifier for OAuth tokens") 
    data_sources: List[str] = Field(["ga4", "gsc"], description="Data sources to query: ga4, gsc, or both")
    ga4_property_id: Optional[str] = Field(None, description="GA4 Property ID (auto-detect if empty)")
    debug: bool = Field(False, description="Enable debug mode")

class ApiResponse(BaseModel):
    status: str
    message: str
    data: List[Dict[str, Any]]
    row_count: int
    source: str

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    details: Optional[str] = None

# Helper functions
def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate date range format and logic"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        return start <= end
    except ValueError:
        return False

def get_default_date_range() -> Dict[str, str]:
    """Get default date range (last 30 days)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
    }

# Simplified endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "GA4 & GSC Simplified API",
        "version": "1.0.0",
        "endpoints": {
            "ga4": "/ga4/query - Query Google Analytics 4 data",
            "gsc": "/gsc/query - Query Google Search Console data", 
            "unified": "/query - Query both GA4 and GSC data",
            "ga4_properties": "/ga4/properties - List GA4 properties",
            "gsc_domains": "/gsc/domains - List GSC domains"
        },
        "docs": "/docs"
    }

@app.post("/ga4/query", response_model=ApiResponse)
async def query_ga4(request: GA4QueryRequest):
    """
    Query Google Analytics 4 data with simplified parameters.
    
    Focus on core metrics: pageviews and totaladrevenue
    """
    if not validate_date_range(request.date_range.start_date, request.date_range.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")
    
    try:
        if request.property_id:
            # Single property
            df = GA4query3.produce_report(
                start_date=request.date_range.start_date,
                end_date=request.date_range.end_date,
                property_id=request.property_id,
                property_name="API_Property",
                account=request.auth_identifier,
                filter_expression=request.filter_expression,
                dimensions=request.dimensions,
                metrics=request.metrics,
                debug=request.debug
            )
        else:
            # All properties
            properties_df = GA4query3.list_properties(request.auth_identifier, debug=request.debug)
            if properties_df is None or properties_df.empty:
                raise HTTPException(status_code=404, detail="No GA4 properties found")
            
            combined_df = pd.DataFrame()
            for _, row in properties_df.iterrows():
                prop_id = str(row['property_id'])
                prop_name = str(row['property_name'])
                
                df_property = GA4query3.produce_report(
                    start_date=request.date_range.start_date,
                    end_date=request.date_range.end_date,
                    property_id=prop_id,
                    property_name=prop_name,
                    account=request.auth_identifier,
                    filter_expression=request.filter_expression,
                    dimensions=request.dimensions,
                    metrics=request.metrics,
                    debug=request.debug
                )
                
                if df_property is not None:
                    df_property['property_id'] = prop_id
                    df_property['property_name'] = prop_name
                    combined_df = pd.concat([combined_df, df_property], ignore_index=True)
            
            df = combined_df if not combined_df.empty else None

        if df is not None and not df.empty:
            return ApiResponse(
                status="success",
                message=f"Retrieved {len(df)} rows of GA4 data",
                data=[{str(k): v for k, v in row.items()} for row in df.to_dict('records')],
                row_count=len(df),
                source="ga4"
            )
        else:
            raise HTTPException(status_code=404, detail="No GA4 data found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GA4 query failed: {str(e)}")

@app.post("/gsc/query", response_model=ApiResponse)
async def query_gsc(request: GSCQueryRequest):
    """
    Query Google Search Console data with simplified parameters.
    
    Focus on core metrics: clicks, impressions, position, devices, countries
    """
    if not validate_date_range(request.date_range.start_date, request.date_range.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")
    
    try:
        df = NewDownloads.fetch_search_console_data(
            start_date=request.date_range.start_date,
            end_date=request.date_range.end_date,
            search_type=request.search_type,
            dimensions=request.dimensions,
            google_account=request.auth_identifier,
            wait_seconds=0,
            debug=request.debug,
            domain_filter=request.domain
        )
        
        if df is not None and not df.empty:
            return ApiResponse(
                status="success",
                message=f"Retrieved {len(df)} rows of GSC data",
                data=df.to_dict('records'),
                row_count=len(df),
                source="gsc"
            )
        else:
            raise HTTPException(status_code=404, detail="No GSC data found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GSC query failed: {str(e)}")

@app.post("/query", response_model=List[ApiResponse])
async def unified_query(request: UnifiedQueryRequest):
    """
    Unified endpoint to query both GA4 and GSC data for a single domain.
    
    This is the main endpoint for AI/MCP access - provides data from both sources
    with sensible defaults and minimal configuration.
    """
    if not validate_date_range(request.date_range.start_date, request.date_range.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")
    
    results = []
    errors = []
    
    # Query GA4 data if requested
    if "ga4" in request.data_sources:
        try:
            ga4_request = GA4QueryRequest(
                date_range=request.date_range,
                auth_identifier=request.auth_identifier,
                property_id=request.ga4_property_id,
                dimensions="pagePath",  # Focus on page-level data
                metrics="screenPageViews,totalAdRevenue",  # Core metrics
                debug=request.debug
            )
            
            ga4_result = await query_ga4(ga4_request)
            results.append(ga4_result)
            
        except Exception as e:
            errors.append(f"GA4 query failed: {str(e)}")
    
    # Query GSC data if requested
    if "gsc" in request.data_sources:
        try:
            gsc_request = GSCQueryRequest(
                date_range=request.date_range,
                domain=request.domain,
                auth_identifier=request.auth_identifier,
                search_type="web",
                dimensions="page,query,country,device",  # Core dimensions
                debug=request.debug
            )
            
            gsc_result = await query_gsc(gsc_request)
            results.append(gsc_result)
            
        except Exception as e:
            errors.append(f"GSC query failed: {str(e)}")
    
    if not results and errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))
    
    return results

@app.get("/ga4/properties")
async def list_ga4_properties(
    auth_identifier: str = Query(..., description="Authentication identifier"),
    debug: bool = Query(False, description="Enable debug mode")
):
    """List available GA4 properties"""
    try:
        properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
        if properties_df is not None and not properties_df.empty:
            return {
                "status": "success",
                "message": f"Found {len(properties_df)} GA4 properties",
                "properties": properties_df.to_dict('records')
            }
        else:
            raise HTTPException(status_code=404, detail="No GA4 properties found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list GA4 properties: {str(e)}")

@app.get("/gsc/domains")
async def list_gsc_domains(
    auth_identifier: str = Query("", description="Authentication identifier"),
    debug: bool = Query(False, description="Enable debug mode")
):
    """List available GSC domains"""
    try:
        domains_df = NewDownloads.list_search_console_sites(google_account=auth_identifier, debug=debug)
        if domains_df is not None and not domains_df.empty:
            return {
                "status": "success", 
                "message": f"Found {len(domains_df)} GSC domains",
                "domains": domains_df.to_dict('records')
            }
        else:
            raise HTTPException(status_code=404, detail="No GSC domains found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list GSC domains: {str(e)}")

# Quick query endpoints with minimal parameters
@app.get("/quick/ga4")
async def quick_ga4_query(
    auth_identifier: str = Query(..., description="Authentication identifier"),
    domain: Optional[str] = Query(None, description="Domain to filter (optional)"),
    days: int = Query(30, description="Number of days back from today", ge=1, le=365)
):
    """
    Quick GA4 query with minimal parameters - last N days of pageviews and revenue
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    request = GA4QueryRequest(
        date_range=DateRange(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        ),
        auth_identifier=auth_identifier,
        dimensions="pagePath" if not domain else "hostname,pagePath",
        metrics="screenPageViews,totalAdRevenue"
    )
    
    return await query_ga4(request)

@app.get("/quick/gsc")
async def quick_gsc_query(
    auth_identifier: str = Query("", description="Authentication identifier"),
    domain: Optional[str] = Query(None, description="Domain to query"),
    days: int = Query(30, description="Number of days back from today", ge=1, le=365)
):
    """
    Quick GSC query with minimal parameters - last N days of clicks, impressions, etc.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    request = GSCQueryRequest(
        date_range=DateRange(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        ),
        domain=domain,
        auth_identifier=auth_identifier,
        dimensions="page,query,country,device"
    )
    
    return await query_gsc(request)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GA4 & GSC Simplified API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    args = parser.parse_args()
    
    print(f"Starting GA4 & GSC Simplified API server on http://{args.host}:{args.port}")
    print("API documentation available at: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "simplified_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )