#!/usr/bin/env python3
"""
MCP Server for Google Analytics 4 and Search Console Data
Designed for AI model access with tools for querying GA4 and GSC data.
"""

import asyncio
import logging
import json
import pandas as pd
import secrets
import hmac
import hashlib
import time
import uuid
import warnings
from typing import Dict, Optional, List, Union
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from datetime import datetime
import concurrent.futures

# Suppress Google API warnings about file_cache and oauth2client
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client')

# Import our existing modules
import GA4query3
import NewDownloads
from NewDownloads import async_persistent_cache


# Configure enhanced logging with structured format, and set level based on DEBUG_MODE env
import os
log_level = os.environ.get("DEBUG_MODE", "false").lower()
if log_level == "true":
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Request tracking and performance monitoring
class RequestTracker:
    """Track requests for monitoring and observability"""
    
    def __init__(self):
        self.active_requests: Dict[str, Dict] = {}
        self.request_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'auth_failures': 0,
            'avg_response_time': 0.0
        }
    
    def start_request(self, request_id: str, client_ip: str, method: str, path: str) -> Dict:
        """Start tracking a new request"""
        request_info = {
            'request_id': request_id,
            'client_ip': client_ip,
            'method': method,
            'path': path,
            'start_time': time.time(),
            'status': 'active'
        }
        self.active_requests[request_id] = request_info
        self.request_stats['total_requests'] += 1
        return request_info
    
    def end_request(self, request_id: str, status_code: int, error: Optional[str] = None):
        """End tracking for a request"""
        if request_id in self.active_requests:
            request_info = self.active_requests[request_id]
            request_info['end_time'] = time.time()
            request_info['duration'] = request_info['end_time'] - request_info['start_time']
            request_info['status_code'] = status_code
            request_info['error'] = error
            
            # Update stats
            if status_code < 400:
                self.request_stats['successful_requests'] += 1
            else:
                self.request_stats['failed_requests'] += 1
                if status_code == 401:
                    self.request_stats['auth_failures'] += 1
            
            # Update average response time
            total_time = (self.request_stats['avg_response_time'] * 
                         (self.request_stats['total_requests'] - 1) + 
                         request_info['duration'])
            self.request_stats['avg_response_time'] = total_time / self.request_stats['total_requests']
            
            del self.active_requests[request_id]
            return request_info
    
    def get_stats(self) -> Dict:
        """Get current request statistics"""
        return {
            **self.request_stats,
            'active_requests': len(self.active_requests)
        }

# Global request tracker, server start time, and middleware reference
request_tracker = RequestTracker()
start_time = time.time()
middleware = None  # Will be set when middleware is created

# Enhanced logging filter to add request context
class RequestContextFilter(logging.Filter):
    """Add request context to log records"""
    
    def filter(self, record):
        # Add request_id to log record if not present
        if not hasattr(record, 'request_id'):
            record.request_id = getattr(self, '_current_request_id', 'no-request')
        return True

# Set up the filter - only apply to our logger, not all loggers
request_filter = RequestContextFilter()

# Create a custom logger for our application that includes request context
app_logger = logging.getLogger(__name__)
app_logger.addFilter(request_filter)

def set_request_context(request_id: str):
    """Set the current request ID for logging"""
    request_filter._current_request_id = request_id

# Security utilities
def secure_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.
    Uses hmac.compare_digest directly for secure comparison of API keys.
    """
    if len(a) != len(b):
        return False
    
    # Use hmac.compare_digest directly for constant-time comparison
    return hmac.compare_digest(a.encode(), b.encode())

# Configure FastMCP with stateless HTTP mode to avoid session ID issues
mcp = FastMCP("ga4-gsc-mcp")
# Set stateless HTTP mode to avoid session initialization issues
mcp.settings.stateless_http = True

# Helper functions
def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate date range format and logic"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        return start <= end
    except ValueError:
        return False

def validate_ga4_dimensions_metrics(dimensions: str, metrics: str) -> dict:
    """
    Validate GA4 dimensions and metrics against common mistakes and provide suggestions.
    
    Returns:
        dict: {"valid": bool, "warnings": list, "suggestions": list}
    """
    result = {"valid": True, "warnings": [], "suggestions": []}
    
    # Common invalid dimensions and their corrections
    invalid_dimensions = {
        "sessionCampaign": "Use 'sessionCampaignId' for campaign ID or 'sessionCampaignName' for campaign name",
        "pageviews": "Use 'screenPageViews' for page view count",
        "users": "Use 'activeUsers' for current active users or 'totalUsers' for all users",
        "sessions": "sessions is a metric, not a dimension",
        "bounceRate": "bounceRate is a metric, not a dimension"
    }
    
    # Common invalid metrics and their corrections  
    invalid_metrics = {
        "pageviews": "Use 'screenPageViews' for page view count",
        "users": "Use 'activeUsers' for current active users or 'totalUsers' for all users",
        "pagePath": "pagePath is a dimension, not a metric",
        "country": "country is a dimension, not a metric"
    }
    
    # Check dimensions
    if dimensions:
        dim_list = [d.strip() for d in dimensions.split(',')]
        for dim in dim_list:
            if dim in invalid_dimensions:
                result["valid"] = False
                result["warnings"].append(f"Invalid dimension '{dim}': {invalid_dimensions[dim]}")
    
    # Check metrics
    if metrics:
        metric_list = [m.strip() for m in metrics.split(',')]
        for metric in metric_list:
            if metric in invalid_metrics:
                result["valid"] = False
                result["warnings"].append(f"Invalid metric '{metric}': {invalid_metrics[metric]}")
    
    # Add general suggestions if any issues found
    if not result["valid"]:
        result["suggestions"].extend([
            "Verify dimensions and metrics at: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema",
            "Use the 'list_ga4_properties' tool first to ensure you have access to the property",
            "Test with simple, known-valid dimensions like 'pagePath' and metrics like 'screenPageViews'"
        ])
    
    return result

def get_default_date_range(days: int = 30) -> dict:
    """Get default date range (last N days)"""
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=days)
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
    }

def add_today_date_to_response(response: dict) -> dict:
    """Add today's date to response for AI client context"""
    if isinstance(response, dict):
        response["todays_date"] = datetime.now().strftime('%Y-%m-%d')
    return response

def parse_multi_input(input_value: Union[str, List[str]]) -> List[str]:
    """
    Parse multi-property/domain input into a list.
    
    Accepts:
    - Single string: "123456789"
    - Comma-separated string: "123456789,987654321,456789123"
    - List of strings: ["123456789", "987654321", "456789123"]
    
    Returns:
    - List of strings, empty list if input is empty/None
    """
    if not input_value:
        return []
    
    if isinstance(input_value, list):
        # Already a list, filter out empty strings
        return [str(item).strip() for item in input_value if str(item).strip()]
    
    if isinstance(input_value, str):
        # Handle comma-separated string
        if ',' in input_value:
            return [item.strip() for item in input_value.split(',') if item.strip()]
        else:
            # Single string
            return [input_value.strip()] if input_value.strip() else []
    
    # Convert other types to string and treat as single item
    return [str(input_value).strip()] if str(input_value).strip() else []

