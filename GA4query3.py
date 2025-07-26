import os
import sys
from datetime import datetime
from functools import wraps
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest, FilterExpression, Filter
from google.analytics.admin_v1beta.types import ListAccountsRequest, ListPropertiesRequest # Import request types
import argparse
import pandas as pd
from tqdm import tqdm # Import tqdm
from dateutil.relativedelta import relativedelta # Import dateutil for date calculations
import diskcache as dc

# Import the Admin API client library
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import ListPropertiesRequest # Import ListPropertiesRequest

# Disk-based cache for GA4 properties (they rarely change)
_cache_dir = os.path.join(os.path.expanduser("~"), ".ga_gsc_cache")
os.makedirs(_cache_dir, exist_ok=True)
_ga4_cache = dc.Cache(_cache_dir, size_limit=500 * 1024 * 1024)  # 500MB limit

def persistent_cache(expire_time=86400*7, typed=False):  # 7 days default for GA4 properties
    """
    Disk-based cache decorator with configurable expiration time.
    
    Args:
        expire_time (int): Cache expiration time in seconds (default: 7 days)
        typed (bool): Whether to cache based on argument types as well
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            if typed:
                cache_key += f":{hash(tuple(type(arg) for arg in args))}"
            
            # Try to get from cache
            cached_result = _ga4_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Cache miss - call function and cache result
            result = func(*args, **kwargs)
            _ga4_cache.set(cache_key, result, expire=expire_time)
            return result
        
        # Add cache management methods to the function
        def cache_info():
            """Get cache statistics"""
            return {
                'cache_size': len(_ga4_cache),
                'cache_directory': _cache_dir,
                'function': func.__name__
            }
        
        def cache_clear():
            """Clear cache for this function"""
            keys_to_delete = [key for key in _ga4_cache if key.startswith(f"{func.__name__}:")]
            for key in keys_to_delete:
                del _ga4_cache[key]
        
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        return wrapper
    return decorator

def produce_report(start_date, end_date, property_id, property_name, account, filter_expression=None, dimensions='pagePath', metrics='screenPageViews', test=None, debug=False):
    """Fetches and processes data from the GA4 API for a single property and returns DataFrame using OAuth.
       Allows specifying dimensions and metrics as comma-separated strings.
       Default dimensions is 'pagePath', default metric is 'screenPageViews'.
       To include domain/hostname in the report, use dimensions='hostname,pagePath'.
    """

    # Validate dates (add more robust date validation if needed)
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print("Error: Invalid date format. Dates must be in yyyy-mm-dd format.")
        return None

    credentials_file = f"google-cloud-credentials.json" # No longer using account in filename here
    token_file = f"{account}-token.json" # Keep account in token file name for now - could also use auth_identifier
    SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

    if debug:
        print(f"Current working directory: {os.getcwd()}")
        print(f"Looking for credentials file: {credentials_file}")

    # Explicitly check if credentials file exists
    if not os.path.exists(credentials_file):
        print(f"Error: Credentials file '{credentials_file}' not found. Please make sure it exists in the current directory. You only need to do this once. You only need to do this once.")
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        if debug:
            print(f"Loaded client secrets from file: {credentials_file}")
            print(f"Flow object created: {flow}")
    except Exception as e:  # Catch any potential errors during flow creation (less likely FileNotFoundError now)
        print(f"Error initializing OAuth flow from credentials file: {e}")
        return None

    authorisation = None # Initialize creds to None

    if os.path.exists(token_file):
        if debug:
            print(f"User authorisation User authorisation Token file found: ")
        try:
            authorisation = Credentials.from_authorized_user_file(token_file, SCOPES)
            if debug:
                print(f"Saved User authorisation authorisation loaded from token file.")
        except Exception as e: # Catch errors if token file is corrupted or invalid in some way
            print(f"Error loading User authorisationisation from token file '{token_file}': {e}")
            authorisation = None # Set creds to None to force re-authentication
    else:
        if debug:
            print(f"Saved User authorisation Saved User authorisation Token file not found: {token_file}. Proceeding with authorization flow.")

    if not authorisation or not authorisation.valid:

        if debug:
            print("User authorisation either not loaded or invalid. Starting authorization flow...")
        def try_run_local_server(flow, debug, ports=[8080, 8081, 8090, 8091, 8100]):
            last_exception = None
            for port in ports:
                try:
                    if debug:
                        print(f"Attempting OAuth local server on port {port}...")
                    flow.run_local_server(port=port)
                    if debug:
                        print(f"OAuth local server succeeded on port {port}.")
                    return flow.credentials
                except Exception as e:
                    print(f"[ERROR] OAuth local server failed on port {port}: {e}")
                    import traceback
                    traceback.print_exc()
                    last_exception = e
            print("[FATAL] All attempted ports failed for OAuth local server. Please check for port conflicts (e.g., with 'netstat -ano | findstr :8080') and close any processes using these ports, or specify a custom port.")
            raise last_exception

        if authorisation and authorisation.expired and authorisation.refresh_token:
            if debug:
                print("User authorisation Token expired, attempting refresh...")
            try:
                authorisation.refresh(google.auth.transport.requests.Request())
                if debug:
                    print("User authorisation Token refreshed successfully.")
            except Exception as refresh_e:
                print(f"Error refreshing User authorisation token: {refresh_e}, re-authorizing...")
                authorisation = try_run_local_server(flow, debug)
        else:
            if debug:
                print("No valid User authorisation token found, running authorization flow...")
            authorisation = try_run_local_server(flow, debug)

        if authorisation and authorisation.valid: # Only save if creds were successfully obtained
            if debug:
                print(f"Saving User authorisation to token file: {token_file}")
            try:
                with open(token_file, 'w') as token:
                    token.write(authorisation.to_json())
                if debug:
                    print("User authorisation saved successfully.")
            except Exception as save_e:
                print(f"Error saving User authorisation to token file: {save_e}")
        else:
            print("Error: Could not obtain valid token after authorization flow.")
            return None # Exit if no valid token  after auth flow

    try:
        client = BetaAnalyticsDataClient(credentials=authorisation) # Create client with OAuth credentials
        if debug:
            print("GA4 Data API client initialized.")

        # Split metrics and dimensions into lists and create Metric/Dimension objects
        metric_list = [metric.strip() for metric in metrics.split(',')]
        dimension_list = [dim.strip() for dim in dimensions.split(',')]

        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name=dimension) for dimension in dimension_list],
            metrics=[Metric(name=metric) for metric in metric_list],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )

        # Add filter if provided
        if filter_expression:
            filter_expression_list = [FilterExpression(filter = Filter(field_name = filter_expression.split('=')[0], string_filter= {'value': filter_expression.split('=')[1]}))] # corrected filter syntax
            request.dimension_filter = filter_expression_list[0]

        if debug:
            print("Sending GA4 API request...")
        response = client.run_report(request) # Fetch report using authenticated client
        if debug:
            print("GA4 API response received.")


        # --- DataFrame Conversion Logic ---
        dimension_names = [header.name for header in response.dimension_headers]
        metric_names = [header.name for header in response.metric_headers]
        column_names = dimension_names + metric_names
        data_rows = []

        for row in response.rows:
            dimension_values = [value.value for value in row.dimension_values]
            metric_values = [value.value for value in row.metric_values]
            data_rows.append(dimension_values + metric_values)

        df = pd.DataFrame(data_rows, columns=column_names)

        return df # Return the DataFrame

    except Exception as api_error:
        # Enhanced error handling with dimension validation suggestions
        error_str = str(api_error)
        error_msg = f"GA4 API Error for property {property_name} ({property_id}): {error_str}"
        
        # Provide helpful suggestions for common dimension/metric errors
        if "is not a valid dimension" in error_str:
            # Extract the invalid dimension name from the error message
            if "sessionCampaign" in error_str:
                error_msg += "\n💡 Suggestion: Use 'sessionCampaignId' for campaign ID or 'sessionCampaignName' for campaign name instead of 'sessionCampaign'"
            elif "Field" in error_str and "is not a valid dimension" in error_str:
                error_msg += "\n💡 Suggestion: Check the GA4 API documentation for valid dimensions: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema"
        elif "is not a valid metric" in error_str:
            error_msg += "\n💡 Suggestion: Check the GA4 API documentation for valid metrics: https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema"
        elif "400" in error_str and ("dimension" in error_str.lower() or "metric" in error_str.lower()):
            error_msg += "\n💡 Suggestion: Verify your dimensions and metrics are valid for GA4. Common dimensions include: pagePath, country, deviceCategory, sessionSource, sessionMedium, sessionCampaignId"
        
        if debug:
            print(error_msg)
            import traceback
            traceback.print_exc()
        # Re-raise the exception with the enhanced context
        raise Exception(error_msg) from api_error


@persistent_cache(expire_time=86400*7)  # Cache for 7 days since GA4 properties rarely change
def list_properties(account, debug=False):
    """Lists available GA4 properties for the authenticated user using Admin API,
       iterating through accounts to ensure all properties are listed.
       Corrected to use ListAccountsRequest and ListPropertiesRequest objects.
    """
    credentials_file = f"google-cloud-credentials.json" # No longer using account name in credentials file
    token_file = f"{account}-token.json" # Keep account in token file for now - could also use auth_identifier
    SCOPES = ['https://www.googleapis.com/auth/analytics.readonly'] # Admin API also uses this scope for read-only

    if debug:
        print(f"Current working directory: {os.getcwd()}")
        print(f"Looking for credentials file: {credentials_file}")

    # Explicitly check if credentials file exists
    if not os.path.exists(credentials_file):
        print(f"Error: Credentials file '{credentials_file}' not found. Please make sure it exists in the current directory.")
        return None

    authorisation = None  # Initialize authorisation *here*, before the try block

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        if debug:
            print(f"Loaded client secrets from file: {credentials_file}")
            print(f"Flow object created: {flow}")
    except Exception as e:
        print(f"Error initializing OAuth flow from credentials file: {e}")
        return None # Exit here if credentials file loading fails


    if os.path.exists(token_file):
        if debug:
            print(f"User authorisation Token file found: {token_file}")
        try:
            authorisation = Credentials.from_authorized_user_file(token_file, SCOPES)
            if debug:
                print(f"User authorisation loaded from token file.")
        except Exception as e:
            print(f"Error loading User authorisation from token file '{token_file}': {e}")
            authorisation = None
    else:
        if debug:
            print(f"User authorisation Token file not found: {token_file}. Proceeding with authorization flow.")


    if not authorisation or not authorisation.valid:
        if debug:
            print("User authorisation either not loaded or invalid. Starting authorization flow...")
        def try_run_local_server(flow, debug, ports=[8080, 8081, 8090, 8091, 8100]):
            last_exception = None
            for port in ports:
                try:
                    if debug:
                        print(f"Attempting OAuth local server on port {port}...")
                    flow.run_local_server(port=port)
                    if debug:
                        print(f"OAuth local server succeeded on port {port}.")
                    return flow.credentials
                except Exception as e:
                    print(f"[ERROR] OAuth local server failed on port {port}: {e}")
                    import traceback
                    traceback.print_exc()
                    last_exception = e
            print("[FATAL] All attempted ports failed for OAuth local server. Please check for port conflicts (e.g., with 'netstat -ano | findstr :8080') and close any processes using these ports, or specify a custom port.")
            raise last_exception

        if authorisation and authorisation.expired and authorisation.refresh_token:
            if debug:
                print("User authorisation Token expired, attempting refresh...")
            try:
                authorisation.refresh(google.auth.transport.requests.Request())
                if debug:
                    print("User authorisation Token refreshed successfully.")
            except Exception as refresh_e:
                print(f"Error refreshing User authorisation token: {refresh_e}, re-authorizing...")
                authorisation = try_run_local_server(flow, debug)
        else:
            if debug:
                print("No valid User authorisation token found, running authorization flow...")
            authorisation = try_run_local_server(flow, debug)

        if authorisation and authorisation.valid:
            if debug:
                print(f"Saving User authorisation to token file: {token_file}")
            try:
                with open(token_file, 'w') as token:
                    token.write(authorisation.to_json())
                if debug:
                    print("User authorisation saved successfully.")
            except Exception as save_e:
                print(f"Error saving User authorisation to token file: {save_e}")
        else:
            print("Error: Could not obtain valid token after authorization flow.")
            return None

    try:
        # Initialize Admin API client
        client = AnalyticsAdminServiceClient(credentials=authorisation)
        if debug:
            print("GA4 Admin API client initialized for property listing.")

        all_properties = []

        # 1. List Accessible Accounts
        account_page_token = None
        while True:
            accounts_request = ListAccountsRequest( # Create ListAccountsRequest object
                page_size=100,
                page_token=account_page_token
            )
            accounts_results = client.list_accounts(request=accounts_request) # Pass request object
            accounts = accounts_results.accounts

            if not accounts:
                break

            for account in accounts:
                account_id = account.name.split('/')[-1] # Extract account ID from account.name
                if debug:
                    print(f"Processing account: {account_id}")

                # 2. List Properties under each Account
                property_page_token = None
                while True:
                    properties_request = ListPropertiesRequest( # Create ListPropertiesRequest object
                        page_size=100,
                        page_token=property_page_token,
                        filter=f'parent:accounts/{account_id}' # Filter properties by account
                    )
                    properties_results = client.list_properties(request=properties_request) # Pass request object
                    property_list = properties_results.properties

                    if not property_list:
                        break

                    for property in property_list: # Iterate through property objects
                        property_id = property.name.split('/')[-1] # Extract property_id from property.name
                        property_name = property.display_name
                        all_properties.append({'property_id': property_id, 'property_name': property_name})
                        if debug:
                            print(f"  Found property: {property_name} ({property_id})")

                    property_page_token = properties_results.next_page_token
                    if not property_page_token:
                        break

            account_page_token = accounts_results.next_page_token
            if not account_page_token:
                break

        properties_df = pd.DataFrame(all_properties)
        return properties_df

    except Exception as api_error:
        print(f"GA4 Admin API Error listing properties: {api_error}")
        return None

def generate_date_ranges(start_month_year, end_month_year):
    """Generates a list of date ranges from the 1st to the 28th of each month
       between start_month_year and end_month_year (inclusive).
       Month and year should be in YYYY-MM format.
    """
    ranges = []
    current_month_year = datetime.strptime(start_month_year + '-01', '%Y-%m-%d') # Add -01 to make it a valid date
    end_month_year_dt = datetime.strptime(end_month_year + '-01', '%Y-%m-%d')

    while current_month_year <= end_month_year_dt:
        start_date = current_month_year.strftime('%Y-%m-01')
        end_date_dt = current_month_year + relativedelta(day=28) # Set day to 28th of the month
        end_date = end_date_dt.strftime('%Y-%m-%d')
        ranges.append({'start_date': start_date, 'end_date': end_date})
        current_month_year += relativedelta(months=1) # Move to the next month
    return ranges


def is_number(s):
    """Checks if a string is a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and process data from Google Analytics 4 for single or multiple properties and date ranges into a single output file using OAuth, or list available properties.") # Modified description
    parser.add_argument("start_date", nargs='?', help="Start date for single date range (yyyy-mm-dd)", default=None) # Made start_date and end_date optional and specific for single range
    parser.add_argument("end_date", nargs='?', help="End date for single date range (yyyy-mm-dd)", default=None) # Made start_date and end_date optional and specific for single range
    parser.add_argument("--start_month_year", help="Start month and year for multiple date ranges (YYYY-MM)", default=None) # New argument for start month-year
    parser.add_argument("--end_month_year", help="End month and year for multiple date ranges (YYYY-MM)", default=None) # New argument for end month-year
    parser.add_argument("-p", "--property_id", help="Google Analytics 4 property ID or path to CSV file with property IDs and names.", default=None) # Made property_id optional for listing properties
    parser.add_argument("-a", "--auth_identifier", help="Base name for Google Cloud OAuth token and credentials files (e.g., 'myproject' will look for 'myproject-credentials.json' and '[identifier]-token.json')", required=True) # Changed argument name and help text for -c
    parser.add_argument("-f", "--filter", help="Filter expression (e.g., 'pagePath=your_page_path')", default=None)
    parser.add_argument("-d", "--dimensions", help="Comma-separated list of dimensions (e.g., 'pagePath,country'). To include domain/hostname, use 'hostname,pagePath'", default='pagePath')
    parser.add_argument("-m", "--metrics", help="Comma-separated list of metrics (e.g., 'screenPageViews,totalAdRevenue')", default='screenPageViews')
    parser.add_argument("-n", "--name", help="Base output file name (without extension)", default=None)
    parser.add_argument("-t", "--test", type=int, help="Limit results to n rows (for testing)", default=None)
    parser.add_argument("-l", "--list_properties", action="store_true", help="List available GA4 properties for the current user.") # Added list_properties flag
    parser.add_argument("--debug", action="store_true", help="Enable debug output to show verbose messages.") # Added debug flag
    args = parser.parse_args()


    properties_df = None # Initialize properties_df outside the if block
    properties_df_list = None # Initialize properties_df_list here

    if args.list_properties:
        properties_df = list_properties(args.auth_identifier, debug=args.debug) # Use auth_identifier and debug flag
        if properties_df is not None and not properties_df.empty:
            print("\nAvailable GA4 Properties:")
            print(properties_df.to_string(index=False))
        elif properties_df is not None:
            print("No GA4 properties found for this account.")
        else:
            print("Failed to retrieve GA4 property list.")
    else: # Proceed with report generation if not listing properties
        combined_df = pd.DataFrame() # Initialize empty DataFrame to store combined data

        if args.name:
            output_filename_base = args.name
        else:
            # Auto-generate filename
            dimensions_part = args.dimensions.replace(',', '_')[:20] #limit length
            metrics_part = args.metrics.replace(',', '_')[:20] #limit length
            property_part = ""
            if args.property_id is None:
                property_part = "ALL_PROPERTIES"
            elif os.path.isfile(args.property_id):
                property_part = "MULTIPLE_PROPERTIES"
            else:
                property_part = f"P{args.property_id}"
            auth_identifier_part = args.auth_identifier[:10] # limit length # Use auth_identifier

            if args.start_month_year and args.end_month_year:
                date_range_part = f"monthly_{args.start_month_year}_to_{args.end_month_year}" # More descriptive monthly range
            elif args.start_date and args.end_date:
                date_range_part = f"{args.start_date}_to_{args.end_date}" # Keep single date range as is
            else:
                date_range_part = "DATERANGE_ERROR" # Fallback, should not happen

            output_filename_base = f"{date_range_part}_{dimensions_part}_{metrics_part}_{property_part}_{auth_identifier_part}_{datetime.now().strftime('%Y%m%d%H%M')}" # Use auth_identifier


        properties_df = None # Initialize properties_df outside the if block


        if args.start_month_year and args.end_month_year: # Multiple date ranges requested
            date_ranges = generate_date_ranges(args.start_month_year, args.end_month_year)
            if args.debug:
                print(f"Generating report for date ranges: {date_ranges}")
            # output_filename_base = f"{args.start_month_year}_{args.end_month_year}_{output_filename_base}" # No longer needed, date range in filename base now

            for date_range in date_ranges:
                start_date = date_range['start_date']
                end_date = date_range['end_date']

                if args.property_id is None: # Handle case where property_id is missing - list properties and run for all
                    print(f"No property ID provided for range {start_date} - {end_date}. Listing all available properties and running report for each.")
                    properties_df_list = list_properties(args.auth_identifier, debug=args.debug) # Use auth_identifier and debug flag
                    if properties_df_list is not None and not properties_df_list.empty:
                        print(f"Found {len(properties_df_list)} properties. Processing reports for date range {start_date} - {end_date}...")
                        for index, row in tqdm(properties_df_list.iterrows(), total=len(properties_df_list), desc=f"Processing Properties for {start_date}"):
                            prop_id = str(row['property_id'])
                            prop_name = str(row['property_name'])
                            tqdm.write(f"Processing property: {prop_name} ({prop_id}) for date range {start_date} - {end_date}")
                            df_property = produce_report(start_date, end_date, prop_id, prop_name, args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                            if df_property is not None:
                                df_property['date'] = start_date # Add date column
                                combined_df = pd.concat([combined_df, df_property], ignore_index=True)
                        if combined_df.empty:
                            print(f"No data retrieved from any properties for date range {start_date} - {end_date}.")
                        else:
                            print(f"Reports generated for all properties for date range {start_date} - {end_date}.")

                    elif properties_df_list is not None:
                        print(f"No GA4 properties found for this account for date range {start_date} - {end_date}. Cannot generate report.")
                    else:
                        print(f"Failed to retrieve GA4 property list for date range {start_date} - {end_date}. Cannot generate report.")


                elif os.path.isfile(args.property_id): # Check if -p arg is a file path
                    print(f"Reading property IDs from CSV file: {args.property_id} for date range {start_date} - {end_date}")
                    try:
                        properties_df = pd.read_csv(args.property_id) # Load properties_df here
                        if properties_df.columns.size < 2:
                            raise ValueError("CSV file must contain at least two columns: property_id and property_name.")
                        for index, row in tqdm(properties_df.iterrows(), total=len(properties_df), desc=f"Processing Properties for {start_date}"): # Wrap loop with tqdm
                            prop_id = str(row.iloc[0]) # Assuming first column is property ID
                            prop_name = str(row.iloc[1]) if properties_df.columns.size > 1 else "UnknownProperty" # Assuming second column is property name, default if not provided

                            tqdm.write(f"Processing property: {prop_name} ({prop_id}) for date range {start_date} - {end_date}") # Use tqdm.write instead of print

                            df_property = produce_report(start_date, end_date, prop_id, prop_name, args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                            if df_property is not None: # Check if DataFrame is returned successfully
                                df_property['date'] = start_date # Add date column
                                combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


                    except FileNotFoundError:
                        print(f"Error: Property ID CSV file not found: {args.property_id} for date range {start_date} - {end_date}")
                    except pd.errors.EmptyDataError:
                        print(f"Error: Property ID CSV file is empty: {args.property_id} for date range {start_date} - {end_date}")
                    except ValueError as ve:
                        print(f"Error reading Property ID CSV file: {ve} for date range {start_date} - {end_date}")
                    except Exception as e:
                        print(f"An unexpected error occurred while processing Property ID CSV file: {e} for date range {start_date} - {end_date}")


                elif is_number(args.property_id): # If -p arg is a number, treat as single property ID
                    if args.debug:
                        print(f"Processing single property ID: {args.property_id} for date range {start_date} - {end_date}")
                    df_property = produce_report(start_date, end_date, args.property_id, "SingleProperty", args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                    if df_property is not None: # Check if DataFrame is returned successfully
                        df_property['date'] = start_date # Add date column
                        combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


                else:
                    print("Error: -p argument should be either a Property ID (number), a path to a CSV file, or omitted to process all properties.")


        elif args.start_date and args.end_date: # Single date range requested (existing logic)
            start_date = args.start_date
            end_date = args.end_date
            # output_filename_base = f"{start_date}_{end_date}_{output_filename_base}" # No longer needed, date range in filename base now
            if not args.start_date or not args.end_date: # property_id is now optional, removed from required check
                print("Error: When generating a report with single date range, start_date and end_date are required.")
                sys.exit(1)


            if args.property_id is None: # Handle case where property_id is missing - list properties and run for all
                print(f"No property ID provided for range {start_date} - {end_date}. Listing all available properties and running report for each.")
                properties_df_list = list_properties(args.auth_identifier, debug=args.debug) # Use auth_identifier and debug flag
                if properties_df_list is not None and not properties_df_list.empty:
                    print(f"Found {len(properties_df_list)} properties. Processing reports for date range {start_date} - {end_date}...")
                    for index, row in tqdm(properties_df_list.iterrows(), total=len(properties_df_list), desc=f"Processing Properties for {start_date}"):
                        prop_id = str(row['property_id'])
                        prop_name = str(row['property_name'])
                        tqdm.write(f"Processing property: {prop_name} ({prop_id}) for date range {start_date} - {end_date}")
                        df_property = produce_report(start_date, end_date, prop_id, prop_name, args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                        if df_property is not None:
                            df_property['date'] = start_date # Add date column
                            combined_df = pd.concat([combined_df, df_property], ignore_index=True)
                    if combined_df.empty:
                        print(f"No data retrieved from any properties for date range {start_date} - {end_date}.")
                    else:
                        print(f"Reports generated for all properties for date range {start_date} - {end_date}.")

                elif properties_df_list is not None:
                    print(f"No GA4 properties found for this account for date range {start_date} - {end_date}. Cannot generate report.")
                else:
                    print(f"Failed to retrieve GA4 property list for date range {start_date} - {end_date}. Cannot generate report.")


            elif os.path.isfile(args.property_id): # Check if -p arg is a file path
                print(f"Reading property IDs from CSV file: {args.property_id} for date range {start_date} - {end_date}")
                try:
                    properties_df = pd.read_csv(args.property_id) # Load properties_df here
                    if properties_df.columns.size < 2:
                        raise ValueError("CSV file must contain at least two columns: property_id and property_name.")
                    for index, row in tqdm(properties_df.iterrows(), total=len(properties_df), desc=f"Processing Properties for {start_date}"): # Wrap loop with tqdm
                        prop_id = str(row.iloc[0]) # Assuming first column is property ID
                        prop_name = str(row.iloc[1]) if properties_df.columns.size > 1 else "UnknownProperty" # Assuming second column is property name, default if not provided

                        tqdm.write(f"Processing property: {prop_name} ({prop_id}) for date range {start_date} - {end_date}") # Use tqdm.write instead of print

                        df_property = produce_report(start_date, end_date, prop_id, prop_name, args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                        if df_property is not None: # Check if DataFrame is returned successfully
                            df_property['date'] = start_date # Add date column
                            combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


                except FileNotFoundError:
                    print(f"Error: Property ID CSV file not found: {args.property_id} for date range {start_date} - {end_date}")
                except pd.errors.EmptyDataError:
                    print(f"Error: Property ID CSV file is empty: {args.property_id} for date range {start_date} - {end_date}")
                except ValueError as ve:
                    print(f"Error reading Property ID CSV file: {ve} for date range {start_date} - {end_date}")
                except Exception as e:
                    print(f"An unexpected error occurred while processing Property ID CSV file: {e} for date range {start_date} - {end_date}")


            elif is_number(args.property_id): # If -p arg is a number, treat as single property ID
                if args.debug:
                    print(f"Processing single property ID: {args.property_id} for date range {start_date} - {end_date}")
                df_property = produce_report(start_date, end_date, args.property_id, "SingleProperty", args.auth_identifier, args.filter, args.dimensions, args.metrics, args.test, debug=args.debug) # Use auth_identifier and debug flag
                if df_property is not None: # Check if DataFrame is returned successfully
                    df_property['date'] = start_date # Add date column
                    combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


            else:
                print("Error: -p argument should be either a Property ID (number), a path to a CSV file, or omitted to process all properties.")
        else:
            print("Error: You must specify either a single date range (start_date and end_date) or multiple date ranges (start_month_year and end_month_year).")
            sys.exit(1)


        if not combined_df.empty: # Save combined DataFrame only if it's not empty
            # **Insert this line to coerce metric columns to numeric:**
            metric_columns = [metric.strip() for metric in args.metrics.split(',')]
            for col in metric_columns:
                if col in combined_df.columns: # Check if the column exists in the DataFrame
                    combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce') # Coerce to numeric, setting errors to NaN


            # Create DataFrame from args
            params_dict = {
                'start_date': [args.start_date if args.start_date else args.start_month_year], # Use month-year if single dates not provided
                'end_date': [args.end_date if args.end_date else args.end_month_year], # Use month-year if single dates not provided
                'property_id': [args.property_id if args.property_id else 'ALL_PROPERTIES_LISTED'], # Indicate all properties if -p is omitted
                'auth_identifier': [args.auth_identifier], # Changed to auth_identifier
                'filter': [args.filter],
                'dimensions': [args.dimensions],
                'metrics': [args.metrics],
                'test': [args.test],
                'command_line': [' '.join(sys.argv)] # Added command line argument string
            }
            params_df = pd.DataFrame(params_dict)

            # Save to Excel with two sheets
            with pd.ExcelWriter(f"{output_filename_base}.xlsx") as writer:
                combined_df.to_excel(writer, sheet_name='data', index=False)
                params_df.to_excel(writer, sheet_name='params', index=False)
                if properties_df is not None and os.path.isfile(args.property_id): # Add properties_df to excel only if it was loaded from a file
                    properties_df.to_excel(writer, sheet_name='properties_list', index=False) # Add properties list to excel
                elif properties_df_list is not None and args.property_id is None: # Save listed properties if -p was omitted
                    properties_df_list.to_excel(writer, sheet_name='properties_list', index=False)


            combined_df.to_csv(f"{output_filename_base}.csv", index=False)
            print(f"Combined report saved to {output_filename_base}.xlsx and {output_filename_base}.csv")
        else:
            print("No data to save in the combined report.")

## Example usage:

# List available properties (OAuth)
# python GA4query3.py -a my_auth_id -l # Changed to auth_identifier

# Single Property ID (OAuth) - Single date range
# python GA4query3.py 2024-10-01 2024-10-31 -p 313646501 -a my_auth_id -m totalAdRevenue -n my_oauth_report # Changed to auth_identifier

# Multiple Property IDs from CSV (OAuth) - Single date range
# python GA4query3.py 2024-10-01 2024-10-31 -p properties.csv -a my_auth_id -m screenPageViews -n my_oauth_report # Changed to auth_identifier

# Run report for ALL properties (OAuth) - Single date range
# python GA4query3.py 2024-10-01 2024-10-31 -a my_auth_id -m screenPageViews -n all_properties_report # Changed to auth_identifier

# Multiple date ranges for ALL properties
# python GA4query3.py --start_month_year 2024-12 --end_month_year 2025-01 -a my_auth_id -m screenPageViews -n monthly_report # Changed to auth_identifier

# Multiple date ranges for single property
# python GA4query3.py --start_month_year 2024-12 --end_month_year 2025-01 -p 313646501 -a my_auth_id -m screenPageViews -n monthly_report_single_prop # Changed to auth_identifier

# Multiple date ranges for properties from CSV
# python GA4query3.py --start_month_year 2024-12 --end_month_year 2025-01 -p properties.csv -a my_auth_id -m screenPageViews -n monthly_report_csv_props # Changed to auth_identifier

# Include hostname/domain in the report
# python GA4query3.py 2024-10-01 2024-10-31 -p 313646501 -a my_auth_id -d hostname,pagePath -m screenPageViews -n my_domain_report # Changed to auth_identifier
# or for multiple properties:
# python GA4query3.py 2024-10-01 2024-10-31 -p properties.csv -a my_auth_id -d hostname,pagePath -m screenPageViews -n my_domain_report # Changed to auth_identifier
