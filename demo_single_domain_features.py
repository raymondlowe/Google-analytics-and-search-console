#!/usr/bin/env python3
"""
Integration test demonstrating the new single domain filtering workflow.
This shows how the features work together without requiring actual API credentials.
"""

import sys
import os
import argparse
from unittest.mock import patch, Mock
import pandas as pd

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import NewDownloads
import ga4_gsc_web_interface


def demo_cli_workflow():
    """Demonstrate the new CLI workflow with mock data"""
    print("🔧 CLI Workflow Demonstration")
    print("=" * 50)
    
    # Mock site data that would come from Google Search Console API
    mock_sites_data = {
        'siteEntry': [
            {'siteUrl': 'https://www.example.com/', 'permissionLevel': 'siteOwner'},
            {'siteUrl': 'https://blog.example.com/', 'permissionLevel': 'siteOwner'},
            {'siteUrl': 'https://test.com/', 'permissionLevel': 'siteFullUser'},
            {'siteUrl': 'https://another-site.net/', 'permissionLevel': 'siteOwner'}
        ]
    }
    
    print("1. Listing available domains (--list-domains):")
    with patch('NewDownloads.get_service') as mock_get_service:
        mock_service = Mock()
        mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
        mock_get_service.return_value = mock_service
        
        sites_df = NewDownloads.list_search_console_sites(debug=False)
        if sites_df is not None:
            print(f"   Found {len(sites_df)} accessible sites:")
            for _, site in sites_df.iterrows():
                print(f"   - {site['siteUrl']} (domain: {site['domain']})")
        print()
    
    print("2. Filtering data for specific domain (--domain example.com):")
    with patch('NewDownloads.get_service') as mock_get_service:
        mock_service = Mock()
        mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
        # Mock search analytics to return some sample data
        mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {
            'rows': [
                {'keys': ['/page1'], 'clicks': 100, 'impressions': 1000, 'ctr': 0.1, 'position': 5.5},
                {'keys': ['/page2'], 'clicks': 50, 'impressions': 500, 'ctr': 0.1, 'position': 8.2}
            ]
        }
        mock_get_service.return_value = mock_service
        
        filtered_df = NewDownloads.fetch_search_console_data(
            start_date="2024-01-01",
            end_date="2024-01-02",
            domain_filter="example.com",
            debug=False
        )
        
        print(f"   Retrieved {len(filtered_df)} rows of data for example.com domain")
        if len(filtered_df) > 0:
            print(f"   Sample data columns: {list(filtered_df.columns)}")
        print()


def demo_web_interface_workflow():
    """Demonstrate the new web interface workflow with mock data"""
    print("🌐 Web Interface Workflow Demonstration") 
    print("=" * 50)
    
    # Mock site data
    mock_sites_data = {
        'siteEntry': [
            {'siteUrl': 'https://www.example.com/', 'permissionLevel': 'siteOwner'},
            {'siteUrl': 'https://test.com/', 'permissionLevel': 'siteFullUser'}
        ]
    }
    
    print("1. Listing GSC domains via web interface:")
    with patch('NewDownloads.get_service') as mock_get_service:
        mock_service = Mock()
        mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
        mock_get_service.return_value = mock_service
        
        sites_df, message = ga4_gsc_web_interface.list_gsc_domains("")
        print(f"   Status: {message}")
        if sites_df is not None:
            print(f"   Available domains: {len(sites_df)} sites")
        print()
    
    print("2. Fetching GSC data with domain filter via web interface:")
    with patch('NewDownloads.fetch_search_console_data') as mock_fetch:
        mock_fetch.return_value = pd.DataFrame({
            'rootDomain': ['example.com', 'example.com'],
            'siteUrl': ['https://www.example.com/', 'https://www.example.com/'],
            'keys': ['/page1', '/page2'],
            'clicks': [100, 50],
            'impressions': [1000, 500]
        })
        
        df, message = ga4_gsc_web_interface.get_gsc_data(
            start_date="2024-01-01",
            end_date="2024-01-02",
            google_account="",
            search_type="web",
            dimensions="page",
            wait_seconds=0,
            debug=False,
            domain_filter="example.com"
        )
        
        print(f"   Status: {message}")
        print(f"   Data retrieved: {len(df) if df is not None else 0} rows")
        print()


def demo_cli_argument_parsing():
    """Demonstrate the new CLI argument parsing"""
    print("⚙️  CLI Argument Parsing Demonstration")
    print("=" * 50)
    
    # Create parser like NewDownloads.py
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date", nargs='?', help="start date")
    parser.add_argument("end_date", nargs='?', help="end date")
    parser.add_argument("-s", "--domain", type=str, default="", help="Filter to specific domain")
    parser.add_argument("--list-domains", action="store_true", help="List available domains")
    
    test_cases = [
        ["--list-domains"],
        ["2024-01-01", "2024-01-02"], 
        ["2024-01-01", "2024-01-02", "--domain", "example.com"],
        ["yesterday", "today", "-s", "test.com"]
    ]
    
    for i, args in enumerate(test_cases, 1):
        parsed = parser.parse_args(args)
        print(f"   Test {i}: {' '.join(args)}")
        print(f"      list_domains: {parsed.list_domains}")
        print(f"      domain: '{parsed.domain}'")
        print(f"      dates: {parsed.start_date}, {parsed.end_date}")
        print()


if __name__ == '__main__':
    print("🚀 Single Domain Filtering Features - Integration Demo")
    print("=" * 60)
    print("This demo shows the new functionality without requiring API credentials.")
    print()
    
    demo_cli_workflow()
    demo_web_interface_workflow() 
    demo_cli_argument_parsing()
    
    print("✅ All demonstrations completed successfully!")
    print()
    print("📋 Summary of New Features:")
    print("   CLI: --domain filter, --list-domains command")
    print("   Web: Domain Filter field, List GSC Domains button")
    print("   API: New REST endpoints for domain listing")
    print("   Backwards compatible: existing workflows unchanged")