async def process_multiple_properties_ga4(
    property_ids: List[str],
    start_date: str,
    end_date: str,
    auth_identifier: str,
    dimensions: str,
    metrics: str,
    debug: bool,
    max_concurrent: int = 5
) -> Dict:
    """
    Process multiple GA4 properties concurrently.
    
    Args:
        property_ids: List of GA4 property IDs
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        auth_identifier: Authentication identifier
        dimensions: Comma-separated dimensions
        metrics: Comma-separated metrics
        debug: Enable debug output
        max_concurrent: Maximum concurrent requests (default: 5)
    
    Returns:
        Dict containing aggregated results with source attribution
    """
    if not property_ids:
        return {"status": "error", "message": "No property IDs provided"}
    
    async def query_single_property(property_id: str) -> Dict:
        """Query a single GA4 property"""
        try:
            if debug:
                logger.info(f"Querying GA4 property: {property_id}")
            
            # Use asyncio to run the sync function in a thread pool
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                GA4query3.produce_report,
                start_date,
                end_date,
                property_id,
                f"Property_{property_id}",
                auth_identifier,
                None,  # filter_expression
                dimensions,
                metrics,
                debug
            )
            
            if df is not None and not df.empty:
                # Add source attribution
                df['source_property_id'] = property_id
                df['source_type'] = 'ga4'
                return {
                    "property_id": property_id,
                    "status": "success",
                    "data": df,
                    "row_count": len(df)
                }
            else:
                return {
                    "property_id": property_id,
                    "status": "success",
                    "data": pd.DataFrame(),
                    "row_count": 0
                }
        except Exception as e:
            logger.error(f"Error querying GA4 property {property_id}: {str(e)}")
            return {
                "property_id": property_id,
                "status": "error",
                "error": str(e),
                "data": pd.DataFrame(),
                "row_count": 0
            }
    
    # Process properties with concurrency limit
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_query(property_id: str):
        async with semaphore:
            return await query_single_property(property_id)
    
    # Execute all queries concurrently
    tasks = [limited_query(prop_id) for prop_id in property_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    all_data = []
    successful_queries = 0
    failed_queries = 0
    property_results = {}
    
    for result in results:
        if isinstance(result, Exception):
            failed_queries += 1
            continue
        
        property_id = result["property_id"]
        property_results[property_id] = {
            "status": result["status"],
            "row_count": result["row_count"],
            "error": result.get("error")
        }
        
        if result["status"] == "success" and not result["data"].empty:
            all_data.append(result["data"])
            successful_queries += 1
        elif result["status"] == "error":
            failed_queries += 1
    
    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        total_rows = len(combined_df)
        data_records = combined_df.to_dict('records')
    else:
        total_rows = 0
        data_records = []
    
    return {
        "status": "success" if successful_queries > 0 else "error",
        "message": f"Processed {len(property_ids)} properties: {successful_queries} successful, {failed_queries} failed",
        "data": data_records,
        "row_count": total_rows,
        "property_count": len(property_ids),
        "successful_properties": successful_queries,
        "failed_properties": failed_queries,
        "property_results": property_results
    }

async def process_multiple_domains_gsc(
    domains: List[str],
    start_date: str,
    end_date: str,
    auth_identifier: str,
    dimensions: str,
    search_type: str,
    debug: bool,
    max_concurrent: int = 5
) -> Dict:
    """
    Process multiple GSC domains concurrently.
    
    Args:
        domains: List of domain names
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        auth_identifier: Authentication identifier
        dimensions: Comma-separated dimensions
        search_type: Type of search data (web, image, video)
        debug: Enable debug output
        max_concurrent: Maximum concurrent requests (default: 5)
    
    Returns:
        Dict containing aggregated results with source attribution
    """
    if not domains:
        return {"status": "error", "message": "No domains provided"}
    
    async def query_single_domain(domain: str) -> Dict:
        """Query a single GSC domain"""
        try:
            if debug:
                logger.info(f"Querying GSC domain: {domain}")
            
            # Use the async version directly
            df = await NewDownloads.fetch_search_console_data_async(
                start_date=start_date,
                end_date=end_date,
                search_type=search_type,
                dimensions=dimensions,
                google_account=auth_identifier,
                wait_seconds=0,
                debug=debug,
                domain_filter=domain
            )
            
            if df is not None and not df.empty:
                # Add source attribution
                df['source_domain'] = domain
                df['source_type'] = 'gsc'
                return {
                    "domain": domain,
                    "status": "success",
                    "data": df,
                    "row_count": len(df)
                }
            else:
                return {
                    "domain": domain,
                    "status": "success",
                    "data": pd.DataFrame(),
                    "row_count": 0
                }
        except Exception as e:
            logger.error(f"Error querying GSC domain {domain}: {str(e)}")
            return {
                "domain": domain,
                "status": "error",
                "error": str(e),
                "data": pd.DataFrame(),
                "row_count": 0
            }
    
    # Process domains with concurrency limit
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_query(domain: str):
        async with semaphore:
            return await query_single_domain(domain)
    
    # Execute all queries concurrently
    tasks = [limited_query(domain) for domain in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    all_data = []
    successful_queries = 0
    failed_queries = 0
    domain_results = {}
    
    for result in results:
        if isinstance(result, Exception):
            failed_queries += 1
            continue
        
        domain = result["domain"]
        domain_results[domain] = {
            "status": result["status"],
            "row_count": result["row_count"],
            "error": result.get("error")
        }
        
        if result["status"] == "success" and not result["data"].empty:
            all_data.append(result["data"])
            successful_queries += 1
        elif result["status"] == "error":
            failed_queries += 1
    
    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        total_rows = len(combined_df)
        data_records = combined_df.to_dict('records')
    else:
        total_rows = 0
        data_records = []
    
    return {
        "status": "success" if successful_queries > 0 else "error",
        "message": f"Processed {len(domains)} domains: {successful_queries} successful, {failed_queries} failed",
        "data": data_records,
        "row_count": total_rows,
        "domain_count": len(domains),
        "successful_domains": successful_queries,
        "failed_domains": failed_queries,
        "domain_results": domain_results
    }

@mcp.tool()
async def query_ga4_data(start_date: str, end_date: str, auth_identifier: str = "", property_id: Union[str, List[str]] = "", domain_filter: str = "", metrics: str = "screenPageViews,totalAdRevenue,sessions", dimensions: str = "pagePath", debug: bool = False) -> dict:
    """
    Query Google Analytics 4 data for comprehensive website analytics.
    
    Business Use Cases:
    - Track page performance and visitor engagement
    - Monitor AdSense revenue by page and traffic source
    - Analyze user behavior patterns and demographics
    - Identify top-performing content for SEO optimization
    
    ⚠️ IMPORTANT: Dimension & Metric Validation
    Only use valid GA4 dimensions and metrics. Invalid ones will cause 400 errors.
    
    📋 Commonly Used Valid Dimensions:
    - Page/Content: pagePath, pageTitle, hostname, landingPage, landingPagePlusQueryString
    - User/Session: country, city, deviceCategory, browser, operatingSystem
    - Traffic Source: sessionSource, sessionMedium, sessionSourceMedium
    - Time: date, hour, dayOfWeek, month, year
    - Custom: Use format "customEvent:parameter_name" for event-scoped custom dimensions
    
    📊 Commonly Used Valid Metrics:
    - Page Views: screenPageViews, screenPageViewsPerSession, scrolledUsers
    - Users: activeUsers, newUsers, totalUsers, sessions, sessionsPerUser
    - Engagement: userEngagementDuration, averageSessionDuration, bounceRate, engagementRate
    - Revenue: totalAdRevenue, totalRevenue, publisherAdClicks, publisherAdImpressions
    - Events: eventCount, eventCountPerUser, keyEvents
    
    🚫 Common Mistakes to Avoid:
    - ❌ sessionCampaign → ✅ sessionCampaignId or sessionCampaignName (if needed for campaigns)
    - ❌ pageviews → ✅ screenPageViews  
    - ❌ users → ✅ activeUsers or totalUsers
    - ❌ Invalid custom dimensions without proper "customEvent:" prefix
    
    📖 Full Reference: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
    
    Example: Find top revenue-generating pages by traffic source:
    - dimensions: "pagePath,sessionSource,sessionMedium"  
    - metrics: "screenPageViews,totalAdRevenue,sessions"
    
    Multi-Property Usage Examples:
    - Single property: property_id="123456789"
    - Multiple properties as list: property_id=["123456789", "987654321", "456789123"]
    - Multiple properties as comma-separated string: property_id="123456789,987654321,456789123"
    
    When querying multiple properties:
    - Results include 'source_property_id' field for attribution
    - Data is aggregated from all specified properties
    - Partial failures are reported in 'property_results'
    
    Filtering Behavior:
    - When property_id is specified: No domain filtering applied (for maximum data reliability)
    - When property_id is omitted: domain_filter applies to all properties (for cross-property filtering)
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Single property ID, list of property IDs, or comma-separated string (optional, queries all properties if not specified)
        domain_filter: Filter by hostname (optional, only applied when querying all properties)
        metrics: Comma-separated metrics (default: screenPageViews,totalAdRevenue,sessions)
        dimensions: Comma-separated dimensions (default: pagePath)
        debug: Enable debug output
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    logger.info(f"[{request_id}] Starting GA4 query - dates: {start_date} to {end_date}, property: {property_id or 'all'}, domain: {domain_filter or 'all'}")
    
    if not start_date or not end_date:
        error_msg = "start_date and end_date are required parameters"
        logger.warning(f"[{request_id}] GA4 query failed - {error_msg}")
        return add_today_date_to_response({"status": "error", "message": error_msg, "request_id": request_id})
    
    if not validate_date_range(start_date, end_date):
        error_msg = "Invalid date range"
        logger.warning(f"[{request_id}] GA4 query failed - {error_msg}: {start_date} to {end_date}")
        return add_today_date_to_response({"status": "error", "message": error_msg, "request_id": request_id})
    
    # Validate dimensions and metrics before API call
    validation_result = validate_ga4_dimensions_metrics(dimensions, metrics)
    if not validation_result["valid"]:
        error_msg = "Invalid dimensions or metrics detected"
        validation_details = {
            "status": "error", 
            "message": error_msg,
            "warnings": validation_result["warnings"],
            "suggestions": validation_result["suggestions"],
            "request_id": request_id,
            "todays_date": datetime.now().strftime('%Y-%m-%d')
        }
        logger.warning(f"[{request_id}] GA4 query failed - {error_msg}: {validation_result['warnings']}")
        return validation_details
    
    try:
        # Parse property_id input to handle multiple properties
        property_ids = parse_multi_input(property_id)
        
        if property_ids:
            # Multiple properties or single property specified
            if len(property_ids) == 1:
                logger.info(f"[{request_id}] Querying single GA4 property: {property_ids[0]}")
                # Single property - use existing logic for compatibility
                df = GA4query3.produce_report(
                    start_date=start_date,
                    end_date=end_date,
                    property_id=property_ids[0],
                    property_name="MCP_Property",
                    account=auth_identifier,
                    filter_expression=None,  # No domain filtering when property_id is specified
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                if df is not None and not df.empty:
                    # Add source attribution for consistency
                    df['source_property_id'] = property_ids[0]
                    df['source_type'] = 'ga4'
                    
                    duration = time.time() - start_time
                    logger.info(f"[{request_id}] GA4 query successful - {len(df)} rows retrieved in {duration:.2f}s")
                    return add_today_date_to_response({
                        "status": "success",
                        "message": f"Retrieved {len(df)} rows of GA4 data",
                        "date_range": {"start_date": start_date, "end_date": end_date},
                        "property_id": property_ids[0],
                        "data": df.to_dict('records'),
                        "row_count": len(df),
                        "source": "ga4",
                        "request_id": request_id,
                        "duration_seconds": round(duration, 2)
                    })
                else:
                    duration = time.time() - start_time
                    logger.info(f"[{request_id}] GA4 query completed - no data found in {duration:.2f}s")
                    return add_today_date_to_response({
                        "status": "success", 
                        "message": "No GA4 data found for the specified criteria", 
                        "data": [], 
                        "row_count": 0, 
                        "source": "ga4",
                        "request_id": request_id,
                        "duration_seconds": round(duration, 2)
                    })
            else:
                # Multiple properties - use new concurrent processing
                logger.info(f"[{request_id}] Querying {len(property_ids)} GA4 properties: {property_ids}")
                result = await process_multiple_properties_ga4(
                    property_ids=property_ids,
                    start_date=start_date,
                    end_date=end_date,
                    auth_identifier=auth_identifier,
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                duration = time.time() - start_time
                result.update({
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "property_ids": property_ids,
                    "source": "ga4",
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2)
                })
                
                logger.info(f"[{request_id}] Multi-property GA4 query completed - {result['row_count']} total rows in {duration:.2f}s")
                return add_today_date_to_response(result)
        else:
            logger.info(f"[{request_id}] Querying all available GA4 properties")
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                error_msg = "No GA4 properties found"
                logger.warning(f"[{request_id}] GA4 query failed - {error_msg}")
                return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
            
            logger.info(f"[{request_id}] Found {len(properties_df)} GA4 properties to query")
            
            # Extract property IDs and use multi-property processing
            all_property_ids = []
            for idx, row in properties_df.iterrows():
                pid = row.get("property_id") or row.get("id")
                if pid:
                    all_property_ids.append(str(pid))
            
            if all_property_ids:
                # Use multi-property processing for all properties
                result = await process_multiple_properties_ga4(
                    property_ids=all_property_ids,
                    start_date=start_date,
                    end_date=end_date,
                    auth_identifier=auth_identifier,
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                # Apply domain filtering to combined results if specified
                if domain_filter and result.get("data"):
                    original_count = result["row_count"]
                    filtered_data = [row for row in result["data"] if row.get("hostname") == domain_filter]
                    result["data"] = filtered_data
                    result["row_count"] = len(filtered_data)
                    if debug:
                        logger.info(f"[{request_id}] Applied domain filter '{domain_filter}': {original_count} -> {len(filtered_data)} rows")
                
                duration = time.time() - start_time
                result.update({
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "domain_filter": domain_filter,
                    "source": "ga4",
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2)
                })
                
                logger.info(f"[{request_id}] All-properties GA4 query completed - {result['row_count']} total rows in {duration:.2f}s")
                return add_today_date_to_response(result)
            else:
                error_msg = "No valid GA4 property IDs found"
                logger.warning(f"[{request_id}] GA4 query failed - {error_msg}")
                return add_today_date_to_response({"status": "error", "message": error_msg, "request_id": request_id})
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"GA4 query failed: {str(e)}"
        logger.error(f"GA4 query exception - {error_msg}, duration: {duration:.2f}s", exc_info=True)
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}

@mcp.tool()
async def query_gsc_data(start_date: str, end_date: str, auth_identifier: str = "", domain: Union[str, List[str]] = "", dimensions: str = "page,query,country,device", search_type: str = "web", debug: bool = False) -> dict:
    """
    Query Google Search Console data for search performance analysis.
    
    Business Use Cases:
    - Identify high-impression, low-click pages needing content optimization
    - Find keyword opportunities with good ranking but poor CTR
    - Analyze page performance across different devices and countries
    - Discover content gaps where rankings could be improved
    
    Common Dimensions: page, query, country, device, date, searchAppearance
    Common Metrics: clicks, impressions, ctr, position (automatically included)
    
    Example: Find underperforming pages with good rankings:
    - dimensions: "page,query" to see page-keyword combinations
    - Filter results for position < 10 but ctr < 0.05 (5%)
    
    Example: Identify mobile vs desktop performance:
    - dimensions: "page,device" to compare device performance
    
    Multi-Domain Usage Examples:
    - Single domain: domain="example.com"
    - Multiple domains as list: domain=["example.com", "subdomain.example.com", "another-site.com"]
    - Multiple domains as comma-separated string: domain="example.com,subdomain.example.com,another-site.com"
    
    When querying multiple domains:
    - Results include 'source_domain' field for attribution
    - Data is aggregated from all specified domains
    - Partial failures are reported in 'domain_results'
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Single domain, list of domains, or comma-separated string (optional, queries all domains if not specified)
        dimensions: Comma-separated dimensions (default: page,query,country,device)
        search_type: Type of search data - web, image, video (default: web)
        debug: Enable debug output
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    # Parse domain input to handle multiple domains
    domains_list = parse_multi_input(domain)
    logger.info(f"Starting GSC query - dates: {start_date} to {end_date}, domain(s): {domains_list if domains_list else 'all'}, search_type: {search_type}")
    
    if not start_date or not end_date:
        error_msg = "start_date and end_date are required parameters"
        logger.warning(f"GSC query failed - {error_msg}")
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
    if not validate_date_range(start_date, end_date):
        error_msg = "Invalid date range"
        logger.warning(f"GSC query failed - {error_msg}: {start_date} to {end_date}")
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
    try:
        # Parse domain input to handle multiple domains
        domains = parse_multi_input(domain)
        
        if domains:
            # Multiple domains or single domain specified
            if len(domains) == 1:
                logger.info(f"[{request_id}] Querying single GSC domain: {domains[0]}")
                # Single domain - use existing logic for compatibility
                logger.info(f"[{request_id}] Calling fetch_search_console_data_async with params: start_date={start_date}, end_date={end_date}, search_type={search_type}, dimensions={dimensions}, google_account={auth_identifier}, wait_seconds=0, debug={debug}, domain_filter={domains[0]}")
                df = await NewDownloads.fetch_search_console_data_async(
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    dimensions=dimensions,
                    google_account=auth_identifier,
                    wait_seconds=0,
                    debug=debug,
                    domain_filter=domains[0]
                )
                
                if df is not None and not df.empty:
                    # Add source attribution for consistency
                    df['source_domain'] = domains[0]
                    df['source_type'] = 'gsc'
                    
                    duration = time.time() - start_time
                    logger.info(f"[{request_id}] GSC query successful - {len(df)} rows retrieved in {duration:.2f}s")
                    return {
                        "status": "success",
                        "message": f"Retrieved {len(df)} rows of GSC data",
                        "date_range": {"start_date": start_date, "end_date": end_date},
                        "domain": domains[0],
                        "data": df.to_dict('records'),
                        "row_count": len(df),
                        "source": "gsc",
                        "request_id": request_id,
                        "duration_seconds": round(duration, 2),
                        "todays_date": datetime.now().strftime('%Y-%m-%d')
                    }
                else:
                    duration = time.time() - start_time
                    logger.info(f"[{request_id}] GSC query completed - no data found in {duration:.2f}s")
                    return {
                        "status": "success", 
                        "message": "No GSC data found for the specified criteria", 
                        "data": [], 
                        "row_count": 0, 
                        "source": "gsc",
                        "request_id": request_id,
                        "duration_seconds": round(duration, 2),
                        "todays_date": datetime.now().strftime('%Y-%m-%d')
                    }
            else:
                # Multiple domains - use new concurrent processing
                logger.info(f"[{request_id}] Querying {len(domains)} GSC domains: {domains}")
                result = await process_multiple_domains_gsc(
                    domains=domains,
                    start_date=start_date,
                    end_date=end_date,
                    auth_identifier=auth_identifier,
                    dimensions=dimensions,
                    search_type=search_type,
                    debug=debug
                )
                
                duration = time.time() - start_time
                result.update({
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "domains": domains,
                    "source": "gsc",
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2),
                    "todays_date": datetime.now().strftime('%Y-%m-%d')
                })
                
                logger.info(f"[{request_id}] Multi-domain GSC query completed - {result['row_count']} total rows in {duration:.2f}s")
                return result
        else:
            logger.info(f"[{request_id}] Querying all available GSC domains")
            # Query all domains - use the existing logic but through our new processing
            logger.info(f"[{request_id}] Calling fetch_search_console_data_async with params: start_date={start_date}, end_date={end_date}, search_type={search_type}, dimensions={dimensions}, google_account={auth_identifier}, wait_seconds=0, debug={debug}, domain_filter=None (all domains)")
            df = await NewDownloads.fetch_search_console_data_async(
                start_date=start_date,
                end_date=end_date,
                search_type=search_type,
                dimensions=dimensions,
                google_account=auth_identifier,
                wait_seconds=0,
                debug=debug,
                domain_filter=None  # Query all domains
            )
            
            if df is not None and not df.empty:
                # Add source attribution
                df['source_type'] = 'gsc'
                # Note: When querying all domains, the source_domain will be derived from the data itself
                
                duration = time.time() - start_time
                logger.info(f"[{request_id}] All-domains GSC query successful - {len(df)} rows retrieved in {duration:.2f}s")
                return {
                    "status": "success",
                    "message": f"Retrieved {len(df)} rows of GSC data from all domains",
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "data": df.to_dict('records'),
                    "row_count": len(df),
                    "source": "gsc",
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2),
                    "todays_date": datetime.now().strftime('%Y-%m-%d')
                }
            else:
                duration = time.time() - start_time
                logger.info(f"[{request_id}] All-domains GSC query completed - no data found in {duration:.2f}s")
                return {
                    "status": "success", 
                    "message": "No GSC data found for the specified criteria", 
                    "data": [], 
                    "row_count": 0, 
                    "source": "gsc",
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2),
                    "todays_date": datetime.now().strftime('%Y-%m-%d')
                }
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"GSC query failed: {str(e)}"
        logger.error(f"GSC query exception - {error_msg}, duration: {duration:.2f}s", exc_info=True)
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}

