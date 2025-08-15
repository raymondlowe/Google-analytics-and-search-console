import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from urllib.parse import urlparse

from googleAPIget_service import get_service


def get_client_secrets_path(default_path: str = 'client_secrets.json') -> str:
    """Resolve the client_secrets.json path using env override and script directory fallback."""
    client_secrets_path = os.environ.get('CLIENT_SECRETS_PATH', default_path)
    if not os.path.isabs(client_secrets_path):
        script_dir = Path(__file__).parent
        client_secrets_path = str(script_dir / client_secrets_path)
    return client_secrets_path


@dataclass
class _Site:
    siteUrl: str
    domain: str
    account: str


def list_search_console_sites(
    google_account: str = "",
    debug: bool = False,
    use_cache: bool = True,
    extra_auth_flags: Optional[dict] = None,
):
    """Return a DataFrame with columns: siteUrl, domain, account."""
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']

    if not google_account or google_account.strip() == "":
        googleaccounts_list = [""]
    else:
        try:
            googleaccounts_list = [x.strip() for x in open(google_account).read().splitlines() if x.strip()]
        except Exception:
            googleaccounts_list = [google_account]

    sites: List[Dict] = []
    for acct in googleaccounts_list:
        try:
            client_secrets_path = get_client_secrets_path()
            service = get_service('webmasters', 'v3', scope, client_secrets_path, acct, extra_auth_flags)
            profiles = service.sites().list().execute()
            for item in profiles.get('siteEntry', []):
                if item.get('permissionLevel') == 'siteUnverifiedUser':
                    continue
                site_url = item['siteUrl']
                if site_url.startswith('sc-domain:'):
                    root_domain = site_url[10:]
                else:
                    root_domain = urlparse(site_url).hostname or 'Unknown'
                sites.append({
                    'siteUrl': site_url,
                    'domain': root_domain,
                    'account': acct or 'default',
                })
        except Exception as e:
            if debug:
                print(f"Error listing sites for account '{acct or 'default'}': {e}")
            continue

    return pd.DataFrame(sites) if sites else None


def fetch_search_console_data(
    start_date: str,
    end_date: str,
    search_type: str = "web",
    dimensions: str = "page",
    google_account: str = "",
    wait_seconds: int = 0,
    debug: bool = False,
    domain_filter: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 5,
    extra_auth_flags: Optional[dict] = None,
    progress_callback=None,
):
    """Serial, simple implementation with optional per-site progress callback."""
    scope = ['https://www.googleapis.com/auth/webmasters.readonly']

    sites_df = list_search_console_sites(google_account=google_account, debug=debug, use_cache=True, extra_auth_flags=extra_auth_flags)
    if sites_df is None or sites_df.empty:
        if progress_callback:
            try:
                progress_callback({"event": "finish", "message": "No sites available", "current": 0, "total": 0, "rows": 0})
            except Exception:
                pass
        return pd.DataFrame()

    if domain_filter:
        filt = domain_filter.lower().strip()
        try:
            parsed = urlparse(filt)
            if parsed.hostname:
                filt = parsed.hostname
        except Exception:
            pass
        if filt.startswith('www.'):
            filt = filt[4:]

        def _matches(row):
            site_url = row['siteUrl']
            if site_url.startswith('sc-domain:'):
                cur = site_url[10:].lower()
            else:
                parsed = urlparse(site_url)
                cur = (parsed.hostname or '').lower()
            if cur.startswith('www.'):
                cur = cur[4:]
            return cur == filt

        sites_df = sites_df[sites_df.apply(_matches, axis=1)]
        if sites_df.empty:
            if progress_callback:
                try:
                    progress_callback({"event": "finish", "message": "No sites match domain filter", "current": 0, "total": 0, "rows": 0})
                except Exception:
                    pass
            return pd.DataFrame()

    total = len(sites_df)
    completed = 0
    if progress_callback:
        try:
            progress_callback({"event": "start", "message": f"Starting GSC fetch for {total} site(s)", "current": 0, "total": total})
        except Exception:
            pass

    combined = pd.DataFrame()
    for account, account_sites in sites_df.groupby('account'):
        client_secrets_path = get_client_secrets_path()
        service = get_service('webmasters', 'v3', scope, client_secrets_path, account if account != 'default' else '', extra_auth_flags)

        for _, row in account_sites.iterrows():
            site_url = row['siteUrl']
            root_domain = row['domain']
            if progress_callback:
                try:
                    progress_callback({"event": "site_start", "message": f"Querying {site_url}", "siteUrl": site_url, "rootDomain": root_domain})
                except Exception:
                    pass

            if wait_seconds:
                time.sleep(wait_seconds)

            dims = [d.strip() for d in dimensions.split(',') if d.strip()]
            attempt = 0
            df_site = pd.DataFrame()
            while attempt <= max_retries:
                try:
                    results = service.searchanalytics().query(
                        siteUrl=site_url,
                        body={
                            'startDate': start_date,
                            'endDate': end_date,
                            'dimensions': dims,
                            'searchType': search_type,
                            'rowLimit': 25000,
                        },
                    ).execute()
                    if results and 'rows' in results and results['rows']:
                        df_site = pd.DataFrame(results['rows'])
                        df_site.insert(0, 'siteUrl', site_url)
                        df_site.insert(0, 'rootDomain', root_domain)
                    break
                except Exception as e:
                    attempt += 1
                    if attempt <= max_retries and any(k in str(e).lower() for k in ['rate', 'quota', 'timeout', 'internal error', '500', '503', '429']):
                        time.sleep(retry_delay * (2 ** (attempt - 1)))
                        continue
                    else:
                        break

            if not df_site.empty:
                combined = pd.concat([combined, df_site], sort=True)

            completed += 1
            if progress_callback:
                try:
                    msg = f"Completed {site_url}" if not df_site.empty else f"No data for {site_url}"
                    progress_callback({"event": "site_done", "message": msg, "siteUrl": site_url, "rootDomain": root_domain, "current": completed, "total": total})
                except Exception:
                    pass

    if not combined.empty:
        combined.reset_index(drop=True, inplace=True)
    if progress_callback:
        try:
            progress_callback({"event": "finish", "message": "Finished GSC fetch", "current": completed, "total": total, "rows": len(combined)})
        except Exception:
            pass
    return combined
