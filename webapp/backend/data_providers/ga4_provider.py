"""
GA4 data provider that reuses existing GA4query3.py logic
"""
import sys
from pathlib import Path

# Add repository root to path for imports
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

import pandas as pd
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import asyncio
import concurrent.futures

# Import existing GA4 module
import GA4query3

logger = logging.getLogger(__name__)


class GA4Provider:
    """Data provider for Google Analytics 4"""
    
    def __init__(self):
        self.source_name = "ga4"
    
    async def get_metadata(self) -> Dict[str, List[Dict[str, str]]]:
        """Get available dimensions and metrics for GA4"""
        # Common GA4 dimensions and metrics
        dimensions = [
            {"id": "pagePath", "name": "Page Path", "type": "string", "category": "Page"},
            {"id": "pageTitle", "name": "Page Title", "type": "string", "category": "Page"},
            {"id": "hostname", "name": "Hostname", "type": "string", "category": "Page"},
            {"id": "landingPage", "name": "Landing Page", "type": "string", "category": "Page"},
            {"id": "country", "name": "Country", "type": "string", "category": "Geography"},
            {"id": "city", "name": "City", "type": "string", "category": "Geography"},
            {"id": "deviceCategory", "name": "Device Category", "type": "string", "category": "Technology"},
            {"id": "browser", "name": "Browser", "type": "string", "category": "Technology"},
            {"id": "operatingSystem", "name": "Operating System", "type": "string", "category": "Technology"},
            {"id": "sessionSource", "name": "Session Source", "type": "string", "category": "Traffic Source"},
            {"id": "sessionMedium", "name": "Session Medium", "type": "string", "category": "Traffic Source"},
            {"id": "sessionCampaignName", "name": "Campaign Name", "type": "string", "category": "Traffic Source"},
            {"id": "date", "name": "Date", "type": "string", "category": "Time"},
            {"id": "hour", "name": "Hour", "type": "string", "category": "Time"},
            {"id": "dayOfWeek", "name": "Day of Week", "type": "string", "category": "Time"},
        ]
        
        metrics = [
            {"id": "screenPageViews", "name": "Screen Page Views", "type": "integer", "category": "Page Views"},
            {"id": "screenPageViewsPerSession", "name": "Page Views per Session", "type": "number", "category": "Page Views"},
            {"id": "scrolledUsers", "name": "Scrolled Users", "type": "integer", "category": "Engagement"},
            {"id": "activeUsers", "name": "Active Users", "type": "integer", "category": "Users"},
            {"id": "newUsers", "name": "New Users", "type": "integer", "category": "Users"},
            {"id": "totalUsers", "name": "Total Users", "type": "integer", "category": "Users"},
            {"id": "sessions", "name": "Sessions", "type": "integer", "category": "Sessions"},
            {"id": "sessionsPerUser", "name": "Sessions per User", "type": "number", "category": "Sessions"},
            {"id": "userEngagementDuration", "name": "User Engagement Duration", "type": "number", "category": "Engagement"},
            {"id": "averageSessionDuration", "name": "Average Session Duration", "type": "number", "category": "Engagement"},
            {"id": "bounceRate", "name": "Bounce Rate", "type": "number", "category": "Engagement"},
            {"id": "engagementRate", "name": "Engagement Rate", "type": "number", "category": "Engagement"},
            {"id": "totalAdRevenue", "name": "Total Ad Revenue", "type": "number", "category": "Revenue"},
            {"id": "totalRevenue", "name": "Total Revenue", "type": "number", "category": "Revenue"},
            {"id": "publisherAdClicks", "name": "Publisher Ad Clicks", "type": "integer", "category": "AdSense"},
            {"id": "publisherAdImpressions", "name": "Publisher Ad Impressions", "type": "integer", "category": "AdSense"},
            {"id": "eventCount", "name": "Event Count", "type": "integer", "category": "Events"},
            {"id": "eventCountPerUser", "name": "Event Count per User", "type": "number", "category": "Events"},
        ]
        
        return {
            "dimensions": dimensions,
            "metrics": metrics
        }
    
    async def list_properties(self, auth_identifier: str = "") -> List[Dict[str, str]]:
        """List available GA4 properties"""
        try:
            # Use existing GA4query3 function
            df = await asyncio.get_event_loop().run_in_executor(
                None, GA4query3.list_properties, auth_identifier, False
            )
            
            if df is not None and not df.empty:
                return [
                    {
                        "id": str(row["property_id"]),
                        "name": str(row["property_name"]),
                        "display_name": f"{row['property_name']} ({row['property_id']})"
                    }
                    for _, row in df.iterrows()
                ]
            return []
        except Exception as e:
            logger.error(f"Error listing GA4 properties: {e}")
            return []
    
    async def execute_query(self, start_date: str, end_date: str, 
                          dimensions: List[str], metrics: List[str],
                          property_ids: Optional[List[str]] = None,
                          auth_identifier: str = "", 
                          filters: Optional[Dict[str, Any]] = None,
                          debug: bool = False) -> pd.DataFrame:
        """Execute GA4 query using existing GA4query3 logic"""
        
        def run_ga4_query():
            """Run GA4 query in thread pool"""
            try:
                if property_ids:
                    # Query specific properties
                    combined_df = pd.DataFrame()
                    
                    for prop_id in property_ids:
                        df = GA4query3.produce_report(
                            start_date=start_date,
                            end_date=end_date,
                            property_id=prop_id,
                            property_name=f"Property_{prop_id}",
                            account=auth_identifier,
                            filter_expression=filters.get("expression") if filters else None,
                            dimensions=",".join(dimensions),
                            metrics=",".join(metrics),
                            debug=debug
                        )
                        
                        if df is not None and not df.empty:
                            df["property_id"] = prop_id
                            combined_df = pd.concat([combined_df, df], ignore_index=True)
                    
                    return combined_df
                else:
                    # Query all properties
                    properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
                    if properties_df is None or properties_df.empty:
                        return pd.DataFrame()
                    
                    combined_df = pd.DataFrame()
                    for _, row in properties_df.iterrows():
                        prop_id = str(row['property_id'])
                        prop_name = str(row['property_name'])
                        
                        df = GA4query3.produce_report(
                            start_date=start_date,
                            end_date=end_date,
                            property_id=prop_id,
                            property_name=prop_name,
                            account=auth_identifier,
                            filter_expression=filters.get("expression") if filters else None,
                            dimensions=",".join(dimensions),
                            metrics=",".join(metrics),
                            debug=debug
                        )
                        
                        if df is not None and not df.empty:
                            df["property_id"] = prop_id
                            df["property_name"] = prop_name
                            combined_df = pd.concat([combined_df, df], ignore_index=True)
                    
                    return combined_df
                    
            except Exception as e:
                logger.error(f"Error in GA4 query execution: {e}")
                return pd.DataFrame()
        
        # Run in thread pool to avoid blocking
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_ga4_query)
                df = future.result(timeout=300)  # 5 minute timeout
                return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error executing GA4 query: {e}")
            return pd.DataFrame()
    
    def normalize_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Normalize GA4 DataFrame to unified format"""
        if df is None or df.empty:
            return []
        
        # Add source information
        records = df.to_dict('records')
        for record in records:
            record['_source'] = 'ga4'
            record['_source_name'] = 'Google Analytics 4'
        
        return records