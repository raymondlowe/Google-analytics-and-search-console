"""
Query execution routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
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

from shared_state import active_queries, progress_websockets
from core.query_models import QueryRequest, QueryResponse, PaginatedResponse
from core.cache import UnifiedCache
from data_providers import DataProviderRegistry

logger = logging.getLogger(__name__)


router = APIRouter()

# Global instances - will be dependency injected in production
# Global instances - will be dependency injected in production
cache = UnifiedCache()
data_registry = DataProviderRegistry()
cancel_flags: Dict[str, bool] = {}  # Track cancellation requests


# --- Cache Management Endpoint ---
@router.post("/cache/clear")
async def clear_cache():
    try:
        deleted = cache.clear_cache()
        return JSONResponse({"success": True, "deleted": deleted})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def execute_query_background(query_id: str, query_request: QueryRequest):
    """Background task to execute query with progress tracking and cancellation support"""
    start_time = time.time()

    # Use a consistent logger prefix
    log_prefix = f"Query {query_id[:8]}:"

    # Log query start with details
    logger.info(f"{log_prefix} Starting query - Sources: {query_request.sources}, "
                f"Date range: {query_request.start_date} to {query_request.end_date}, "
                f"Dimensions: {query_request.dimensions}, Metrics: {query_request.metrics}")
    
    try:
        # Update status and initialize progress
        active_queries[query_id].update({
            "status": "running",
            "progress": {"current": 0, "total": 3, "message": "Initializing query..."},
            "can_cancel": True
        })
        logger.info(f"{log_prefix} Initializing query...")
        await broadcast_progress(query_id)
        
        # Check for cancellation
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            logger.info(f"{log_prefix} Cancelled before starting.")
            await broadcast_progress(query_id)
            return
        
        # Step 1: Check cache
        logger.info(f"{log_prefix} Checking cache...")
        active_queries[query_id]["progress"] = {"current": 1, "total": 3, "message": "Checking cache..."}
        await broadcast_progress(query_id)
        query_data = query_request.dict()
        cached_result = cache.get_cached_query(query_data, ttl_seconds=3600)
        
        if cached_result and not query_request.debug:
            # Cache hit
            execution_time = (time.time() - start_time) * 1000
            logger.info(f"{log_prefix} Cache hit! Returning {len(cached_result['data'])} rows in {execution_time:.1f}ms")
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
            await broadcast_progress(query_id)
            cache.log_query(query_data, execution_time, True, len(cached_result["data"]))
            return
        
        # Check for cancellation
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            logger.info(f"{log_prefix} Cancelled after cache check.")
            await broadcast_progress(query_id)
            return
        
        # Step 2: Execute fresh query
        logger.info(f"{log_prefix} Executing fresh query on {', '.join(query_request.sources)} data sources...")
        active_queries[query_id]["progress"] = {"current": 2, "total": 3, "message": f"Querying {', '.join(query_request.sources)} data..."}
        await broadcast_progress(query_id)
        
        # Create progress callback for more granular updates
        async def progress_update(progress_info):
            # Ensure current/total always present; default to stage 2/3
            existing = active_queries.get(query_id, {}).get("progress", {"current": 2, "total": 3})
            current = progress_info.get("current", existing.get("current", 2))
            total = progress_info.get("total", existing.get("total", 3))
            message = progress_info.get("message", existing.get("message", "Querying..."))
            active_queries[query_id]["progress"] = {"current": current, "total": total, "message": message}
            logger.info(f"{log_prefix} Sub-progress: {message}")
            await broadcast_progress(query_id)
        
        results = await data_registry.execute_unified_query(
            start_date=query_request.start_date.isoformat(),
            end_date=query_request.end_date.isoformat(),
            sources=query_request.sources,
            dimensions=query_request.dimensions,
            metrics=query_request.metrics,
            properties=query_request.properties,
            auth_identifier=query_request.auth_identifier,
            debug=query_request.debug,
            filters=query_request.filters,
            progress_callback=progress_update
        )
        
        logger.info(f"{log_prefix} Raw query returned {len(results) if results else 0} rows")
        
        # Check for cancellation after query execution
        if cancel_flags.get(query_id, False):
            active_queries[query_id]["status"] = "cancelled"
            logger.info(f"{log_prefix} Cancelled after data retrieval.")
            await broadcast_progress(query_id)
            return
        
        # Step 3: Process results
        logger.info(f"{log_prefix} Processing and formatting results...")
        active_queries[query_id]["progress"] = {"current": 3, "total": 3, "message": "Processing results..."}
        await broadcast_progress(query_id)
        
        # Apply sorting if specified
        if query_request.sort and results:
            logger.info(f"{log_prefix} Applying sorting: {query_request.sort}")
            for sort_spec in reversed(query_request.sort):
                field = sort_spec.get("field")
                reverse = sort_spec.get("order", "asc").lower() == "desc"
                if field:
                    try:
                        results.sort(key=lambda x: x.get(field, 0) or 0, reverse=reverse)
                    except (TypeError, ValueError):
                        # Handle mixed types or non-comparable values
                        results.sort(key=lambda x: str(x.get(field, "")), reverse=reverse)
        
        # Only apply a limit if the user explicitly sets one (not default, not 0/None)
        if hasattr(query_request, 'limit') and query_request.limit is not None and query_request.limit > 0:
            original_count = len(results)
            results = results[:query_request.limit]
            if original_count > query_request.limit:
                logger.info(f"{log_prefix} Limited results from {original_count} to {query_request.limit} rows")
        
        execution_time = (time.time() - start_time) * 1000
        
        logger.info(f"{log_prefix} Completed successfully! "
                   f"Returned {len(results)} rows in {execution_time:.1f}ms")
        
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
        logger.info(f"{log_prefix} Final progress update.")
        await broadcast_progress(query_id)
        
        # Cache the result
        cache_data = {"data": results, "row_count": len(results)}
        cache.cache_query_result(query_data, cache_data, ttl_seconds=3600, execution_time_ms=execution_time)
        cache.log_query(query_data, execution_time, False, len(results))
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"{log_prefix} FAILED after {execution_time:.1f}ms: {str(e)}", exc_info=True)
        active_queries[query_id].update({
            "status": "failed",
            "error": str(e),
            "execution_time_ms": execution_time,
            "can_cancel": False,
            "progress": {"current": 3, "total": 3, "message": f"Failed: {str(e)}"}
        })
        await broadcast_progress(query_id)
    finally:
        # Clean up cancellation flag
        cancel_flags.pop(query_id, None)

# --- Place broadcast_progress OUTSIDE the function ---
async def broadcast_progress(query_id: str):
    """Send progress update to websocket client if connected"""
    log_prefix = f"Query {query_id[:8]}:"
    logger.debug(f"{log_prefix} Attempting to broadcast progress.")
    progress = active_queries.get(query_id, {}).get("progress")
    ws = progress_websockets.get(query_id)
    if ws and progress:
        logger.info(f"{log_prefix} Broadcasting progress via WebSocket: {progress}")
        try:
            await ws.send_json(progress)
            logger.debug(f"{log_prefix} WebSocket send successful.")
        except Exception as e:
            logger.error(f"{log_prefix} WebSocket send error: {e}", exc_info=True)
            # Optional: remove broken websocket connection
            progress_websockets.pop(query_id, None)
            logger.warning(f"{log_prefix} Removed broken WebSocket connection.")
    elif not ws:
        logger.debug(f"{log_prefix} No active WebSocket found for this query ID.")
    elif not progress:
        logger.debug(f"{log_prefix} No progress data to broadcast.")


@router.post("/query", response_model=QueryResponse)
async def create_query(query_request: QueryRequest, background_tasks: BackgroundTasks):
    """Create and execute a new query"""
    query_id = str(uuid.uuid4())
    
    logger.info(f"Created new query {query_id[:8]}... - Request queued for processing")
    
    # Initialize query tracking
    active_queries[query_id] = {
        "status": "queued",
        "created_at": time.time(),
        "query": query_request.dict()
    }
    
    # Start background execution using asyncio task to ensure async function runs
    asyncio.create_task(execute_query_background(query_id, query_request))
    logger.debug(f"Scheduled background task for query {query_id[:8]}")
    
    return QueryResponse(
        query_id=query_id,
        status="queued",
        sources_queried=query_request.sources
    )


@router.get("/query/{query_id}", response_model=QueryResponse)
async def get_query_status(query_id: str):
    """Get query status and results"""
    logger.debug(f"GET /api/query/{query_id} called")
    if query_id not in active_queries:
        logger.debug(f"Query {query_id} not found")
        raise HTTPException(status_code=404, detail="Query not found")
    
    query_info = active_queries[query_id]
    logger.debug(f"Returning status for {query_id}: {query_info.get('status')} with progress {query_info.get('progress')}")
    
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
    # Write parameters as # comments at the top
    params = query_info.get("query", {})
    if params:
        for k, v in params.items():
            csv_buffer.write(f"# {k}: {v}\n")
    else:
        csv_buffer.write("# No query parameters available\n")
    csv_buffer.write("\n")
    # Write CSV header and data
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
        # Write the dataframe as text, then overwrite metrics as numbers with formatting
        df.to_excel(writer, sheet_name='Query Results', index=False)

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
        number_format = workbook.add_format({'num_format': '0.##########'})  # No scientific notation

        # Identify metric columns (try to get from query or infer from data)
        metric_cols = []
        if 'query' in query_info and query_info['query'].get('metrics'):
            metric_cols = [col for col in df.columns if col in query_info['query']['metrics']]
        else:
            # Fallback: infer numeric columns
            metric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

        # Apply header formatting and set column width
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 15)

        # Overwrite metric columns as numbers with fixed-point format
        for col_num, col_name in enumerate(df.columns):
            if col_name in metric_cols:
                for row_num, val in enumerate(df[col_name], start=1):
                    if pd.notnull(val):
                        try:
                            worksheet.write_number(row_num, col_num, float(val), number_format)
                        except Exception:
                            worksheet.write(row_num, col_num, val)

        # Add an 'options' tab with parameters
        params = query_info.get('query', {})
        if params:
            options_df = pd.DataFrame(list(params.items()), columns=['Parameter', 'Value'])
        else:
            options_df = pd.DataFrame([['No query parameters available', '']], columns=['Parameter', 'Value'])
        options_df.to_excel(writer, sheet_name='options', index=False)
    
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