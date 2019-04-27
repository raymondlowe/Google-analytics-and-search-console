import argparse
import datetime
import win_unicode_console
from apiclient.discovery import build
import httplib2
from oauth2client import client
from oauth2client import file
from oauth2client import tools
import pandas as pd
import openpyxl
from progress.bar import IncrementalBar

win_unicode_console.enable()

# copied from original
def get_service(api_name, api_version, scope, client_secrets_path):
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
  flags = parser.parse_args([])

  # Set up a Flow object to be used if we need to authenticate.
  flow = client.flow_from_clientsecrets(
      client_secrets_path, scope=scope,
      message=tools.message_if_missing(client_secrets_path))

  # Prepare credentials, and authorize HTTP object with them.
  # If the credentials don't exist or are invalid run through the native client
  # flow. The Storage object will ensure that if successful the good
  # credentials will get written back to a file.
  storage = file.Storage(api_name + '.dat')
  credentials = storage.get()
  if credentials is None or credentials.invalid:
    credentials = tools.run_flow(flow, storage, flags)
  http = credentials.authorize(http=httplib2.Http())

  # Build the service object.
  service = build(api_name, api_version, http=http)

  return service

parser = argparse.ArgumentParser()

#when doing argument parsing in command terminal put python before file name. No idea why, so just do it.


#parser.add_argument("viewProfileID",type=int, help="GA View (profile) ID as a number") !!!already got this from loop!!!
parser.add_argument("start_date", help="start date in format yyyy-mm-dd or 'yesterday' '7DaysAgo'")
parser.add_argument("end_date", help="start date in format yyyy-mm-dd or 'today'")
parser.add_argument("-t", "--type", default="web", choices=("image","video","web"), help="Search types for the returned data, default is web")
#parser.add_argument("-f","--filters",default=2,type=int, help="Minimum number for metric, default is 2")
parser.add_argument("-d","--dimensions",default="page", help="The dimensions are the left hand side of the table, default is page")
#parser.add_argument("-m","--metrics",default="pageviews", help="The metrics are the things on the left, default is pageviews")
parser.add_argument("-n","--name",default='search-console' + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),type=str, help="File name for final output, default is finaloutput + the current date. You do NOT need to add file extension.")
#parser.add_argument("-c", "--clean", action="count", default=0, help="clean output skips header and count and just sends csv rows")

args = parser.parse_args()

start_date = args.start_date
end_date = args.end_date
#filters = args.filters
dimensions = args.dimensions
#metrics = args.metrics
name = args.name
dataType = args.type

## test vars defined here
# start_date = '2019-04-01'
# end_date = '2019-04-07'

# dimensions = 'page'
# name = 'output'

## end test vars

scope = ['https://www.googleapis.com/auth/webmasters.readonly']
# Authenticate and construct service.
service = get_service('webmasters', 'v3', scope, 'client_secrets.json')
profiles = service.sites().list().execute()
#profiles is now list    

print(len(profiles['siteEntry']))

bar = IncrementalBar('Processing',max=len(profiles['siteEntry']))


bigdf = pd.DataFrame()

for item in profiles['siteEntry']:
    bar.next()
    if item['permissionLevel'] != 'siteUnverifiedUser':

        smalldf = pd.DataFrame()

        #print(item['id'] + ',' + start_date + ',' + end_date)
        results = service.searchanalytics().query(
        siteUrl=item['siteUrl'], body={
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': [dimensions],
            'searchType': dataType,
            'rowLimit': 5000
        }).execute()

        if len(results) == 2:
            #print(results['rows'])
            #print(smalldf)
            smalldf = smalldf.append(results['rows'])
            #print(smalldf)
        
            smalldf.insert(0,'siteUrl',item['siteUrl'])
            #print(smalldf)
            if len(bigdf.columns) == 0:
                bigdf = smalldf.copy()
            else:
                bigdf = pd.concat([bigdf,smalldf])

            #print(bigdf)
            print('.',end='')
bar.finish()

bigdf.reset_index()
#bigdf.to_json("output.json",orient="records")

bigdf['keys'] = bigdf["keys"].str[0]

bigdf.to_excel(name + '.xlsx', sheet_name='data')
print("finished")

