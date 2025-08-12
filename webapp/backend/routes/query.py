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

from core.query_models import QueryRequest, QueryResponse, PaginatedResponse
from core.cache import UnifiedCache
from data_providers import DataProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances - will be dependency injected in production
cache = UnifiedCache()
data_registry = DataProviderRegistry()
active_queries: Dict[str, Dict[str, Any]] = {}
cancel_flags: Dict[str, bool] = {}  # Track cancellation requests


async def execute_query_background(query_id: str, query_request: QueryRequest):
    """Background task to execute query with progress tracking and cancellation support"""
    start_time = time.time()
    
    try:
        # Update status and initialize progress
        active_queries[query_id].update({
            "status": "running",
            "progress": {"current": 0, "total": 3, "message": "Initializing query..."},
            "can_cancel": True
        })
        
        # Check for cancellation
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            return
        
        # Step 1: Check cache
        active_queries[query_id]["progress"] = {"current": 1, "total": 3, "message": "Checking cache..."}
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
                "sources_queried": query_request.sources,
                "progress": {"current": 3, "total": 3, "message": "Completed (cache hit)"},
                "can_cancel": False
            })
            
            cache.log_query(query_data, execution_time, True, len(cached_result["data"]))
            return
        
        # Check for cancellation
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            return
        
        # Step 2: Execute fresh query
        active_queries[query_id]["progress"] = {"current": 2, "total": 3, "message": f"Querying {', '.join(query_request.sources)} data..."}
        
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
        
        # Check for cancellation after query execution
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            return
        
        # Step 3: Process results
        active_queries[query_id]["progress"] = {"current": 3, "total": 3, "message": "Processing results..."}
        
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
            "sources_queried": query_request.sources,
            "progress": {"current": 3, "total": 3, "message": "Completed"},
            "can_cancel": False
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
            "execution_time_ms": (time.time() - start_time) * 1000,
            "can_cancel": False
        })
    finally:
        # Clean up cancellation flag
        cancel_flags.pop(query_id, None)


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
        sources_queried=query_info.get("sources_queried", []),
        progress=query_info.get("progress"),
        can_cancel=query_info.get("can_cancel", False)
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


@router.delete("/query/{query_id}/cancel")
async def cancel_query(query_id: str):
    """Cancel a running query"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    if query_info["status"] not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail="Query cannot be cancelled in current state")
    
    # Set cancellation flag
    cancel_flags[query_id] = True
    
    # Update query status
    active_queries[query_id].update({
        "status": "cancelled",
        "can_cancel": False
    })
    
    return {"message": "Query cancellation requested"}


@router.get("/query/{query_id}/results", response_model=PaginatedResponse)
async def get_paginated_results(query_id: str, page: int = 1, page_size: int = 100):
    """Get paginated query results"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    if query_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="Query not completed")
    
    data = query_info.get("data", [])
    total_rows = len(data)
    
    # Validate pagination parameters
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 100
    if page_size > 1000:  # Limit max page size
        page_size = 1000
    
    # Calculate pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_data = data[start_idx:end_idx]
    
    total_pages = (total_rows + page_size - 1) // page_size
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginatedResponse(
        data=paginated_data,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.delete("/query/{query_id}")
async def delete_query(query_id: str):
    """Delete a query from memory"""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")
    
    # Clean up both active queries and cancel flags
    del active_queries[query_id]
    cancel_flags.pop(query_id, None)
    
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