# Simplified GA4 & GSC API for AI/MCP Access

This document describes the improved web interface and REST API endpoints that provide simplified access to Google Analytics 4 (GA4) and Google Search Console (GSC) data specifically designed for AI model consumption via MCP or curl.

## Problem Solved

The original Gradio interface had too many required fields with poor separation between GA4 and GSC parameters, making it impractical for AI/MCP access. This improvement provides:

1. **Simplified REST API** with fewer required fields and better defaults
2. **Dedicated MCP Server** for AI model integration
3. **Unified Query Endpoint** that can fetch both GA4 and GSC data in a single request
4. **Focus on Core Metrics** for the most common use cases

## New Components

### 1. Simplified REST API (`simplified_api.py`)

A FastAPI-based REST API with clean, minimal endpoints:

#### Core Endpoints:
- `GET /` - API information and available endpoints
- `POST /ga4/query` - Query GA4 data
- `POST /gsc/query` - Query GSC data  
- `POST /query` - Unified query for both GA4 and GSC data
- `GET /ga4/properties` - List available GA4 properties
- `GET /gsc/domains` - List available GSC domains

#### Quick Access Endpoints:
- `GET /quick/ga4` - Quick GA4 query with minimal parameters
- `GET /quick/gsc` - Quick GSC query with minimal parameters

#### Key Improvements:
- **Fewer Required Fields**: Only `auth_identifier` is required for most queries
- **Sensible Defaults**: Default date ranges (last 30 days), metrics, and dimensions
- **Single Domain Focus**: Simplified filtering by domain
- **Core Metrics Focus**: 
  - GA4: `screenPageViews`, `totalAdRevenue`
  - GSC: `clicks`, `impressions`, `position` (via `page,query,country,device` dimensions)

### 2. MCP Server (`mcp_server.py`)

A Model Context Protocol server providing AI models with tools to access GA4 and GSC data:

#### Available Tools:
- `query_ga4_data` - Query GA4 analytics data
- `query_gsc_data` - Query Search Console data
- `query_unified_data` - Query both sources in one request
- `list_ga4_properties` - List available GA4 properties
- `list_gsc_domains` - List available GSC domains

#### Tool Features:
- **Optional Parameters**: Most parameters have sensible defaults
- **Automatic Date Handling**: Defaults to last 30 days if not specified
- **JSON Responses**: Structured data perfect for AI consumption
- **Error Handling**: Graceful error responses with helpful messages

## Usage Examples

### Starting the Services

#### REST API Server:
```bash
python simplified_api.py --host 0.0.0.0 --port 8000
```

#### MCP Server:
```bash
python mcp_server.py
```

### REST API Examples

#### Quick GA4 Query (minimal parameters):
```bash
curl "http://127.0.0.1:8000/quick/ga4?auth_identifier=myproject&days=30"
```

#### Quick GSC Query for specific domain:
```bash
curl "http://127.0.0.1:8000/quick/gsc?auth_identifier=myproject&domain=example.com&days=7"
```

#### Unified Query (both GA4 and GSC):
```bash
curl -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "date_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    },
    "domain": "example.com",
    "auth_identifier": "myproject",
    "data_sources": ["ga4", "gsc"]
  }'
```

### MCP Tool Usage

When using the MCP server, AI models can call tools with minimal parameters:

#### Query GA4 Data:
```json
{
  "tool": "query_ga4_data",
  "arguments": {
    "auth_identifier": "myproject",
    "domain_filter": "example.com"
  }
}
```

#### Unified Query:
```json
{
  "tool": "query_unified_data", 
  "arguments": {
    "auth_identifier": "myproject",
    "domain": "example.com"
  }
}
```

## API Response Format

All endpoints return consistent JSON responses:

```json
{
  "status": "success",
  "message": "Retrieved 150 rows of GA4 data",
  "data": [
    {
      "pagePath": "/page1",
      "screenPageViews": 1250,
      "totalAdRevenue": 15.75
    }
  ],
  "row_count": 150,
  "source": "ga4"
}
```

## Parameter Simplification

### Before (Original Gradio Interface):
Required for GA4: `data_source`, `start_date`, `end_date`, `ga4_property_id`, `ga4_auth_id`, `ga4_dimensions`, `ga4_metrics`, `ga4_filter`, `gsc_account`, `gsc_search_type`, `gsc_dimensions`, `gsc_wait_seconds`, `gsc_domain_filter`, `debug_mode`

### After (Simplified API):
**Required for GA4**: `auth_identifier`
**Optional**: `date_range`, `property_id`, `domain_filter`, `metrics`, `dimensions`, `debug`

### Parameter Defaults:
- **Date Range**: Last 30 days (if not specified)
- **GA4 Metrics**: `screenPageViews,totalAdRevenue`
- **GA4 Dimensions**: `pagePath`
- **GSC Dimensions**: `page,query,country,device`
- **GSC Search Type**: `web`

## Authentication

Uses the same OAuth2 authentication as the original system:
- **GA4**: Uses `{auth_identifier}-token.json` for stored tokens
- **GSC**: Uses `{auth_identifier}-webmasters.dat` for stored tokens
- **Client Secrets**: Uses `google-cloud-credentials.json` or `{auth_identifier}-client_secret.json`

## Testing

Run the test suite to validate functionality:

```bash
python test_simplified_api.py
```

The tests include:
- API endpoint validation
- Parameter validation
- Error handling
- Mock data testing
- Date range validation

## Integration with Existing Code

The simplified API builds on the existing `GA4query3.py` and `NewDownloads.py` modules without modifying them, ensuring backward compatibility with existing scripts and the original Gradio interface.

## Benefits for AI/MCP Access

1. **Reduced Complexity**: Only 1-2 required parameters vs 10+ in original
2. **Better Defaults**: Sensible defaults for common use cases
3. **Focused Metrics**: Emphasis on the most commonly needed data points
4. **Single Domain Support**: Clean filtering for analyzing specific domains
5. **Unified Access**: One endpoint to get both GA4 and GSC data
6. **MCP Integration**: Native support for AI model access patterns
7. **Error Handling**: Clear error messages for troubleshooting
8. **Documentation**: Auto-generated API docs at `/docs` endpoint