# @mcp.tool()
# async def query_unified_data(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", ga4_property_id: str = "", data_sources: list = ["ga4", "gsc"], debug: bool = False) -> dict:
#     """
#     Query both GA4 and GSC data for comprehensive cross-platform analysis.
    
#     Business Use Cases:
#     - Compare organic search performance (GSC) with actual user behavior (GA4)
#     - Identify pages with high search impressions but low GA4 pageviews (optimization opportunity)
#     - Cross-reference revenue data with search performance
#     - Comprehensive SEO and monetization analysis
    
#     This tool combines data from both platforms to provide insights that neither platform 
#     alone can offer, ideal for holistic website performance analysis.
    
#     Args:
#         start_date: Start date in YYYY-MM-DD format (required)
#         end_date: End date in YYYY-MM-DD format (required)
#         domain: Domain to analyze (optional, analyzes all domains if not specified)
#         ga4_property_id: Specific GA4 property ID (optional)
#         data_sources: List of data sources to query - ["ga4"], ["gsc"], or ["ga4", "gsc"] (default: both)
#         debug: Enable debug output
#     """
#     if not start_date or not end_date:
#         return {"status": "error", "message": "start_date and end_date are required parameters", "todays_date": datetime.now().strftime('%Y-%m-%d')}
#     if not validate_date_range(start_date, end_date):
#         return {"status": "error", "message": "Invalid date range", "todays_date": datetime.now().strftime('%Y-%m-%d')}
#     results = []
#     errors = []
#     if "ga4" in data_sources:
#         ga4_result = await query_ga4_data(auth_identifier, start_date, end_date, ga4_property_id, domain, debug=debug)
#         if ga4_result.get("status") == "success":
#             results.append(ga4_result)
#         else:
#             errors.append(ga4_result.get("message"))
#     if "gsc" in data_sources:
#         gsc_result = await query_gsc_data(auth_identifier, start_date, end_date, domain, debug=debug)
#         if gsc_result.get("status") == "success":
#             results.append(gsc_result)
#         else:
#             errors.append(gsc_result.get("message"))
#     if not results and errors:
#         return {"status": "error", "message": "; ".join(errors), "todays_date": datetime.now().strftime('%Y-%m-%d')}
#     if errors:
#         return {"status": "partial_success", "message": f"Retrieved data from {len(results)} source(s) with {len(errors)} error(s)", "errors": errors, "results": results, "todays_date": datetime.now().strftime('%Y-%m-%d')}
#     return {"status": "success", "message": f"Retrieved data from {len(results)} source(s)", "results": results, "todays_date": datetime.now().strftime('%Y-%m-%d')}

