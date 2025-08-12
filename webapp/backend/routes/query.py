"""
Query execution routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
import pandas as pd
import io
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional
import json
import xlsxwriter

from core.query_models import QueryRequest, QueryResponse
from core.cache import UnifiedCache
from data_providers import DataProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances - will be dependency injected in production
cache = UnifiedCache()
data_registry = DataProviderRegistry()
active_queries: Dict[str, Dict[str, Any]] = {}


async def execute_query_background(query_id: str, query_request: QueryRequest):
    """Background task to execute query"""
    start_time = time.time()
    
    try:
        # Update status
        active_queries[query_id]["status"] = "running"
        
        # Check cache first
        query_data = query_request.dict()
        cached_result = cache.get_cached_query(query_data, ttl_seconds=3600)
        
        if cached_result and not query_request.debug:
            # Cache hit
            execution_time = (time.time() - start_time) * 1000
            active_queries[query_id].update({
                "status": "completed",
                "data": cached_result["data"],
                "row_count": len(cached_result["data"]),
                "cache_hit": True,
                "execution_time_ms": execution_time,
                "sources_queried": query_request.sources
            })
            
            cache.log_query(query_data, execution_time, True, len(cached_result["data"]))
            return
        
        # Execute fresh query
        results = await data_registry.execute_unified_query(
            start_date=query_request.start_date.isoformat(),
            end_date=query_request.end_date.isoformat(),
            sources=query_request.sources,
            dimensions=query_request.dimensions,
            metrics=query_request.metrics,
            properties=query_request.properties,
            auth_identifier=query_request.auth_identifier,
            debug=query_request.debug,
            filters=query_request.filters
        )
        
        # Apply sorting if specified
        if query_request.sort and results:
            for sort_spec in reversed(query_request.sort):
                field = sort_spec.get("field")
                reverse = sort_spec.get("order", "asc").lower() == "desc"
                if field:
                    try:
                        results.sort(key=lambda x: x.get(field, 0) or 0, reverse=reverse)
                    except (TypeError, ValueError):
                        # Handle mixed types or non-comparable values
                        results.sort(key=lambda x: str(x.get(field, "")), reverse=reverse)
        
        # Apply limit if specified
        if query_request.limit and query_request.limit > 0:
            results = results[:query_request.limit]
        
        execution_time = (time.time() - start_time) * 1000
        
        # Update query status
        active_queries[query_id].update({
            "status": "completed",
            "data": results,
            "row_count": len(results),
            "cache_hit": False,
            "execution_time_ms": execution_time,
            "sources_queried": query_request.sources
        })
        
        # Cache the result
        cache_data = {"data": results, "row_count": len(results)}
        cache.cache_query_result(query_data, cache_data, ttl_seconds=3600, execution_time_ms=execution_time)
        cache.log_query(query_data, execution_time, False, len(results))
        
    except Exception as e:
        logger.error(f"Error executing query {query_id}: {e}")
        active_queries[query_id].update({
            "status": "failed",
            "error": str(e),
            "execution_time_ms": (time.time() - start_time) * 1000
        })


@router.post("/query", response_model=QueryResponse)
async def create_query(query_request: QueryRequest, background_tasks: BackgroundTasks):
    """Create and execute a new query"""
    query_id = str(uuid.uuid4())
    
    # Initialize query tracking
    active_queries[query_id] = {
        "status": "queued",
        "created_at": time.time(),
        "query": query_request.dict()
    }
    
    # Start background execution
    background_tasks.add_task(execute_query_background, query_id, query_request)
    
    return QueryResponse(
        query_id=query_id,
        status="queued",
        sources_queried=query_request.sources
    )


@router.get("/query/{query_id}", response_model=QueryResponse)
async def get_query_status(query_id: str):
    """Get query status and results"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    
    return QueryResponse(
        query_id=query_id,
        status=query_info["status"],
        data=query_info.get("data"),
        error=query_info.get("error"),
        row_count=query_info.get("row_count"),
        cache_hit=query_info.get("cache_hit", False),
        execution_time_ms=query_info.get("execution_time_ms"),
        sources_queried=query_info.get("sources_queried", [])
    )


@router.get("/query/{query_id}/export/csv")
async def export_csv(query_id: str):
    """Export query results as CSV"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    if query_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Query not completed")
    
    data = query_info.get("data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No data to export")
    
    # Convert to DataFrame and then CSV
    df = pd.DataFrame(data)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=query_{query_id}.csv"}
    )


@router.get("/query/{query_id}/export/xlsx")
async def export_xlsx(query_id: str):
    """Export query results as Excel"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    if query_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Query not completed")
    
    data = query_info.get("data", [])
    if not data:
        raise HTTPException(status_code=404, detail="No data to export")
    
    # Create Excel file in memory
    output = io.BytesIO()
    df = pd.DataFrame(data)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Query Results', index=False)
        
        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Query Results']
        
        # Add some formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Apply header formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 15)
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=query_{query_id}.xlsx"}
    )


@router.delete("/query/{query_id}")
async def delete_query(query_id: str):
    """Delete a query from memory"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    del active_queries[query_id]
    return {"message": "Query deleted successfully"}


@router.get("/queries")
async def list_queries():
    """List all active queries"""
    return {
        "queries": [
            {
                "query_id": query_id,
                "status": info["status"],
                "created_at": info["created_at"],
                "row_count": info.get("row_count"),
                "execution_time_ms": info.get("execution_time_ms")
            }
            for query_id, info in active_queries.items()
        ]
    }