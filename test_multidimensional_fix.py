#!/usr/bin/env python3
"""
Test the fixed multi-dimensional response processing for GSC
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

# Add the project directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import NewDownloads

class TestMultiDimensionalFix(unittest.TestCase):
    """Test the multi-dimensional response processing fix"""

    def test_4_dimensional_response_processing(self):
        """Test that 4-dimensional responses (page,query,country,device) are handled correctly"""
        
        # Mock the get_service function to avoid authentication
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            # Mock search console sites
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.quincy-market.com/',
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            
            # Mock search analytics API to return 4-dimensional data like real GSC API
            mock_search_response = {
                'rows': [
                    {
                        'keys': ['/page1', 'keyword1', 'US', 'DESKTOP'],
                        'clicks': 100,
                        'impressions': 1000,
                        'ctr': 0.1,
                        'position': 5.0
                    },
                    {
                        'keys': ['/page2', 'keyword2', 'CA', 'MOBILE'],
                        'clicks': 50,
                        'impressions': 500,
                        'ctr': 0.1,
                        'position': 3.0
                    }
                ]
            }
            
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            # Test with 4 dimensions (this was causing the "Columns must be same length" error)
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                dimensions="page,query,country,device",  # 4 dimensions
                domain_filter="quincy-market.com",
                debug=True
            )
            
            # Verify the function ran without errors and returned data
            self.assertTrue(isinstance(result, pd.DataFrame))
            self.assertGreater(len(result), 0)
            
            # Check that multi-dimensional keys are properly processed
            self.assertIn('key-1', result.columns)  # page
            self.assertIn('key-2', result.columns)  # query  
            self.assertIn('key-3', result.columns)  # country
            self.assertIn('key-4', result.columns)  # device
            
            # Check that the data is correctly parsed
            self.assertEqual(result.iloc[0]['key-1'], '/page1')
            self.assertEqual(result.iloc[0]['key-2'], 'keyword1')
            self.assertEqual(result.iloc[0]['key-3'], 'US')
            self.assertEqual(result.iloc[0]['key-4'], 'DESKTOP')
            
            print("✓ 4-dimensional response processing works correctly")

    def test_2_dimensional_response_processing(self):
        """Test that 2-dimensional responses still work correctly"""
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.example.com/',
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            
            # Mock search analytics API to return 2-dimensional data
            mock_search_response = {
                'rows': [
                    {
                        'keys': ['/page1', 'keyword1'],
                        'clicks': 100,
                        'impressions': 1000,
                        'ctr': 0.1,
                        'position': 5.0
                    }
                ]
            }
            
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            # Test with 2 dimensions
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                dimensions="page,query",  # 2 dimensions
                domain_filter="example.com",
                debug=True
            )
            
            # Verify the function ran without errors and returned data
            self.assertTrue(isinstance(result, pd.DataFrame))
            self.assertGreater(len(result), 0)
            
            # Check that 2-dimensional keys are properly processed
            self.assertIn('key-1', result.columns)
            self.assertIn('key-2', result.columns)
            
            print("✓ 2-dimensional response processing works correctly")

    def test_single_dimensional_response_processing(self):
        """Test that single-dimensional responses work correctly"""
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.example.com/',
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            
            # Mock search analytics API to return single-dimensional data
            mock_search_response = {
                'rows': [
                    {
                        'keys': ['/page1'],
                        'clicks': 100,
                        'impressions': 1000,
                        'ctr': 0.1,
                        'position': 5.0
                    }
                ]
            }
            
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            # Test with 1 dimension (multi_dimension should be False)
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                dimensions="page",  # 1 dimension
                domain_filter="example.com",
                debug=True
            )
            
            # Verify the function ran without errors and returned data
            self.assertTrue(isinstance(result, pd.DataFrame))
            self.assertGreater(len(result), 0)
            
            # For single dimension, the original behavior should be preserved
            # The keys should remain as a single value in the 'keys' column
            
            print("✓ Single-dimensional response processing works correctly")

    def test_inconsistent_keys_handling(self):
        """Test that inconsistent key lengths are handled gracefully"""
        
        with patch('NewDownloads.get_service') as mock_get_service:
            mock_service = Mock()
            
            mock_sites = {
                'siteEntry': [
                    {
                        'siteUrl': 'https://www.example.com/',
                        'permissionLevel': 'siteFullUser'
                    }
                ]
            }
            
            mock_service.sites.return_value.list.return_value.execute.return_value = mock_sites
            
            # Mock search analytics API to return inconsistent key lengths (this would cause the old error)
            mock_search_response = {
                'rows': [
                    {
                        'keys': ['/page1', 'keyword1', 'US'],  # 3 keys
                        'clicks': 100,
                        'impressions': 1000,
                        'ctr': 0.1,
                        'position': 5.0
                    },
                    {
                        'keys': ['/page2', 'keyword2'],  # 2 keys (inconsistent!)
                        'clicks': 50,
                        'impressions': 500,
                        'ctr': 0.1,
                        'position': 3.0
                    }
                ]
            }
            
            mock_service.searchanalytics.return_value.query.return_value.execute.return_value = mock_search_response
            mock_get_service.return_value = mock_service
            
            # This should not crash even with inconsistent key lengths
            result = NewDownloads.fetch_search_console_data(
                start_date="2024-01-01",
                end_date="2024-01-02",
                dimensions="page,query,country",  # 3 dimensions expected
                domain_filter="example.com",
                debug=True
            )
            
            # The function should not crash and should return some data
            self.assertTrue(isinstance(result, pd.DataFrame))
            
            print("✓ Inconsistent key lengths handled gracefully")


if __name__ == '__main__':
    print("Testing multi-dimensional response processing fix...")
    unittest.main(verbosity=2)