import os
import sys
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest, FilterExpression, Filter
from google.analytics.admin_v1beta.types import ListAccountsRequest, ListPropertiesRequest # Import request types
import argparse
import pandas as pd
from tqdm import tqdm # Import tqdm

# Import the Admin API client library
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import ListPropertiesRequest # Import ListPropertiesRequest

def produce_report(start_date, end_date, property_id, property_name, account, filter_expression=None, dimensions='pagePath', metrics='screenPageViews', test=None):
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

    credentials_file = f"google-cloud-credentials.json"
    token_file = f"{account}-token.json"
    SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

    print(f"Current working directory: {os.getcwd()}")
    print(f"Looking for credentials file: {credentials_file}")

    # Explicitly check if credentials file exists
    if not os.path.exists(credentials_file):
        print(f"Error: Credentials file '{credentials_file}' not found. Please make sure it exists in the current directory. You only need to do this once. You only need to do this once.")
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        print(f"Loaded client secrets from file: {credentials_file}")
        print(f"Flow object created: {flow}")
    except Exception as e:  # Catch any potential errors during flow creation (less likely FileNotFoundError now)
        print(f"Error initializing OAuth flow from credentials file: {e}")
        return None

    authorisation = None # Initialize creds to None

    if os.path.exists(token_file):
        print(f"User authorisation User authorisation Token file found: ")
        try:
            authorisation = Credentials.from_authorized_user_file(token_file, SCOPES)
            print(f"Saved User authorisation authorisation loaded from token file.")
        except Exception as e: # Catch errors if token file is corrupted or invalid in some way
            print(f"Error loading User authorisationisation from token file '{token_file}': {e}")
            authorisation = None # Set creds to None to force re-authentication
    else:
        print(f"Saved User authorisation Saved User authorisation Token file not found: {token_file}. Proceeding with authorization flow.")

    if not authorisation or not authorisation.valid:
        print("User authorisation either not loaded or invalid. Starting authorization flow...")
        if authorisation and authorisation.expired and authorisation.refresh_token:
            print("User authorisation Token expired, attempting refresh...")
            try:
                authorisation.refresh(google.auth.transport.requests.Request())
                print("User authorisation Token refreshed successfully.")
            except Exception as refresh_e:
                print(f"Error refreshing User authorisation token: {refresh_e}, re-authorizing...")
                flow.run_local_server() # Re-authorize if refresh fails
                authorisation = flow.credentials
        else:
            print("No valid User authorisation token found, running authorization flow...")
            flow.run_local_server() # Run flow to get new credentials
            authorisation = flow.credentials

        if authorisation and authorisation.valid: # Only save if creds were successfully obtained
            print(f"Saving User authorisation to token file: {token_file}")
            try:
                with open(token_file, 'w') as token:
                    token.write(authorisation.to_json())
                print("User authorisation saved successfully.")
            except Exception as save_e:
                print(f"Error saving User authorisation to token file: {save_e}")
        else:
            print("Error: Could not obtain valid token after authorization flow.")
            return None # Exit if no valid token  after auth flow

    try:
        client = BetaAnalyticsDataClient(credentials=authorisation) # Create client with OAuth credentials
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
            request.filter = filter_expression_list[0]

        print("Sending GA4 API request...")
        response = client.run_report(request) # Fetch report using authenticated client
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
        print(f"GA4 API Error for property {property_name} ({property_id}): {api_error}")
        return None
    except Exception as api_error: # Catch any errors during API interaction
        print(f"GA4 API Error for property {property_name} ({property_id}): {api_error}")
        return None



