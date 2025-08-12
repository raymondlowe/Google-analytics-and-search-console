
# Google Analytics & Search Console Reporting Tools

This repo contains tools for downloading reports and a unified web dashboard:

## 🚀 **NEW: Unified Web Dashboard**

**Run multi-property GA4 & GSC queries through a web interface!**

```bash
uv run webfrontend.py
# Open http://127.0.0.1:8000
```

The web dashboard provides:
- **Multi-property queries** across all GA4 properties and GSC domains
- **Unified data access** combining GA4 and GSC in single queries  
- **Export functionality** (CSV/Excel)
- **Preset queries** for common use cases
- **Web-based query builder** with validation

👉 **See [WEBAPP_README.md](WEBAPP_README.md) for complete web dashboard documentation**

---

## Command Line Tools

## 1. Google Search Console: `NewDownloads.py`

Download search analytics data (queries, pages, countries, devices, etc.) from Google Search Console.

### Usage

```bash
uv run python NewDownloads.py <start_date> <end_date> [options]
```

**Arguments:**
- `start_date` and `end_date`: Format `yyyy-mm-dd`, or use `yesterday`, `today`, `7DaysAgo`, etc.

**Options:**
- `-t {image,video,web}`: Search type (default: web)
- `-d DIMENSIONS`: Dimensions (e.g. `page`, `query`, `country`, `device`, or `page,query`)
- `-n NAME`: Output file name (default: search-console-YYYY-MM-DD)
- `-g GOOGLEACCOUNT`: Account token (see authentication below)

**Example:**
```bash
uv run python NewDownloads.py 2025-07-01 2025-07-17 -d "page,query" -n mysearchreport -g myaccount
```

## 2. Google Analytics 4: `GA4query3.py`

Download page-level metrics (page views, AdSense revenue, etc.) from all your GA4 properties, or just one, or list all properties.

### Usage

```bash
uv run python GA4query3.py <start_date> <end_date> -a <account_token> [options]
```

**Arguments:**
- `start_date` and `end_date`: Format `yyyy-mm-dd`
- `-a <account_token>`: Your account token (see authentication below)

**Options:**
- `-d DIMENSIONS`: Comma-separated dimensions (default: `pagePath`)
- `-m METRICS`: Comma-separated metrics (default: `screenPageViews`)
- `-p PROPERTY_ID`: Run for a single property only
- `-t N`: Limit results to N rows per property (for testing)
- `--list_properties`: List all available GA4 properties

### Examples

**List all GA4 properties:**
```bash
uv run python GA4query3.py --list_properties -a myaccount
```

**Report for ALL properties (page views & AdSense revenue):**
```bash
uv run python GA4query3.py 2025-07-01 2025-07-17 -a myaccount -d "pagePath" -m "screenPageViews,totalAdRevenue"
```

**Report for ONE property:**
```bash
uv run python GA4query3.py 2025-07-01 2025-07-17 -a myaccount -p 314029096 -d "pagePath" -m "screenPageViews,totalAdRevenue"
```

**Limit results for testing:**
```bash
uv run python GA4query3.py 2025-07-01 2025-07-17 -a myaccount -d "pagePath" -m "screenPageViews,totalAdRevenue" -t 5
```

**Output:**
- Results are saved as both `.xlsx` and `.csv` files in the current directory.

## Authentication Setup


### How to Set Up Authentication

Both tools use OAuth2 authentication. You need a Google Cloud OAuth client secrets file to get started:

1. Go to [Google Cloud Console](https://console.developers.google.com/apis/credentials)
2. Create a new project (if you don't have one)
3. Enable the required APIs:
   - Google Analytics API
   - Google Search Console API
4. Create credentials:
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app"
   - Download the credentials file
5. Rename the downloaded file to one of the following (depending on your usage):
   - `google-cloud-credentials.json` (for single account usage)
   - `<token>-client_secret.json` (for multiple accounts; `<token>` is any string you use as your account identifier)
6. Place the credentials file in this project folder.

**What happens next?**
- On first run, you'll be prompted to authenticate in your browser.
- A token file will be created (e.g. `myaccount-token.json`) and reused for future runs.

**Credential files used:**
- `google-cloud-credentials.json` or `<token>-client_secret.json`: Your OAuth client secrets
- `<token>-token.json`: Your saved authentication token (created automatically after first login)

**Tip:** If you use multiple Google accounts, create a separate credentials file for each and use the `-a` or `-g` option to specify which account to use.

See `google-client-secrets-instructions.md` for more details and troubleshooting.

## Dependency Management

This repo uses [uv](https://github.com/astral-sh/uv) for fast Python dependency management.

**Install dependencies:**
```bash
uv pip install -r requirements.txt
```

Or use uv's automatic install with `uv run`.

## Legacy & Special Tools

Other scripts in this repo are legacy or for special use cases. For most users, use only `NewDownloads.py` and `GA4query3.py`.