import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Mock dependencies
sys.modules['sqlalchemy'] = MagicMock()

# Mock Celery to pass-through tasks
mock_celery = MagicMock()
def task_decorator(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def wrapper(func):
        return func
    return wrapper
    
mock_celery.Celery.return_value.task.side_effect = task_decorator
sys.modules['celery'] = mock_celery

# Mock env
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://mock", "REDIS_URL": "redis://mock"}):
    import risk_prediction

class TestRiskPrediction(unittest.TestCase):
    def setUp(self):
        # Create synthetic data for 100 months/districts
        # 2 states, 5 districts each, 24 months
        dates = pd.date_range(start='2022-01-01', periods=24, freq='M')
        data = []
        for state in ['S1', 'S2']:
            for dist in range(5):
                for d in dates:
                    # Random enrollments
                    enrol = np.random.randint(100, 1000)
                    # Random success rate (ensure some < 60%)
                    success_rate = np.random.uniform(0.4, 0.9)
                    bio = int(enrol * success_rate)
                    demo = int(enrol * 0.1)
                    
                    data.append({
                        'month': d,
                        'state': state,
                        'district': f"D{dist}",
                        'enrollments': enrol,
                        'biometric_attempts': bio,
                        'demo_updates': demo
                    })
        self.df = pd.DataFrame(data)

    @patch('risk_prediction.pd.read_sql')
    def test_end_to_end(self, mock_read_sql):
        mock_read_sql.return_value = self.df
        
        # 1. Train Model
        # This should execute GridSearch and save model
        risk_prediction.train_model()
        
        # Check if model exists
        self.assertTrue(os.path.exists(risk_prediction.MODEL_PATH))
        self.assertTrue(os.path.exists(risk_prediction.FEATURE_NAMES_PATH))
        
        # 2. Predict Risk
        # Should return filtering for S1, D0
        res = risk_prediction.predict_risk('S1', 'D0')
        
        self.assertIn('district', res)
        self.assertIn('risk_score', res)
        self.assertIn('risk_category', res)
        self.assertIn('top_factors', res)
        
        # Check category logic
        score = res['risk_score']
        if score > 0.7: self.assertEqual(res['risk_category'], 'High')
        elif score > 0.4: self.assertEqual(res['risk_category'], 'Medium')
        else: self.assertEqual(res['risk_category'], 'Low')

    def tearDown(self):
        # Cleanup artifacts
        if os.path.exists(risk_prediction.MODEL_PATH):
            os.remove(risk_prediction.MODEL_PATH)
        if os.path.exists(risk_prediction.FEATURE_NAMES_PATH):
            os.remove(risk_prediction.FEATURE_NAMES_PATH)

if __name__ == '__main__':
    unittest.main()
