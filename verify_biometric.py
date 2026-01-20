import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Mock sqlalchemy, redis before import
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['redis'] = MagicMock()

# Mock env
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://mock", "REDIS_URL": "redis://mock"}):
    import biometric_analysis

class TestBiometricAnalysis(unittest.TestCase):
    def setUp(self):
        # Create synthetic joined data
        # enrollments: date, state, district, age_5_17, age_18_greater
        # attempts: bio_age_5_17, bio_age_17_
        
        self.df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'state': ['S1', 'S1'],
            'district': ['D1', 'D2'],
            'age_5_17': [100, 100],
            'age_18_greater': [100, 100],
            'bio_age_5_17': [80, 40], # D1=80%, D2=40%
            'bio_age_17_': [90, 50]   # D1=90%, D2=50%
        })
        # D1: High performer
        # D2: Low performer (avg < 60)

    @patch('biometric_analysis.pd.read_sql')
    def test_calculate_success_rates(self, mock_read_sql):
        mock_read_sql.return_value = self.df.copy()
        
        results = biometric_analysis.calculate_success_rates()
        
        self.assertEqual(len(results), 2)
        # Check D1
        d1 = next(r for r in results if r['district'] == 'D1')
        self.assertEqual(d1['success_rate_5_17'], 80.0)
        self.assertEqual(d1['success_rate_17_plus'], 90.0)

    @patch('biometric_analysis.pd.read_sql')
    def test_identify_low_performers(self, mock_read_sql):
        mock_read_sql.return_value = self.df.copy()
        
        # Test threshold 60
        # D1 avg = (80+90)/2 = 85 (High)
        # D2 avg = (40+50)/2 = 45 (Low)
        
        # We need to ensure cache doesnt interfere across tests or we patch the calculator
        # The decorator caches based on args. 
        # But we verify logic.
        
        # Note: identify_low_performers calls calculate_success_rates which calls get_joined_data -> read_sql
        # So mocking read_sql works for the whole chain if cache is empty.
        
        results = biometric_analysis.identify_low_performers(threshold=60)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['district'], 'D2')
        self.assertEqual(results[0]['success_rate'], 45.0) # avg_rate renamed to success_rate

    @patch('biometric_analysis.pd.read_sql')
    def test_detect_repeat_patterns(self, mock_read_sql):
        # Create anomaly data
        # Attempts > 2 * Enrollments
        anomaly_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'state': ['S1'],
            'district': ['D3'],
            'age_5_17': [10],
            'age_18_greater': [10], # Total enroll = 20
            'bio_age_5_17': [30],
            'bio_age_17_': [20]     # Total attempts = 50. Rate = 2.5
        })
        
        mock_read_sql.return_value = anomaly_df.copy()
        
        results = biometric_analysis.detect_repeat_attempt_patterns()
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['district'], 'D3')
        self.assertEqual(results[0]['repeat_rate'], 2.5)

    def test_caching(self):
        # Verify redis set is called
        # We access the redis_client used in module
        mock_redis = biometric_analysis.redis_client
        mock_redis.get.return_value = None # Cache miss
        
        # Patch read_sql to return something valid so function completes
        with patch('biometric_analysis.pd.read_sql') as mock_read:
            mock_read.return_value = self.df.copy()
            biometric_analysis.calculate_success_rates(state="CacheTest")
            
            # Check if setex was called
            self.assertTrue(mock_redis.setex.called)

if __name__ == '__main__':
    unittest.main()
