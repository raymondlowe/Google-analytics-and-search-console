import argparse
import httplib2

from apiclient.discovery import build
from oauth2client import file
from oauth2client import tools
from oauth2client import client
import logging
import os


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
  logger = logging.getLogger('googleAPIget_service') # Use a specific name

  # Parse command-line arguments.

  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      parents=[tools.argparser])
  # Always parse empty list, then set flag manually if needed
  flags = parser.parse_args([])
  if extra_auth_flags and extra_auth_flags.get('noauth_local_webserver'):
      setattr(flags, 'noauth_local_webserver', True)
  logger.debug(f"Auth flags set: {flags}")

  # Fix: treat None as empty string for usernameToken
  if not usernameToken:
    combined_client_secrets_path = client_secrets_path
  else:
    combined_client_secrets_path = str(usernameToken) + "-" + client_secrets_path
  logger.info(f"Attempting to use client secrets file: {combined_client_secrets_path}")

  # If the custom client secrets file does not exist, fall back to the default
  if not os.path.exists(combined_client_secrets_path):
    if usernameToken != "" and os.path.exists(client_secrets_path):
      # Fallback to default client_secrets.json
      combined_client_secrets_path = client_secrets_path
      logger.warning(f"Custom secrets file not found. Falling back to default: {client_secrets_path}")
    else:
      raise RuntimeError(f"Could not find Google client secrets file '{combined_client_secrets_path}'. This may be due to an invalid or missing 'auth_identifier' or secrets file. Checked: '{combined_client_secrets_path}' and '{client_secrets_path}'")

  # Set up a Flow object to be used if we need to authenticate.
  try:
    logger.debug(f"Creating OAuth flow from: {combined_client_secrets_path}")
    flow = client.flow_from_clientsecrets(
        combined_client_secrets_path, scope=scope,
        message=tools.message_if_missing(combined_client_secrets_path))
    logger.debug("OAuth flow created successfully.")
  except Exception as e:
    # Provide a clear error if the client secrets file is missing or invalid
    raise RuntimeError(f"Could not load Google client secrets file '{combined_client_secrets_path}'. This may be due to an invalid or missing 'auth_identifier' or secrets file. Details: {e}")

  # Ensure usernameToken is always a string, never None
  safe_username_token = str(usernameToken) if usernameToken else ""
  if safe_username_token == "":
    combined_data_file_name = api_name + '.dat'
  else:
    combined_data_file_name = safe_username_token + "-" + api_name + '.dat'
  logger.info(f"Using token storage file: {combined_data_file_name}")

  storage = file.Storage(combined_data_file_name)
  credentials = storage.get()
  logger.debug(f"Initial credentials from storage: {'Exists' if credentials else 'None'}")
  try:
    if credentials is None or credentials.invalid:
        if credentials is None:
            logger.warning(f"Credentials not found in '{combined_data_file_name}'.")
        else:
            logger.warning(f"Credentials in '{combined_data_file_name}' are invalid. Expired: {credentials.expired}")

        # In a server environment, we cannot run an interactive flow.
        # We can only try to refresh if we have a refresh token.
        if credentials and credentials.expired and credentials.refresh_token:
            logger.info("Attempting to refresh expired credentials...")
            try:
                # This is a potential blocking call
                credentials.refresh(httplib2.Http())
                storage.put(credentials)
                logger.info("Credentials refreshed successfully.")
            except client.HttpAccessTokenRefreshError as e:
                logger.error(f"Failed to refresh credentials: {e}")
                raise RuntimeError(
                    f"The credentials have expired and could not be refreshed. "
                    f"Please re-authenticate locally to generate a new token file: '{combined_data_file_name}'."
                )
        else:
            # If there's no refresh token or no credentials at all, we cannot proceed.
            logger.error("FATAL: No valid credentials and no refresh token available.")
            raise RuntimeError(
                f"Credentials not found or invalid in '{combined_data_file_name}'. "
                "Cannot run interactive auth flow in a server environment. "
                "Please run a local script to generate a valid token file."
            )
    logger.debug("Authorizing HTTP transport with credentials.")
    http = credentials.authorize(http=httplib2.Http())
    logger.debug("HTTP transport authorized.")
  except Exception as e:
    logger.error(f"Google OAuth authentication process failed for secrets file '{combined_client_secrets_path}'.", exc_info=True)
    raise RuntimeError(f"Google OAuth authentication failed. Details: {e}")

  # Build the service object.
  try:
    logger.debug(f"Building Google API service for '{api_name}' v'{api_version}'...")
    service = build(api_name, api_version, http=http)
    logger.info(f"Successfully built Google API service for '{api_name}' version '{api_version}'.")
  except Exception as e:
    logger.error(f"Failed to build Google API service for '{api_name}'.", exc_info=True)
    raise RuntimeError(f"Failed to build Google API service. Details: {e}")

  return service