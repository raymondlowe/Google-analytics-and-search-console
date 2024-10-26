# filename: GA4query.py

import argparse
import datetime
import time
import win_unicode_console
from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from googleAPIget_service import get_service  # Assuming this is adapted for GA4
import pandas as pd
from pandas import ExcelWriter
from progress.bar import IncrementalBar
from googleapiclient.errors import HttpError
from urllib.parse import urlparse

win_unicode_console.enable()

parser = argparse.ArgumentParser()

parser.add_argument("start_date", help="Start date in format yyyy-mm-dd or 'yesterday', '7DaysAgo'")
parser.add_argument("end_date", help="End date in format yyyy-mm-dd or 'today'")
parser.add_argument("-f", "--filters", default='', help="Filter string for GA4 API")  # Adapted for GA4
parser.add_argument("-d", "--dimensions", default="pagePath", help="Comma-separated dimensions for GA4 API")
parser.add_argument("-m", "--metrics", default="activeUsers", help="Comma-separated metrics for GA4 API")
parser.add_argument("-n", "--name", default='analytics-' + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"), type=str,
                    help="File name for output")
parser.add_argument("-t", "--test", nargs='?', const=3, type=int, help="Test mode: limit to n properties")
parser.add_argument("-w", "--wait", type=int, default=0, help="Wait time in seconds between API calls")
parser.add_argument("-g", "--googleaccount", type=str, required=True,
                    help="Google account token or file with account tokens, one per line")

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


options = [[start_date, end_date, filters, dimensions, metrics, name, googleaccountstring]]
optionsdf = pd.DataFrame(options,
                         columns=["start_date", "end_date", "filters", "dimensions", "metrics", "name", "Google Account"])

splitMetrics = metrics.split(',')


combined_df = pd.DataFrame()
google_accounts_list = [args.googleaccount]  # Initialize for single account case

try:  # Handling multiple accounts
    google_accounts_list = open(args.googleaccount).read().splitlines()
    google_accounts_list = [x.strip() for x in google_accounts_list if x.strip()]
except FileNotFoundError:
    pass  # Proceed with single account

for google_account in google_accounts_list:
    print(f"Processing account: {google_account}")
    admin_client = AnalyticsAdminServiceClient()  # No credentials needed here, uses GOOGLE_APPLICATION_CREDENTIALS
    data_client = BetaAnalyticsDataClient()  # No credentials needed here, uses GOOGLE_APPLICATION_CREDENTIALS


    properties = admin_client.list_properties(filter_=f"parent:accounts/{google_account.split('-')[0]}")
    property_count = len(list(properties))

    if property_count == 0:
        print("No accessible GA4 properties found for account %s" % (google_account))
        continue

    print(f"Processing: {google_account}")
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
                    property=f"properties/{property_.name.split('/')[-1]}",  # Use property name from list
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
                df.insert(0, 'google_account', google_account)  # Add Google Account column
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