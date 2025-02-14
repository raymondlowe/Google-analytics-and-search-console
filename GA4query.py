# filename: GA4query.py

import argparse
import datetime
import time
import platform  # For OS detection
import webbrowser  # For opening URLs
import re  # For parsing error messages
import os
import pickle

from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from google.api_core.exceptions import PermissionDenied
import pandas as pd
from pandas import ExcelWriter
from progress.bar import IncrementalBar


# OS-specific console setup
if platform.system() == "Windows":
    import win_unicode_console  # Import only if on Windows
    win_unicode_console.enable()

parser = argparse.ArgumentParser()

parser.add_argument("start_date", help="Start date in format yyyy-mm-dd or 'yesterday', '7DaysAgo'")
parser.add_argument("end_date", help="End date in format yyyy-mm-dd or 'today'")
parser.add_argument("-f", "--filters", default='', help="Filter string for GA4 API")
parser.add_argument("-d", "--dimensions", default="pagePath", help="Comma-separated dimensions for GA4 API")
parser.add_argument("-m", "--metrics", default="activeUsers", help="Comma-separated metrics for GA4 API")
parser.add_argument("-n", "--name", default='analytics-' + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"), type=str,
                    help="File name for output")
parser.add_argument("-t", "--test", nargs='?', const=3, type=int, help="Test mode: limit to n properties")
parser.add_argument("-w", "--wait", type=int, default=0, help="Wait time in seconds between API calls")
parser.add_argument("-g", "--googleaccount", type=str, required=True,
                    help="Google account email or file with account emails, one per line")
parser.add_argument("-s", "--secrets", type=str, required=True, help="Path to client_secrets.json")

args = parser.parse_args()

start_date = args.start_date
end_date = args.end_date
filters = args.filters
dimensions = args.dimensions
metrics = args.metrics
name = args.name
test = args.test
googleaccountstring = args.googleaccount
wait_seconds = args.wait
CLIENT_SECRETS_FILE = args.secrets
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

options = [[start_date, end_date, filters, dimensions, metrics, name, googleaccountstring]]
optionsdf = pd.DataFrame(options,
                         columns=["start_date", "end_date", "filters", "dimensions", "metrics", "name", "Google Account"])

splitMetrics = metrics.split(',')



def authenticate_and_get_clients(google_account_email, client_secrets_file):
    """Authenticates the user and returns GA4 clients."""

    creds = None

    token_pickle_file = f"token_{google_account_email.replace(':', '_')}.pickle"

    if os.path.exists(token_pickle_file):
        with open(token_pickle_file, 'rb') as token:
            creds = pickle.load(token)

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        creds = flow.run_local_server(port=0)

        store_credentials = input(f"Do you want to store credentials for {google_account_email} for future use? (yes/no): ")
        if store_credentials.lower() == "yes":
           with open(token_pickle_file, 'wb') as token:
               pickle.dump(creds, token)

    try:
        data_client = BetaAnalyticsDataClient(credentials=creds)
        admin_client = AnalyticsAdminServiceClient(credentials=creds)

        account_id = google_account_email.split('@')[0] # Fix: split at "@"
        admin_client.list_properties(filter_=f"parent:accounts/{account_id}", page_size=1) # Test API call
        return admin_client, data_client

    except PermissionDenied as e:
        match = re.search(r"project (\d+).*https://console\.developers\.google\.com/apis/api/[^/]+/overview\?project=(\d+)", e.message, re.DOTALL)
        if match:
            project_id = match.group(1)
            url = f"https://console.developers.google.com/apis/api/analyticsdata.googleapis.com/overview?project={project_id}"
            print(f"Google Analytics Data API not enabled for project {project_id}.")
            print(f"Opening URL to enable the API: {url}")
            webbrowser.open(url)
            input("Press Enter to continue after enabling the API in your browser...")
        else:
            print(f"An unexpected PermissionDenied error occurred:\n{e.message}")
        exit(1)

    except HttpError as err:
        print(f"An HTTP error occurred: {err.resp.status} {err._get_reason()}")
        exit(1)

    except Exception as e:
        print("An unexpected error occurred:", e)
        exit(1)



combined_df = pd.DataFrame()
google_accounts_list = []

try:
    with open(args.googleaccount, 'r') as f:
        google_accounts_list = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    google_accounts_list = [args.googleaccount]


for google_account_email in google_accounts_list:
    print(f"Processing account: {google_account_email}")
    admin_client, data_client = authenticate_and_get_clients(google_account_email, CLIENT_SECRETS_FILE)

    if admin_client is None or data_client is None:
        print(f"Authentication failed for {google_account_email}. Skipping.")
        continue

    try:
        properties = admin_client.list_properties(filter_=f"parent:accounts/{google_account_email.split('@')[0]}")
    except HttpError as err:
        print(f"Error listing properties for {google_account_email}: {err.resp.status} {err._get_reason()}")
        continue
    except Exception as e:
        print(f"An unexpected error occurred listing properties for {google_account_email}: {e}")
        continue

    property_count = len(list(properties))

    if property_count == 0:
        print("No accessible GA4 properties found for account %s" % (google_account_email))
        continue

    print(f"Processing: {google_account_email}")
    print(f"Total GA4 properties: {property_count}")
    bar = IncrementalBar('Processing', max=property_count)
    property_counter = 0
    for property_ in properties:
        if args.test is not None and property_counter == args.test:
            break
        bar.next()
        property_counter += 1
        try:
            response = data_client.run_report(
                RunReportRequest(
                    property=f"properties/{property_.name.split('/')[-1]}",
                    dimensions=[Dimension(name=dim) for dim in args.dimensions.split(",")],
                    metrics=[Metric(name=met) for met in args.metrics.split(",")],
                    date_ranges=[DateRange(start_date=args.start_date, end_date=args.end_date)],
                    # Add filters if provided...
                )
            )
            df = pd.DataFrame([
                {response.dimension_headers[i].name: row.dimension_values[i].value for i in range(len(response.dimension_headers))} |
                {response.metric_headers[i].name: row.metric_values[i].value for i in range(len(response.metric_headers))}
                for row in response.rows
            ])
            if not df.empty:
                df.insert(0, 'google_account_email', google_account_email)  # Add Google Account column
                combined_df = pd.concat([combined_df, df], ignore_index=True)

        except HttpError as err:
            print(err.resp.status, err._get_reason())
        except Exception as e:
            print("Error with %s: %s" % (property_.name, e))

        if args.wait > 0:
            time.sleep(args.wait)
    bar.finish()


if googleaccountstring > "" :
    name = googleaccountstring + "-" + name

combined_df.reset_index()

with ExcelWriter(name + '.xlsx') as writer:
    combined_df.to_excel(writer, sheet_name='data')
    optionsdf.to_excel(writer, sheet_name="Options")
print("Finished and outputted to Excel file")