import argparse
import datetime
import time
import asyncio
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from functools import wraps
import os
import pandas as pd
from pandas import ExcelWriter
import openpyxl
from progress.bar import IncrementalBar
from googleAPIget_service import get_service
from urllib.parse import urlparse
import diskcache as dc

# Import win_unicode_console only when needed for CLI
try:
    import win_unicode_console
    win_unicode_console.enable()
except ImportError:
    # Skip if not available (e.g., when running in web environments)
    pass

# Performance optimization: Domain caching to avoid repeated API calls
@dataclass
class CachedDomainList:
    """Cached domain list with timestamp for TTL management"""
    domains: List[Dict]
    timestamp: float
    account: str

# Disk-based cache for persistent caching across sessions
_cache_dir = os.path.join(os.path.expanduser("~"), ".ga_gsc_cache")
os.makedirs(_cache_dir, exist_ok=True)
_disk_cache = dc.Cache(_cache_dir, size_limit=500 * 1024 * 1024)  # 500MB limit

def persistent_cache(expire_time=86400, typed=False):
    """
    Disk-based cache decorator with configurable expiration time.
    
    Args:
        expire_time (int): Cache expiration time in seconds (default: 24 hours)
        typed (bool): Whether to cache based on argument types as well
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            if typed:
                cache_key += f":{hash(tuple(type(arg) for arg in args))}"
            
            # Try to get from cache
            cached_result = _disk_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Cache miss - call function and cache result
            result = func(*args, **kwargs)
            _disk_cache.set(cache_key, result, expire=expire_time)
            return result
        
        # Add cache management methods to the function
        def cache_info():
            """Get cache statistics"""
            return {
                'cache_size': len(_disk_cache),
                'cache_directory': _cache_dir,
                'function': func.__name__
            }
        
        def cache_clear():
            """Clear cache for this function"""
            keys_to_delete = [key for key in _disk_cache if key.startswith(f"{func.__name__}:")]
            for key in keys_to_delete:
                del _disk_cache[key]
        
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        return wrapper
    return decorator

def async_persistent_cache(expire_time=86400, typed=False):
    """
    Async version of persistent_cache decorator.
    
    Args:
        expire_time (int): Cache expiration time in seconds (default: 24 hours)
        typed (bool): Whether to cache based on argument types as well
    
    Returns:
        Async decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            if typed:
                cache_key += f":{hash(tuple(type(arg) for arg in args))}"
            
            # Try to get from cache
            cached_result = _disk_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Cache miss - call function and cache result
            result = await func(*args, **kwargs)
            _disk_cache.set(cache_key, result, expire=expire_time)
            return result
        
        # Add cache management methods to the function
        def cache_info():
            """Get cache statistics"""
            return {
                'cache_size': len(_disk_cache),
                'cache_directory': _cache_dir,
                'function': func.__name__
            }
        
        def cache_clear():
            """Clear cache for this function"""
            keys_to_delete = [key for key in _disk_cache if key.startswith(f"{func.__name__}:")]
            for key in keys_to_delete:
                del _disk_cache[key]
        
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        return wrapper
    return decorator

