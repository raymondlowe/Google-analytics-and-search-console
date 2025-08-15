"""
Google Search Console data provider that reuses existing NewDownloads.py logic
"""
import sys
from pathlib import Path
import traceback

# Add repository root to path for imports
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

import pandas as pd
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import asyncio
import concurrent.futures
import contextlib

# Import GSC modules: prefer original, fallback to clean minimal if needed
try:
    import NewDownloads
    _ND = NewDownloads
except Exception:
    import NewDownloads_clean as _ND

from googleAPIget_service import get_service
import os

logger = logging.getLogger(__name__)


class _LineForwarder:
    def __init__(self, emit):
        self._buf = ""
        self._emit = emit
    def write(self, s):
        # Handle both CR and LF so tqdm/carriage-return updates are captured
        self._buf += s
        # Process lines terminated by \n or \r
        while True:
            idx_n = self._buf.find("\n")
            idx_r = self._buf.find("\r")
            candidates = [i for i in (idx_n, idx_r) if i != -1]
            if not candidates:
                break
            idx = min(candidates)
            line, self._buf = self._buf[:idx], self._buf[idx+1:]
            line = line.strip()
            if line:
                self._emit(line)
        return len(s)
    def flush(self):
        if self._buf.strip():
            self._emit(self._buf.strip())
        self._buf = ""


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
        logger.info(f"GSC Provider: Starting domain listing for auth_identifier='{auth_identifier}'")
        try:
            domains = await asyncio.get_event_loop().run_in_executor(
                None, self._get_domains_sync, auth_identifier
            )
            
            logger.info(f"GSC Provider: Successfully retrieved {len(domains)} raw domains")
            
            result = [
                {
                    "id": domain["siteUrl"],
                    "name": domain["siteUrl"],
                    "display_name": domain["siteUrl"]
                }
                for domain in domains
            ]
            
            logger.info(f"GSC Provider: Returning {len(result)} formatted domains")
            return result
        except Exception as e:
            logger.error(f"GSC Provider: Error listing GSC domains: {e}", exc_info=True)

            logger.error(f"GSC Provider: Traceback: {traceback.format_exc()}")
            return []
    
    def _get_domains_sync(self, auth_identifier: str) -> List[Dict[str, str]]:
        """Synchronous helper to get domains using existing NewDownloads logic"""
        logger.info(f"GSC Provider: Starting sync domain retrieval for auth_identifier='{auth_identifier}'")
        try:
            # Get the GSC service using existing authentication

            
            # Use CLIENT_SECRETS_PATH environment variable or fallback to default
            client_secrets_path = os.environ.get('CLIENT_SECRETS_PATH', 'client_secrets.json')
            logger.info(f"GSC Provider: CLIENT_SECRETS_PATH from environment: {client_secrets_path}")
            
            # If the path is relative, make it relative to the repository root
            if not os.path.isabs(client_secrets_path):
                # Get repository root (4 levels up from this file)
                repo_root = Path(__file__).parent.parent.parent.parent
                client_secrets_path = str(repo_root / client_secrets_path)
            
            logger.info(f"GSC Provider: Using resolved client secrets path: {client_secrets_path}")
            logger.info(f"GSC Provider: Client secrets file exists: {os.path.exists(client_secrets_path)}")
            
            scope = ['https://www.googleapis.com/auth/webmasters.readonly']
            logger.info(f"GSC Provider: Calling get_service with scope: {scope}")
            # Only use auth_identifier for token file if it is not blank
            token_identifier = auth_identifier.strip() or ""
            service = get_service('webmasters', 'v3', scope, client_secrets_path, token_identifier)
            
            logger.info("GSC Provider: Successfully obtained GSC service, calling sites().list()")
            sites = service.sites().list().execute()
            
            site_entries = sites.get('siteEntry', [])
            logger.info(f"GSC Provider: Retrieved {len(site_entries)} site entries from GSC API")
            
            return site_entries
        except Exception as e:
            logger.error(f"GSC Provider: Error in _get_domains_sync: {e}", exc_info=True)
            return []
    
    async def execute_query(self, start_date: str, end_date: str,
                          dimensions: List[str], 
                          domain_filter: Optional[List[str]] = None,
                          auth_identifier: str = "",
                          search_type: str = "web",
                          debug: bool = False,
                          progress_callback=None) -> pd.DataFrame:
        """Execute GSC query using existing NewDownloads logic with optional progress reporting"""
        
        # Capture the main loop once so worker thread can marshal updates back
        main_loop = asyncio.get_running_loop()

        def emit_progress(message: str, current: Optional[int] = None, total: Optional[int] = None):
            # Print to the original stdout to avoid being captured by our own redirect
            try:
                sys.__stdout__.write(f"Progress: {message} (current={current}, total={total})\n")
                sys.__stdout__.flush()
            except Exception:
                pass
            if not progress_callback:
                return
            payload: Dict[str, Any] = {"message": message}
            if current is not None and total is not None:
                payload.update({"current": current, "total": total})
            # Always schedule on the captured loop (safe from worker thread)
            try:
                main_loop.call_soon_threadsafe(lambda: asyncio.create_task(progress_callback(payload)))
            except Exception:
                pass
        
        def run_gsc_query():
            """Run GSC query in thread pool"""
            try:
                logger.info(f"GSC Thread: Starting query for {domain_filter or 'all domains'}")
                # Announce start
                emit_progress("GSC: starting domain discovery...", None, None)
                # Wire through a native progress callback from NewDownloads (no stdout redirect to avoid loops)
                def nd_progress(payload: Dict[str, Any]):
                    msg = payload.get("message") or payload.get("event", "progress")
                    emit_progress(f"GSC: {msg}", payload.get("current"), payload.get("total"))

                df = _ND.fetch_search_console_data(
                    start_date=start_date,
                    end_date=end_date,
                    search_type=search_type,
                    dimensions=",".join(dimensions),
                    google_account=auth_identifier,
                    wait_seconds=2,  # Conservative wait time
                    debug=debug,
                    domain_filter=domain_filter[0] if domain_filter and len(domain_filter) == 1 else None,
                    max_retries=3,
                    retry_delay=5,
                    progress_callback=nd_progress
                )
                emit_progress("GSC: finished fetching data", 1, 1)

                logger.info(f"GSC Thread: Query finished. Rows: {len(df) if df is not None else 0}")
                return df if df is not None else pd.DataFrame()
            except Exception as e:
                logger.error(f"GSC Thread: Exception during query execution: {e}", exc_info=True)
                emit_progress(f"GSC: Error - {e}", 1, 1)
                return pd.DataFrame()
        
        # Run in thread pool to avoid blocking
        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,  # Use default executor
                run_gsc_query
            )
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error executing GSC query: {e}", exc_info=True)
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