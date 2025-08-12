"""
Google Search Console data provider that reuses existing NewDownloads.py logic
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

# Import existing GSC module
import NewDownloads

logger = logging.getLogger(__name__)


class GSCProvider:
    """Data provider for Google Search Console"""
    
    def __init__(self):
        self.source_name = "gsc"
    
    async def get_metadata(self) -> Dict[str, List[Dict[str, str]]]:
        """Get available dimensions and metrics for GSC"""
        dimensions = [
            {"id": "page", "name": "Page", "type": "string", "category": "Content"},
            {"id": "query", "name": "Query", "type": "string", "category": "Search"},
            {"id": "country", "name": "Country", "type": "string", "category": "Geography"},
            {"id": "device", "name": "Device", "type": "string", "category": "Technology"},
            {"id": "date", "name": "Date", "type": "string", "category": "Time"},
            {"id": "searchAppearance", "name": "Search Appearance", "type": "string", "category": "Search"},
        ]
        
        # GSC metrics are automatically included: clicks, impressions, ctr, position
        metrics = [
            {"id": "clicks", "name": "Clicks", "type": "integer", "category": "Performance"},
            {"id": "impressions", "name": "Impressions", "type": "integer", "category": "Performance"},
            {"id": "ctr", "name": "Click-through Rate", "type": "number", "category": "Performance"},
            {"id": "position", "name": "Average Position", "type": "number", "category": "Performance"},
        ]
        
        return {
            "dimensions": dimensions,
            "metrics": metrics
        }
    
    async def list_domains(self, auth_identifier: str = "") -> List[Dict[str, str]]:
        """List available GSC domains/sites"""
        try:
            # Use existing NewDownloads function to get domain list
            domains = await asyncio.get_event_loop().run_in_executor(
                None, self._get_domains_sync, auth_identifier
            )
            
            return [
                {
                    "id": domain["siteUrl"],
                    "name": domain["siteUrl"],
                    "display_name": domain["siteUrl"]
                }
                for domain in domains
            ]
        except Exception as e:
            logger.error(f"Error listing GSC domains: {e}")
            return []
    
    def _get_domains_sync(self, auth_identifier: str) -> List[Dict[str, str]]:
        """Synchronous helper to get domains using existing NewDownloads logic"""
        try:
            # Get the GSC service using existing authentication
            from googleAPIget_service import get_service
            service = get_service('searchconsole', 'v1', auth_identifier)
            
            sites = service.sites().list().execute()
            return sites.get('siteEntry', [])
        except Exception as e:
            logger.error(f"Error in _get_domains_sync: {e}")
            return []
    
    async def execute_query(self, start_date: str, end_date: str,
                          dimensions: List[str], 
                          domain_filter: Optional[List[str]] = None,
                          auth_identifier: str = "",
                          search_type: str = "web",
                          debug: bool = False) -> pd.DataFrame:
        """Execute GSC query using existing NewDownloads logic"""
        
        def run_gsc_query():
            """Run GSC query in thread pool"""
            try:
                # Use existing NewDownloads function
                df = NewDownloads.fetch_search_console_data(
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    dimensions=",".join(dimensions),
                    google_account=auth_identifier,
                    wait_seconds=2,  # Conservative wait time
                    debug=debug,
                    domain_filter=domain_filter[0] if domain_filter and len(domain_filter) == 1 else None,
                    max_retries=3,
                    retry_delay=5
                )
                
                return df if df is not None else pd.DataFrame()
                
            except Exception as e:
                logger.error(f"Error in GSC query execution: {e}")
                return pd.DataFrame()
        
        # Run in thread pool to avoid blocking
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_gsc_query)
                df = future.result(timeout=300)  # 5 minute timeout
                return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error executing GSC query: {e}")
            return pd.DataFrame()
    
    def normalize_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Normalize GSC DataFrame to unified format"""
        if df is None or df.empty:
            return []
        
        # Add source information
        records = df.to_dict('records')
        for record in records:
            record['_source'] = 'gsc'
            record['_source_name'] = 'Google Search Console'
        
        return records