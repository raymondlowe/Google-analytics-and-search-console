#!/bin/bash
# Setup and test MCP server for Google Analytics & Search Console using uv
# Usage: bash setup_and_test_mcp.sh
set -e

# 1. Create and activate uv environment if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Initializing uv environment..."
    uv init google-analytics-and-search-console || true
    source .venv/bin/activate
else
    echo "Using existing virtual environment: $VIRTUAL_ENV"
fi

# 2. Add dependencies with uv
uv pip install --upgrade pip
uv add -r requirements.txt
uv add "mcp[cli]"

# 3. Start MCP server in stdio mode (background)
echo "Starting MCP server (stdio)..."
nohup uv run mcp_server.py > mcp_server.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID $MCP_PID. Log: mcp_server.log"
sleep 2

# 4. Test MCP server with MCP Inspector (CLI)
echo "Testing MCP server with MCP Inspector..."
uv run mcp dev mcp_server.py

# 5. Instructions for HTTP mode
echo "To test HTTP mode, run:"
echo "  uv run mcp_server.py --http"
echo "Then inspect with:"
echo "  uv run mcp dev --url http://localhost:8000/mcp"

# 6. To stop the MCP server (if running in background)
echo "To stop MCP server:"
echo "  kill $MCP_PID"
