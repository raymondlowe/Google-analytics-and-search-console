#!/usr/bin/env python3
"""
Debug script to investigate GSC data issue for quincy-market.com
"""

import NewDownloads
import pandas as pd
from datetime import datetime, timedelta

def debug_gsc_properties():
    """List all GSC properties to understand what's available"""
    print("=== Debugging GSC Properties ===")
    
    sites_df = NewDownloads.list_search_console_sites(debug=True)
    if sites_df is not None and len(sites_df) > 0:
        print(f"\nFound {len(sites_df)} total sites")
        
        # Filter for quincy-market.com related properties
        quincy_properties = sites_df[sites_df['domain'].str.contains('quincy-market', case=False, na=False)]
        print(f"\nQuincy Market related properties ({len(quincy_properties)}):")
        if len(quincy_properties) > 0:
            print(quincy_properties.to_string(index=False))
        else:
            print("No quincy-market.com properties found!")
            
        print(f"\nAll domains found:")
        unique_domains = sites_df['domain'].unique()
        for domain in sorted(unique_domains):
            print(f"  - {domain}")
            
        return sites_df
    else:
        print("No sites found or authentication failed!")
        return None

def debug_gsc_data_fetch():
    """Test GSC data fetching with different parameters"""
    print("\n=== Debugging GSC Data Fetch ===")
    
    # Test with a recent date range (not future dates)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    print(f"Testing date range: {week_ago} to {yesterday}")
    
    # Test 1: Without domain filter (all domains)
    print("\n--- Test 1: All domains ---")
    df_all = NewDownloads.fetch_search_console_data(
        start_date=week_ago,
        end_date=yesterday,
        search_type="web",
        dimensions="page",
        google_account="",
        wait_seconds=0,
        debug=True,
        domain_filter=None
    )
    
    if df_all is not None and len(df_all) > 0:
        print(f"Found {len(df_all)} rows of data across all domains")
        unique_domains = df_all['rootDomain'].unique() if 'rootDomain' in df_all.columns else []
        print(f"Domains with data: {list(unique_domains)}")
    else:
        print("No data found across all domains")
    
    # Test 2: With quincy-market.com filter
    print("\n--- Test 2: quincy-market.com filter ---")
    df_quincy = NewDownloads.fetch_search_console_data(
        start_date=week_ago,
        end_date=yesterday,
        search_type="web",
        dimensions="page",
        google_account="",
        wait_seconds=0,
        debug=True,
        domain_filter="quincy-market.com"
    )
    
    if df_quincy is not None and len(df_quincy) > 0:
        print(f"Found {len(df_quincy)} rows of data for quincy-market.com")
        print(df_quincy.head())
    else:
        print("No data found for quincy-market.com")
    
    # Test 3: Try different domain variations
    print("\n--- Test 3: Different domain variations ---")
    domain_variations = [
        "www.quincy-market.com",
        "quincy-market.com",
        "https://www.quincy-market.com/",
        "https://quincy-market.com/"
    ]
    
    for domain in domain_variations:
        print(f"\nTrying domain filter: '{domain}'")
        df_test = NewDownloads.fetch_search_console_data(
            start_date=week_ago,
            end_date=yesterday,
            search_type="web",
            dimensions="page",
            google_account="",
            wait_seconds=0,
            debug=True,
            domain_filter=domain
        )
        
        if df_test is not None and len(df_test) > 0:
            print(f"SUCCESS: Found {len(df_test)} rows with filter '{domain}'")
            break
        else:
            print(f"No data with filter '{domain}'")

def debug_domain_matching_logic():
    """Test the domain matching logic specifically"""
    print("\n=== Debugging Domain Matching Logic ===")
    
    # Simulate the domain normalization logic
    test_cases = [
        ("quincy-market.com", "www.quincy-market.com"),
        ("quincy-market.com", "quincy-market.com"),
        ("quincy-market.com", "https://www.quincy-market.com/"),
        ("quincy-market.com", "https://quincy-market.com/"),
        ("www.quincy-market.com", "www.quincy-market.com"),
    ]
    
    for filter_domain, site_domain in test_cases:
        # Simulate the normalization logic from the code
        from urllib.parse import urlparse
        
        # Extract hostname from site URL
        if site_domain.startswith('sc-domain:'):
            root_domain = site_domain[10:]
        else:
            root_domain = urlparse(site_domain).hostname if '://' in site_domain else site_domain
            
        if root_domain is None:
            print(f"SKIP: {site_domain} -> hostname extraction failed")
            continue
            
        # Normalize filter domain
        normalized_filter = filter_domain.lower().strip()
        if normalized_filter.startswith('www.'):
            normalized_filter = normalized_filter[4:]
        
        # Normalize current domain
        normalized_current = root_domain.lower()
        if normalized_current.startswith('www.'):
            normalized_current = normalized_current[4:]
        
        match = normalized_current == normalized_filter
        print(f"Filter: '{filter_domain}' -> '{normalized_filter}'")
        print(f"Site: '{site_domain}' -> '{root_domain}' -> '{normalized_current}'")
        print(f"Match: {match}")
        print()

if __name__ == "__main__":
    print("Starting GSC debugging for quincy-market.com issue...")
    
    # Step 1: Check what properties are available
    sites_df = debug_gsc_properties()
    
    # Step 2: Test domain matching logic
    debug_domain_matching_logic()
    
    # Step 3: Test data fetching
    debug_gsc_data_fetch()
    
    print("\nDebugging complete!")