"""
Cache management for the unified web dashboard
"""
import sqlite3
import json
import hashlib
import time
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import diskcache as dc

logger = logging.getLogger(__name__)


class UnifiedCache:
    """Unified caching layer with SQLite persistence and in-memory cache"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".ga_gsc_cache")
        
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        self.db_path = os.path.join(cache_dir, "webapp_cache.sqlite")
        self.disk_cache = dc.Cache(cache_dir, size_limit=1024 * 1024 * 1024)  # 1GB limit
        
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for query cache"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    query_hash TEXT PRIMARY KEY,
                    query_json TEXT,
                    response_data TEXT,
                    timestamp REAL,
                    ttl_seconds INTEGER,
                    sources TEXT,
                    row_count INTEGER,
                    execution_time_ms REAL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT,
                    timestamp REAL,
                    execution_time_ms REAL,
                    cache_hit BOOLEAN,
                    sources TEXT,
                    row_count INTEGER,
                    auth_identifier TEXT
                )
            """)
            conn.commit()
    
    def _generate_cache_key(self, query_data: Dict[str, Any]) -> str:
        """Generate a stable cache key for query data"""
        # Sort and serialize for stable hashing
        normalized = json.dumps(query_data, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def get_cached_query(self, query_data: Dict[str, Any], ttl_seconds: int = 3600) -> Optional[Dict[str, Any]]:
        """Get cached query result if available and not expired"""
        cache_key = self._generate_cache_key(query_data)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT response_data, timestamp, ttl_seconds FROM query_cache WHERE query_hash = ?",
                    (cache_key,)
                )
                row = cursor.fetchone()
                
                if row:
                    response_data, timestamp, stored_ttl = row
                    if time.time() - timestamp < stored_ttl:
                        return json.loads(response_data)
                    else:
                        # Expired, remove from cache
                        conn.execute("DELETE FROM query_cache WHERE query_hash = ?", (cache_key,))
                        conn.commit()
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
        
        return None
    
    def cache_query_result(self, query_data: Dict[str, Any], response_data: Dict[str, Any], 
                          ttl_seconds: int = 3600, execution_time_ms: float = 0) -> None:
        """Cache query result with TTL"""
        cache_key = self._generate_cache_key(query_data)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO query_cache 
                       (query_hash, query_json, response_data, timestamp, ttl_seconds, sources, row_count, execution_time_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cache_key,
                        json.dumps(query_data, default=str),
                        json.dumps(response_data, default=str),
                        time.time(),
                        ttl_seconds,
                        ",".join(query_data.get("sources", [])),
                        response_data.get("row_count", 0),
                        execution_time_ms
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error caching result: {e}")
    
    def log_query(self, query_data: Dict[str, Any], execution_time_ms: float, 
                  cache_hit: bool, row_count: int = 0) -> None:
        """Log query execution for monitoring"""
        cache_key = self._generate_cache_key(query_data)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO query_log 
                       (query_hash, timestamp, execution_time_ms, cache_hit, sources, row_count, auth_identifier)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cache_key,
                        time.time(),
                        execution_time_ms,
                        cache_hit,
                        ",".join(query_data.get("sources", [])),
                        row_count,
                        query_data.get("auth_identifier", "")
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging query: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Cache hit rate
                hit_rate_cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_queries,
                        SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits
                    FROM query_log 
                    WHERE timestamp > ?
                """, (time.time() - 86400,))  # Last 24 hours
                
                total_queries, cache_hits = hit_rate_cursor.fetchone()
                hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0
                
                # Cache size
                cache_size_cursor = conn.execute("SELECT COUNT(*) FROM query_cache")
                cache_size = cache_size_cursor.fetchone()[0]
                
                # Average execution time
                avg_time_cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) 
                    FROM query_log 
                    WHERE timestamp > ? AND NOT cache_hit
                """, (time.time() - 86400,))
                avg_execution_time = avg_time_cursor.fetchone()[0] or 0
                
                return {
                    "cache_hit_rate_24h": round(hit_rate, 2),
                    "total_queries_24h": total_queries,
                    "cache_hits_24h": cache_hits,
                    "cached_queries": cache_size,
                    "avg_execution_time_ms": round(avg_execution_time, 2)
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def clear_cache(self, older_than_hours: int = None) -> int:
        """Clear cache entries, optionally only older than specified hours"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if older_than_hours:
                    cutoff_time = time.time() - (older_than_hours * 3600)
                    cursor = conn.execute("DELETE FROM query_cache WHERE timestamp < ?", (cutoff_time,))
                else:
                    cursor = conn.execute("DELETE FROM query_cache")
                
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0