# Google-analytics-and-search-console
These script can scrape Google analytics and the Google search console for info about your websites.

# Usage

## NewDownloads.py
~~~~
usage: NewDownloads.py [-h] [-t {image,video,web}] [-d DIMENSIONS] [-n NAME]
                       [-g GOOGLEACCOUNT]
                       start_date end_date

positional arguments:
  start_date            start date in format yyyy-mm-dd or 'yesterday'
                        '7DaysAgo'
  end_date              start date in format yyyy-mm-dd or 'today'

optional arguments:
  -h, --help            show this help message and exit
  -t {image,video,web}, --type {image,video,web}
                        Search types for the returned data, default is web
  -d DIMENSIONS, --dimensions DIMENSIONS
                        The dimensions are the left hand side of the table,
                        default is page. Options are date, query, page,
                        country, device. Combine two by specifying -d
                        page,query
  -n NAME, --name NAME  File name for final output, default is search-console-
                        + the current date. You do NOT need to add file
                        extension
  -g GOOGLEACCOUNT, --googleaccount GOOGLEACCOUNT
                        Name of a google account; does not have to literally
                        be the account name but becomes a token to access that
                        particular set of secrets. Client secrets will have to
                        be in this a file that is this string concatenated
                        with client_secret.json. OR if this is the name of a
                        text file then every line in the text file is
                        processed as one user and all results appended
                        together into a file file

~~~~
## GACombined2.py      

This script download from Google Analytics but ***ONLY*** views which are marked as starred/fav

~~~~
usage: GACombined2.py [-h] [-f FILTERS] [-d DIMENSIONS] [-m METRICS] [-n NAME] [-t [TEST]] [-g GOOGLEACCOUNT]
                      start_date end_date

positional arguments:
  start_date            start date in format yyyy-mm-dd or 'yesterday' '7DaysAgo'
  end_date              start date in format yyyy-mm-dd or 'today'

optional arguments:
  -h, --help            show this help message and exit
  -f FILTERS, --filters FILTERS
                        Filter, default is 'ga:pageviews>2'
  -d DIMENSIONS, --dimensions DIMENSIONS
                        The dimensions are the left hand side of the table, default is pagePath. YOU HAVE TO
                        ADD 'ga:' before your dimension
  -m METRICS, --metrics METRICS
                        The metrics are the things on the left, default is pageviews. YOU HAVE TO ADD 'ga:'
                        before your metric
  -n NAME, --name NAME  File name for final output, default is analytics- + the current date. You do NOT need
                        to add file extension.
  -t [TEST], --test [TEST]
                        Test option which makes the script output only n results, default is 3.
  -g GOOGLEACCOUNT, --googleaccount GOOGLEACCOUNT
                        Name of a google account; does not have to literally be the account name but becomes
                        a token to access that particular set of secrets. Client secrets will have to be in
                        this a file that is this string concatenated with client_secret.json. OR if this is
                        the name of a text file then every line in the text file is processed as one user and
                        all results appended together into a file file

~~~~
#pip commands
copy and paste these into the terminal

~~~~
pip install -r requirements.txt
~~~~

You need a Oauth2 account and put client_secret.json in same folder as script
https://developers.google.com/webmaster-tools/search-console-api-original/v3/quickstart/quickstart-python 

If you are using multiple google accounts then for every google account "email@example.com" create a secrets file called email@example.com-client_secret.json

For detailed instructions see the file: google-client-secrets-instructions.md

## list_ga4_properties.py
Lists details about a GA4 property, including its ID, name, and domain.

~~~~
usage: list_ga4_properties.py [-h] -c CREDENTIALS -p PROPERTY_ID [--format {table,json,csv}] [--output OUTPUT]

List details about a GA4 property with its ID, name, and domain.

required arguments:
  -c CREDENTIALS, --credentials CREDENTIALS
                        Path to Google Cloud credentials JSON file
  -p PROPERTY_ID, --property_id PROPERTY_ID
                        Google Analytics 4 property ID

optional arguments:
  -h, --help            show this help message and exit
  --format {table,json,csv}
                        Output format (default: table)
  --output OUTPUT       Output file path. If not provided, prints to stdout

Examples:
  # List property details in table format (default)
  python list_ga4_properties.py -c path/to/credentials.json -p 313646501

  # List property details in JSON format
  python list_ga4_properties.py -c path/to/credentials.json -p 313646501 --format json

  # Save output to a file
  python list_ga4_properties.py -c path/to/credentials.json -p 313646501 --output properties.txt

Note: Uses the same Google Cloud credentials JSON file format as GA4query2.py
~~~~
