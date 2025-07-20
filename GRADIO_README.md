# Gradio Web Interface for Google Analytics & Search Console

This Gradio application provides a web interface for fetching data from Google Analytics 4 and Google Search Console, with built-in REST API and MCP server capabilities.

## Features

- 🌐 **Web Interface**: User-friendly form-based interface for data queries
- 📊 **Dual Data Sources**: Support for both Google Analytics 4 and Google Search Console
- 📱 **REST API**: Programmatic access via HTTP endpoints
- 🔌 **MCP Server**: Model Context Protocol server capabilities
- 💾 **CSV Download**: Export results to CSV format
- 🔐 **Persistent Authentication**: OAuth tokens are saved and reused
- 🐛 **Debug Mode**: Verbose logging for troubleshooting

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
pip install gradio
```

### 2. Set Up Authentication

You need Google OAuth2 credentials:

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Analytics Reporting API and Search Console API  
3. Create OAuth2 credentials and download as `google-cloud-credentials.json`
4. Place the file in the same directory as the scripts

For detailed instructions, see: `google-client-secrets-instructions.md`

### 3. Run the Web Interface

```bash
python gradio_app.py
```

The interface will be available at: http://127.0.0.1:7860

### 4. Optional: Public Access

To create a public shareable link:

```bash
python gradio_app.py --share
```

To run on a specific host/port:

```bash
python gradio_app.py --host 0.0.0.0 --port 8080
```

## Usage Guide

### Web Interface

1. **Choose Data Source**: Select either "Google Analytics 4 (GA4)" or "Google Search Console (GSC)"

2. **Configure Parameters**:
   - **Start/End Date**: Date range for data (yyyy-mm-dd format)
   - **Authentication**: Provide your auth identifier for token file naming
   
   **For GA4:**
   - Property ID (optional - leave empty for all properties)
   - Dimensions (e.g., "pagePath", "hostname,pagePath")
   - Metrics (e.g., "screenPageViews", "totalAdRevenue")
   - Filter (optional - e.g., "pagePath=your_page_path")

   **For Search Console:**
   - Google Account identifier
   - Search Type (web, image, video)
   - Dimensions (e.g., "page", "query", "page,query")
   - Wait Seconds (delay between API calls)

3. **Fetch Data**: Click "Fetch Data" to retrieve results

4. **Download Results**: Use the "Download CSV" button to export data

### REST API

The application automatically exposes REST API endpoints. Access the API documentation at:
http://127.0.0.1:7860/?view=api

#### Example API Usage

```python
from gradio_client import Client

client = Client("http://127.0.0.1:7860/")

# Fetch GA4 data
result = client.predict(
    "Google Analytics 4 (GA4)",  # data_source
    "2024-01-01",               # start_date  
    "2024-01-31",               # end_date
    "",                         # ga4_property_id (empty for all)
    "myproject",                # ga4_auth_id
    "pagePath",                 # ga4_dimensions
    "screenPageViews",          # ga4_metrics
    "",                         # ga4_filter
    "",                         # gsc_account
    "web",                      # gsc_search_type
    "page",                     # gsc_dimensions
    0,                          # gsc_wait_seconds
    False,                      # debug_mode
    api_name="/process_query"
)

print(result)
```

#### cURL Example

```bash
curl -X POST "http://127.0.0.1:7860/api/process_query" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      "Google Analytics 4 (GA4)",
      "2024-01-01", 
      "2024-01-31",
      "",
      "myproject",
      "pagePath",
      "screenPageViews", 
      "",
      "",
      "web",
      "page",
      0,
      false
    ]
  }'
```

### MCP Server

To use as an MCP server, the Gradio application can be configured to run as a service and accessed programmatically via the API endpoints.

## Configuration Options

### Command Line Arguments

```bash
python gradio_app.py [OPTIONS]

Options:
  --host TEXT          Host to bind to (default: 127.0.0.1)
  --port INTEGER       Port to bind to (default: 7860)
  --share             Create a public shareable link
  --auth TEXT         Set authentication (username:password)
  --help              Show this message and exit
```

### Authentication

Add basic authentication to the interface:

```bash
python gradio_app.py --auth username:password
```

## File Structure

- `gradio_app.py` - Main Gradio web application
- `search_console_api.py` - Refactored Search Console API functions
- `GA4query3.py` - Google Analytics 4 API functions (unchanged)
- `NewDownloads.py` - Original Search Console script (still functional)
- `googleAPIget_service.py` - OAuth service helper

## API Endpoints

The application exposes three main API endpoints:

1. **`/toggle_fields`** - Toggle UI field visibility based on data source
2. **`/process_query`** - Main data fetching endpoint
3. **`/show_properties`** - List available GA4 properties

## Error Handling

- Authentication errors will prompt for re-authentication
- API quota errors are handled with configurable wait times
- Missing credentials files show helpful error messages
- Debug mode provides verbose logging for troubleshooting

## Authentication Persistence

OAuth tokens are automatically saved and reused:
- GA4: `{auth_identifier}-token.json` 
- Search Console: `{google_account}-webmasters.dat`

This eliminates the need to re-authenticate on each use.

## Troubleshooting

### Common Issues

1. **"Module not found" errors**: Install missing dependencies
   ```bash
   pip install -r requirements.txt
   pip install gradio
   ```

2. **Authentication failures**: Check your credentials file and ensure APIs are enabled

3. **No data returned**: Verify date ranges and property access permissions

4. **API quota exceeded**: Increase wait time between calls or reduce data volume

### Debug Mode

Enable debug mode for verbose logging:
- In web interface: Check the "Debug Mode" checkbox
- In API calls: Set the debug parameter to `true`

This will show detailed information about authentication, API calls, and data processing.

## Contributing

This application extends the existing GA4query3.py and NewDownloads.py functionality with a modern web interface while maintaining backward compatibility with the original command-line scripts.