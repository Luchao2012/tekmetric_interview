"""
Unit tests for the NASA Near Earth Object data collection modules.
"""
import os
import json
import unittest
from unittest import mock
import pandas as pd
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path so we can import src modules
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_client import NeoApiClient
from src.data_processor import parse_neo_record, compute_aggregations, DataProcessor


class TestParseNeoRecord(unittest.TestCase):
    """Test the parse_neo_record function."""
    
    def test_parse_complete_record(self):
        """Test parsing a complete NEO record."""
        # Mock NEO data with close approach data
        mock_neo = {
            'id': '12345',
            'neo_reference_id': 'ref12345',
            'name': 'Test Asteroid',
            'designation': 'T123',
            'nasa_jpl_url': 'http://example.com',
            'absolute_magnitude_h': 20.5,
            'is_potentially_hazardous_asteroid': True,
            'estimated_diameter': {
                'meters': {
                    'estimated_diameter_min': 100.0,
                    'estimated_diameter_max': 200.0
                }
            },
            'close_approach_data': [
                {
                    'close_approach_date': '2020-01-01',
                    'miss_distance': {
                        'kilometers': '50000',
                        'astronomical': '0.3'
                    },
                    'relative_velocity': {
                        'kilometers_per_second': '10.5'
                    }
                },
                {
                    'close_approach_date': '2021-01-01',
                    'miss_distance': {
                        'kilometers': '40000',  # This is closer so should be selected
                        'astronomical': '0.25'
                    },
                    'relative_velocity': {
                        'kilometers_per_second': '12.5'
                    }
                }
            ],
            'orbital_data': {
                'first_observation_date': '2000-01-01',
                'last_observation_date': '2022-01-01',
                'observations_used': 100,
                'orbital_period': '365.5'
            }
        }
        
        result = parse_neo_record(mock_neo)
        
        # Check basic fields
        self.assertEqual(result['id'], '12345')
        self.assertEqual(result['name'], 'Test Asteroid')
        self.assertEqual(result['name_limited'], 'Asteroid')
        self.assertEqual(result['est_diam_min_m'], 100.0)
        
        # Check it selected the closest approach (the second one)
        self.assertEqual(result['close_approach_date'], '2021-01-01')
        self.assertEqual(result['miss_distance_km'], 40000.0)
        self.assertEqual(result['miss_distance_au'], 0.25)
        self.assertEqual(result['relative_velocity_kps'], 12.5)
        
    def test_parse_record_without_close_approach(self):
        """Test parsing a NEO record without close approach data."""
        mock_neo = {
            'id': '12345',
            'neo_reference_id': 'ref12345',
            'name': 'Test',  # Single word name
            'designation': 'T123',
            'nasa_jpl_url': 'http://example.com',
            'absolute_magnitude_h': 20.5,
            'is_potentially_hazardous_asteroid': False,
            'estimated_diameter': {
                'meters': {
                    'estimated_diameter_min': 100.0,
                    'estimated_diameter_max': 200.0
                }
            },
            'close_approach_data': [],  # Empty list
            'orbital_data': {
                'first_observation_date': '2000-01-01',
                'last_observation_date': '2022-01-01',
                'observations_used': 100,
                'orbital_period': '365.5'
            }
        }
        
        result = parse_neo_record(mock_neo)
        
        # Check basic fields
        self.assertEqual(result['id'], '12345')
        self.assertEqual(result['name'], 'Test')
        self.assertEqual(result['name_limited'], 'Test')  # Same as name for single word
        
        # Check close approach fields are None
        self.assertIsNone(result['close_approach_date'])
        self.assertIsNone(result['miss_distance_km'])
        self.assertIsNone(result['miss_distance_au'])
        self.assertIsNone(result['relative_velocity_kps'])


class TestComputeAggregations(unittest.TestCase):
    """Test the compute_aggregations function."""
    
    def test_compute_aggregations(self):
        """Test computing aggregations."""
        # Create a test DataFrame
        data = {
            'miss_distance_au': [0.1, 0.3, 0.15, 0.25, None],
            'close_approach_date': ['2020-01-01', '2020-05-01', '2021-01-01', 
                                    '2021-06-01', None]
        }
        df = pd.DataFrame(data)
        
        # Compute aggregations
        aggs = compute_aggregations(df)
        
        # Check total approaches < 0.2 AU
        self.assertEqual(aggs['total_approaches_lt_0.2_AU'], 2)
        
        # Check approaches per year
        self.assertEqual(aggs['approaches_per_year'][2020], 2)
        self.assertEqual(aggs['approaches_per_year'][2021], 2)


class TestDataProcessor(unittest.TestCase):
    """Test the DataProcessor class."""
    
    def setUp(self):
        """Set up a temporary directory for test files."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.processor = DataProcessor()
        self.test_df = pd.DataFrame({
            'id': ['1', '2', '3'],
            'name': ['A', 'B', 'C'],
            'miss_distance_au': [0.1, 0.3, 0.15]
        })
        
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
        
    def test_save_to_parquet_excludes_au(self):
        """Test that save_to_parquet excludes miss_distance_au column."""
        output_path = self.temp_dir / 'test.parquet'
        self.processor.save_to_parquet(self.test_df, output_path)
        
        # Read back and check missing column
        df_read = pd.read_parquet(output_path)
        self.assertIn('id', df_read.columns)
        self.assertIn('name', df_read.columns)
        self.assertNotIn('miss_distance_au', df_read.columns)
        

if __name__ == '__main__':
    unittest.main()
