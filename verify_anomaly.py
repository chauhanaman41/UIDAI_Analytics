import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Mock dependencies
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['celery'] = MagicMock()

# Mock env
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://mock", "REDIS_URL": "redis://mock"}):
    import anomaly_detection

class TestAnomalyDetection(unittest.TestCase):
    def setUp(self):
        # Create 90 days of data
        dates = pd.date_range(start='2024-01-01', periods=90, freq='D')
        
        # Base signal: Stable around 100
        values = np.random.normal(100, 5, 90)
        
        # Introduce a HUGE spike at index 50
        self.spike_date = dates[50]
        values[50] = 200 # Z-score will be (200-100)/5 = 20. Very high.
        
        # Introduce a outlier drop at index 70
        self.drop_date = dates[70]
        values[70] = 50 # Drop to 50
        
        self.df = pd.DataFrame({
            'date': dates,
            'daily_enrollments': values
        })

    def test_z_score(self):
        series = self.df.set_index('date')['daily_enrollments']
        anoms = anomaly_detection.z_score_anomalies(series)
        
        # Should find the spike
        spike_found = any(a['date'] == self.spike_date for a in anoms)
        self.assertTrue(spike_found)
        
    def test_iqr(self):
        series = self.df.set_index('date')['daily_enrollments']
        anoms = anomaly_detection.iqr_outliers(series)
        
        spike_found = any(a['date'] == self.spike_date for a in anoms)
        self.assertTrue(spike_found)

    def test_rolling_deviation(self):
        series = self.df.set_index('date')['daily_enrollments']
        anoms = anomaly_detection.rolling_average_deviation(series)
        
        # Spike should deviate significantly from previous 30 day avg
        spike_found = any(a['date'] == self.spike_date for a in anoms)
        self.assertTrue(spike_found)

    @patch('anomaly_detection.pd.read_sql')
    def test_comprehensive_report(self, mock_read_sql):
        # We assume the read_sql returns our DF sorted
        mock_read_sql.return_value = self.df.sort_values('date')
        
        results = anomaly_detection.comprehensive_anomaly_report(state="S1", district="D1")
        
        # The spike matches Z-score (>3), IQR (way outside), and Rolling (>50% dev).
        # So it should be included and validated (2+ methods).
        
        spike_result = next((r for r in results if pd.to_datetime(r['date']) == self.spike_date), None)
        
        self.assertIsNotNone(spike_result)
        self.assertEqual(spike_result['anomaly_type'], 'spike')
        self.assertTrue(len(spike_result['detection_methods']) >= 2)
        # Severity should be high (Z-score around 7-8, capped at 10)
        self.assertTrue(spike_result['severity_score'] > 5.0)

if __name__ == '__main__':
    unittest.main()
