# GA4 & GSC Unified Web Dashboard

A unified web dashboard application for querying and analyzing data from Google Analytics 4 (GA4) and Google Search Console (GSC) across multiple websites/properties. This application provides capabilities not available in the official Google interfaces, which are limited to single properties.

## Features

### 🎯 Core Capabilities
- **Multi-property queries** across all GA4 properties and GSC domains
- **Unified data access** combining GA4 and GSC data in single queries
- **Web-based query builder** with dimension/metric selection
- **Export functionality** (CSV and Excel)
- **Preset queries** for common use cases
- **Caching system** for improved performance
- **Real-time validation** and status updates

### 📊 Business Use Cases
- Compare sessions, ad revenue, and impressions across all sites
- Identify underperforming pages with high impressions but low CTR
- Analyze traffic vs revenue patterns across properties
- Export unified analytics data for further analysis
- Run queries not possible with single-property limitations

### 🔧 Technical Features
- **FastAPI backend** with async support and background tasks
- **SQLite caching** with TTL and performance monitoring
- **Responsive web UI** with search and filtering
- **Data provider abstraction** reusing existing GA4query3.py and NewDownloads.py
- **RESTful API** with OpenAPI documentation

## Quick Start

### Prerequisites
- Python 3.10 or higher
- [uv package manager](https://github.com/astral-sh/uv) (installed automatically)
- Google Cloud credentials for GA4 and GSC access

### Installation & Setup

1. **Clone and enter the repository:**
   ```bash
   cd Google-analytics-and-search-console
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Set up authentication** (same as existing tools):
   - Place your Google Cloud OAuth credentials file as `google-cloud-credentials.json` or `<token>-client_secret.json`
   - See existing `AUTHENTICATION_GUIDE.md` for detailed setup

4. **Start the web dashboard:**
   ```bash
   uv run webfrontend.py
   ```

5. **Access the dashboard:**
   - Open http://127.0.0.1:8000 in your browser
   - API documentation: http://127.0.0.1:8000/docs

## Usage Guide

### Basic Query Workflow

1. **Select date range** using the date inputs or quick preset buttons (Today, Yesterday, Last 7 days, etc.)

2. **Choose data sources:**
   - ✅ Google Analytics 4 (for page views, sessions, revenue data)
   - ✅ Google Search Console (for clicks, impressions, position data)
   - Both can be selected for unified queries

3. **Configure authentication:**
   - Enter your account token identifier (optional - leave empty to use default)

4. **Select dimensions and metrics:**
   - Use the search boxes to filter available options
   - GA4 and GSC options are grouped separately
   - Multiple selections supported

5. **Choose properties/domains:**
   - Leave empty to query ALL available properties
   - Select specific properties for focused analysis

6. **Set sorting and limits:**
   - Sort by any selected metric
   - Limit results to control query size

7. **Execute query** and view results in the interactive table

8. **Export results** as CSV or Excel for further analysis

### Preset Queries

The dashboard includes 4 built-in preset queries:

#### 📈 **Traffic vs Revenue Analysis** (GA4)
- Compare page views and ad revenue across all GA4 properties
- Dimensions: Page Path, Hostname
- Metrics: Screen Page Views, Total Ad Revenue, Sessions

#### 🔍 **High Impressions, Low Position Pages** (GSC)
- Find pages with high search impressions but poor rankings
- Dimensions: Page, Query
- Metrics: Impressions, Position, Clicks, CTR

#### 📊 **Multi-Source Overview** (GA4 + GSC)
- Combined analytics for comprehensive site analysis
- Dimensions: Page Path (GA4), Page (GSC)
- Metrics: Page Views, Sessions, Impressions, Clicks

#### 📱 **Top Content by Device** (GA4)
- Analyze content performance across device types
- Dimensions: Page Path, Device Category
- Metrics: Page Views, Sessions, User Engagement Duration

### Custom Preset Creation

1. Configure your desired query in the query builder
2. Click **Save Preset**
3. Enter name, description, and category
4. Preset will be available in the **Load Preset** panel

## API Endpoints

### Query Execution
- `POST /api/query` - Execute a new query
- `GET /api/query/{id}` - Get query status and results
- `GET /api/query/{id}/export/csv` - Export results as CSV
- `GET /api/query/{id}/export/xlsx` - Export results as Excel

### Metadata
- `GET /api/meta/sources` - Available data sources
- `GET /api/meta/dimensions` - Available dimensions
- `GET /api/meta/metrics` - Available metrics
- `GET /api/meta/properties` - Available properties/domains
- `GET /api/meta/all` - All metadata in one call

### Presets
- `GET /api/presets` - List all preset queries
- `POST /api/presets` - Create new preset
- `GET /api/presets/{id}` - Get specific preset
- `PUT /api/presets/{id}` - Update preset
- `DELETE /api/presets/{id}` - Delete preset

### System
- `GET /health` - Health check with cache statistics

## Configuration

### Site Configuration
Edit `webapp/config/sites.yaml` to customize:

```yaml
# GA4 Properties (leave empty for all)
ga4_properties:
  # - "123456789"

# GSC Domains (leave empty for all)  
gsc_domains:
  # - "https://example.com/"

# Default auth identifier
default_auth_identifier: ""

# Cache settings
cache:
  ttl_seconds: 3600  # 1 hour
  max_size_mb: 1024  # 1GB

# Query limits
query_limits:
  max_rows: 10000
  timeout_seconds: 300
```

### Authentication
Uses the same authentication system as existing tools:
- OAuth2 with Google Cloud credentials
- Token files cached for reuse
- Multiple account support via account identifiers

## Architecture

### Backend Structure
```
webapp/backend/
├── app.py                 # FastAPI application entry point
├── core/
│   ├── cache.py          # SQLite caching with TTL
│   └── query_models.py   # Pydantic models for requests/responses
├── data_providers/
│   ├── ga4_provider.py   # GA4 data access (reuses GA4query3.py)
│   ├── gsc_provider.py   # GSC data access (reuses NewDownloads.py)
│   └── registry.py       # Unified provider interface
└── routes/
    ├── query.py          # Query execution and export endpoints
    ├── meta.py           # Metadata endpoints
    └── presets.py        # Preset management endpoints
```

### Frontend Structure
```
webapp/frontend/
├── index.html            # Main dashboard page
└── static/
    ├── css/main.css      # Responsive styling
    └── js/
        ├── main.js       # Core dashboard functionality
        ├── query_builder.js  # Query builder features
        └── presets.js    # Preset management
```

## Performance & Caching

### Caching Strategy
- **SQLite database** for persistent query caching
- **Automatic TTL** expiration (default: 1 hour)
- **Cache hit tracking** for performance monitoring
- **LRU eviction** when size limits exceeded

### Performance Features
- **Background task processing** for long-running queries
- **Async request handling** with FastAPI
- **Request deduplication** via cache keys
- **Incremental loading** for large datasets

### Monitoring
- Cache hit rates and performance stats available at `/health`
- Query execution times logged
- Error tracking and reporting

## Troubleshooting

### Common Issues

**Authentication Errors:**
- Verify Google Cloud credentials are properly configured
- Check that GA4 and GSC APIs are enabled
- Ensure account has access to the properties/domains

**Empty Results:**
- Verify date range is valid
- Check that properties/domains exist and are accessible
- Ensure selected dimensions/metrics are compatible

**Performance Issues:**
- Use date range limits for large queries
- Enable query result limits
- Check cache hit rates at `/health`

**Import Errors:**
- Ensure you're running from repository root
- Use `uv run webfrontend.py` not direct python execution
- Check that all dependencies are installed with `uv sync`

### Development & Debugging

**Enable debug mode:**
```bash
# Set debug flag in query for verbose logging
# Check backend logs for detailed error information
```

**Clear cache:**
```bash
# Access /health endpoint to view cache stats
# Use API endpoints to manage cache if needed
```

## Integration

### With Existing Tools
The webapp integrates seamlessly with existing repository tools:
- **Reuses authentication** from `googleAPIget_service.py`
- **Leverages GA4 logic** from `GA4query3.py`
- **Incorporates GSC functionality** from `NewDownloads.py`
- **Maintains MCP server** functionality in `mcp_server.py`

### API Integration
The REST API can be used by other applications:
- Standard JSON request/response format
- OpenAPI specification at `/docs`
- Background task support for long queries
- Export endpoints for programmatic data access

## Contributing

When extending the dashboard:
1. Follow existing code patterns in data providers
2. Add new presets to `webapp/presets/` directory
3. Update metadata in providers for new dimensions/metrics
4. Test with both GA4 and GSC data sources
5. Ensure responsive UI design principles

## License

Same license as the main repository.