def list_properties(account):
    """Lists available GA4 properties for the authenticated user using Admin API,
       iterating through accounts to ensure all properties are listed.
       Corrected to use ListAccountsRequest and ListPropertiesRequest objects.
    """
    credentials_file = f"google-cloud-credentials.json"
    token_file = f"{account}-token.json"
    SCOPES = ['https://www.googleapis.com/auth/analytics.readonly'] # Admin API also uses this scope for read-only

    print(f"Current working directory: {os.getcwd()}")
    print(f"Looking for credentials file: {credentials_file}")

    # Explicitly check if credentials file exists
    if not os.path.exists(credentials_file):
        print(f"Error: Credentials file '{credentials_file}' not found. Please make sure it exists in the current directory.")
        return None

    authorisation = None  # Initialize authorisation *here*, before the try block

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        print(f"Loaded client secrets from file: {credentials_file}")
        print(f"Flow object created: {flow}")
    except Exception as e:
        print(f"Error initializing OAuth flow from credentials file: {e}")
        return None # Exit here if credentials file loading fails


    if os.path.exists(token_file):
        print(f"User authorisation Token file found: {token_file}")
        try:
            authorisation = Credentials.from_authorized_user_file(token_file, SCOPES)
            print(f"User authorisation loaded from token file.")
        except Exception as e:
            print(f"Error loading User authorisation from token file '{token_file}': {e}")
            authorisation = None
    else:
        print(f"User authorisation Token file not found: {token_file}. Proceeding with authorization flow.")

    if not authorisation or not authorisation.valid:
        print("User authorisation either not loaded or invalid. Starting authorization flow...")
        if authorisation and authorisation.expired and authorisation.refresh_token:
            print("User authorisation Token expired, attempting refresh...")
            try:
                authorisation.refresh(google.auth.transport.requests.Request())
                print("User authorisation Token refreshed successfully.")
            except Exception as refresh_e:
                print(f"Error refreshing User authorisation token: {refresh_e}, re-authorizing...")
                flow.run_local_server()
                authorisation = flow.credentials
        else:
            print("No valid User authorisation token found, running authorization flow...")
            flow.run_local_server()
            authorisation = flow.credentials

        if authorisation and authorisation.valid:
            print(f"Saving User authorisation to token file: {token_file}")
            try:
                with open(token_file, 'w') as token:
                    token.write(authorisation.to_json())
                print("User authorisation saved successfully.")
            except Exception as save_e:
                print(f"Error saving User authorisation to token file: {save_e}")
        else:
            print("Error: Could not obtain valid token after authorization flow.")
            return None

    try:
        # Initialize Admin API client
        client = AnalyticsAdminServiceClient(credentials=authorisation)
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



