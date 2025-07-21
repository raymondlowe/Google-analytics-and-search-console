#!/bin/bash

# Entrypoint script for GA4/GSC Web Interface
set -e

# Default values
HOST=${GRADIO_SERVER_NAME:-0.0.0.0}
PORT=${GRADIO_SERVER_PORT:-7860}
SHARE=${GRADIO_SHARE:-false}
AUTH=${GRADIO_AUTH:-}

# Build command arguments
ARGS="--host $HOST --port $PORT"

if [ "$SHARE" = "true" ]; then
    ARGS="$ARGS --share"
fi

if [ -n "$AUTH" ]; then
    ARGS="$ARGS --auth $AUTH"
fi

echo "Starting GA4/GSC Web Interface..."
echo "Server will run on http://$HOST:$PORT"

# Execute the main application
exec python ga4_gsc_web_interface.py $ARGS