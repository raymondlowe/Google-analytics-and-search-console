# filename: ga4_property_access_automation.py

# pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client google-cloud-resource-manager google-cloud-iam


import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.cloud import resource_manager, iam
import time
import argparse
from datetime import datetime
from google.cloud import resource_manager_v1 as resource_manager

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly', 'https://www.googleapis.com/auth/cloud-platform']


def get_credentials(credentials_file):
    """Gets valid user credentials from storage.
    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(credentials_file):
        creds = Credentials.from_authorized_user_file(credentials_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(credentials_file, 'w') as token:
            token.write(creds.to_json())
    return creds

def get_ga4_properties(creds):
    """Retrieves a list of GA4 properties the user has access to."""
    service = build('analyticsadmin', 'v1alpha', credentials=creds)
    properties = []
    page_token = None
    while True:
      response = service.properties().list(pageSize=100, pageToken=page_token).execute()
      for property in response.get('properties', []):
        properties.append({'property_id': property['propertyUri'].split('/')[-1], 'property_name': property.get('displayName', 'Unknown')})
      page_token = response.get('nextPageToken', None)
      if not page_token:
        break
    return properties


def create_gcp_project(project_name_prefix):
    """Creates a new Google Cloud project."""
    project_name = f"{project_name_prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    resource_manager_client = resource_manager.Client()
    project = resource_manager_client.create_project(project_name, 'A new Google Cloud Project')
    print(f"Waiting for project {project_name} creation to complete...")
    while project.state != 'ACTIVE':
        time.sleep(5)
        project.reload()

    return project.project_id

def create_service_account_and_key(project_id, key_file_path):
    """Creates a service account and downloads the key file."""
    iam_client = iam.Client()
    service_account = iam_client.create_service_account(
        request={
            'accountId': 'ga4-api-access',
            'serviceAccountId': f'ga4-api-access-{datetime.now().strftime("%Y%m%d%H%M%S")}', # Unique name
            'displayName': f'GA4 API Access - {project_id}'
        },
        parent=f'projects/{project_id}'
    )

    key = service_account.create_signed_key(
        privateKeyType='TYPE_GOOGLE_CREDENTIALS'
    )

    with open(key_file_path, "w") as f:
        f.write(key.privateKeyData.decode())

    print(f"Service account key file saved to: {key_file_path}")
    return service_account.email

def grant_access_to_property(property_id, service_account_email, creds):
    """Grants the service account viewer access to the specified GA4 property."""
    service = build('analyticsadmin', 'v1alpha', credentials=creds)
    try:
        service.users().create(parent=f'properties/{property_id}', body={'email':service_account_email, 'direct_roles': ['READER']}).execute()
        print(f"Successfully granted access to service account {service_account_email} in property {property_id}")

    except Exception as e:
        print(f"Error granting access to property {property_id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automate GA4 property access for a service account.")
    parser.add_argument("-c", "--credentials", help="Path to existing Google account credentials file (JSON)", default="token.json")
    parser.add_argument("-k", "--keyfile", help="Path to save the service account key file (JSON)", default="service_account_key.json")
    parser.add_argument("-p", "--project_prefix", help="Prefix for the new Google Cloud project name", default="ga4-api-access")
    args = parser.parse_args()

    creds = get_credentials(args.credentials)
    properties = get_ga4_properties(creds)
    project_id = create_gcp_project(args.project_prefix)
    service_account_email = create_service_account_and_key(project_id, args.keyfile)

    for property in properties:
        grant_access_to_property(property['property_id'], service_account_email, creds)
        print(f"Access granted for property: {property['property_name']}")