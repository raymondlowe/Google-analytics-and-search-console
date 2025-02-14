import argparse
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
# import matplotlib.pyplot as plt
# import seaborn as sns
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest, OrderBy, FilterExpression, Filter
from tqdm import tqdm # Import tqdm for progress bar

def format_report(request, property_id, property_name):
    """Formats the GA4 API response into a Pandas DataFrame and adds property info."""
    try:
        client = BetaAnalyticsDataClient()
        response = client.run_report(request)

    except Exception as e:
        print(f"Error fetching data from GA4 API for property {property_name} ({property_id}): {e}")
        return None

    if not response.rows:
        print(f"No data found for property {property_name} ({property_id}) for this query.")
        return pd.DataFrame()
    try:
        # Get dimension and metric headers
        dimension_headers = [header.name for header in response.dimension_headers]
        metric_headers = [header.name for header in response.metric_headers]

        # Create empty lists to store data.
        data = {header: [] for header in dimension_headers + metric_headers}

        # Iterate through rows and append data
        for row in response.rows:
            for i, dim_val in enumerate(row.dimension_values):
                data[dimension_headers[i]].append(dim_val.value)
            for i, metric_val in enumerate(row.metric_values):
                data[metric_headers[i]].append(float(metric_val.value)) # convert to float instead of string

        # Create DataFrame
        df = pd.DataFrame(data)

        # Add property ID and Name columns
        df['property_id'] = property_id
        df['property_name'] = property_name
        return df

    except Exception as e:
        print(f"An error occurred during report formatting for property {property_name} ({property_id}): {e}")
        return None


def produce_report(start_date, end_date, property_id, property_name, credentials_path, filter_expression=None, dimensions='pagePath', metrics='screenPageViews', test=None): # Removed name arg
    """Fetches and processes data from the GA4 API for a single property and returns DataFrame.""" # Modified docstring
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
            filter_expression_list = [FilterExpression(filter = Filter(field_name = filter_expression.split('=')[0], string_filter= {'value': filter_expression.split('=')[1]}))] # corrected filter syntax
            request.filter = filter_expression_list[0]


        df = format_report(request, property_id, property_name) # Pass property info to format_report
        if df is None:
            return None  # Return None if data fetch failed, important for combining

        if test:
            df = df.head(test)

        return df # Return the DataFrame instead of saving

    except Exception as e:
        print(f"An error occurred while processing property '{property_name} ({property_id})': {e}")
        return None # Return None in case of error


def is_number(s):
    """Checks if a string is a number."""
    try:
        float(s)
        return True
    except ValueError:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and process data from Google Analytics 4 for single or multiple properties into a single output file.") # Modified description
    parser.add_argument("start_date", help="Start date (yyyy-mm-dd)")
    parser.add_argument("end_date", help="End date (yyyy-mm-dd)")
    parser.add_argument("-p", "--property_id", help="Google Analytics 4 property ID or path to CSV file with property IDs and names.", required=True)
    parser.add_argument("-c", "--credentials", help="Path to Google Cloud credentials JSON file", required=True)
    parser.add_argument("-f", "--filter", help="Filter expression (e.g., 'pagePath=your_page_path')", default=None)
    parser.add_argument("-d", "--dimensions", help="Dimension (e.g., 'pagePath')", default='pagePath')
    parser.add_argument("-m", "--metrics", help="Comma-separated list of metrics (e.g., 'screenPageViews,totalAdRevenue')", default='screenPageViews')
    parser.add_argument("-n", "--name", help="Base output file name (without extension)", default=None)
    parser.add_argument("-t", "--test", type=int, help="Limit results to n rows (for testing)", default=None)
    args = parser.parse_args()

    combined_df = pd.DataFrame() # Initialize empty DataFrame to store combined data
    output_filename_base = args.name if args.name else f"combined-analytics-{datetime.now().strftime('%Y%m%d%H%M%S')}" # Filename for combined output

    if os.path.isfile(args.property_id): # Check if -p arg is a file path
        print(f"Reading property IDs from CSV file: {args.property_id}")
        try:
            properties_df = pd.read_csv(args.property_id)
            if properties_df.columns.size < 2:
                raise ValueError("CSV file must contain at least two columns: property_id and property_name.")
            for index, row in tqdm(properties_df.iterrows(), total=len(properties_df), desc="Processing Properties"): # Wrap loop with tqdm
                prop_id = str(row.iloc[0]) # Assuming first column is property ID
                prop_name = str(row.iloc[1]) if properties_df.columns.size > 1 else "UnknownProperty" # Assuming second column is property name, default if not provided

                tqdm.write(f"Processing property: {prop_name} ({prop_id})") # Use tqdm.write instead of print

                df_property = produce_report(args.start_date, args.end_date, prop_id, prop_name, args.credentials, args.filter, args.dimensions, args.metrics, args.test) # Removed name arg from call
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
        df_property = produce_report(args.start_date, args.end_date, args.property_id, "SingleProperty", args.credentials, args.filter, args.dimensions, args.metrics, args.test) # Removed name arg from call, default property name
        if df_property is not None: # Check if DataFrame is returned successfully
            combined_df = pd.concat([combined_df, df_property], ignore_index=True) # Append to combined DataFrame


    else:
        print("Error: -p argument should be either a Property ID (number) or a path to a CSV file.")

    if not combined_df.empty: # Save combined DataFrame only if it's not empty
        # Create DataFrame from args
        params_dict = {
            'start_date': [args.start_date],
            'end_date': [args.end_date],
            'property_id': [args.property_id],
            'credentials': [args.credentials],
            'filter': [args.filter],
            'dimensions': [args.dimensions],
            'metrics': [args.metrics],
            'test': [args.test]
        }
        params_df = pd.DataFrame(params_dict)

        # Save to Excel with two sheets
        with pd.ExcelWriter(f"{output_filename_base}.xlsx") as writer:
            combined_df.to_excel(writer, sheet_name='data', index=False)
            params_df.to_excel(writer, sheet_name='params', index=False)

        combined_df.to_csv(f"{output_filename_base}.csv", index=False)
        print(f"Combined report saved to {output_filename_base}.xlsx and {output_filename_base}.csv")
    else:
        print("No data to save in the combined report.")

## Example usage:

# Single Property ID (as before - will still produce combined output, though only for one property)
# python GA4query2.py 2024-10-01 2024-10-31 -p 313646501 -c Quickstart-1bfb41aa93a5.json -m totalAdRevenue -n my_combined_report

# Multiple Property IDs from CSV
# python GA4query2.py 2024-10-01 2024-10-31 -p properties.csv -c Quickstart-1bfb41aa93a5.json -m screenPageViews -n my_combined_report