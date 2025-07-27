usage: GA4query3.py [-h] [--start_month_year START_MONTH_YEAR]
                    [--end_month_year END_MONTH_YEAR] [-p PROPERTY_ID] -a
                    AUTH_IDENTIFIER [-f FILTER] [-d DIMENSIONS] [-m METRICS]
                    [-n NAME] [-t TEST] [-l] [--debug]
                    [start_date] [end_date]

Fetch and process data from Google Analytics 4 for single or multiple
properties and date ranges into a single output file using OAuth, or list
available properties.

positional arguments:
  start_date            Start date for single date range (yyyy-mm-dd)
  end_date              End date for single date range (yyyy-mm-dd)

options:
  -h, --help            show this help message and exit
  --start_month_year START_MONTH_YEAR
                        Start month and year for multiple date ranges (YYYY-
                        MM)
  --end_month_year END_MONTH_YEAR
                        End month and year for multiple date ranges (YYYY-MM)
  -p PROPERTY_ID, --property_id PROPERTY_ID
                        Google Analytics 4 property ID or path to CSV file
                        with property IDs and names.
  -a AUTH_IDENTIFIER, --auth_identifier AUTH_IDENTIFIER
                        Base name for Google Cloud OAuth token and credentials
                        files (e.g., 'myproject' will look for 'myproject-
                        credentials.json' and '[identifier]-token.json')
  -f FILTER, --filter FILTER
                        Filter expression (e.g., 'pagePath=your_page_path')
  -d DIMENSIONS, --dimensions DIMENSIONS
                        Comma-separated list of dimensions (e.g.,
                        'pagePath,country'). To include domain/hostname, use
                        'hostname,pagePath'
  -m METRICS, --metrics METRICS
                        Comma-separated list of metrics (e.g.,
                        'screenPageViews,totalAdRevenue')
  -n NAME, --name NAME  Base output file name (without extension)
  -t TEST, --test TEST  Limit results to n rows (for testing)
  -l, --list_properties
                        List available GA4 properties for the current user.
  --debug               Enable debug output to show verbose messages.
