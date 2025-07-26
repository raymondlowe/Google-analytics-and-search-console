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
from typing import Dict, Optional
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from datetime import datetime

# Suppress Google API warnings about file_cache and oauth2client
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client')

# Import our existing modules
import GA4query3
import NewDownloads
from NewDownloads import async_persistent_cache

# Configure enhanced logging with structured format but simpler format for compatibility
logging.basicConfig(
    level=logging.INFO,
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

mcp = FastMCP("ga4-gsc-mcp")

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

@mcp.tool()
async def query_ga4_data(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", metrics: str = "screenPageViews,totalAdRevenue,sessions", dimensions: str = "pagePath", debug: bool = False) -> dict:
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
    
    Filtering Behavior:
    - When property_id is specified: No domain filtering applied (for maximum data reliability)
    - When property_id is omitted: domain_filter applies to all properties (for cross-property filtering)
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional, queries all properties if not specified)
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
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
    if not validate_date_range(start_date, end_date):
        error_msg = "Invalid date range"
        logger.warning(f"[{request_id}] GA4 query failed - {error_msg}: {start_date} to {end_date}")
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
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
        if property_id:
            logger.info(f"[{request_id}] Querying single GA4 property: {property_id}")
            # When property_id is specified, don't apply domain filtering for better reliability
            # Property ID already targets the specific property, additional filtering can exclude valid data
            df = GA4query3.produce_report(
                start_date=start_date,
                end_date=end_date,
                property_id=property_id,
                property_name="MCP_Property",
                account=auth_identifier,
                filter_expression=None,  # No domain filtering when property_id is specified
                dimensions=dimensions,
                metrics=metrics,
                debug=debug
            )
        else:
            logger.info(f"[{request_id}] Querying all available GA4 properties")
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                error_msg = "No GA4 properties found"
                logger.warning(f"[{request_id}] GA4 query failed - {error_msg}")
                return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
            
            logger.info(f"[{request_id}] Found {len(properties_df)} GA4 properties to query")
            combined_df = pd.DataFrame()
            errors = []
            
            # Apply domain filtering only when querying all properties (to filter results across properties)
            filter_expr = f"hostname=={domain_filter}" if domain_filter else None
            if domain_filter:
                logger.info(f"[{request_id}] Applying domain filter for all properties: {domain_filter}")
            
            for idx, row in properties_df.iterrows():
                pid = row.get("property_id") or row.get("id")
                if not pid:
                    continue
                
                property_name = row.get("displayName", "Property")
                logger.debug(f"Querying GA4 property: {property_name} ({pid})")
                
                try:
                    df_prop = GA4query3.produce_report(
                        start_date=start_date,
                        end_date=end_date,
                        property_id=pid,
                        property_name=property_name,
                        account=auth_identifier,
                        filter_expression=filter_expr,
                        dimensions=dimensions,
                        metrics=metrics,
                        debug=debug
                    )
                    if df_prop is not None and not df_prop.empty:
                        combined_df = pd.concat([combined_df, df_prop], ignore_index=True)
                        logger.debug(f"Property {property_name} returned {len(df_prop)} rows")
                except Exception as prop_error:
                    # Collect individual property errors but continue processing
                    error_msg = f"Error for property {property_name} ({pid}): {str(prop_error)}"
                    errors.append(error_msg)
                    logger.warning(f"Property query failed: {error_msg}")
                    if debug:
                        print(f"Property error: {error_msg}")
            
            df = combined_df if not combined_df.empty else None
            
            # If we have errors but some data, include error details in response
            if errors and df is not None and not df.empty:
                duration = time.time() - start_time
                logger.info(f"GA4 query completed with partial success - {len(df)} rows, {len(errors)} errors, {duration:.2f}s")
                return {
                    "status": "partial_success",
                    "message": f"Retrieved {len(df)} rows of GA4 data with {len(errors)} property errors",
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "data": df.to_dict('records'),
                    "row_count": len(df),
                    "source": "ga4",
                    "errors": errors,
                    "request_id": request_id,
                    "duration_seconds": round(duration, 2),
                    "todays_date": datetime.now().strftime('%Y-%m-%d')
                }
            elif errors and (df is None or df.empty):
                # All properties failed, return error with all details
                error_msg = f"All properties failed: {'; '.join(errors)}"
                logger.error(f"GA4 query failed completely - {error_msg}")
                return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
        
        if df is not None and not df.empty:
            duration = time.time() - start_time
            logger.info(f"GA4 query successful - {len(df)} rows retrieved in {duration:.2f}s")
            response = {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GA4 data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "ga4",
                "request_id": request_id,
                "duration_seconds": round(duration, 2),
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
            return response
        else:
            duration = time.time() - start_time
            logger.info(f"GA4 query completed - no data found in {duration:.2f}s")
            response = {
                "status": "success", 
                "message": "No GA4 data found for the specified criteria", 
                "data": [], 
                "row_count": 0, 
                "source": "ga4",
                "request_id": request_id,
                "duration_seconds": round(duration, 2),
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
            return response
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"GA4 query failed: {str(e)}"
        logger.error(f"GA4 query exception - {error_msg}, duration: {duration:.2f}s", exc_info=True)
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}

@mcp.tool()
async def query_gsc_data(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", dimensions: str = "page,query,country,device", search_type: str = "web", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Filter by specific domain (optional, queries all domains if not specified)
        dimensions: Comma-separated dimensions (default: page,query,country,device)
        search_type: Type of search data - web, image, video (default: web)
        debug: Enable debug output
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    set_request_context(request_id)
    
    logger.info(f"Starting GSC query - dates: {start_date} to {end_date}, domain: {domain or 'all'}, search_type: {search_type}")
    
    if not start_date or not end_date:
        error_msg = "start_date and end_date are required parameters"
        logger.warning(f"GSC query failed - {error_msg}")
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
    if not validate_date_range(start_date, end_date):
        error_msg = "Invalid date range"
        logger.warning(f"GSC query failed - {error_msg}: {start_date} to {end_date}")
        return {"status": "error", "message": error_msg, "request_id": request_id, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    
    try:
        logger.info(f"Fetching GSC data with dimensions: {dimensions}")
        
        # Use the optimized async version for better performance
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
            duration = time.time() - start_time
            logger.info(f"GSC query successful - {len(df)} rows retrieved in {duration:.2f}s")
            return {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GSC data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "domain": domain,
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "gsc",
                "request_id": request_id,
                "duration_seconds": round(duration, 2),
                "todays_date": datetime.now().strftime('%Y-%m-%d')
            }
        else:
            duration = time.time() - start_time
            logger.info(f"GSC query completed - no data found in {duration:.2f}s")
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

@mcp.tool()
async def query_unified_data(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", ga4_property_id: str = "", data_sources: list = ["ga4", "gsc"], debug: bool = False) -> dict:
    """
    Query both GA4 and GSC data for comprehensive cross-platform analysis.
    
    Business Use Cases:
    - Compare organic search performance (GSC) with actual user behavior (GA4)
    - Identify pages with high search impressions but low GA4 pageviews (optimization opportunity)
    - Cross-reference revenue data with search performance
    - Comprehensive SEO and monetization analysis
    
    This tool combines data from both platforms to provide insights that neither platform 
    alone can offer, ideal for holistic website performance analysis.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Domain to analyze (optional, analyzes all domains if not specified)
        ga4_property_id: Specific GA4 property ID (optional)
        data_sources: List of data sources to query - ["ga4"], ["gsc"], or ["ga4", "gsc"] (default: both)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters", "todays_date": datetime.now().strftime('%Y-%m-%d')}
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range", "todays_date": datetime.now().strftime('%Y-%m-%d')}
    results = []
    errors = []
    if "ga4" in data_sources:
        ga4_result = await query_ga4_data(auth_identifier, start_date, end_date, ga4_property_id, domain, debug=debug)
        if ga4_result.get("status") == "success":
            results.append(ga4_result)
        else:
            errors.append(ga4_result.get("message"))
    if "gsc" in data_sources:
        gsc_result = await query_gsc_data(auth_identifier, start_date, end_date, domain, debug=debug)
        if gsc_result.get("status") == "success":
            results.append(gsc_result)
        else:
            errors.append(gsc_result.get("message"))
    if not results and errors:
        return {"status": "error", "message": "; ".join(errors), "todays_date": datetime.now().strftime('%Y-%m-%d')}
    if errors:
        return {"status": "partial_success", "message": f"Retrieved data from {len(results)} source(s) with {len(errors)} error(s)", "errors": errors, "results": results, "todays_date": datetime.now().strftime('%Y-%m-%d')}
    return {"status": "success", "message": f"Retrieved data from {len(results)} source(s)", "results": results, "todays_date": datetime.now().strftime('%Y-%m-%d')}

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
async def page_performance_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional)
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
async def traffic_sources_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional)
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
async def audience_analysis_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional)
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
async def revenue_analysis_ga4(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional)
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
async def page_performance_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Filter by specific domain (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for page performance analysis
    dimensions = "page,country,device"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache GSC query analysis for 1 hour
async def query_analysis_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Filter by specific domain (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for query analysis
    dimensions = "query,country,device"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

@mcp.tool()
@async_persistent_cache(expire_time=3600)  # Cache GSC page-query opportunities for 1 hour
async def page_query_opportunities_gsc(start_date: str, end_date: str, auth_identifier: str = "", domain: str = "", debug: bool = False) -> dict:
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Filter by specific domain (optional)
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
                'cache_hit_rate': (domain_cache_stats.get('valid_entries', 0) / 
                                 max(domain_cache_stats.get('total_entries', 1), 1)) * 100 if domain_cache_stats.get('total_entries', 0) > 0 else 0
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
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        domain: Filter by specific domain (optional)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    
    # Use specific dimensions optimized for page-query opportunity analysis
    dimensions = "page,query"
    
    return await query_gsc_data(start_date, end_date, auth_identifier, domain, dimensions, "web", debug)

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
        
        # Check rate limiting
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
        
        # Primary authentication: Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            if not auth_header.startswith("Bearer "):
                self.auth_stats['auth_failures'] += 1
                self.logger.warning(f"Invalid Authorization header format from {client_ip}")
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
        
        # Fallback authentication: Check URL parameter
        elif "key" in request.query_params:
            token = request.query_params.get("key")
            auth_method = "url_param"
            self.auth_stats['url_param_auth'] += 1
            
            # Only log this message once per IP to avoid spam
            if not hasattr(self, '_logged_url_param_ips'):
                self._logged_url_param_ips = set()
            
            if client_ip not in self._logged_url_param_ips:
                self.logger.info(f"Using URL parameter authentication from {client_ip} (consider using Authorization header for better security)")
                self._logged_url_param_ips.add(client_ip)
        
        # No authentication provided
        if not token:
            self.auth_stats['auth_failures'] += 1
            self.logger.warning(f"No authentication provided from {client_ip}")
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
            self.logger.warning(f"Invalid API key via {auth_method} from {client_ip}")
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
        self.logger.debug(f"Authentication successful via {auth_method} from {client_ip}")
        
        # Add middleware to track successful completion
        async def tracking_send(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
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
            "query_unified_data",
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
            "invalidate_cache"
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
        "query_unified_data",
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
        "invalidate_cache"
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