@mcp.tool()
async def validate_ga4_parameters(dimensions: str = "", metrics: str = "") -> dict:
    """
    Validate GA4 dimensions and metrics before making API calls to avoid errors.
    
    Use this tool to check if your dimensions and metrics are valid before querying data.
    This helps prevent 400 errors and provides helpful suggestions for corrections.
    
    Args:
        dimensions: Comma-separated dimensions to validate (optional)
        metrics: Comma-separated metrics to validate (optional)
        
    Returns:
        dict: Validation results with warnings and suggestions
    """
    request_id = str(uuid.uuid4())[:8]
    
    if not dimensions and not metrics:
        return {
            "status": "error",
            "message": "Please provide dimensions or metrics to validate",
            "request_id": request_id,
            "todays_date": datetime.now().strftime('%Y-%m-%d')
        }
    
    validation_result = validate_ga4_dimensions_metrics(dimensions, metrics)
    
    response = {
        "status": "success" if validation_result["valid"] else "warning",
        "message": "Parameters validated",
        "valid": validation_result["valid"],
        "request_id": request_id,
        "todays_date": datetime.now().strftime('%Y-%m-%d')
    }
    
    if validation_result["warnings"]:
        response["warnings"] = validation_result["warnings"]
    
    if validation_result["suggestions"]:
        response["suggestions"] = validation_result["suggestions"]
    
    if validation_result["valid"]:
        response["message"] = "All dimensions and metrics appear valid"
    else:
        response["message"] = "Issues found with dimensions or metrics"
    
    return response

