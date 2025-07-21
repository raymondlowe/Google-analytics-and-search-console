#!/bin/bash
# 
# Example curl commands for the Simplified GA4 & GSC API
# These demonstrate how AI models can access the API with minimal parameters
#
# Usage: ./curl_examples.sh
# 
# Note: You'll need to update the auth_identifier and other parameters
# based on your actual Google OAuth setup.

set -e

API_BASE="http://127.0.0.1:8000"
AUTH_ID="myproject"  # Change this to your auth identifier
DOMAIN="example.com"  # Change this to your domain

echo "=== GA4 & GSC Simplified API Examples ==="
echo ""

# 1. Check API status
echo "1. Checking API status..."
curl -s "${API_BASE}/" | jq '.'
echo ""

# 2. Quick GA4 query (last 30 days)
echo "2. Quick GA4 query (last 30 days)..."
curl -s "${API_BASE}/quick/ga4?auth_identifier=${AUTH_ID}&days=30" | jq '.'
echo ""

# 3. Quick GSC query (last 7 days for specific domain)
echo "3. Quick GSC query (last 7 days for ${DOMAIN})..."
curl -s "${API_BASE}/quick/gsc?auth_identifier=${AUTH_ID}&domain=${DOMAIN}&days=7" | jq '.'
echo ""

# 4. List GA4 properties
echo "4. Listing GA4 properties..."
curl -s "${API_BASE}/ga4/properties?auth_identifier=${AUTH_ID}" | jq '.'
echo ""

# 5. List GSC domains
echo "5. Listing GSC domains..."
curl -s "${API_BASE}/gsc/domains?auth_identifier=${AUTH_ID}" | jq '.'
echo ""

# 6. Detailed GA4 query with POST
echo "6. Detailed GA4 query (POST)..."
curl -s -X POST "${API_BASE}/ga4/query" \
  -H "Content-Type: application/json" \
  -d '{
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    },
    "auth_identifier": "'${AUTH_ID}'",
    "dimensions": "pagePath",
    "metrics": "screenPageViews,totalAdRevenue",
    "debug": false
  }' | jq '.'
echo ""

# 7. Detailed GSC query with POST
echo "7. Detailed GSC query (POST)..."
curl -s -X POST "${API_BASE}/gsc/query" \
  -H "Content-Type: application/json" \
  -d '{
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    },
    "domain": "'${DOMAIN}'",
    "auth_identifier": "'${AUTH_ID}'",
    "search_type": "web",
    "dimensions": "page,query,country,device",
    "debug": false
  }' | jq '.'
echo ""

# 8. Unified query (both GA4 and GSC)
echo "8. Unified query (both GA4 and GSC)..."
curl -s -X POST "${API_BASE}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    },
    "domain": "'${DOMAIN}'",
    "auth_identifier": "'${AUTH_ID}'",
    "data_sources": ["ga4", "gsc"],
    "debug": false
  }' | jq '.'
echo ""

echo "=== API Examples Complete ==="
echo ""
echo "To start the API server, run:"
echo "  python simplified_api.py --host 0.0.0.0 --port 8000"
echo ""
echo "API documentation is available at:"
echo "  http://127.0.0.1:8000/docs"