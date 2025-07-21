import argparse
import datetime
import time
import pandas as pd
from pandas import ExcelWriter
import openpyxl
from progress.bar import IncrementalBar
from googleAPIget_service import get_service
from urllib.parse import urlparse

# Import win_unicode_console only when needed for CLI
try:
    import win_unicode_console
    win_unicode_console.enable()
except ImportError:
    # Skip if not available (e.g., when running in web environments)
    pass


def list_search_console_sites(google_account="", debug=False):
    """
    List all available Google Search Console sites/domains for the authenticated account.
    
    Args:
        google_account (str): Google account identifier for secrets/tokens
        debug (bool): Enable debug output
        
    Returns:
        pandas.DataFrame: DataFrame with site URLs and domains, or None if error
    """
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    # Handle multiple google accounts if file is provided
    if not google_account or google_account.strip() == "":
        # No account specified, use only 'client_secrets.json' as secrets file
        googleaccounts_list = [""]
    else:
        try:
            googleaccounts_list = open(google_account).read().splitlines()
            # remove empty lines
            googleaccounts_list = [x.strip() for x in googleaccounts_list if x.strip()]
        except:
            googleaccounts_list = [google_account]

    if debug:
        print(f"Listing sites for {len(googleaccounts_list)} Google account(s)")

    all_sites = []

    for this_google_account in googleaccounts_list:
        if debug:
            print("Processing: " + (this_google_account if this_google_account else "default client_secrets.json"))
        
        try:
            # Authenticate and construct service
            service = get_service('webmasters', 'v3', scope, 'client_secrets.json', this_google_account)
            profiles = service.sites().list().execute()
            
            if 'siteEntry' not in profiles:
                if debug:
                    print("No siteEntry found for this profile")
                continue
            
            if debug:
                print(f"Found {len(profiles['siteEntry'])} site entries")
            
            for item in profiles['siteEntry']:
                if item['permissionLevel'] != 'siteUnverifiedUser':
                    # Parse the hostname
                    root_domain = urlparse(item['siteUrl']).hostname
                    
                    site_info = {
                        'siteUrl': item['siteUrl'],
                        'domain': root_domain if root_domain else 'Domain Property',
                        'permissionLevel': item['permissionLevel'],
                        'account': this_google_account if this_google_account else 'default'
                    }
                    all_sites.append(site_info)
                    
        except Exception as e:
            if debug:
                print(f"Error processing account {this_google_account}: {str(e)}")
            continue
    
    if all_sites:
        sites_df = pd.DataFrame(all_sites)
        return sites_df
    else:
        if debug:
            print("No accessible sites found")
        return None


