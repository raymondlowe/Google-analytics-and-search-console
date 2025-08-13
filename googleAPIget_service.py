import argparse
import httplib2

from apiclient.discovery import build
from oauth2client import file
from oauth2client import tools
from oauth2client import client


def get_service(api_name, api_version, scope, client_secrets_path, usernameToken = "", extra_auth_flags=None):
  """Get a service that communicates to a Google API.

  Args:
    api_name: string The name of the api to connect to.
    api_version: string The api version to connect to.
    scope: A list of strings representing the auth scopes to authorize for the
      connection.
    client_secrets_path: string A path to a valid client secrets file.

  Returns:
    A service that is connected to the specified API.
  """
  # Parse command-line arguments.

  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      parents=[tools.argparser])
  # Always parse empty list, then set flag manually if needed
  flags = parser.parse_args([])
  if extra_auth_flags and extra_auth_flags.get('noauth_local_webserver'):
      setattr(flags, 'noauth_local_webserver', True)

  import os
  # Fix: treat None as empty string for usernameToken
  if not usernameToken:
    combined_client_secrets_path = client_secrets_path
  else:
    combined_client_secrets_path = str(usernameToken) + "-" + client_secrets_path

  # If the custom client secrets file does not exist, fall back to the default
  if not os.path.exists(combined_client_secrets_path):
    if usernameToken != "" and os.path.exists(client_secrets_path):
      # Fallback to default client_secrets.json
      combined_client_secrets_path = client_secrets_path
    else:
      raise RuntimeError(f"Could not find Google client secrets file '{combined_client_secrets_path}'. This may be due to an invalid or missing 'auth_identifier' or secrets file. Checked: '{combined_client_secrets_path}' and '{client_secrets_path}'")

  # Set up a Flow object to be used if we need to authenticate.
  try:
    flow = client.flow_from_clientsecrets(
        combined_client_secrets_path, scope=scope,
        message=tools.message_if_missing(combined_client_secrets_path))
  except Exception as e:
    # Provide a clear error if the client secrets file is missing or invalid
    raise RuntimeError(f"Could not load Google client secrets file '{combined_client_secrets_path}'. This may be due to an invalid or missing 'auth_identifier' or secrets file. Details: {e}")

  # Prepare credentials, and authorize HTTP object with them.
  # If the credentials don't exist or are invalid run through the native client
  # flow. The Storage object will ensure that if successful the good
  # credentials will get written back to a file.

  # Ensure usernameToken is always a string, never None
  safe_username_token = str(usernameToken) if usernameToken else ""
  if safe_username_token == "":
    combined_data_file_name = api_name + '.dat'
  else:
    combined_data_file_name = safe_username_token + "-" + api_name + '.dat'

  storage = file.Storage(combined_data_file_name)
  credentials = storage.get()
  try:
    if credentials is None or credentials.invalid:
      credentials = tools.run_flow(flow, storage, flags)
    http = credentials.authorize(http=httplib2.Http())
  except Exception as e:
    raise RuntimeError(f"Google OAuth authentication failed for secrets file '{combined_client_secrets_path}'. Details: {e}")

  # Build the service object.
  try:
    service = build(api_name, api_version, http=http)
  except Exception as e:
    raise RuntimeError(f"Failed to build Google API service for '{api_name}'. Details: {e}")

  return service