def is_number(s):
    """Checks if a string is a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and process data from Google Analytics 4 for single or multiple properties into a single output file using OAuth, or list available properties.") # Modified description
    parser.add_argument("start_date", nargs='?', help="Start date (yyyy-mm-dd)", default=None) # Made start_date and end_date optional for listing properties
    parser.add_argument("end_date", nargs='?', help="End date (yyyy-mm-dd)", default=None) # Made start_date and end_date optional for listing properties
    parser.add_argument("-p", "--property_id", help="Google Analytics 4 property ID or path to CSV file with property IDs and names.", default=None) # Made property_id optional for listing properties
    parser.add_argument("-c", "--credentials_name", help="Base name for Google Cloud OAuth credentials files (e.g., 'myproject' will look for 'myproject-credentials.json' and 'myproject-token.json')", required=True) # Changed help text for -c
    parser.add_argument("-f", "--filter", help="Filter expression (e.g., 'pagePath=your_page_path')", default=None)
    parser.add_argument("-d", "--dimensions", help="Comma-separated list of dimensions (e.g., 'pagePath,country'). To include domain/hostname, use 'hostname,pagePath'", default='pagePath')
    parser.add_argument("-m", "--metrics", help="Comma-separated list of metrics (e.g., 'screenPageViews,totalAdRevenue')", default='screenPageViews')
    parser.add_argument("-n", "--name", help="Base output file name (without extension)", default=None)
    parser.add_argument("-t", "--test", type=int, help="Limit results to n rows (for testing)", default=None)
    parser.add_argument("-l", "--list_properties", action="store_true", help="List available GA4 properties for the current user.") # Added list_properties flag
    args = parser.parse_args()

    if args.list_properties:
        properties_df = list_properties(args.credentials_name)
        if properties_df is not None and not properties_df.empty:
            print("\nAvailable GA4 Properties:")
            print(properties_df.to_string(index=False))
        elif properties_df is not None:
            print("No GA4 properties found for this account.")
        else:
            print("Failed to retrieve GA4 property list.")
    else: # Proceed with report generation if not listing properties
        if not args.start_date or not args.end_date: # property_id is now optional, removed from required check
            print("Error: When generating a report, start_date and end_date are required.")
            sys.exit(1)

        combined_df = pd.DataFrame() # Initialize empty DataFrame to store combined data
        output_filename_base = args.name if args.name else f"combined-analytics-{datetime.now().strftime('%Y%m%d%H%M%S')}" # Filename for combined output
        properties_df = None # Initialize properties_df outside the if block

        if args.property_id is None: # Handle case where property_id is missing - list properties and run for all
            print("No property ID provided. Listing all available properties and running report for each.")
            properties_df_list = list_properties(args.credentials_name)
            if properties_df_list is not None and not properties_df_list.empty:
                print(f"Found {len(properties_df_list)} properties. Processing reports...")
                for index, row in tqdm(properties_df_list.iterrows(), total=len(properties_df_list), desc="Processing Properties"):
                    prop_id = str(row['property_id'])
                    prop_name = str(row['property_name'])
                    tqdm.write(f"Processing property: {prop_name} ({prop_id})")
                    df_property = produce_report(args.start_date, args.end_date, prop_id, prop_name, args.credentials_name, args.filter, args.dimensions, args.metrics, args.test)
                    if df_property is not None:
                        combined_df = pd.concat([combined_df, df_property], ignore_index=True)
                if combined_df.empty:
                    print("No data retrieved from any properties.")
                else:
                    print("Reports generated for all properties.")

            elif properties_df_list is not None:
                print("No GA4 properties found for this account. Cannot generate report.")
            else:
                print("Failed to retrieve GA4 property list. Cannot generate report.")


        elif os.path.isfile(args.property_id): # Check if -p arg is a file path
            print(f"Reading property IDs from CSV file: {args.property_id}")
            try:
                properties_df = pd.read_csv(args.property_id) # Load properties_df here
                if properties_df.columns.size < 2:
                    raise ValueError("CSV file must contain at least two columns: property_id and property_name.")
                for index, row in tqdm(properties_df.iterrows(), total=len(properties_df), desc="Processing Properties"): # Wrap loop with tqdm
                    prop_id = str(row.iloc[0]) # Assuming first column is property ID
                    prop_name = str(row.iloc[1]) if properties_df.columns.size > 1 else "UnknownProperty" # Assuming second column is property name, default if not provided

                    tqdm.write(f"Processing property: {prop_name} ({prop_id})") # Use tqdm.write instead of print

                    df_property = produce_report(args.start_date, args.end_date, prop_id, prop_name, args.credentials_name, args.filter, args.dimensions, args.metrics, args.test) # Using credentials_name
                    if df_property is not None: # Check if DataFrame is returned successfully
                        combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


            except FileNotFoundError:
                print(f"Error: Property ID CSV file not found: {args.property_id}")
            except pd.errors.EmptyDataError:
                print(f"Error: Property ID CSV file is empty: {args.property_id}")
            except ValueError as ve:
                print(f"Error reading Property ID CSV file: {ve}")
            except Exception as e:
                print(f"An unexpected error occurred while processing Property ID CSV file: {e}")


        elif is_number(args.property_id): # If -p arg is a number, treat as single property ID
            print(f"Processing single property ID: {args.property_id}")
            df_property = produce_report(args.start_date, args.end_date, args.property_id, "SingleProperty", args.credentials_name, args.filter, args.dimensions, args.metrics, args.test) # Using credentials_name, default property name
            if df_property is not None: # Check if DataFrame is returned successfully
                combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


        else:
            print("Error: -p argument should be either a Property ID (number), a path to a CSV file, or omitted to process all properties.")

        if not combined_df.empty: # Save combined DataFrame only if it's not empty
            # Create DataFrame from args
            params_dict = {
                'start_date': [args.start_date],
                'end_date': [args.end_date],
                'property_id': [args.property_id if args.property_id else 'ALL_PROPERTIES_LISTED'], # Indicate all properties if -p is omitted
                'credentials_name': [args.credentials_name], # Changed to credentials_name
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
# python GA4query3.py -c my_oauth_creds -l

# Single Property ID (OAuth)
# python GA4query3.py 2024-10-01 2024-10-31 -p 313646501 -c my_oauth_creds -m totalAdRevenue -n my_oauth_report

# Multiple Property IDs from CSV (OAuth)
# python GA4query3.py 2024-10-01 2024-10-31 -p properties.csv -c my_oauth_creds -m screenPageViews -n my_oauth_report

# Run report for ALL properties (OAuth)
# python GA4query3.py 2024-10-01 2024-10-31 -c my_oauth_creds -m screenPageViews -n all_properties_report


# Include hostname/domain in the report
# python GA4query3.py 2024-10-01 2024-10-31 -p 313646501 -c my_oauth_creds -d hostname,pagePath -m screenPageViews -n my_domain_report
# or for multiple properties:
# python GA4query3.py 2024-10-01 2024-10-31 -p properties.csv -c my_oauth_creds -d hostname,pagePath -m screenPageViews -n my_domain_report

# Other userful dimensions:
# -d pagePath,pageTitle,hostname
# -d pagePath,country,city
# -d pagePath,deviceCategory