import argparse
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

def list_ga4_properties(credentials_file):
    """Lists GA4 properties accessible with the provided credentials by iterating through accounts.
       Correctly extracts Property ID from the 'name' field.
    """

    try:
        creds = service_account.Credentials.from_service_account_file(credentials_file)

        # Build the Analytics Admin API client
        service = build('analyticsadmin', 'v1alpha', credentials=creds)

        all_properties = []

        # 1. List Accessible Accounts
        account_page_token = None
        while True:
            accounts_results = service.accounts().list(pageSize=100, pageToken=account_page_token).execute()
            accounts = accounts_results.get('accounts', [])

            if not accounts:
                break

            for account in accounts:
                account_id = account.get('name').split('/')[-1] # Extract account ID

                # 2. List Properties under each Account
                property_page_token = None
                while True:
                    properties_results = service.properties().list(
                        pageSize=100,
                        pageToken=property_page_token,
                        filter=f'parent:accounts/{account_id}' # Filter properties by account
                    ).execute()
                    property_list = properties_results.get('properties', [])

                    if not property_list:
                        break

                    for property_item in property_list:
                        # Extract property_id from the 'name' field:
                        property_id = property_item['name'].split('/')[-1]
                        property_name = property_item.get('displayName', 'Unknown')
                        all_properties.append({'id': property_id, 'name': property_name, 'account_id': account_id})

                    property_page_token = properties_results.get('nextPageToken')
                    if not property_page_token:
                        break

            account_page_token = accounts_results.get('nextPageToken')
            if not account_page_token:
                break

        return all_properties

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List GA4 properties accessible with a service account credential.")
    parser.add_argument("-c", "--credentials", help="Path to Google Cloud service account credentials JSON file", required=True)

    args = parser.parse_args()

    if not os.path.exists(args.credentials):
        print(f"Error: Credentials file not found at '{args.credentials}'")
    else:
        ga4_properties = list_ga4_properties(args.credentials)

        if ga4_properties:
            print("GA4 Properties accessible with these credentials:")
            for prop in ga4_properties:
                print(f"  Property ID: {prop['id']}, Name: {prop['name']}, Account ID: {prop['account_id']}")
        else:
            print("Could not retrieve GA4 properties or an error occurred.")