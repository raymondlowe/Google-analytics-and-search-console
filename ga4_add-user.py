from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']

flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
credentials = flow.run_local_server(port=0)
service = build('analyticsadmin', 'v1beta', credentials=credentials)

def get_account_id():
    accounts = service.accounts().list().execute().get("accounts", [])
    if accounts:
      return accounts[0]['name'].split('/')[1] # Extract account ID from resource name
    else:
      print("No accounts found.")
      return None

def list_properties():
    account_id = get_account_id()
    if account_id:
        filter_expression = f"parent:accounts/{account_id}"  # Correct filter expression
        try:
            response = service.properties().list(filter=filter_expression).execute()
            properties = response.get('properties', [])
            if not properties:
                print("No properties found.")
            else:
                print("Properties:")
                for property in properties:
                    print(f"- Property ID: {property['name']} | Property Name: {property['displayName']}")
        except Exception as e:
            print(f"An error occurred: {e}")


list_properties()