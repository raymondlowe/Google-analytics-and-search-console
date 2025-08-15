"""
Shared state for the web application.

This module holds global state that needs to be accessed by different parts
of the application, like the main app and the API routes. This avoids
circular dependencies.
"""
from typing import Dict, Any
from fastapi import WebSocket

# Store websocket connections for progress updates
# key: query_id, value: WebSocket connection
progress_websockets: Dict[str, WebSocket] = {}

# Store information about active queries
# key: query_id, value: Dict with query status, data, etc.
active_queries: Dict[str, Dict[str, Any]] = {}