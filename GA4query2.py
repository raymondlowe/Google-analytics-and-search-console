import argparse
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
# import matplotlib.pyplot as plt
# import seaborn as sns
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest, OrderBy

def format_report(request):
    """Formats the GA4 API response into a Pandas DataFrame."""
    try:
        client = BetaAnalyticsDataClient()
        response = client.run_report(request)

    except Exception as e:
        print(f"Error fetching data from GA4 API: {e}")
        return None  # Or raise the exception, depending on your error handling strategy


        if not response.rows:
            print("No data found for this query.")
            return pd.DataFrame()
    try:
        # Get dimension and metric headers
        dimension_headers = [header.name for header in response.dimension_headers]
        metric_headers = [header.name for header in response.metric_headers]

        # Create empty lists to store data. The size of each array is determined by the response.
        data = {header: [] for header in dimension_headers + metric_headers}

        # Iterate through rows and append data
        for row in response.rows:
            for i, dim_val in enumerate(row.dimension_values):
                data[dimension_headers[i]].append(dim_val.value)
            for i, metric_val in enumerate(row.metric_values):
                data[metric_headers[i]].append(str(metric_val.value)) # added str() to convert to string to handle potential issues

        # Create DataFrame
        return pd.DataFrame(data)

    except Exception as e:
        print(f"An error occurred during report formatting: {e}")
        return None




def produce_report(start_date, end_date, property_id, credentials_path, filter_expression=None, dimensions='pagePath', metrics='screenPageViews', name=None, test=None, wait=0):
    """Fetches and processes data from the GA4 API.
    
    Args:
        metrics: Single metric or comma-separated list of metrics (e.g., 'screenPageViews' or 'screenPageViews,totalAdRevenue')
    """
    try:
        # Validate dates (add more robust date validation if needed)
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Split metrics into list and create Metric objects
        metric_list = [metric.strip() for metric in metrics.split(',')]
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name=dimensions)],
            metrics=[Metric(name=metric) for metric in metric_list],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )

        # Add filter if provided
        if filter_expression:
            filter_expression_list = [FilterExpression(filter = Filter(fieldName = filter_expression.split('=')[0], filterType = 'IN', stringValues = [filter_expression.split('=')[1]]))]
            request.filter = filter_expression_list[0]

        df = format_report(request)
        if df is None:
            return  # Exit if data fetch failed

        if test:
            df = df.head(test)

        if name is None:
            name = f"analytics-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        df.to_excel(f"{name}.xlsx")
        df.to_csv(f"{name}.csv")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and process data from Google Analytics 4.")
    parser.add_argument("start_date", help="Start date (yyyy-mm-dd)")
    parser.add_argument("end_date", help="End date (yyyy-mm-dd)")
    parser.add_argument("-p", "--property_id", help="Google Analytics 4 property ID", required=True)
    parser.add_argument("-c", "--credentials", help="Path to Google Cloud credentials JSON file", required=True)
    parser.add_argument("-f", "--filter", help="Filter expression (e.g., 'pagePath=your_page_path')", default=None) # Changed to filter
    parser.add_argument("-d", "--dimensions", help="Dimension (e.g., 'pagePath').  Add 'ga:' prefix", default='pagePath')
    parser.add_argument("-m", "--metrics", help="Comma-separated list of metrics (e.g., 'screenPageViews,totalAdRevenue'). Add 'ga:' prefix", default='screenPageViews')
    parser.add_argument("-n", "--name", help="Output file name (without extension)", default=None)
    parser.add_argument("-t", "--test", type=int, help="Limit results to n (for testing)", default=None)
    args = parser.parse_args()
    produce_report(args.start_date, args.end_date, args.property_id, args.credentials, args.filter, args.dimensions, args.metrics, args.name, args.test)
    
    
    ## Example usage that works
    
    # python GA4query2.py 2024-10-01 2024-10-31 -p 313646501 -c Quickstart-1bfb41aa93a5.json -m totalAdRevenue
