#!/usr/bin/env python3
"""
Test specifically for the domain property fix for GSC
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Add the project directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import NewDownloads

class TestDomainPropertyFix(unittest.TestCase):
    """Test the domain property filtering fix"""

    def test_domain_property_filtering(self):
        """Test that domain properties (sc-domain:) are now properly handled"""
        
        # Mock the get_service function to avoid authentication
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            # Mock search console sites with both URL-prefix and domain properties
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.quincy-market.com/',
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'https://quincy-market.com/',
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'sc-domain:quincy-market.com',  # This should NOW be processed
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'sc-domain:www.quincy-market.com',  # This should NOW be processed
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'https://example.com/',
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'sc-domain:example.com',  # This should be skipped due to domain filter
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            mock_get_service.return_value = mock_service
            
            # Mock search analytics API to return empty results (we just care about which properties are processed)
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = {'rows': []}
            
            # Test with domain filter for quincy-market.com
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                domain_filter="quincy-market.com",
                debug=True  # Enable debug to see what's happening
            )
            
            # Verify the function ran without errors
            self.assertTrue(isinstance(result, pd.DataFrame))
            
            # Check that searchanalytics.query was called for quincy-market properties
            # It should be called 4 times: 2 URL-prefix + 2 domain properties for quincy-market.com
            call_count = mock_service.searchanalytics.return_value.query.call_count
            
            print(f"Number of API calls made: {call_count}")
            print("This should be 4 calls (2 URL-prefix + 2 domain properties for quincy-market.com)")
            
            # Before the fix, this would be 2 (only URL-prefix properties)
            # After the fix, this should be 4 (URL-prefix + domain properties)
            self.assertEqual(call_count, 4, 
                           f"Expected 4 API calls (2 URL-prefix + 2 domain properties), but got {call_count}")

    def test_list_search_console_sites_with_domain_properties(self):
        """Test that list_search_console_sites properly categorizes domain properties"""
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.example.com/',
                        'permissionLevel': 'siteFullUser'
                    },
                    {
                        'siteUrl': 'sc-domain:example.com',
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            mock_get_service.return_value = mock_service
            
            result = NewDownloads.list_search_console_sites(debug=True)
            
            self.assertTrue(isinstance(result, pd.DataFrame))
            self.assertEqual(len(result), 2)
            
            # Check that both entries have proper domains extracted
            domains = result['domain'].tolist()
            self.assertIn('www.example.com', domains)
            self.assertIn('example.com', domains)
            
            # Check that property types are correctly identified
            property_types = result['property_type'].tolist()
            self.assertIn('URL-prefix Property', property_types)
            self.assertIn('Domain Property', property_types)


if __name__ == '__main__':
    print("Testing domain property fix for GSC...")
    unittest.main(verbosity=2)