def fetch_search_console_data(
    start_date,
    end_date,
    search_type="web",
    dimensions="page",
    google_account="",
    wait_seconds=0,
    debug=False,
    domain_filter=None,
    max_retries=3,
    retry_delay=5
):
    """
    Fetch data from Google Search Console API.
    
    Args:
        start_date (str): Start date in format yyyy-mm-dd or 'yesterday', '7DaysAgo'
        end_date (str): End date in format yyyy-mm-dd or 'today'
        search_type (str): Search types for the returned data ('image', 'video', 'web')
        dimensions (str): Comma-separated dimensions ('date', 'query', 'page', 'country', 'device')
        google_account (str): Google account identifier for secrets/tokens
        wait_seconds (int): Wait seconds between API calls to prevent quota problems
        debug (bool): Enable debug output
        domain_filter (str): Optional domain to filter results (e.g., 'example.com')
        max_retries (int): Maximum number of retry attempts for failed API calls
        retry_delay (int): Base delay in seconds for retry attempts (with exponential backoff)
        
    Returns:
        pandas.DataFrame: Combined search console data from all accessible properties
    """
    
    # Parse dimensions
    dimensions_array = dimensions.split(",")
    multi_dimension = len(dimensions_array) > 1
    
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    # Handle multiple google accounts if file is provided
    if not google_account or google_account.strip() == "":
        # No account specified, use only 'client_secrets.json' as secrets file
        googleaccounts_list = [""]
    else:
        try:
            googleaccounts_list = open(google_account).read().splitlines()
            # remove empty lines
            googleaccounts_list = [x.strip() for x in googleaccounts_list if x.strip()]
        except:
            googleaccounts_list = [google_account]

    if debug:
        print(f"Processing {len(googleaccounts_list)} Google account(s)")

    combined_df = pd.DataFrame()

    for this_google_account in googleaccounts_list:
        if debug:
            print("Processing: " + (this_google_account if this_google_account else "default client_secrets.json"))
        # Authenticate and construct service
        # If this_google_account is blank, use only 'client_secrets.json' as secrets file
        service = get_service('webmasters', 'v3', scope, 'client_secrets.json', this_google_account)
        profiles = service.sites().list().execute()
        
        if 'siteEntry' not in profiles:
            if debug:
                print("No siteEntry found for this profile")
            continue
        
        if debug:
            print(f"Found {len(profiles['siteEntry'])} site entries")
        
        bar = IncrementalBar('Processing', max=len(profiles['siteEntry']))
        
        big_df = pd.DataFrame()
        
        for item in profiles['siteEntry']:
            bar.next()
            if item['permissionLevel'] != 'siteUnverifiedUser':
                # Parse the hostname
                root_domain = urlparse(item['siteUrl']).hostname
                
                # Skip if rootDomain is None (likely a "Domain" property)
                if root_domain is None:
                    if debug:
                        print(f"Skipping domain property: {item['siteUrl']}")
                    continue
                
                # Apply domain filter if specified
                if domain_filter:
                    # Normalize the domain filter and root domain for comparison
                    filter_domain = domain_filter.lower().strip()
                    if filter_domain.startswith('www.'):
                        filter_domain = filter_domain[4:]
                    
                    current_domain = root_domain.lower()
                    if current_domain.startswith('www.'):
                        current_domain = current_domain[4:]
                    
                    # Skip if this domain doesn't match the filter
                    if current_domain != filter_domain:
                        if debug:
                            print(f"Skipping {item['siteUrl']} (doesn't match filter: {domain_filter})")
                        continue
                    
                    if debug:
                        print(f"Processing {item['siteUrl']} (matches filter: {domain_filter})")
                        
                small_df = pd.DataFrame()
                if wait_seconds > 0:
                    if debug:
                        print(f"Sleeping {wait_seconds} seconds")
                    time.sleep(wait_seconds)
                
                if debug:
                    print(f"Querying {item['siteUrl']} from {start_date} to {end_date}")
                
                # Add error handling for individual domain API calls with retry logic
                retry_count = 0
                success = False
                
                while retry_count <= max_retries and not success:
                    try:
                        if retry_count > 0:
                            # Exponential backoff for retries
                            backoff_delay = retry_delay * (2 ** (retry_count - 1))
                            if debug:
                                print(f"Retrying {item['siteUrl']} (attempt {retry_count}/{max_retries}) after {backoff_delay}s delay")
                            time.sleep(backoff_delay)
                        
                        results = service.searchanalytics().query(
                            siteUrl=item['siteUrl'], body={
                                'startDate': start_date,
                                'endDate': end_date,
                                'dimensions': dimensions_array,
                                'searchType': search_type,
                                'rowLimit': 25000
                            }).execute()
                        
                        success = True  # Mark as successful if we get here
                        
                        if len(results) == 2:
                            small_df = small_df._append(results['rows'])
                            
                            if multi_dimension:
                                # solves key1 reserved word problem
                                small_df[['key-1','key-2']] = pd.DataFrame(small_df['keys'].tolist(), index=small_df.index)
                                small_df['keys']
                            
                            root_domain = urlparse(item['siteUrl']).hostname
                            if 'www.' in root_domain:
                                root_domain = root_domain.replace('www.','')
                            
                            small_df.insert(0,'siteUrl',item['siteUrl'])
                            small_df.insert(0,'rootDomain',root_domain)
                            
                            if len(big_df.columns) == 0:
                                big_df = small_df.copy()
                            else:
                                big_df = pd.concat([big_df,small_df])
                        elif debug:
                            print(f"No data returned for {item['siteUrl']}")
                            
                    except Exception as e:
                        retry_count += 1
                        error_msg = f"Error fetching data for {item['siteUrl']} (attempt {retry_count}/{max_retries + 1}): {str(e)}"
                        
                        # Check if this is a rate limiting or server error that we should retry
                        error_str = str(e).lower()
                        should_retry = (retry_count <= max_retries and 
                                      ('rate' in error_str or 'quota' in error_str or 
                                       'timeout' in error_str or 'internal error' in error_str or
                                       '500' in error_str or '503' in error_str or '429' in error_str))
                        
                        if should_retry:
                            if debug:
                                print(f"Retryable error: {error_msg}")
                        else:
                            # Final failure or non-retryable error
                            if debug:
                                print(f"Final error: {error_msg}")
                            else:
                                # Always show important failures even when not in debug mode
                                print(f"Warning: {error_msg}")
                            break
        
        bar.finish()
        
        big_df.reset_index()
        
        if len(big_df) > 0:
            big_df['keys'] = big_df["keys"].str[0]
            # Add the data from this account to the combined dataframe
            combined_df = pd.concat([combined_df, big_df], sort=True)
        
        # Clean up objects used in this pass
        del big_df
        del profiles
        del service
    
    if len(combined_df) > 0:
        combined_df.reset_index(drop=True, inplace=True)
    
    return combined_df


