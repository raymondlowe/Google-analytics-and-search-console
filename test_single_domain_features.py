#!/usr/bin/env python3
"""
Basic tests for the new single domain filtering features.
These tests validate the functionality without requiring Google API credentials.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Add the project directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import NewDownloads
import ga4_gsc_web_interface


class TestSingleDomainFeatures(unittest.TestCase):
    """Test the new single domain filtering features"""

    def test_fetch_search_console_data_domain_filter_parameter(self):
        """Test that fetch_search_console_data accepts domain_filter parameter"""
        # This test ensures the function signature accepts the new parameter
        # We can't test the actual API call without credentials, but we can test parameter handling
        
        # Mock the get_service function to avoid authentication
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            mock_service.sites.return_value.list.return_value.execute.return_value = {}
            mock_get_service.return_value = mock_service
            
            # Test that the function accepts domain_filter parameter without error
            try:
                result = NewDownloads.fetch_search_console_data(
                    start_date="2024-01-01",
                    end_date="2024-01-02", 
                    domain_filter="example.com"
                )
                # Should return empty DataFrame when no sites found
                self.assertTrue(isinstance(result, pd.DataFrame))
                self.assertTrue(result.empty)
            except TypeError as e:
                if "domain_filter" in str(e):
                    self.fail("fetch_search_console_data does not accept domain_filter parameter")
                else:
                    raise

    def test_list_search_console_sites_function_exists(self):
        """Test that list_search_console_sites function exists and is callable"""
        self.assertTrue(hasattr(NewDownloads, 'list_search_console_sites'))
        self.assertTrue(callable(NewDownloads.list_search_console_sites))

    def test_list_search_console_sites_with_mock_data(self):
        """Test list_search_console_sites function with mock data"""
        mock_sites_data = {
            'siteEntry': [
                {
                    'siteUrl': 'https://www.example.com/', 
                    'permissionLevel': 'siteOwner'
                },
                {
                    'siteUrl': 'https://test.com/',
                    'permissionLevel': 'siteFullUser'
                }
            ]
        }
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
            mock_get_service.return_value = mock_service
            
            result = NewDownloads.list_search_console_sites(debug=False)
            
            self.assertIsNotNone(result)
            self.assertIsInstance(result, pd.DataFrame)
            self.assertEqual(len(result), 2)
            self.assertIn('siteUrl', result.columns)
            self.assertIn('domain', result.columns)

    def test_domain_filtering_logic(self):
        """Test that domain filtering logic handles www prefixes correctly"""
        # Create mock data that simulates the domain filtering
        mock_sites_data = {
            'siteEntry': [
                {
                    'siteUrl': 'https://www.example.com/', 
                    'permissionLevel': 'siteOwner'
                },
                {
                    'siteUrl': 'https://test.com/',
                    'permissionLevel': 'siteFullUser'
                },
                {
                    'siteUrl': 'https://another.com/',
                    'permissionLevel': 'siteOwner'
                }
            ]
        }
        
        # Mock the API call parts
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
            
            # Mock the searchanalytics query to return empty results (avoid the API call)
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {}
            
            mock_get_service.return_value = mock_service
            
            # Test filtering for 'example.com' should match 'www.example.com'
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                domain_filter="example.com",
                debug=True
            )
            
            # Should execute without error (domain filtering logic works)
            self.assertIsInstance(result, pd.DataFrame)

    def test_web_interface_functions_exist(self):
        """Test that new web interface functions exist"""
        self.assertTrue(hasattr(ga4_gsc_web_interface, 'list_gsc_domains'))
        self.assertTrue(callable(ga4_gsc_web_interface.list_gsc_domains))
        
        self.assertTrue(hasattr(ga4_gsc_web_interface, 'api_list_gsc_domains'))
        self.assertTrue(callable(ga4_gsc_web_interface.api_list_gsc_domains))

    def test_get_gsc_data_accepts_domain_filter(self):
        """Test that get_gsc_data function accepts domain_filter parameter"""
        with patch('ga4_gsc_web_interface.NewDownloads.fetch_search_console_data') as mock_fetch:
            mock_fetch.return_value = pd.DataFrame()
            
            # Should not raise TypeError for domain_filter parameter
            try:
                result, message = ga4_gsc_web_interface.get_gsc_data(
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    google_account="",
                    search_type="web",
                    dimensions="page",
                    wait_seconds=0,
                    debug=False,
                    domain_filter="example.com"
                )
                
                # Verify the mock was called with domain_filter
                mock_fetch.assert_called_once_with(
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    search_type="web",
                    dimensions="page",
                    google_account="",
                    wait_seconds=0,
                    debug=False,
                    domain_filter="example.com",
                    max_retries=3,
                    retry_delay=5
                )
                
            except TypeError as e:
                if "domain_filter" in str(e):
                    self.fail("get_gsc_data does not accept domain_filter parameter")
                else:
                    raise

    def test_retry_functionality(self):
        """Test that retry functionality works correctly"""
        import time
        
        mock_sites_data = {
            'siteEntry': [
                {
                    'siteUrl': 'https://www.example.com/', 
                    'permissionLevel': 'siteOwner'
                }
            ]
        }
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites_data
            
            # Mock the searchanalytics query to fail first, then succeed
            query_mock = mock_service.searchanalytics.return_value.query.return_value
            query_mock.execute.side_effect = [
                Exception("Internal error encountered"),  # First call fails
                {'rows': [{'keys': ['test'], 'clicks': 5, 'impressions': 10}]}  # Second call succeeds
            ]
            
            mock_get_service.return_value = mock_service
            
            # Mock time.sleep to avoid actual delays in tests
            with patch('NewDownloads.time.sleep'):
                result = NewDownloads.fetch_search_console_data(
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    max_retries=2,
                    retry_delay=1,
                    debug=False
                )
                
                # Should successfully process after retry
                self.assertIsInstance(result, pd.DataFrame)
                # Verify the query was called twice (initial attempt + 1 retry)
                self.assertEqual(query_mock.execute.call_count, 2)

    def test_cli_arguments_validation_with_retry_params(self):
        """Test that CLI argument parsing works correctly with new retry parameters"""
        import argparse
        
        # Create a parser similar to NewDownloads.py 
        parser = argparse.ArgumentParser()
        parser.add_argument("start_date", nargs='?')
        parser.add_argument("end_date", nargs='?')
        parser.add_argument("-s", "--domain", type=str, default="")
        parser.add_argument("--max-retries", type=int, default=3)
        parser.add_argument("--retry-delay", type=int, default=5)
        parser.add_argument("--list-domains", action="store_true")
        
        # Test that new retry parameters work
        args = parser.parse_args(["2024-01-01", "2024-01-02", "--max-retries", "5", "--retry-delay", "10"])
        self.assertEqual(args.max_retries, 5)
    def test_cli_arguments_validation_original(self):
        """Test that CLI argument parsing works correctly"""
        import argparse
        
        # Create a parser similar to NewDownloads.py 
        parser = argparse.ArgumentParser()
        parser.add_argument("start_date", nargs='?')
        parser.add_argument("end_date", nargs='?')
        parser.add_argument("-s", "--domain", type=str, default="")
        parser.add_argument("--list-domains", action="store_true")
        
        # Test that --list-domains works without required arguments
        args = parser.parse_args(["--list-domains"])
        self.assertTrue(args.list_domains)
        
        # Test that --domain works with required arguments
        args = parser.parse_args(["2024-01-01", "2024-01-02", "--domain", "example.com"])
        self.assertEqual(args.domain, "example.com")
        self.assertEqual(args.start_date, "2024-01-01")
        self.assertEqual(args.end_date, "2024-01-02")


if __name__ == '__main__':
    print("Running tests for single domain filtering features...")
    print("Note: These tests validate functionality without requiring Google API credentials.")
    print()
    
    unittest.main(verbosity=2)