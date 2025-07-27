usage: NewDownloads.py [-h] [-t {image,video,web}] [-d DIMENSIONS] [-n NAME]
                       [-g GOOGLEACCOUNT] [-w WAIT] [-s DOMAIN]
                       [--list-domains] [--max-retries MAX_RETRIES]
                       [--retry-delay RETRY_DELAY]
                       [start_date] [end_date]

positional arguments:
  start_date            start date in format yyyy-mm-dd or 'yesterday'
                        '7DaysAgo'
  end_date              start date in format yyyy-mm-dd or 'today'

options:
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
  -w WAIT, --wait WAIT  Wait in seconds between API calls to prevent quota
                        problems; default 0 seconds
  -s DOMAIN, --domain DOMAIN
                        Filter results to a specific domain (e.g.,
                        'example.com'). If not specified, data from all
                        accessible domains will be downloaded.
  --list-domains        List all available Search Console domains/sites and
                        exit
  --max-retries MAX_RETRIES
                        Maximum retry attempts for failed API calls; default 3
  --retry-delay RETRY_DELAY
                        Base delay in seconds for retry attempts (uses
                        exponential backoff); default 5