class DomainCache:
    """Thread-safe cache for GSC domain lists to optimize performance"""
    
    def __init__(self, ttl_seconds: int = 86400):  # 24 hour default TTL (domain lists rarely change)
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CachedDomainList] = {}
        self._lock = threading.Lock()
    
    def get(self, account: str) -> Optional[List[Dict]]:
        """Get cached domain list if still valid"""
        with self._lock:
            cached = self._cache.get(account)
            if cached and (time.time() - cached.timestamp) < self.ttl_seconds:
                return cached.domains
            return None
    
    def set(self, account: str, domains: List[Dict]) -> None:
        """Cache domain list with current timestamp"""
        with self._lock:
            self._cache[account] = CachedDomainList(
                domains=domains,
                timestamp=time.time(),
                account=account
            )
    
    def invalidate(self, account: str = None) -> None:
        """Invalidate cache for specific account or all accounts"""
        with self._lock:
            if account:
                self._cache.pop(account, None)
            else:
                self._cache.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics for monitoring"""
        with self._lock:
            current_time = time.time()
            valid_entries = sum(
                1 for cached in self._cache.values()
                if (current_time - cached.timestamp) < self.ttl_seconds
            )
            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'expired_entries': len(self._cache) - valid_entries,
                'ttl_seconds': self.ttl_seconds
            }

# Global domain cache instance
_domain_cache = DomainCache()

def get_current_date():
    """Get current date in YYYY-MM-DD format for AI clients"""
    return datetime.datetime.now().strftime('%Y-%m-%d')

def get_disk_cache_stats() -> Dict:
    """Get disk cache statistics for monitoring"""
    return {
        'cache_size': len(_disk_cache),
        'cache_directory': _cache_dir,
        'cache_size_mb': sum(os.path.getsize(os.path.join(_cache_dir, f)) 
                           for f in os.listdir(_cache_dir) if os.path.isfile(os.path.join(_cache_dir, f))) / (1024 * 1024)
    }

def clear_disk_cache():
    """Clear all disk cache entries"""
    _disk_cache.clear()

def invalidate_domain_cache(account: str = None) -> None:
    """Invalidate domain cache for specific account or all accounts"""
    _domain_cache.invalidate(account)

def get_domain_cache_stats() -> Dict:
    """Get domain cache statistics for monitoring"""
    return _domain_cache.get_stats()


@persistent_cache(expire_time=86400*7)  # Cache for 7 days since domain lists rarely change
def list_search_console_sites(google_account="", debug=False, use_cache=True):
    """
    List all available Google Search Console sites/domains for the authenticated account.
    
    Args:
        google_account (str): Google account identifier for secrets/tokens
        debug (bool): Enable debug output
        use_cache (bool): Use cached domain list if available (default: True)
        
    Returns:
        pandas.DataFrame: DataFrame with site URLs and domains, or None if error
    """
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    # Handle multiple google accounts if file is provided
    if not google_account or google_account.strip() == "":
        # No account specified, use only 'client_secrets.json' as secrets file
        googleaccounts_list = [""]
    else:
        try:
            googleaccounts_list = open(google_account).read().splitlines()
            # remove empty lines
            googleaccounts_list = [x.strip() for x in googleaccounts_list if x.strip()]
        except:
            googleaccounts_list = [google_account]

    if debug:
        print(f"Listing sites for {len(googleaccounts_list)} Google account(s)")

    all_sites = []

    for this_google_account in googleaccounts_list:
        # Check cache first if enabled
        if use_cache:
            cached_sites = _domain_cache.get(this_google_account)
            if cached_sites:
                if debug:
                    print(f"Using cached domain list for account: {this_google_account if this_google_account else 'default'}")
                all_sites.extend(cached_sites)
                continue
        
        if debug:
            print("Processing: " + (this_google_account if this_google_account else "default client_secrets.json"))
        
        try:
            # Authenticate and construct service
            service = get_service('webmasters', 'v3', scope, 'client_secrets.json', this_google_account)
            profiles = service.sites().list().execute()
            
            if 'siteEntry' not in profiles:
                if debug:
                    print("No siteEntry found for this profile")
                continue
            
            if debug:
                print(f"Found {len(profiles['siteEntry'])} site entries")
            
            account_sites = []  # Sites for this specific account
            
            for item in profiles['siteEntry']:
                if item['permissionLevel'] != 'siteUnverifiedUser':
                    # Parse the hostname - handle both URL-prefix and domain properties
                    site_url = item['siteUrl']
                    
                    if site_url.startswith('sc-domain:'):
                        # GSC Domain property (e.g., "sc-domain:example.com")
                        root_domain = site_url[10:]  # Remove "sc-domain:" prefix
                        property_type = 'Domain Property'
                    else:
                        # URL-prefix property (e.g., "https://example.com/")
                        root_domain = urlparse(site_url).hostname
                        property_type = 'URL-prefix Property'
                    
                    site_info = {
                        'siteUrl': site_url,
                        'domain': root_domain if root_domain else 'Unknown',
                        'permissionLevel': item['permissionLevel'],
                        'property_type': property_type,
                        'account': this_google_account if this_google_account else 'default'
                    }
                    account_sites.append(site_info)
                    all_sites.append(site_info)
            
            # Cache the sites for this account
            if use_cache and account_sites:
                _domain_cache.set(this_google_account, account_sites)
                if debug:
                    print(f"Cached {len(account_sites)} sites for account: {this_google_account if this_google_account else 'default'}")
                    
        except Exception as e:
            if debug:
                print(f"Error processing account {this_google_account}: {str(e)}")
            continue
    
    if all_sites:
        sites_df = pd.DataFrame(all_sites)
        return sites_df
    else:
        if debug:
            print("No accessible sites found")
        return None


@async_persistent_cache(expire_time=3600)  # Cache GSC data for 1 hour 
async def fetch_search_console_data_async(
    start_date,
    end_date,
    search_type="web",
    dimensions="page",
    google_account="",
    wait_seconds=0,
    debug=False,
    domain_filter=None,
    max_retries=3,
    retry_delay=5
):
    """
    Async version of fetch_search_console_data with performance optimizations.
    
    Args:
        start_date (str): Start date in format yyyy-mm-dd or 'yesterday', '7DaysAgo'
        end_date (str): End date in format yyyy-mm-dd or 'today'
        search_type (str): Search types for the returned data ('image', 'video', 'web')
        dimensions (str): Comma-separated dimensions ('date', 'query', 'page', 'country', 'device')
        google_account (str): Google account identifier for secrets/tokens
        wait_seconds (int): Wait seconds between API calls to prevent quota problems
        debug (bool): Enable debug output
        domain_filter (str): Optional domain to filter results (e.g., 'example.com')
        max_retries (int): Maximum number of retry attempts for failed API calls
        retry_delay (int): Base delay in seconds for retry attempts (with exponential backoff)
        
    Returns:
        pandas.DataFrame: Combined search console data from all accessible properties
    """
    
    # Parse dimensions
    dimensions_array = dimensions.split(",")
    multi_dimension = len(dimensions_array) > 1
    
    if debug:
        print(f"Starting async GSC data fetch - domain_filter: {domain_filter}")
        cache_stats = _domain_cache.get_stats()
        print(f"Domain cache stats: {cache_stats}")
    
    # Get cached domain list instead of making API calls every time
    sites_df = await asyncio.to_thread(list_search_console_sites, google_account, debug, True)
    
    if sites_df is None or sites_df.empty:
        if debug:
            print("No sites found")
        return pd.DataFrame()
    
    # Filter sites based on domain_filter early to avoid unnecessary API calls
    if domain_filter:
        filter_domain = domain_filter.lower().strip()
        if filter_domain.startswith('www.'):
            filter_domain = filter_domain[4:]
        
        # Filter sites to only those matching the domain filter
        def matches_domain(row):
            site_url = row['siteUrl']
            if site_url.startswith('sc-domain:'):
                current_domain = site_url[10:].lower()
            else:
                parsed = urlparse(site_url)
                current_domain = parsed.hostname.lower() if parsed.hostname else ''
            
            if current_domain.startswith('www.'):
                current_domain = current_domain[4:]
            
            return current_domain == filter_domain
        
        filtered_sites = sites_df[sites_df.apply(matches_domain, axis=1)]
        
        if debug:
            print(f"Filtered {len(sites_df)} sites to {len(filtered_sites)} matching domain '{domain_filter}'")
        
        sites_df = filtered_sites
    
    if sites_df.empty:
        if debug:
            print(f"No sites match domain filter: {domain_filter}")
        return pd.DataFrame()
    
    # Group sites by account for concurrent processing
    sites_by_account = sites_df.groupby('account')
    
    if debug:
        print(f"Processing {len(sites_df)} sites across {len(sites_by_account)} accounts")
    
    # Process accounts concurrently
    account_tasks = []
    for account, account_sites in sites_by_account:
        task = _process_account_sites_async(
            account, account_sites, start_date, end_date, search_type, 
            dimensions_array, multi_dimension, wait_seconds, debug, 
            max_retries, retry_delay
        )
        account_tasks.append(task)
    
    # Wait for all accounts to complete
    account_results = await asyncio.gather(*account_tasks, return_exceptions=True)
    
    # Combine results
    combined_df = pd.DataFrame()
    for result in account_results:
        if isinstance(result, Exception):
            if debug:
                print(f"Account processing failed: {result}")
            continue
        if result is not None and not result.empty:
            combined_df = pd.concat([combined_df, result], sort=True)
    
    if len(combined_df) > 0:
        combined_df.reset_index(drop=True, inplace=True)
        if debug:
            print(f"Successfully retrieved {len(combined_df)} rows total")
    
    return combined_df


async def _process_account_sites_async(
    account, account_sites, start_date, end_date, search_type, 
    dimensions_array, multi_dimension, wait_seconds, debug, 
    max_retries, retry_delay
):
    """Process all sites for a single account concurrently"""
    
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']
    
    try:
        # Get service in thread to avoid blocking
        service = await asyncio.to_thread(
            get_service, 'webmasters', 'v3', scope, 'client_secrets.json', account
        )
        
        # Process sites concurrently (but limit concurrency to avoid quota issues)
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests per account
        
        site_tasks = []
        for _, site_row in account_sites.iterrows():
            task = _process_single_site_async(
                semaphore, service, site_row, start_date, end_date, search_type,
                dimensions_array, multi_dimension, wait_seconds, debug,
                max_retries, retry_delay
            )
            site_tasks.append(task)
        
        # Wait for all sites in this account
        site_results = await asyncio.gather(*site_tasks, return_exceptions=True)
        
        # Combine results for this account
        account_df = pd.DataFrame()
        for result in site_results:
            if isinstance(result, Exception):
                if debug:
                    print(f"Site processing failed: {result}")
                continue
            if result is not None and not result.empty:
                account_df = pd.concat([account_df, result])
        
        return account_df
        
    except Exception as e:
        if debug:
            print(f"Error processing account {account}: {str(e)}")
        return pd.DataFrame()


async def _process_single_site_async(
    semaphore, service, site_row, start_date, end_date, search_type,
    dimensions_array, multi_dimension, wait_seconds, debug,
    max_retries, retry_delay
):
    """Process a single site with async support and retry logic"""
    
    async with semaphore:  # Limit concurrent requests
        site_url = site_row['siteUrl']
        root_domain = site_row['domain']
        
        if debug:
            print(f"Querying {site_url} from {start_date} to {end_date}")
        
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        
        retry_count = 0
        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    backoff_delay = retry_delay * (2 ** (retry_count - 1))
                    if debug:
                        print(f"Retrying {site_url} (attempt {retry_count}/{max_retries}) after {backoff_delay}s delay")
                    await asyncio.sleep(backoff_delay)
                
                # Make API call in thread to avoid blocking
                results = await asyncio.to_thread(
                    lambda: service.searchanalytics().query(
                        siteUrl=site_url, body={
                            'startDate': start_date,
                            'endDate': end_date,
                            'dimensions': dimensions_array,
                            'searchType': search_type,
                            'rowLimit': 25000
                        }
                    ).execute()
                )
                
                if 'rows' in results and len(results['rows']) > 0:
                    small_df = pd.DataFrame(results['rows'])
                    
                    if multi_dimension:
                        # Handle multi-dimensional keys
                        try:
                            if len(small_df) > 0 and 'keys' in small_df.columns:
                                keys_list = small_df['keys'].tolist()
                                if keys_list:
                                    first_keys = keys_list[0] if keys_list else []
                                    num_dimensions = len(first_keys) if isinstance(first_keys, list) else 0
                                    
                                    if num_dimensions > 0:
                                        key_columns = [f'key-{i+1}' for i in range(num_dimensions)]
                                        keys_df = pd.DataFrame(keys_list, index=small_df.index, columns=key_columns)
                                        for col in key_columns:
                                            small_df[col] = keys_df[col]
                        except Exception as keys_error:
                            if debug:
                                print(f"Warning: Could not process multi-dimensional keys for {site_url}: {keys_error}")
                    
                    # Add domain and site info
                    small_df.insert(0, 'siteUrl', site_url)
                    small_df.insert(0, 'rootDomain', root_domain)
                    
                    return small_df
                
                elif debug:
                    print(f"No data returned for {site_url}")
                
                return pd.DataFrame()
                
            except Exception as e:
                retry_count += 1
                error_str = str(e).lower()
                should_retry = (retry_count <= max_retries and 
                              ('rate' in error_str or 'quota' in error_str or 
                               'timeout' in error_str or 'internal error' in error_str or
                               '500' in error_str or '503' in error_str or '429' in error_str))
                
                if should_retry:
                    if debug:
                        print(f"Retryable error for {site_url} (attempt {retry_count}/{max_retries + 1}): {str(e)}")
                else:
                    if debug:
                        print(f"Final error for {site_url}: {str(e)}")
                    break
        
        return pd.DataFrame()


def fetch_search_console_data(
    start_date,
    end_date,
    search_type="web",
    dimensions="page",
    google_account="",
    wait_seconds=0,
    debug=False,
    domain_filter=None,
    max_retries=3,
    retry_delay=5
):
    """
    Synchronous wrapper for the async fetch_search_console_data_async function.
    
    This maintains backward compatibility while providing optimized performance.
    For best performance, use fetch_search_console_data_async directly in async contexts.
    """
    if debug:
        print("Using optimized GSC data fetcher (async version)")
    
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're already in an async context, create a new thread to run the async function
        # This prevents "RuntimeError: cannot be called from a running event loop"
        import concurrent.futures
        import threading
        
        def run_async_in_thread():
            return asyncio.run(fetch_search_console_data_async(
                start_date, end_date, search_type, dimensions, google_account,
                wait_seconds, debug, domain_filter, max_retries, retry_delay
            ))
        
        # Run in a separate thread to avoid blocking the main event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async_in_thread)
            return future.result()
            
    except RuntimeError:
        # No event loop running, we can use asyncio.run() directly
        return asyncio.run(fetch_search_console_data_async(
            start_date, end_date, search_type, dimensions, google_account,
            wait_seconds, debug, domain_filter, max_retries, retry_delay
        ))


# Add cache management functions
def get_domain_cache_stats():
    """Get domain cache statistics for monitoring"""
    domain_stats = _domain_cache.get_stats()
    disk_stats = {
        'disk_cache_size': len(_disk_cache),
        'disk_cache_directory': _cache_dir,
        'disk_cache_volume_info': _disk_cache.volume()
    }
    return {**domain_stats, **disk_stats}


def invalidate_domain_cache(account=None):
    """Invalidate domain cache for specific account or all accounts"""
    _domain_cache.invalidate(account)


def get_disk_cache_stats():
    """Get comprehensive disk cache statistics"""
    return {
        'size': len(_disk_cache),
        'directory': _cache_dir,
        'volume_info': _disk_cache.volume(),
        'cache_info': _disk_cache.stats()
    }


def clear_disk_cache():
    """Clear all disk cache entries"""
    _disk_cache.clear()


def clear_function_cache(function_name):
    """Clear cache entries for a specific function"""
    keys_to_delete = [key for key in _disk_cache if key.startswith(f"{function_name}:")]
    for key in keys_to_delete:
        del _disk_cache[key]
    return len(keys_to_delete)


def save_search_console_data(data_df, start_date, end_date, dimensions, name, search_type, google_account):
    """
    Save search console data to Excel file with options sheet.
    
    Args:
        data_df (pandas.DataFrame): The data to save
        start_date (str): Start date used in query
        end_date (str): End date used in query  
        dimensions (str): Dimensions used in query
        name (str): Output filename base (without extension)
        search_type (str): Search type used in query
        google_account (str): Google account identifier used
    """
    if len(data_df) == 0:
        print("No data to save")
        return
        
    # Generate filename if needed
    if name == 'search-console-[dimensions]-[datestring]':
        name = 'search-console-' + dimensions + '-' + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    if google_account > "":
        name = google_account + "-" + name 
    
    # Create options dataframe
    options = [[start_date, end_date, dimensions, name, search_type, google_account]]
    options_df = pd.DataFrame(options, columns=["start_date", "end_date", "dimensions", "name", "Data Type", "Google Account"])
    
    # Save to Excel
    with ExcelWriter(name + '.xlsx') as writer:
        data_df.to_excel(writer, sheet_name='data')
        options_df.to_excel(writer, sheet_name="Options")
        print(f"Data saved to {name}.xlsx")


# CLI functionality - only runs when script is executed directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    #when doing argument parsing in command terminal put python before file name. No idea why, so just do it.

    #parser.add_argument("viewProfileID",type=int, help="GA View (profile) ID as a number") !!!already got this from loop!!!
    parser.add_argument("start_date", nargs='?', help="start date in format yyyy-mm-dd or 'yesterday' '7DaysAgo'")
    parser.add_argument("end_date", nargs='?', help="start date in format yyyy-mm-dd or 'today'")
    parser.add_argument("-t", "--type", default="web", choices=("image","video","web"), help="Search types for the returned data, default is web")
    #parser.add_argument("-f","--filters",default=2,type=int, help="Minimum number for metric, default is 2")
    parser.add_argument("-d","--dimensions",default="page", help="The dimensions are the left hand side of the table, default is page. Options are date, query, page, country, device.  Combine two by specifying -d page,query ")
    #parser.add_argument("-m","--metrics",default="pageviews", help="The metrics are the things on the left, default is pageviews")
    parser.add_argument("-n","--name",default='search-console-[dimensions]-[datestring]',type=str, help="File name for final output, default is search-console- + the current date. You do NOT need to add file extension")
    #parser.add_argument("-c", "--clean", action="count", default=0, help="clean output skips header and count and just sends csv rows")
    parser.add_argument("-g","--googleaccount",type=str, default="", help="Name of a google account; does not have to literally be the account name but becomes a token to access that particular set of secrets. Client secrets will have to be in this a file that is this string concatenated with client_secret.json.  OR if this is the name of a text file then every line in the text file is processed as one user and all results appended together into a file file")
    parser.add_argument("-w","--wait",type=int, default=0, help="Wait in seconds between API calls to prevent quota problems; default 0 seconds")
    parser.add_argument("-s","--domain",type=str, default="", help="Filter results to a specific domain (e.g., 'example.com'). If not specified, data from all accessible domains will be downloaded.")
    parser.add_argument("--list-domains", action="store_true", help="List all available Search Console domains/sites and exit")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for failed API calls; default 3")
    parser.add_argument("--retry-delay", type=int, default=5, help="Base delay in seconds for retry attempts (uses exponential backoff); default 5")

    args = parser.parse_args()

    # Handle list domains command
    if args.list_domains:
        print("Listing available Google Search Console domains...")
        sites_df = list_search_console_sites(google_account=args.googleaccount, debug=True)
        if sites_df is not None and len(sites_df) > 0:
            print("\nAvailable domains:")
            print(sites_df.to_string(index=False))
            print(f"\nTotal: {len(sites_df)} accessible sites")
        else:
            print("No accessible sites found or authentication failed.")
        exit(0)
    
    # Check required arguments when not listing domains
    if not args.start_date or not args.end_date:
        parser.error("start_date and end_date are required unless using --list-domains")

    start_date = args.start_date
    end_date = args.end_date
    wait_seconds = args.wait

    dimensionsstring = args.dimensions
    name = args.name
    dataType = args.type
    googleaccountstring = args.googleaccount
    domain_filter = args.domain.strip() if args.domain else None

    # Fetch the data using the new function
    combined_df = fetch_search_console_data(
        start_date=start_date,
        end_date=end_date,
        search_type=dataType,
        dimensions=dimensionsstring,
        google_account=googleaccountstring,
        wait_seconds=wait_seconds,
        debug=True,
        domain_filter=domain_filter,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )
    
    # Save the data if we got any
    if len(combined_df) > 0:
        save_search_console_data(
            data_df=combined_df,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensionsstring,
            name=name,
            search_type=dataType,
            google_account=googleaccountstring
        )
        print("finished and outputed to excel file")
    else:
        print("nothing found")
