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
async def query_ga4_data(start_date: str, end_date: str, auth_identifier: str = "", property_id: str = "", domain_filter: str = "", metrics: str = "screenPageViews,totalAdRevenue", dimensions: str = "pagePath", debug: bool = False) -> dict:
    """
    Query Google Analytics 4 data for comprehensive website analytics.
    
    Business Use Cases:
    - Track page performance and visitor engagement
    - Monitor AdSense revenue by page and traffic source
    - Analyze user behavior patterns and demographics
    - Identify top-performing content for SEO optimization
    
    Common Dimensions: pagePath, hostname, country, deviceCategory, sessionSource, sessionMedium, 
                      sessionCampaign, date, hour, dayOfWeek, language, operatingSystem, browser
    
    Common Metrics: screenPageViews, sessions, totalUsers, activeUsers, averageSessionDuration,
                   bounceRate, totalAdRevenue, screenPageViewsPerSession, sessionDuration
    
    Example: Find top revenue-generating pages by traffic source:
    - dimensions: "pagePath,sessionSource,sessionMedium"  
    - metrics: "screenPageViews,totalAdRevenue,sessions"
    
    Args:
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        property_id: Specific GA4 property ID (optional, queries all properties if not specified)
        domain_filter: Filter by hostname (optional)
        metrics: Comma-separated metrics (default: screenPageViews,totalAdRevenue)
        dimensions: Comma-separated dimensions (default: pagePath)
        debug: Enable debug output
    """
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range"}
    filter_expr = f"hostname=={domain_filter}" if domain_filter else None
    try:
        if property_id:
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
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                return {"status": "error", "message": "No GA4 properties found"}
            combined_df = pd.DataFrame()
            errors = []
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
                except Exception as prop_error:
                    # Collect individual property errors but continue processing
                    error_msg = f"Error for property {row.get('displayName', 'Unknown')} ({pid}): {str(prop_error)}"
                    errors.append(error_msg)
                    if debug:
                        print(f"Property error: {error_msg}")
            df = combined_df if not combined_df.empty else None
            # If we have errors but some data, include error details in response
            if errors and df is not None and not df.empty:
                return {
                    "status": "partial_success",
                    "message": f"Retrieved {len(df)} rows of GA4 data with {len(errors)} property errors",
                    "date_range": {"start_date": start_date, "end_date": end_date},
                    "data": df.to_dict('records'),
                    "row_count": len(df),
                    "source": "ga4",
                    "errors": errors
                }
            elif errors and (df is None or df.empty):
                # All properties failed, return error with all details
                return {"status": "error", "message": f"All properties failed: {'; '.join(errors)}"}
        if df is not None and not df.empty:
            return {
                "status": "success",
                "message": f"Retrieved {len(df)} rows of GA4 data",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "data": df.to_dict('records'),
                "row_count": len(df),
                "source": "ga4"
            }
        else:
            return {"status": "success", "message": "No GA4 data found for the specified criteria", "data": [], "row_count": 0, "source": "ga4"}
    except Exception as e:
        return {"status": "error", "message": f"GA4 query failed: {str(e)}"}

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
    if not start_date or not end_date:
        return {"status": "error", "message": "start_date and end_date are required parameters"}
    if not validate_date_range(start_date, end_date):
        return {"status": "error", "message": "Invalid date range"}
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
            return {"status": "success", "message": "No GSC data found for the specified criteria", "data": [], "row_count": 0, "source": "gsc"}
    except Exception as e:
        return {"status": "error", "message": f"GSC query failed: {str(e)}"}

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
        return {"status": "error", "message": "start_date and end_date are required parameters"}
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
async def list_ga4_properties(auth_identifier: str = "", debug: bool = False) -> dict:
    """
    List all available GA4 properties for the authenticated account.
    
    Use this tool to discover which GA4 properties you have access to before running
    detailed analytics queries. Essential for multi-property setups or when you need
    to identify the correct property_id for focused analysis.
    
    Args:
        debug: Enable debug output
    """
    try:
        properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
        if properties_df is not None and not properties_df.empty:
            return {
                "status": "success",
                "message": f"Found {len(properties_df)} GA4 properties",
                "properties": properties_df.to_dict('records')
            }
        else:
            return {"status": "success", "message": "No GA4 properties found", "properties": []}
    except Exception as e:
        return {"status": "error", "message": f"Failed to list GA4 properties: {str(e)}"}

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
    try:
        domains_df = NewDownloads.list_search_console_sites(google_account=auth_identifier, debug=debug)
        if domains_df is not None and not domains_df.empty:
            return {
                "status": "success",
                "message": f"Found {len(domains_df)} GSC domains",
                "domains": domains_df.to_dict('records')
            }
        else:
            return {"status": "success", "message": "No GSC domains found", "domains": []}
    except Exception as e:
        return {"status": "error", "message": f"Failed to list GSC domains: {str(e)}"}

# Focused GA4 Business-Intent Tools

@mcp.tool()
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
    metrics = "screenPageViews,sessions,averageSessionDuration,bounceRate,totalUsers"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
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
    dimensions = "sessionSource,sessionMedium,sessionCampaign,country"
    metrics = "sessions,totalUsers,averageSessionDuration,bounceRate,screenPageViews"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
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
    metrics = "totalUsers,sessions,averageSessionDuration,screenPageViews"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

@mcp.tool()
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
    metrics = "totalAdRevenue,screenPageViews,sessions,totalUsers"
    
    return await query_ga4_data(start_date, end_date, auth_identifier, property_id, domain_filter, metrics, dimensions, debug)

# Focused GSC Business-Intent Tools

@mcp.tool()
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
            "page_query_opportunities_gsc"
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
            print(f'        "{tool}"{comma}')
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
        "list_gsc_domains",
        "page_performance_ga4",
        "traffic_sources_ga4", 
        "audience_analysis_ga4",
        "revenue_analysis_ga4",
        "page_performance_gsc",
        "query_analysis_gsc",
        "page_query_opportunities_gsc"
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