@mcp.tool()
async def list_ga4_properties(auth_identifier: str = "", debug: bool = False) -> dict:
    """
    List all available GA4 properties for the authenticated account.
    
    Use this tool to discover which GA4 properties you have access to before running
    detailed analytics queries. Essential for multi-property setups or when you need
    to identify the correct property_id for focused analysis.
    
    Args:
        debug: Enable debug output
    """
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    try:
        logger.info(f"[{request_id}] Listing GA4 properties")
        properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
        if properties_df is not None and not properties_df.empty:
            logger.info(f"[{request_id}] Found {len(properties_df)} GA4 properties")
            return {
                "status": "success",
                "message": f"Found {len(properties_df)} GA4 properties",
                "properties": properties_df.to_dict('records'),
                "request_id": request_id,
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
        else:
            logger.info(f"[{request_id}] No GA4 properties found")
            return {
                "status": "success", 
                "message": "No GA4 properties found", 
                "properties": [],
                "request_id": request_id,
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
    except Exception as e:
        error_msg = f"Failed to list GA4 properties: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}", exc_info=True)
        return {
            "status": "error", 
            "message": error_msg,
            "request_id": request_id,
            "todays_date": datetime.now().strftime('%Y-%m-%d')
        }

@mcp.tool()
async def list_gsc_domains(auth_identifier: str = "", debug: bool = False) -> dict:
    """
    List all available Google Search Console domains for the authenticated account.
    
    Use this tool to discover which domains/sites you have access to before running
    search performance queries. Essential for multi-domain setups or when you need
    to identify the correct domain parameter for focused analysis.
    
    Args:
        debug: Enable debug output
    """
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    try:
        logger.info(f"[{request_id}] Listing GSC domains")
        domains_df = NewDownloads.list_search_console_sites(google_account=auth_identifier, debug=debug)
        if domains_df is not None and not domains_df.empty:
            logger.info(f"[{request_id}] Found {len(domains_df)} GSC domains")
            return {
                "status": "success",
                "message": f"Found {len(domains_df)} GSC domains",
                "domains": domains_df.to_dict('records'),
                "request_id": request_id,
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
        else:
            logger.info(f"[{request_id}] No GSC domains found")
            return {
                "status": "success", 
                "message": "No GSC domains found", 
                "domains": [],
                "request_id": request_id,
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
    except Exception as e:
        error_msg = f"Failed to list GSC domains: {str(e)}"
        logger.error(f"[{request_id}] {error_msg}", exc_info=True)
        return {
            "status": "error", 
            "message": error_msg,
            "request_id": request_id,
            "todays_date": datetime.now().strftime('%Y-%m-%d')
        }

# Focused GA4 Business-Intent Tools

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache page performance queries for 1 hour
async def page_performance_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: Union[str, List[str]] = "", domain_filter: str = "", debug: bool = False) -> dict:
    """
    Analyze page performance metrics for content optimization and SEO.
    
    Business Purpose: Identify your best and worst performing pages to optimize content strategy.
    Perfect for finding pages that need attention or content that's working well.
    
    This tool focuses on:
    - Which pages get the most visits and engagement
    - Time spent on each page (engagement quality)
    - Bounce rates and user retention
    - Page performance across different devices
    
    Returns data optimized for: Content optimization, SEO strategy, user experience improvements
    
    Multi-Property Usage Examples:
    - Single property: property_id="123456789"
    - Multiple properties as list: property_id=["123456789", "987654321"]
    - Multiple properties as comma-separated: property_id="123456789,987654321"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Single property ID, list of property IDs, or comma-separated string (optional)
        domain_filter: Filter by hostname (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions and metrics optimized for page performance analysis
    dimensions = "pagePath,deviceCategory"
    metrics = "screenPageViews,sessions,userEngagementDuration,bounceRate,totalUsers"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache traffic sources queries for 1 hour
async def traffic_sources_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: Union[str, List[str]] = "", domain_filter: str = "", debug: bool = False) -> dict:
    """
    Analyze traffic sources to understand how visitors find your website.
    
    Business Purpose: Optimize marketing spend and SEO efforts by understanding which 
    channels drive the most valuable traffic. Essential for marketing ROI analysis.
    
    This tool focuses on:
    - Which sources drive the most traffic (organic, social, direct, referral)
    - Medium and campaign performance analysis  
    - Geographic distribution of traffic sources
    - Source quality based on engagement metrics
    
    Returns data optimized for: Marketing optimization, channel attribution, campaign analysis
    
    Multi-Property Usage Examples:
    - Single property: property_id="123456789"
    - Multiple properties as list: property_id=["123456789", "987654321"]
    - Multiple properties as comma-separated: property_id="123456789,987654321"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Single property ID, list of property IDs, or comma-separated string (optional)
        domain_filter: Filter by hostname (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions and metrics optimized for traffic source analysis
    dimensions = "sessionSource,sessionMedium,country"
    metrics = "sessions,totalUsers,userEngagementDuration,bounceRate,screenPageViews"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache audience analysis queries for 1 hour
async def audience_analysis_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: Union[str, List[str]] = "", domain_filter: str = "", debug: bool = False) -> dict:
    """
    Analyze your website audience demographics and behavior patterns.
    
    Business Purpose: Understand your audience to create better content and optimize 
    user experience. Essential for content strategy and personalization efforts.
    
    This tool focuses on:
    - Geographic distribution of your audience
    - Device and technology preferences  
    - Language and browser patterns
    - Operating system and screen resolution data
    
    Returns data optimized for: Content personalization, UX optimization, market research
    
    Multi-Property Usage Examples:
    - Single property: property_id="123456789"
    - Multiple properties as list: property_id=["123456789", "987654321"]
    - Multiple properties as comma-separated: property_id="123456789,987654321"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Single property ID, list of property IDs, or comma-separated string (optional)
        domain_filter: Filter by hostname (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions and metrics optimized for audience analysis
    dimensions = "country,deviceCategory,operatingSystem,browser,language"
    metrics = "totalUsers,sessions,userEngagementDuration,screenPageViews"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache revenue analysis queries for 1 hour
async def revenue_analysis_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: Union[str, List[str]] = "", domain_filter: str = "", debug: bool = False) -> dict:
    """
    Analyze AdSense revenue and monetization performance across your website.
    
    Business Purpose: Maximize ad revenue by understanding which pages, traffic sources,
    and audience segments generate the most income. Critical for monetization optimization.
    
    This tool focuses on:
    - Revenue by page (which content makes money)
    - Revenue by traffic source (which channels are most profitable)
    - Revenue by geography and device type
    - Revenue trends and patterns
    
    Returns data optimized for: Monetization strategy, ad placement optimization, revenue growth
    
    Multi-Property Usage Examples:
    - Single property: property_id="123456789"
    - Multiple properties as list: property_id=["123456789", "987654321"]
    - Multiple properties as comma-separated: property_id="123456789,987654321"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Single property ID, list of property IDs, or comma-separated string (optional)
        domain_filter: Filter by hostname (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions and metrics optimized for revenue analysis
    dimensions = "pagePath,sessionSource,country,deviceCategory"
    metrics = "totalAdRevenue,publisherAdClicks,publisherAdImpressions,screenPageViews,sessions,totalUsers"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

# Focused GSC Business-Intent Tools

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache GSC page performance queries for 1 hour
async def page_performance_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: Union[str, List[str]] = "", debug: bool = False) -> dict:
    """
    Analyze page performance in Google Search to identify SEO optimization opportunities.
    
    Business Purpose: Find pages with high potential that need optimization - either pages 
    getting impressions but poor clicks, or pages with good rankings but room for improvement.
    
    This tool focuses on:
    - Pages with high impressions but low click-through rates (CTR optimization needed)
    - Pages with good rankings but poor CTR (title/meta description optimization)
    - Page performance across different devices and countries
    - Position trends for your most important pages
    
    Returns data optimized for: Content optimization, title/meta improvements, CTR optimization
    
    Multi-Domain Usage Examples:
    - Single domain: domain="example.com"
    - Multiple domains as list: domain=["example.com", "subdomain.example.com"]
    - Multiple domains as comma-separated: domain="example.com,subdomain.example.com"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Single domain, list of domains, or comma-separated string (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for page performance analysis
    dimensions = "page,country,device"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache GSC query analysis for 1 hour
async def query_analysis_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: Union[str, List[str]] = "", debug: bool = False) -> dict:
    """
    Analyze search query performance to identify keyword opportunities and content gaps.
    
    Business Purpose: Discover which keywords you rank for and find opportunities to improve
    rankings or target new keywords. Essential for SEO content strategy.
    
    This tool focuses on:
    - Keywords with high impressions but low rankings (content improvement opportunities)
    - Keywords where you rank well but have poor CTR (meta optimization needed)
    - Emerging keyword trends and seasonal patterns
    - Geographic and device-specific keyword performance
    
    Returns data optimized for: Keyword strategy, content planning, SEO optimization
    
    Multi-Domain Usage Examples:
    - Single domain: domain="example.com"
    - Multiple domains as list: domain=["example.com", "subdomain.example.com"]
    - Multiple domains as comma-separated: domain="example.com,subdomain.example.com"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Single domain, list of domains, or comma-separated string (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for query analysis
    dimensions = "query,country,device"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache GSC page-query opportunities for 1 hour
async def page_query_opportunities_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: Union[str, List[str]] = "", debug: bool = False) -> dict:
    """
    Analyze page-query combinations to find content optimization opportunities.
    
    Business Purpose: Identify specific page-keyword combinations where you can improve
    rankings through content optimization. Perfect for finding quick SEO wins.
    
    This tool focuses on:
    - Page-keyword pairs with good impressions but poor rankings
    - Content that ranks on page 2-3 of Google (positions 11-30) with optimization potential
    - Pages that could rank for additional related keywords
    - Content gaps where competitors outrank you
    
    Returns data optimized for: Content optimization, on-page SEO, competitive analysis
    
    Multi-Domain Usage Examples:
    - Single domain: domain="example.com"
    - Multiple domains as list: domain=["example.com", "subdomain.example.com"]
    - Multiple domains as comma-separated: domain="example.com,subdomain.example.com"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Single domain, list of domains, or comma-separated string (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for page-query opportunity analysis
    dimensions = "page,query"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

@mcp.tool()
async def get_server_stats(include_details: bool = False) -> dict:
    """
    Get MCP server statistics and health information for monitoring and debugging.
    
    Business Purpose: Monitor server performance, authentication patterns, and usage analytics
    to ensure optimal operation and identify potential issues or security concerns.
    
    This tool provides:
    - Request volume and success/failure rates
    - Authentication method usage and failure patterns
    - Performance metrics (average response times)
    - Rate limiting statistics
    - Active session information
    - Domain cache performance (NEW - for timeout optimization)
    
    Returns data optimized for: Server monitoring, performance analysis, security auditing
    
    Args:
        include_details: Include detailed breakdown of statistics (default: False)
    """
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    logger.info("Retrieving server statistics")
    
    try:
        # Get basic stats
        basic_stats = {
            'server_uptime_seconds': time.time() - start_time,
            'current_time': datetime.now().isoformat(),
            'request_id': request_id,
            'todays_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Get request tracker stats
        tracker_stats = request_tracker.get_stats()
        
        # Get domain cache stats for performance monitoring
        domain_cache_stats = NewDownloads.get_domain_cache_stats()
        
        # Get disk cache stats for comprehensive monitoring  
        disk_cache_stats = NewDownloads.get_disk_cache_stats()
        
        # Get comprehensive cache health validation
        cache_health = NewDownloads.validate_cache_health()
        
        # Get basic auth stats (since middleware might not be available in stdio mode)
        auth_stats = {
            'auth_stats': {},
            'unique_ips': 0,
            'rate_limited': 0
        }
        
        stats = {
            'status': 'success',
            'message': 'Server statistics retrieved successfully',
            'basic_info': basic_stats,
            'request_metrics': tracker_stats,
            'domain_cache_metrics': domain_cache_stats,  # Memory-based domain cache
            'disk_cache_metrics': disk_cache_stats,      # Persistent disk cache
            'cache_health': cache_health,                # Comprehensive cache health
            'authentication_metrics': auth_stats.get('auth_stats', {}),
            'rate_limiting': {
                'unique_ips': auth_stats.get('unique_ips', 0),
                'rate_limited_requests': auth_stats.get('rate_limited', 0)
            }
        }
        
        if include_details:
            stats['detailed_metrics'] = {
                'success_rate': (tracker_stats.get('successful_requests', 0) / 
                               max(tracker_stats.get('total_requests', 1), 1)) * 100,
                'failure_rate': (tracker_stats.get('failed_requests', 0) / 
                               max(tracker_stats.get('total_requests', 1), 1)) * 100,
                'auth_failure_rate': (tracker_stats.get('auth_failures', 0) / 
                                     max(tracker_stats.get('total_requests', 1), 1)) * 100,
                'avg_response_time_ms': tracker_stats.get('avg_response_time', 0) * 1000,
                'cache_hit_rate': (domain_cache_stats.get('stats', {}).get('hits', 0) / 
                                 max(domain_cache_stats.get('stats', {}).get('hits', 0) + 
                                     domain_cache_stats.get('stats', {}).get('misses', 0), 1)) * 100,
                'overall_cache_healthy': cache_health.get('overall_healthy', False)
            }
        
        logger.info(f"Server stats retrieved - {tracker_stats.get('total_requests', 0)} total requests processed")
        return stats
        
    except Exception as e:
        error_msg = f"Failed to retrieve server statistics: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'request_id': request_id,
            'todays_date': datetime.now().strftime('%Y-%m-%d')
        }


@mcp.tool()
async def invalidate_cache(cache_type: str = "domain", account: str = "") -> dict:
    """
    Invalidate server caches to force fresh data retrieval.
    
    Business Purpose: Allow manual cache invalidation when fresh data is needed
    or when troubleshooting performance issues.
    
    Args:
        cache_type: Type of cache to invalidate ('domain', 'disk', or 'all')
        account: Specific account to invalidate (empty = all accounts)
        
    Returns:
        dict: Operation status and cache statistics
    """
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    try:
        if cache_type.lower() == "domain":
            # Get stats before invalidation
            stats_before = NewDownloads.get_domain_cache_stats()
            
            # Invalidate cache
            NewDownloads.invalidate_domain_cache(account if account else None)
            
            # Get stats after invalidation
            stats_after = NewDownloads.get_domain_cache_stats()
            
            logger.info(f"Domain cache invalidated - account: {account or 'all'}")
            
            return {
                'status': 'success',
                'message': f"Domain cache invalidated for {account or 'all accounts'}",
                'cache_stats_before': stats_before,
                'cache_stats_after': stats_after,
                'request_id': request_id,
                'todays_date': datetime.now().strftime('%Y-%m-%d')
            }
        elif cache_type.lower() == "disk":
            # Get stats before invalidation
            stats_before = NewDownloads.get_disk_cache_stats()
            
            # Clear disk cache
            NewDownloads.clear_disk_cache()
            
            # Get stats after invalidation  
            stats_after = NewDownloads.get_disk_cache_stats()
            
            logger.info(f"Disk cache cleared")
            
            return {
                'status': 'success',
                'message': 'Disk cache cleared',
                'cache_stats_before': stats_before,
                'cache_stats_after': stats_after,
                'request_id': request_id,
                'todays_date': datetime.now().strftime('%Y-%m-%d')
            }
        elif cache_type.lower() == "all":
            # Get stats before invalidation
            domain_stats_before = NewDownloads.get_domain_cache_stats()
            disk_stats_before = NewDownloads.get_disk_cache_stats()
            
            # Invalidate all caches
            NewDownloads.invalidate_domain_cache(account if account else None)
            NewDownloads.clear_disk_cache()
            
            # Get stats after invalidation
            domain_stats_after = NewDownloads.get_domain_cache_stats()
            disk_stats_after = NewDownloads.get_disk_cache_stats()
            
            logger.info(f"All caches invalidated - account: {account or 'all'}")
            
            return {
                'status': 'success',
                'message': f"All caches invalidated for {account or 'all accounts'}",
                'domain_cache_before': domain_stats_before,
                'domain_cache_after': domain_stats_after,
                'disk_cache_before': disk_stats_before,
                'disk_cache_after': disk_stats_after,
                'request_id': request_id,
                'todays_date': datetime.now().strftime('%Y-%m-%d')
            }
        else:
            return {
                'status': 'error',
                'message': f"Unknown cache type: {cache_type}. Supported types: 'domain', 'disk', 'all'",
                'request_id': request_id,
                'todays_date': datetime.now().strftime('%Y-%m-%d')
            }
            
    except Exception as e:
        error_msg = f"Failed to invalidate cache: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'request_id': request_id,
            'todays_date': datetime.now().strftime('%Y-%m-%d')
        }

@mcp.tool()
async def debug_request_headers() -> dict:
    """
    Debug tool to show what headers and authentication the server is receiving.
    
    This tool helps diagnose authentication issues, especially when using proxies,
    tunnels, or load balancers that might modify headers.
    
    Returns:
        dict: Current request information and authentication details
    """
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    try:
        # Get the middleware stats to see auth patterns
        middleware_stats = middleware.get_stats() if middleware else {}
        
        return {
            'status': 'success',
            'message': 'Debug information retrieved',
            'server_info': {
                'request_id': request_id,
                'server_uptime_seconds': time.time() - start_time,
                'todays_date': datetime.now().strftime('%Y-%m-%d'),
                'current_time': datetime.now().isoformat()
            },
            'authentication_stats': middleware_stats,
            'debug_note': 'Check server logs for detailed header information on recent requests',
            'troubleshooting_tips': [
                'Compare local vs remote request logs to identify header differences',
                'Check if Cloudflare or proxy is stripping Authorization headers',
                'Verify VS Code MCP client is sending identical headers in both cases',
                'Consider using URL parameter authentication as fallback if headers are being modified'
            ]
        }
        
    except Exception as e:
        error_msg = f"Failed to get debug information: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'request_id': request_id,
            'todays_date': datetime.now().strftime('%Y-%m-%d')
        }

# Security middleware for HTTP mode with enhanced logging and rate limiting
class BearerTokenMiddleware:
    """
    Enhanced middleware to handle Bearer token authentication for HTTP mode.
    Provides secure API key validation with proper error handling, logging, and rate limiting.
    
    Authentication Methods (in order of preference):
    1. Authorization header: "Bearer <token>" (recommended, most secure)
    2. URL parameter: "?key=<token>" (fallback for clients that can't send headers)
    
    Security Note: URL parameters are logged in server logs and browser history.
    Use Authorization headers when possible for better security.
    """
    
    def __init__(self, app, api_key: str):
        self.app = app
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.BearerTokenMiddleware")
        
        # Rate limiting per IP (simple in-memory implementation)
        self.rate_limit_window = 60  # 1 minute
        self.rate_limit_requests = 100  # requests per window
        self.ip_requests: Dict[str, list] = {}
        
        # Authentication statistics
        self.auth_stats = {
            'total_requests': 0,
            'header_auth': 0,
            'url_param_auth': 0,
            'auth_failures': 0,
            'rate_limited': 0
        }
    
    def _cleanup_rate_limit_data(self):
        """Clean up old rate limiting data"""
        current_time = time.time()
        cutoff_time = current_time - self.rate_limit_window
        
        for ip in list(self.ip_requests.keys()):
            self.ip_requests[ip] = [req_time for req_time in self.ip_requests[ip] if req_time > cutoff_time]
            if not self.ip_requests[ip]:
                del self.ip_requests[ip]
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client IP is rate limited"""
        current_time = time.time()
        
        # Clean up old data periodically
        self._cleanup_rate_limit_data()
        
        # Get requests for this IP in the current window
        if client_ip not in self.ip_requests:
            self.ip_requests[client_ip] = []
        
        cutoff_time = current_time - self.rate_limit_window
        recent_requests = [req_time for req_time in self.ip_requests[client_ip] if req_time > cutoff_time]
        
        if len(recent_requests) >= self.rate_limit_requests:
            return True
        
        # Add current request
        self.ip_requests[client_ip] = recent_requests + [current_time]
        return False
    
    def get_stats(self) -> Dict:
        """Get authentication and rate limiting statistics"""
        return {
            **self.auth_stats,
            'unique_ips': len(self.ip_requests),
            'request_tracker_stats': request_tracker.get_stats()
        }
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        
        request = Request(scope, receive)
        client_ip = request.client.host if request.client else 'unknown'
        method = request.method
        path = request.url.path
        
        # Generate unique request ID for tracking
        request_id = str(uuid.uuid4())[:8]
        set_request_context(request_id)
        
        # Start request tracking
        request_info = request_tracker.start_request(request_id, client_ip, method, path)
        
        self.auth_stats['total_requests'] += 1
        
        # Handle CORS preflight requests (OPTIONS method)
        if method == "OPTIONS":
            self.logger.info(f"[{request_id}] Handling CORS preflight request from {client_ip}")
            
            # Get the origin from request headers
            origin = request.headers.get("origin", "*")
            
            # CORS preflight response
            cors_headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, X-API-Key, X-Auth-Token",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400",  # 24 hours
            }
            
            response = JSONResponse(
                status_code=200,
                content={"message": "CORS preflight OK"},
                headers=cors_headers
            )
            request_tracker.end_request(request_id, 200)
            await response(scope, receive, send)
            return
        
        # Check rate limiting (skip for OPTIONS requests)
        if self._is_rate_limited(client_ip):
            self.auth_stats['rate_limited'] += 1
            self.logger.warning(f"Rate limit exceeded for {client_ip} - {len(self.ip_requests.get(client_ip, []))} requests in window")
            
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests from {client_ip}. Limit: {self.rate_limit_requests} requests per {self.rate_limit_window} seconds",
                    "request_id": request_id
                }
            )
            request_tracker.end_request(request_id, 429, "Rate limit exceeded")
            await response(scope, receive, send)
            return
        
        token = None
        auth_method = None
        
        # DEBUG: Log all headers received for troubleshooting Cloudflare tunnel issues
        headers_debug = dict(request.headers)
        self.logger.info(f"[{request_id}] Headers received from {client_ip}: {headers_debug}")
        self.logger.info(f"[{request_id}] Query params: {dict(request.query_params)}")
        self.logger.info(f"[{request_id}] Request method: {method}, path: {path}")
        
        # Additional debugging for proxy/tunnel scenarios
        proxy_headers = [
            'cf-ray', 'cf-connecting-ip', 'cf-ipcountry', 'cf-visitor',
            'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host',
            'x-real-ip', 'x-original-forwarded-for'
        ]
        found_proxy_headers = {h: headers_debug.get(h) for h in proxy_headers if h in headers_debug}
        if found_proxy_headers:
            self.logger.info(f"[{request_id}] Proxy/Cloudflare headers detected: {found_proxy_headers}")
        
        # Check for case variations of Authorization header (including custom headers for proxy compatibility)
        auth_header_variations = [
            'authorization', 'Authorization', 'AUTHORIZATION',
            'x-authorization', 'X-Authorization',
            'x-api-key', 'X-API-Key',  # Custom headers that proxies usually preserve
            'x-auth-token', 'X-Auth-Token'
        ]
        auth_headers_found = {h: headers_debug.get(h) for h in auth_header_variations if h in headers_debug}
        if auth_headers_found:
            self.logger.info(f"[{request_id}] Authorization-related headers found: {list(auth_headers_found.keys())}")
        else:
            self.logger.warning(f"[{request_id}] No Authorization headers found in any variation")
        
        # Primary authentication: Check Authorization header
        auth_header = request.headers.get("Authorization")
        # Fallback: Check custom headers that might bypass proxy filtering
        if not auth_header:
            auth_header = request.headers.get("X-API-Key")
            if auth_header and not auth_header.startswith("Bearer "):
                auth_header = f"Bearer {auth_header}"  # Normalize format
        if not auth_header:
            auth_header = request.headers.get("X-Auth-Token")
            if auth_header and not auth_header.startswith("Bearer "):
                auth_header = f"Bearer {auth_header}"  # Normalize format
                
        self.logger.info(f"[{request_id}] Authorization header: {repr(auth_header)}")
        
        if auth_header:
            if not auth_header.startswith("Bearer "):
                self.auth_stats['auth_failures'] += 1
                self.logger.warning(f"[{request_id}] Invalid Authorization header format from {client_ip}: {repr(auth_header)}")
                response = JSONResponse(
                    status_code=401,
                    content={
                        "error": "Invalid Authorization header format", 
                        "message": "Expected 'Bearer <token>'",
                        "request_id": request_id
                    }
                )
                request_tracker.end_request(request_id, 401, "Invalid auth header format")
                await response(scope, receive, send)
                return
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            auth_method = "header"
            self.auth_stats['header_auth'] += 1
            self.logger.info(f"[{request_id}] Found Bearer token via header (length: {len(token)})")
        
        # Fallback authentication: Check URL parameter
        elif "key" in request.query_params:
            token = request.query_params.get("key")
            auth_method = "url_param"
            self.auth_stats['url_param_auth'] += 1
            self.logger.info(f"[{request_id}] Found key via URL parameter (length: {len(token) if token else 0})")
            
            # Only log this message once per IP to avoid spam
            if not hasattr(self, '_logged_url_param_ips'):
                self._logged_url_param_ips = set()
            
            if client_ip not in self._logged_url_param_ips:
                self.logger.info(f"Using URL parameter authentication from {client_ip} (consider using Authorization header for better security)")
                self._logged_url_param_ips.add(client_ip)
        
        # No authentication provided
        if not token:
            self.auth_stats['auth_failures'] += 1
            self.logger.warning(f"[{request_id}] No authentication provided from {client_ip}")
            self.logger.warning(f"[{request_id}] Available headers: {list(request.headers.keys())}")
            self.logger.warning(f"[{request_id}] Available query params: {list(request.query_params.keys())}")
            response = JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required", 
                    "message": "Provide either 'Authorization: Bearer <token>' header or '?key=<token>' URL parameter",
                    "request_id": request_id
                }
            )
            request_tracker.end_request(request_id, 401, "No authentication")
            await response(scope, receive, send)
            return
        
        # Validate the token using secure comparison to prevent timing attacks
        if not secure_compare(token, self.api_key):
            self.auth_stats['auth_failures'] += 1
            self.logger.warning(f"[{request_id}] Invalid API key via {auth_method} from {client_ip}")
            self.logger.warning(f"[{request_id}] Token received (length {len(token)}): {token[:8]}...{token[-8:] if len(token) > 16 else token}")
            self.logger.warning(f"[{request_id}] Expected token (length {len(self.api_key)}): {self.api_key[:8]}...{self.api_key[-8:] if len(self.api_key) > 16 else self.api_key}")
            response = JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid API key",
                    "request_id": request_id
                }
            )
            request_tracker.end_request(request_id, 401, "Invalid API key")
            await response(scope, receive, send)
            return
        
        # Token is valid, log success and proceed
        self.logger.info(f"[{request_id}] Authentication successful via {auth_method} from {client_ip}")
        self.logger.debug(f"[{request_id}] Proceeding to process request: {method} {path}")
        
        # Add middleware to track successful completion and add CORS headers
        async def tracking_send(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                
                # Add CORS headers to all responses
                if "headers" not in message:
                    message["headers"] = []
                
                origin = request.headers.get("origin", "*")
                cors_headers = [
                    (b"access-control-allow-origin", origin.encode()),
                    (b"access-control-allow-credentials", b"true"),
                    (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                    (b"access-control-allow-headers", b"Authorization, Content-Type, Accept, X-API-Key, X-Auth-Token"),
                ]
                
                # Add CORS headers if not already present
                existing_headers = [h[0].lower() for h in message["headers"]]
                for header_name, header_value in cors_headers:
                    if header_name not in existing_headers:
                        message["headers"].append((header_name, header_value))
                
                request_tracker.end_request(request_id, status_code)
            await send(message)
        
        await self.app(scope, receive, tracking_send)

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="GA4 & GSC MCP Server")
    parser.add_argument("--http", action="store_true", help="Run as HTTP server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for all routines")
    parser.add_argument("--key", type=str, help="API key for authentication (if not provided, a random key will be generated)")
    args = parser.parse_args()

    # Generate API key if not provided
    api_key = args.key if args.key else secrets.token_urlsafe(32)

    def print_github_copilot_mcp_config(host, port, api_key, scheme="http"):
        # If host is 0.0.0.0, suggest localhost for local, or let user replace with public/tunnel hostname
        display_host = host if host != "0.0.0.0" else "localhost"
        url = f"{scheme}://{display_host}:{port}/mcp"
        tools = [
            "query_ga4_data",
            "query_gsc_data", 
            # "query_unified_data",
            "list_ga4_properties",
            "list_gsc_domains",
            "page_performance_ga4",
            "traffic_sources_ga4",
            "audience_analysis_ga4", 
            "revenue_analysis_ga4",
            "page_performance_gsc",
            "query_analysis_gsc",
            "page_query_opportunities_gsc",
            "get_server_stats",
            "invalidate_cache",
            "debug_request_headers"
        ]
        print("\n🔗 Sample mcpServers config for GitHub Copilot coding agent (RECOMMENDED - Header Auth):\n")
        print("{")
        print('  "mcpServers": {')
        print('    "ga4-gsc-mcp": {')
        print('      "type": "http",')
        print(f'      "url": "{url}",')
        print(f'      "headers": {{')
        print(f'        "Authorization": "Bearer {api_key}"')
        print(f'      }},')
        print('      "tools": [')
        for i, tool in enumerate(tools):
            comma = "," if i < len(tools) - 1 else ""
            print(f'        "{tool}"{comma}')
        print('      ]')
        print('    }')
        print('  }')
        print('}')
        print("➡️  Paste this block into your repository’s Copilot coding agent MCP configuration \n")

        
        # Add fallback configuration for clients that don't support Authorization headers
        url_with_key = f"{scheme}://{display_host}:{port}/mcp?key={api_key}"
        print("🔗 Alternative config for clients that don't support Authorization headers (FALLBACK - URL Auth):\n")
        print("{")
        print('  "mcpServers": {')
        print('    "ga4-gsc-mcp": {')
        print('      "type": "http",')
        print(f'      "url": "{url_with_key}",')
        print('      "tools": [')
        for i, tool in enumerate(tools):
            comma = "," if i < len(tools) - 1 else ""
            print(f'        "{tool}"{comma}')
        print('      ]')
        print('    }')
        print('  }')
        print('}')
        print("⚠️  URL-based auth exposes the key in logs. Use header auth when possible.\n")
    # Patch: Set a global debug flag and patch all tool functions to pass debug if not explicitly set
    DEBUG_FLAG = args.debug

    # Patch all mcp.tool functions to inject debug if not set
    import functools
    for tool_name in [
        "query_ga4_data",
        "query_gsc_data",
        # "query_unified_data",
        "list_ga4_properties",
        "list_gsc_domains",
        "page_performance_ga4",
        "traffic_sources_ga4", 
        "audience_analysis_ga4",
        "revenue_analysis_ga4",
        "page_performance_gsc",
        "query_analysis_gsc",
        "page_query_opportunities_gsc",
        "get_server_stats",
        "invalidate_cache",
        "debug_request_headers"
    ]:
        orig_func = getattr(mcp, tool_name, None)
        if orig_func is not None:
            async def wrapper(*a, __orig_func=orig_func, **kw):
                if 'debug' not in kw:
                    kw['debug'] = DEBUG_FLAG
                return await __orig_func(*a, **kw)
            setattr(mcp, tool_name, wrapper)

    if args.http:
        print(f"Starting MCP HTTP server on {args.host}:{args.port}")
        print_github_copilot_mcp_config(args.host, args.port, api_key, scheme="http")
        import uvicorn
        
        # Create the streamable HTTP app and add authentication middleware
        app = mcp.streamable_http_app()
        
        # Use the improved BearerTokenMiddleware with secure comparison and logging
        middleware = BearerTokenMiddleware(app, api_key)
        
        logger.info(f"MCP server starting with enhanced monitoring and security features")
        logger.info(f"Rate limiting: {middleware.rate_limit_requests} requests per {middleware.rate_limit_window} seconds per IP")
        
        uvicorn.run(middleware, host=args.host, port=args.port)
    else:
        print("Starting MCP stdio server")
        mcp.run()

    #ok
    