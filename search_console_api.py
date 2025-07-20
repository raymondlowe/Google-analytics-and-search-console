"""
Refactored Search Console API functionality for importing.
Based on NewDownloads.py but restructured as importable functions.
"""
import datetime
import time
import pandas as pd
from urllib.parse import urlparse
from progress.bar import IncrementalBar
from googleAPIget_service import get_service


def fetch_search_console_data(
    start_date,
    end_date,
    search_type="web",
    dimensions="page",
    google_account="",
    wait_seconds=0,
    debug=False
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
        
    Returns:
        pandas.DataFrame: Combined search console data from all accessible properties
    """
    
    # Parse dimensions
    dimensions_array = dimensions.split(",")
    multi_dimension = len(dimensions_array) > 1
    
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    # Handle multiple google accounts if file is provided
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
            print("Processing: " + this_google_account)
            
        # Authenticate and construct service
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
                    
                small_df = pd.DataFrame()
                if wait_seconds > 0:
                    if debug:
                        print(f"Sleeping {wait_seconds} seconds")
                    time.sleep(wait_seconds)
                
                if debug:
                    print(f"Querying {item['siteUrl']} from {start_date} to {end_date}")
                    
                results = service.searchanalytics().query(
                    siteUrl=item['siteUrl'], body={
                        'startDate': start_date,
                        'endDate': end_date,
                        'dimensions': dimensions_array,
                        'searchType': search_type,
                        'rowLimit': 25000
                    }).execute()
                
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
    with pd.ExcelWriter(name + '.xlsx') as writer:
        data_df.to_excel(writer, sheet_name='data')
        options_df.to_excel(writer, sheet_name="Options")
        print(f"Data saved to {name}.xlsx")


# For backwards compatibility - keep the original CLI interface
if __name__ == "__main__":
    import argparse
    import win_unicode_console
    
    win_unicode_console.enable()
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument("start_date", help="start date in format yyyy-mm-dd or 'yesterday' '7DaysAgo'")
    parser.add_argument("end_date", help="end date in format yyyy-mm-dd or 'today'")
    parser.add_argument("-t", "--type", default="web", choices=("image","video","web"), help="Search types for the returned data, default is web")
    parser.add_argument("-d","--dimensions",default="page", help="The dimensions are the left hand side of the table, default is page. Options are date, query, page, country, device. Combine two by specifying -d page,query ")
    parser.add_argument("-n","--name",default='search-console-[dimensions]-[datestring]',type=str, help="File name for final output, default is search-console- + the current date. You do NOT need to add file extension")
    parser.add_argument("-g","--googleaccount",type=str, default="", help="Name of a google account; does not have to literally be the account name but becomes a token to access that particular set of secrets. Client secrets will have to be in this a file that is this string concatenated with client_secret.json. OR if this is the name of a text file then every line in the text file is processed as one user and all results appended together into a file file")
    parser.add_argument("-w","--wait",type=int, default=0, help="Wait in seconds between API calls to prevent quota problems; default 0 seconds")
    
    args = parser.parse_args()
    
    # Fetch the data
    combined_df = fetch_search_console_data(
        start_date=args.start_date,
        end_date=args.end_date,
        search_type=args.type,
        dimensions=args.dimensions,
        google_account=args.googleaccount,
        wait_seconds=args.wait
    )
    
    if len(combined_df) > 0:
        save_search_console_data(
            data_df=combined_df,
            start_date=args.start_date,
            end_date=args.end_date,
            dimensions=args.dimensions,
            name=args.name,
            search_type=args.type,
            google_account=args.googleaccount
        )
        print("Finished and output to excel file")
    else:
        print("Nothing found")