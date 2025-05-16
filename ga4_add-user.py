from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/analytics.edit']

flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
credentials = flow.run_local_server(port=0)
service = build('analyticsadmin', 'v1beta', credentials=credentials)

def get_account_id():
    try:
        accounts = service.accounts().list().execute().get("accounts", [])
        if accounts:
            return accounts[0]['name']
        else:
            print("No accounts found.")
            return None
    except HttpError as e:
        print(f"An HTTP error occurred: {e}")
        return None

def list_properties(account_name):
    try:
        response = service.properties().list(filter=f"parent:{account_name}").execute()
        return response.get('properties', [])
    except HttpError as e:
        print(f"An HTTP error occurred listing properties: {e}")
        return []


def add_user_to_property(account_name, property_id, user_email):
    try:
        # Construct the effectivePermissions field correctly
        user_link = {
            "email_address": user_email,
            "effective_permissions": [
                {
                    "name": f"properties/{property_id}/permissions/READER" # Note the structure here!
                }
            ],
        }
        request = service.accounts().userLinks().create(parent=account_name, body=user_link)
        response = request.execute()
        print(f"User '{user_email}' added to property '{property_id}' with VIEW permissions.")
        return response
    except HttpError as e:
        print(f"An HTTP error occurred adding user to property {property_id}: {e}")
        return None


def main():
    account_name = get_account_id()
    if account_name:
        properties = list_properties(account_name)
        user_email_to_add = "user@example.com"  # Replace with the actual email address

        if properties:
            for property in properties:
                property_id = property['name'].split('/')[-1] # Extract property ID
                add_user_to_property(account_name, property_id, user_email_to_add)
        else:
            print("No properties found.")
    else:
        print("Could not retrieve account information.")


if __name__ == "__main__":
    main()