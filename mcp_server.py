#!/usr/bin/env python3
"""
MCP Server for Google Analytics 4 and Search Console Data
Designed for AI model access with tools for querying GA4 and GSC data.
"""

import asyncio
import logging
import json
import pandas as pd
from mcp.server.fastmcp import FastMCP
from datetime import datetime

# Import our existing modules
import GA4query3
import NewDownloads

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def get_default_date_range(days: int = 30) -> dict:
    """Get default date range (last N days)"""
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=days)
    return {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d')
    }

@mcp.tool()
async def query_ga4_data(auth_identifier: str, start_date: str = "", end_date: str = "", property_id: str = "", domain_filter: str = "", metrics: str = "screenPageViews,totalAdRevenue", dimensions: str = "pagePath", debug: bool = False) -> dict:
    """Query Google Analytics 4 data for pageviews and ad revenue"""
    # Use get_default_date_range if dates not provided
    if not auth_identifier:
        return {"status": "error", "message": "auth_identifier is required"}
    if not start_date or not end_date:
        date_range = get_default_date_range()
        start_date = start_date or date_range["start_date"]
        end_date = end_date or date_range["end_date"]
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range"}
    # Use correct filter field for GA4 API (dimensionFilter)
    filter_expr = None
    if domain_filter:
        # Suggest using dimensionFilter for hostname
        filter_expr = {"dimensionFilter": {"filter": f"hostname=={domain_filter}"}}
    try:
        if property_id:
            try:
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
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"GA4 query failed for property {property_id}: {str(e)}",
                    "suggestion": "Check if the property ID is correct and if the filter field is supported. If you see 'Unknown field for RunReportRequest: filter', try removing or updating the filter."
                }
        else:
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                return {"status": "error", "message": "No GA4 properties found", "suggestion": "Authenticate with a Google account that has GA4 properties."}
            combined_df = pd.DataFrame()
            for _, row in properties_df.iterrows():
                pid = row.get("property_id") or row.get("id")
                if not pid:
                    continue
                try:
                    df_prop = GA4query3.produce_report(
                        start_date=start_date,
                        end_date=end_date,
                        property_id=pid,
                        property_name=row.get("displayName", "Property"),
                        account=auth_identifier,
                        filter_expression=filter_expr,
                        dimensions=dimensions,
                        metrics=metrics,
                        debug=debug
                    )
                    if df_prop is not None and not df_prop.empty:
                        combined_df = pd.concat([combined_df, df_prop], ignore_index=True)
                except Exception as e:
                    # Collect error for this property, but continue
                    if "errors" not in locals():
                        errors = []
                    errors.append(f"Property {pid}: {str(e)}")
            df = combined_df if not combined_df.empty else None
        if df is not None and not df.empty:
            return {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GA4 data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "ga4",
                "errors": locals().get("errors", [])
            }
        else:
            return {
                "status": "success",
                "message": "No GA4 data found for the specified criteria",
                "data": [],
                "row_count": 0,
                "source": "ga4",
                "errors": locals().get("errors", [])
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"GA4 query failed: {str(e)}",
            "suggestion": "Check your parameters, authentication, and try again. If the error persists, try a different date range or property."
        }

@mcp.tool()
async def query_gsc_data(auth_identifier: str = "", start_date: str = "", end_date: str = "", domain: str = "", dimensions: str = "page,query,country,device", search_type: str = "web", debug: bool = False) -> dict:
    """Query Google Search Console data for clicks, impressions, position, devices, and countries"""
    if not start_date or not end_date:
        date_range = get_default_date_range()
        start_date = start_date or date_range["start_date"]
        end_date = end_date or date_range["end_date"]
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range"}
    try:
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
        except Exception as e:
            return {
                "status": "error",
                "message": f"GSC query failed: {str(e)}",
                "suggestion": "Check your authentication, domain, and date range. If you see a pandas error like 'Columns must be same length as key', the data source may be malformed. Try again later or with different parameters."
            }
        if df is not None and not df.empty:
            return {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GSC data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "domain": domain,
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "gsc"
            }
        else:
            return {
                "status": "success",
                "message": "No GSC data found for the specified criteria",
                "data": [],
                "row_count": 0,
                "source": "gsc"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"GSC query failed: {str(e)}",
            "suggestion": "Check your parameters, authentication, and try again."
        }

