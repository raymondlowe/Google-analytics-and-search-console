#!/usr/bin/env python3
"""
MCP Server for Google Analytics 4 and Search Console Data
Designed for AI model access with tools for querying GA4 and GSC data.
"""

import asyncio
from typing import Any, Sequence, Optional, Dict, List
from datetime import datetime, timedelta
import logging

from mcp.server import Server
from mcp.server.models import InitializationOptions  
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    JSONRPCError,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
)
import pandas as pd
import json

# Import our existing modules
import GA4query3
import NewDownloads

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("ga4-gsc-mcp")

# Helper functions
def validate_date_range(start_date: str, end_date: str) -> bool:
    """Validate date range format and logic"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        return start <= end
    except ValueError:
        return False

def get_default_date_range(days: int = 30) -> Dict[str, str]:
    """Get default date range (last N days)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
    }

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools for the MCP server"""
    return [
        Tool(
            name="query_ga4_data",
            description="Query Google Analytics 4 data for pageviews and ad revenue",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_identifier": {
                        "type": "string",
                        "description": "Authentication identifier for OAuth tokens"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "end_date": {
                        "type": "string", 
                        "description": "End date in YYYY-MM-DD format (optional, defaults to today)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "property_id": {
                        "type": "string",
                        "description": "GA4 Property ID (optional, queries all properties if not specified)"
                    },
                    "domain_filter": {
                        "type": "string",
                        "description": "Filter results to a specific domain (optional)"
                    },
                    "metrics": {
                        "type": "string",
                        "description": "Comma-separated metrics (default: screenPageViews,totalAdRevenue)",
                        "default": "screenPageViews,totalAdRevenue"
                    },
                    "dimensions": {
                        "type": "string", 
                        "description": "Comma-separated dimensions (default: pagePath)",
                        "default": "pagePath"
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Enable debug output",
                        "default": False
                    }
                },
                "required": ["auth_identifier"]
            }
        ),
        Tool(
            name="query_gsc_data",
            description="Query Google Search Console data for clicks, impressions, position, devices, and countries",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_identifier": {
                        "type": "string",
                        "description": "Authentication identifier for OAuth tokens (can be empty for default)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional, defaults to today)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Single domain to query (e.g., example.com) - optional but recommended"
                    },
                    "dimensions": {
                        "type": "string",
                        "description": "Comma-separated dimensions (default: page,query,country,device)",
                        "default": "page,query,country,device"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Search type: web, image, or video",
                        "enum": ["web", "image", "video"],
                        "default": "web"
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Enable debug output",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query_unified_data",
            description="Query both GA4 and GSC data for a domain in a single request - ideal for comprehensive analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_identifier": {
                        "type": "string",
                        "description": "Authentication identifier for OAuth tokens"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to analyze (e.g., example.com)"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)",
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (optional, defaults to today)", 
                        "pattern": r"^\d{4}-\d{2}-\d{2}$"
                    },
                    "ga4_property_id": {
                        "type": "string",
                        "description": "GA4 Property ID (optional, auto-detects if not specified)"
                    },
                    "data_sources": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["ga4", "gsc"]
                        },
                        "description": "Data sources to include",
                        "default": ["ga4", "gsc"]
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Enable debug output",
                        "default": False
                    }
                },
                "required": ["auth_identifier"]
            }
        ),
        Tool(
            name="list_ga4_properties",
            description="List all available GA4 properties for the authenticated account",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_identifier": {
                        "type": "string",
                        "description": "Authentication identifier for OAuth tokens"
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Enable debug output",
                        "default": False
                    }
                },
                "required": ["auth_identifier"]
            }
        ),
        Tool(
            name="list_gsc_domains",
            description="List all available Google Search Console domains for the authenticated account",
            inputSchema={
                "type": "object",
                "properties": {
                    "auth_identifier": {
                        "type": "string",
                        "description": "Authentication identifier for OAuth tokens (can be empty for default)"
                    },
                    "debug": {
                        "type": "boolean",
                        "description": "Enable debug output",
                        "default": False
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "query_ga4_data":
            return await handle_query_ga4_data(arguments)
        elif name == "query_gsc_data":
            return await handle_query_gsc_data(arguments)
        elif name == "query_unified_data":
            return await handle_query_unified_data(arguments)
        elif name == "list_ga4_properties":
            return await handle_list_ga4_properties(arguments)
        elif name == "list_gsc_domains":
            return await handle_list_gsc_domains(arguments)
        else:
            raise JSONRPCError(METHOD_NOT_FOUND, f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}")
        raise JSONRPCError(INTERNAL_ERROR, f"Tool execution failed: {str(e)}")

async def handle_query_ga4_data(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle GA4 data query"""
    auth_identifier = arguments.get("auth_identifier")
    if not auth_identifier:
        raise JSONRPCError(INVALID_PARAMS, "auth_identifier is required")
    
    # Use provided dates or defaults
    if "start_date" in arguments and "end_date" in arguments:
        start_date = arguments["start_date"]
        end_date = arguments["end_date"]
    else:
        date_range = get_default_date_range()
        start_date = arguments.get("start_date", date_range["start_date"])
        end_date = arguments.get("end_date", date_range["end_date"])
    
    if not validate_date_range(start_date, end_date):
        raise JSONRPCError(INVALID_PARAMS, "Invalid date range")
    
    property_id = arguments.get("property_id")
    domain_filter = arguments.get("domain_filter")
    metrics = arguments.get("metrics", "screenPageViews,totalAdRevenue")
    dimensions = arguments.get("dimensions", "pagePath")
    debug = arguments.get("debug", False)
    
    # Build filter expression for domain filtering
    filter_expr = None
    if domain_filter:
        filter_expr = f"hostname=={domain_filter}"
    
    try:
        if property_id:
            # Single property
            df = GA4query3.produce_report(
                start_date=start_date,
                end_date=end_date,
                property_id=property_id,
                property_name="MCP_Property",
                account=auth_identifier,
                filter_expression=filter_expr,
                dimensions=dimensions,
                metrics=metrics,
                debug=debug
            )
        else:
            # All properties
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                return [TextContent(type="text", text="No GA4 properties found")]
            
            combined_df = pd.DataFrame()
            for _, row in properties_df.iterrows():
                prop_id = str(row['property_id'])
                prop_name = str(row['property_name'])
                
                df_property = GA4query3.produce_report(
                    start_date=start_date,
                    end_date=end_date,
                    property_id=prop_id,
                    property_name=prop_name,
                    account=auth_identifier,
                    filter_expression=filter_expr,
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                if df_property is not None:
                    df_property['property_id'] = prop_id
                    df_property['property_name'] = prop_name
                    combined_df = pd.concat([combined_df, df_property], ignore_index=True)
            
            df = combined_df if not combined_df.empty else None

        if df is not None and not df.empty:
            result = {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GA4 data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "ga4"
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        else:
            return [TextContent(type="text", text="No GA4 data found for the specified criteria")]
            
    except Exception as e:
        raise JSONRPCError(INTERNAL_ERROR, f"GA4 query failed: {str(e)}")

async def handle_query_gsc_data(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle GSC data query"""
    auth_identifier = arguments.get("auth_identifier", "")
    
    # Use provided dates or defaults
    if "start_date" in arguments and "end_date" in arguments:
        start_date = arguments["start_date"]
        end_date = arguments["end_date"]
    else:
        date_range = get_default_date_range()
        start_date = arguments.get("start_date", date_range["start_date"])
        end_date = arguments.get("end_date", date_range["end_date"])
    
    if not validate_date_range(start_date, end_date):
        raise JSONRPCError(INVALID_PARAMS, "Invalid date range")
    
    domain = arguments.get("domain")
    dimensions = arguments.get("dimensions", "page,query,country,device")
    search_type = arguments.get("search_type", "web")
    debug = arguments.get("debug", False)
    
    try:
        df = NewDownloads.fetch_search_console_data(
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
            result = {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GSC data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "domain": domain,
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "gsc"
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        else:
            return [TextContent(type="text", text="No GSC data found for the specified criteria")]
            
    except Exception as e:
        raise JSONRPCError(INTERNAL_ERROR, f"GSC query failed: {str(e)}")

async def handle_query_unified_data(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle unified data query (both GA4 and GSC)"""
    auth_identifier = arguments.get("auth_identifier")
    if not auth_identifier:
        raise JSONRPCError(INVALID_PARAMS, "auth_identifier is required")
    
    domain = arguments.get("domain")
    data_sources = arguments.get("data_sources", ["ga4", "gsc"])
    
    # Use provided dates or defaults
    if "start_date" in arguments and "end_date" in arguments:
        start_date = arguments["start_date"]
        end_date = arguments["end_date"]
    else:
        date_range = get_default_date_range()
        start_date = arguments.get("start_date", date_range["start_date"])
        end_date = arguments.get("end_date", date_range["end_date"])
    
    if not validate_date_range(start_date, end_date):
        raise JSONRPCError(INVALID_PARAMS, "Invalid date range")
    
    ga4_property_id = arguments.get("ga4_property_id")
    debug = arguments.get("debug", False)
    
    results = []
    errors = []
    
    # Query GA4 data if requested
    if "ga4" in data_sources:
        try:
            ga4_args = {
                "auth_identifier": auth_identifier,
                "start_date": start_date,
                "end_date": end_date,
                "property_id": ga4_property_id,
                "domain_filter": domain,
                "dimensions": "pagePath",
                "metrics": "screenPageViews,totalAdRevenue",
                "debug": debug
            }
            ga4_result = await handle_query_ga4_data(ga4_args)
            results.extend(ga4_result)
        except Exception as e:
            errors.append(f"GA4 query failed: {str(e)}")
    
    # Query GSC data if requested
    if "gsc" in data_sources:
        try:
            gsc_args = {
                "auth_identifier": auth_identifier,
                "start_date": start_date,
                "end_date": end_date,
                "domain": domain,
                "dimensions": "page,query,country,device",
                "search_type": "web",
                "debug": debug
            }
            gsc_result = await handle_query_gsc_data(gsc_args)
            results.extend(gsc_result)
        except Exception as e:
            errors.append(f"GSC query failed: {str(e)}")
    
    if not results and errors:
        raise JSONRPCError(INTERNAL_ERROR, "; ".join(errors))
    
    if errors:
        # Partial success - include errors in the response
        combined_result = {
            "status": "partial_success",
            "message": f"Retrieved data from {len(results)} source(s) with {len(errors)} error(s)",
            "errors": errors,
            "results": [json.loads(result.text) for result in results]
        }
    else:
        combined_result = {
            "status": "success",
            "message": f"Retrieved data from {len(results)} source(s)",
            "results": [json.loads(result.text) for result in results]
        }
    
    return [TextContent(type="text", text=json.dumps(combined_result, indent=2))]

async def handle_list_ga4_properties(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle listing GA4 properties"""
    auth_identifier = arguments.get("auth_identifier")
    if not auth_identifier:
        raise JSONRPCError(INVALID_PARAMS, "auth_identifier is required")
    
    debug = arguments.get("debug", False)
    
    try:
        properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
        if properties_df is not None and not properties_df.empty:
            result = {
                "status": "success",
                "message": f"Found {len(properties_df)} GA4 properties",
                "properties": properties_df.to_dict('records')
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        else:
            return [TextContent(type="text", text="No GA4 properties found")]
    except Exception as e:
        raise JSONRPCError(INTERNAL_ERROR, f"Failed to list GA4 properties: {str(e)}")

async def handle_list_gsc_domains(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle listing GSC domains"""
    auth_identifier = arguments.get("auth_identifier", "")
    debug = arguments.get("debug", False)
    
    try:
        domains_df = NewDownloads.list_search_console_sites(google_account=auth_identifier, debug=debug)
        if domains_df is not None and not domains_df.empty:
            result = {
                "status": "success",
                "message": f"Found {len(domains_df)} GSC domains",
                "domains": domains_df.to_dict('records')
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        else:
            return [TextContent(type="text", text="No GSC domains found")]
    except Exception as e:
        raise JSONRPCError(INTERNAL_ERROR, f"Failed to list GSC domains: {str(e)}")

async def main():
    """Main entry point for the MCP server"""
    # Run the server using stdio
    await server.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())