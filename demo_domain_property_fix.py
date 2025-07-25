#!/usr/bin/env python3
"""
Demonstration script showing the GSC domain property fix in action
This script simulates the GSC domain filtering without requiring API credentials.
"""

import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from urllib.parse import urlparse

def demonstrate_fix():
    """Demonstrate the before and after behavior"""
    
    print("=" * 80)
    print("GSC DOMAIN PROPERTY FILTERING FIX DEMONSTRATION")
    print("=" * 80)
    
    # Simulate typical GSC properties for a domain like quincy-market.com
    mock_gsc_properties = [
        "https://www.quincy-market.com/",
        "https://quincy-market.com/", 
        "sc-domain:quincy-market.com",      # This was being skipped before
        "sc-domain:www.quincy-market.com",  # This was being skipped before
        "https://example.com/",             # Should be filtered out
        "sc-domain:example.com",            # Should be filtered out
    ]
    
    domain_filter = "quincy-market.com"
    
    print(f"Searching for domain: {domain_filter}")
    print(f"Available GSC properties: {len(mock_gsc_properties)}")
    print()
    
    # Show OLD behavior (before fix)
    print("BEFORE FIX (OLD BEHAVIOR):")
    print("-" * 40)
    old_processed = 0
    for prop in mock_gsc_properties:
        # Old logic: only handle URL-prefix properties
        hostname = urlparse(prop).hostname
        if hostname is None:
            print(f"❌ SKIP: {prop} (domain property - hostname is None)")
            continue
            
        # Old domain matching
        normalized_hostname = hostname.lower()
        if normalized_hostname.startswith('www.'):
            normalized_hostname = normalized_hostname[4:]
            
        if normalized_hostname == domain_filter.lower():
            print(f"✅ PROCESS: {prop} (URL-prefix property)")
            old_processed += 1
        else:
            print(f"❌ SKIP: {prop} (doesn't match domain filter)")
    
    print(f"\nOld behavior: {old_processed} properties processed")
    print()
    
    # Show NEW behavior (after fix)
    print("AFTER FIX (NEW BEHAVIOR):")
    print("-" * 40)
    new_processed = 0
    for prop in mock_gsc_properties:
        # New logic: handle both URL-prefix and domain properties
        if prop.startswith('sc-domain:'):
            # GSC Domain property
            domain = prop[10:]  # Remove "sc-domain:" prefix
            property_type = "Domain property"
        else:
            # URL-prefix property
            domain = urlparse(prop).hostname
            property_type = "URL-prefix property"
            
        if domain is None:
            print(f"❌ SKIP: {prop} (unparseable)")
            continue
            
        # Normalize domain for comparison
        normalized_domain = domain.lower()
        if normalized_domain.startswith('www.'):
            normalized_domain = normalized_domain[4:]
            
        if normalized_domain == domain_filter.lower():
            print(f"✅ PROCESS: {prop} ({property_type})")
            new_processed += 1
        else:
            print(f"❌ SKIP: {prop} (doesn't match domain filter)")
    
    print(f"\nNew behavior: {new_processed} properties processed")
    print()
    
    print("SUMMARY:")
    print("=" * 40)
    print(f"Before fix: {old_processed} properties processed")
    print(f"After fix:  {new_processed} properties processed")
    print(f"Improvement: +{new_processed - old_processed} additional properties")
    print()
    print("The fix ensures that GSC domain properties (sc-domain:) are no longer")
    print("ignored during domain filtering, which should resolve the 'no data'")
    print("issue for domains that use domain properties in Google Search Console.")
    print()
    print("This is especially important for high-traffic domains like quincy-market.com")
    print("that may have domain properties configured in addition to URL-prefix properties.")

if __name__ == "__main__":
    demonstrate_fix()