@mcp.tool()
async def query_unified_data(auth_identifier: str, domain: str = "", start_date: str = "", end_date: str = "", ga4_property_id: str = "", data_sources: list = ["ga4", "gsc"], debug: bool = False) -> dict:
    """Query both GA4 and GSC data for a domain in a single request - ideal for comprehensive analysis"""
    if not auth_identifier:
        return {"status": "error", "message": "auth_identifier is required"}
    if not start_date or not end_date:
        date_range = get_default_date_range()
        start_date = start_date or date_range["start_date"]
        end_date = end_date or date_range["end_date"]
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range"}
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
        return {"status": "error", "message": "; ".join(errors)}
    if errors:
        return {"status": "partial_success", "message": f"Retrieved data from {len(results)} source(s) with {len(errors)} error(s)", "errors": errors, "results": results}
    return {"status": "success", "message": f"Retrieved data from {len(results)} source(s)", "results": results}

@mcp.tool()
async def list_ga4_properties(auth_identifier: str, debug: bool = False) -> dict:
    """List all available GA4 properties for the authenticated account"""
    try:
        properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
        if properties_df is not None and not properties_df.empty:
            return {
                "status": "success",
                "message": f"Found {len(properties_df)} GA4 properties",
                "properties": properties_df.to_dict('records')
            }
        else:
            return {
                "status": "success",
                "message": "No GA4 properties found",
                "properties": [],
                "suggestion": "Authenticate with a Google account that has GA4 properties."
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list GA4 properties: {str(e)}",
            "suggestion": "Check your authentication and try again."
        }

@mcp.tool()
async def list_gsc_domains(auth_identifier: str = "", debug: bool = False) -> dict:
    """List all available Google Search Console domains for the authenticated account"""
    try:
        domains_df = NewDownloads.list_search_console_sites(google_account=auth_identifier, debug=debug)
        if domains_df is not None and not domains_df.empty:
            return {
                "status": "success",
                "message": f"Found {len(domains_df)} GSC domains",
                "domains": domains_df.to_dict('records')
            }
        else:
            return {
                "status": "success",
                "message": "No GSC domains found",
                "domains": [],
                "suggestion": "Authenticate with a Google account that has Search Console access."
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list GSC domains: {str(e)}",
            "suggestion": "Check your authentication and try again."
        }

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="GA4 & GSC MCP Server")
    parser.add_argument("--http", action="store_true", help="Run as HTTP server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output for all routines")
    args = parser.parse_args()

    def print_github_copilot_mcp_config(host, port, scheme="http"):
        # If host is 0.0.0.0, suggest localhost for local, or let user replace with public/tunnel hostname
        display_host = host if host != "0.0.0.0" else "localhost"
        url = f"{scheme}://{display_host}:{port}/mcp"
        tools = [
            {"name": "query_ga4_data", "description": "Query Google Analytics 4 data for pageviews and ad revenue."},
            {"name": "query_gsc_data", "description": "Query Google Search Console data for clicks, impressions, etc."},
            {"name": "query_unified_data", "description": "Query both GA4 and GSC data for a domain in a single request."},
            {"name": "list_ga4_properties", "description": "List all available GA4 properties for the authenticated account."},
            {"name": "list_gsc_domains", "description": "List all available Google Search Console domains for the authenticated account."}
        ]
        print("\n🔗 Sample mcpServers config for GitHub Copilot coding agent:\n")
        print("{")
        print('  "mcpServers": {')
        print('    "ga4-gsc-mcp": {')
        print('      "type": "http",')
        print(f'      "url": "{url}",')
        print('      "tools": [')
        for i, tool in enumerate(tools):
            comma = "," if i < len(tools) - 1 else ""
            print(f'        {{ "name": "{tool["name"]}", "description": "{tool["description"]}" }}{comma}')
        print('      ]')
        print('    }')
        print('  }')
        print('}')
        print("➡️  Paste this block into your repository’s Copilot coding agent MCP configuration \n")

    # Patch: Set a global debug flag and patch all tool functions to pass debug if not explicitly set
    DEBUG_FLAG = args.debug

    # Patch all mcp.tool functions to inject debug if not set
    import functools
    for tool_name in [
        "query_ga4_data",
        "query_gsc_data",
        "query_unified_data",
        "list_ga4_properties",
        "list_gsc_domains"
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
        print_github_copilot_mcp_config(args.host, args.port, scheme="http")
        import uvicorn
        # Create the streamable HTTP app and run it with uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        print("Starting MCP stdio server")
        mcp.run()