def save_search_console_data(data_df, start_date, end_date, dimensions, name, search_type, google_account):
    """
    Save search console data to Excel file with options sheet.
    
    Args:
        data_df (pandas.DataFrame): The data to save
        start_date (str): Start date used in query
        end_date (str): End date used in query  
        dimensions (str): Dimensions used in query
        name (str): Output filename base (without extension)
        search_type (str): Search type used in query
        google_account (str): Google account identifier used
    """
    if len(data_df) == 0:
        print("No data to save")
        return
        
    # Generate filename if needed
    if name == 'search-console-[dimensions]-[datestring]':
        name = 'search-console-' + dimensions + '-' + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    if google_account > "":
        name = google_account + "-" + name 
    
    # Create options dataframe
    options = [[start_date, end_date, dimensions, name, search_type, google_account]]
    options_df = pd.DataFrame(options, columns=["start_date", "end_date", "dimensions", "name", "Data Type", "Google Account"])
    
    # Save to Excel
    with ExcelWriter(name + '.xlsx') as writer:
        data_df.to_excel(writer, sheet_name='data')
        options_df.to_excel(writer, sheet_name="Options")
        print(f"Data saved to {name}.xlsx")


# CLI functionality - only runs when script is executed directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    #when doing argument parsing in command terminal put python before file name. No idea why, so just do it.

    #parser.add_argument("viewProfileID",type=int, help="GA View (profile) ID as a number") !!!already got this from loop!!!
    parser.add_argument("start_date", nargs='?', help="start date in format yyyy-mm-dd or 'yesterday' '7DaysAgo'")
    parser.add_argument("end_date", nargs='?', help="start date in format yyyy-mm-dd or 'today'")
    parser.add_argument("-t", "--type", default="web", choices=("image","video","web"), help="Search types for the returned data, default is web")
    #parser.add_argument("-f","--filters",default=2,type=int, help="Minimum number for metric, default is 2")
    parser.add_argument("-d","--dimensions",default="page", help="The dimensions are the left hand side of the table, default is page. Options are date, query, page, country, device.  Combine two by specifying -d page,query ")
    #parser.add_argument("-m","--metrics",default="pageviews", help="The metrics are the things on the left, default is pageviews")
    parser.add_argument("-n","--name",default='search-console-[dimensions]-[datestring]',type=str, help="File name for final output, default is search-console- + the current date. You do NOT need to add file extension")
    #parser.add_argument("-c", "--clean", action="count", default=0, help="clean output skips header and count and just sends csv rows")
    parser.add_argument("-g","--googleaccount",type=str, default="", help="Name of a google account; does not have to literally be the account name but becomes a token to access that particular set of secrets. Client secrets will have to be in this a file that is this string concatenated with client_secret.json.  OR if this is the name of a text file then every line in the text file is processed as one user and all results appended together into a file file")
    parser.add_argument("-w","--wait",type=int, default=0, help="Wait in seconds between API calls to prevent quota problems; default 0 seconds")
    parser.add_argument("-s","--domain",type=str, default="", help="Filter results to a specific domain (e.g., 'example.com'). If not specified, data from all accessible domains will be downloaded.")
    parser.add_argument("--list-domains", action="store_true", help="List all available Search Console domains/sites and exit")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for failed API calls; default 3")
    parser.add_argument("--retry-delay", type=int, default=5, help="Base delay in seconds for retry attempts (uses exponential backoff); default 5")

    args = parser.parse_args()

    # Handle list domains command
    if args.list_domains:
        print("Listing available Google Search Console domains...")
        sites_df = list_search_console_sites(google_account=args.googleaccount, debug=True)
        if sites_df is not None and len(sites_df) > 0:
            print("\nAvailable domains:")
            print(sites_df.to_string(index=False))
            print(f"\nTotal: {len(sites_df)} accessible sites")
        else:
            print("No accessible sites found or authentication failed.")
        exit(0)
    
    # Check required arguments when not listing domains
    if not args.start_date or not args.end_date:
        parser.error("start_date and end_date are required unless using --list-domains")

    start_date = args.start_date
    end_date = args.end_date
    wait_seconds = args.wait

    dimensionsstring = args.dimensions
    name = args.name
    dataType = args.type
    googleaccountstring = args.googleaccount
    domain_filter = args.domain.strip() if args.domain else None

    # Fetch the data using the new function
    combined_df = fetch_search_console_data(
        start_date=start_date,
        end_date=end_date,
        search_type=dataType,
        dimensions=dimensionsstring,
        google_account=googleaccountstring,
        wait_seconds=wait_seconds,
        debug=True,
        domain_filter=domain_filter,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )
    
    # Save the data if we got any
    if len(combined_df) > 0:
        save_search_console_data(
            data_df=combined_df,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensionsstring,
            name=name,
            search_type=dataType,
            google_account=googleaccountstring
        )
        print("finished and outputed to excel file")
    else:
        print("nothing found")
