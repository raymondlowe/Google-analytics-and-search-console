# Single Domain Filtering for Google Search Console

This document describes the new single domain filtering features added to both the CLI and web interface.

## Overview

Previously, the application would download Google Search Console (GSC) data for ALL domains accessible by your Google account. This was time-consuming and inefficient when you only needed data for a specific domain.

The new features allow you to:
1. **Filter data download to a single domain**
2. **List all available domains** before downloading
3. **Use these features in both CLI and web interface**

## CLI Usage (NewDownloads.py)

### New Command Line Arguments

#### `--domain` / `-s`
Filter results to a specific domain.

```bash
# Download data for a specific domain
python NewDownloads.py yesterday today --domain example.com

# Works with www prefix too
python NewDownloads.py 2024-01-01 2024-01-31 --domain www.example.com

# Short form
python NewDownloads.py yesterday today -s example.com
```

#### `--list-domains`
List all available Search Console domains and exit (no data download).

```bash
# List all accessible domains
python NewDownloads.py --list-domains

# List domains for specific Google account
python NewDownloads.py --list-domains --googleaccount myaccount
```

### Examples

```bash
# Traditional usage (downloads ALL domains) - still works
python NewDownloads.py yesterday today

# New: Download only example.com data
python NewDownloads.py yesterday today --domain example.com

# New: See what domains are available first
python NewDownloads.py --list-domains

# Combined with other options
python NewDownloads.py 2024-01-01 2024-01-31 \
  --domain example.com \
  --dimensions page,query \
  --type web \
  --wait 1
```

## Web Interface Usage

### New Features in GSC Section

When you select "Google Search Console (GSC)" as your data source, you'll see:

1. **Domain Filter (optional)** - Text field to specify a single domain
2. **List Available GSC Domains** - Button to see what domains are accessible

### Workflow

1. Open the web interface
2. Select "Google Search Console (GSC)" 
3. Fill in your Google Account (if needed)
4. **Optional**: Enter a domain in "Domain Filter" field (e.g., "example.com")
5. **Optional**: Click "List Available GSC Domains" to see accessible sites
6. Click "Fetch Data"

### Example Scenarios

**Scenario 1: Download all domains (traditional)**
- Leave "Domain Filter" field empty
- Click "Fetch Data"

**Scenario 2: Download specific domain**
- Enter "example.com" in "Domain Filter" field  
- Click "Fetch Data"

**Scenario 3: Explore available domains first**
- Click "List Available GSC Domains" to see what's available
- Copy a domain from the results
- Paste it into "Domain Filter" field
- Click "Fetch Data"

## REST API Usage

### New Endpoint: List GSC Domains

```python
# List available GSC domains
response = api_list_gsc_domains(google_account="")
```

### Enhanced Data Query

```python
# Query with domain filter
response = api_query_data(
    source="gsc",
    start_date="2024-01-01", 
    end_date="2024-01-31",
    domain_filter="example.com"  # New parameter
)
```

## Domain Matching Logic

The domain filtering is smart and handles common variations:

- **www prefix**: "example.com" matches "www.example.com" and vice versa
- **Case insensitive**: "Example.COM" matches "example.com"
- **Exact subdomain matching**: "blog.example.com" is different from "example.com"

## Backwards Compatibility

All existing functionality is preserved:

- ✅ Old CLI commands work exactly the same
- ✅ Web interface behavior unchanged when no domain filter used
- ✅ API endpoints maintain existing signatures
- ✅ No breaking changes

## Performance Benefits

**Before**: Download data for 10 domains = 10 API calls + processing time for all domains
**After**: Download data for 1 domain = 1 API call + processing time for 1 domain

Typical performance improvement: **5-10x faster** when filtering to a single domain.

## Troubleshooting

### "No accessible sites found"
- Check your Google API credentials
- Verify the account has access to Search Console properties
- Ensure the domain is verified in Google Search Console

### "Domain doesn't match filter"  
- Check spelling of the domain
- Try with/without 'www' prefix
- Use the "List Available GSC Domains" feature to see exact domain names

### Authentication Issues
- Make sure `client_secrets.json` is configured
- Check that OAuth tokens are valid
- See main README for Google API setup instructions

## Migration Guide

### If you currently use:
```bash
python NewDownloads.py yesterday today
```

### You can now use:
```bash
# Same behavior (all domains)
python NewDownloads.py yesterday today

# Or target specific domain
python NewDownloads.py yesterday today --domain yoursite.com

# Or explore domains first
python NewDownloads.py --list-domains
```

No changes required to existing scripts or workflows.