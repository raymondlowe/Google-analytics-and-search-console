#!/usr/bin/env python3
"""
Example script demonstrating how to use the new modular API functions
for Google Analytics 4 and Search Console data fetching.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import GA4query3
import search_console_api

def demo_ga4_functions():
    """
    Demonstrate GA4 API functions
    """
    print("=" * 60)
    print("Google Analytics 4 API Demo")
    print("=" * 60)
    
    # Example auth identifier - replace with your own
    auth_identifier = "demo_auth"
    
    print(f"1. Listing available GA4 properties for auth: {auth_identifier}")
    print("-" * 40)
    
    try:
        properties_df = GA4query3.list_properties(auth_identifier, debug=True)
        if properties_df is not None and not properties_df.empty:
            print(f"Found {len(properties_df)} properties:")
            print(properties_df.to_string(index=False))
            
            # Get data for the first property as an example
            if len(properties_df) > 0:
                property_id = str(properties_df.iloc[0]['property_id'])
                property_name = str(properties_df.iloc[0]['property_name'])
                
                print(f"\n2. Fetching data for property: {property_name} ({property_id})")
                print("-" * 40)
                
                # Date range: last 30 days
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                
                data_df = GA4query3.produce_report(
                    start_date=start_date,
                    end_date=end_date,
                    property_id=property_id,
                    property_name=property_name,
                    account=auth_identifier,
                    dimensions='pagePath',
                    metrics='screenPageViews',
                    debug=True
                )
                
                if data_df is not None and not data_df.empty:
                    print(f"Retrieved {len(data_df)} rows of data:")
                    print(data_df.head().to_string(index=False))
                    
                    # Save to CSV as an example
                    filename = f"ga4_demo_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    data_df.to_csv(filename, index=False)
                    print(f"\nData saved to: {filename}")
                else:
                    print("No data returned")
            
        else:
            print("No properties found or authentication failed")
            print("Make sure you have:")
            print("1. google-cloud-credentials.json file in the current directory")
            print("2. Proper OAuth setup for your Google account")
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nThis is expected if you haven't set up authentication yet.")


def demo_search_console_functions():
    """
    Demonstrate Search Console API functions
    """
    print("\n" + "=" * 60)
    print("Google Search Console API Demo") 
    print("=" * 60)
    
    # Example Google account identifier - replace with your own
    google_account = "demo_account"
    
    print(f"Fetching Search Console data for account: {google_account}")
    print("-" * 40)
    
    try:
        # Date range: last 30 days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        data_df = search_console_api.fetch_search_console_data(
            start_date=start_date,
            end_date=end_date,
            search_type="web",
            dimensions="page",
            google_account=google_account,
            wait_seconds=0,
            debug=True
        )
        
        if data_df is not None and not data_df.empty:
            print(f"Retrieved {len(data_df)} rows of Search Console data:")
            print(data_df.head().to_string(index=False))
            
            # Save to CSV as an example
            filename = f"gsc_demo_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            data_df.to_csv(filename, index=False)
            print(f"\nData saved to: {filename}")
            
            # Also demonstrate the save function
            search_console_api.save_search_console_data(
                data_df=data_df,
                start_date=start_date,
                end_date=end_date,
                dimensions="page",
                name="demo_gsc_output",
                search_type="web",
                google_account=google_account
            )
            
        else:
            print("No data returned or authentication failed")
            print("Make sure you have:")
            print("1. client_secrets.json file in the current directory")
            print("2. Proper OAuth setup for Search Console")
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nThis is expected if you haven't set up authentication yet.")


def demo_gradio_api_usage():
    """
    Demonstrate how to use the Gradio API programmatically
    """
    print("\n" + "=" * 60)
    print("Gradio API Usage Demo")
    print("=" * 60)
    
    print("To use the Gradio API, first start the server:")
    print("python gradio_app.py")
    print("\nThen you can use the gradio_client to interact with it:")
    print()
    
    example_code = '''
from gradio_client import Client

# Connect to the running Gradio app
client = Client("http://127.0.0.1:7860/")

# Fetch GA4 data via API
result = client.predict(
    "Google Analytics 4 (GA4)",  # data_source
    "2024-01-01",               # start_date
    "2024-01-31",               # end_date  
    "",                         # property_id (empty for all)
    "your_auth_id",             # auth_identifier
    "pagePath",                 # dimensions
    "screenPageViews",          # metrics
    "",                         # filter
    "",                         # gsc_account (not used for GA4)
    "web",                      # gsc_search_type (not used for GA4)
    "page",                     # gsc_dimensions (not used for GA4)
    0,                          # gsc_wait_seconds (not used for GA4)
    False,                      # debug_mode
    api_name="/process_query"
)

# The result contains: [status_message, dataframe, csv_file, properties_table]
status, data_df, csv_file, properties = result
print(f"Status: {status}")
if data_df:
    print(f"Retrieved {len(data_df['data'])} rows")
'''
    
    print(example_code)
    
    print("\nFor REST API access with curl:")
    print()
    
    curl_example = '''
curl -X POST "http://127.0.0.1:7860/api/process_query" \\
  -H "Content-Type: application/json" \\
  -d '{
    "data": [
      "Google Analytics 4 (GA4)",
      "2024-01-01",
      "2024-01-31", 
      "",
      "your_auth_id",
      "pagePath",
      "screenPageViews",
      "",
      "",
      "web", 
      "page",
      0,
      false
    ]
  }'
'''
    
    print(curl_example)


if __name__ == "__main__":
    print("Google Analytics & Search Console API Demo")
    print("This script demonstrates the new modular API functions.")
    print("\nNOTE: This demo requires proper authentication setup.")
    print("See GRADIO_README.md for setup instructions.\n")
    
    # Run the demos
    demo_ga4_functions()
    demo_search_console_functions() 
    demo_gradio_api_usage()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Set up your Google OAuth credentials")
    print("2. Run: python gradio_app.py")
    print("3. Visit: http://127.0.0.1:7860")
    print("4. Use the web interface or API endpoints")