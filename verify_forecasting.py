import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Mock dependencies that might be heavy or missing during test
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['celery'] = MagicMock()
# We don't mock pmdarima/prophet here immediately because we want to see if they import
# But if installation fails, we might want to mock them to verify logic.
# Let's verify logic by patching the train functions in the module.

# Mock env
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://mock", "REDIS_URL": "redis://mock"}):
    import forecasting_module

class TestForecasting(unittest.TestCase):
    def setUp(self):
        # Create 24 months of data
        dates = pd.date_range(start='2024-01-01', periods=24, freq='MS')
        
        # Linear trend: y = 1000 + 10x
        values = 1000 + 10 * np.arange(24)
        
        self.df = pd.DataFrame({
            'ds': dates,
            'y': values
        })

    @patch('forecasting_module.pd.read_sql')
    @patch('forecasting_module.create_engine') # Ensure engine creation doesn't fail
    def test_prepare_data(self, mock_engine, mock_read_sql):
        # read_sql should return daily data, logic aggregates it
        # Let's return daily data that sums up to our monthly 'y'
        
        # For simplicity, let's assume read_sql returns already what we want? 
        # No, the function aggregates.
        # So we mock read_sql to return daily data.
        
        dates_daily = pd.date_range(start='2024-01-01', periods=24*30, freq='D')
        values_daily = np.ones(len(dates_daily)) * 10 # 10 per day
        
        df_daily = pd.DataFrame({
            'ds': dates_daily,
            'y': values_daily
        })
        
        mock_read_sql.return_value = df_daily
        
        monthly = forecasting_module.get_monthly_data(state="S1")
        
        # Check aggregation
        self.assertEqual(len(monthly), 24) # 24 months roughly
        self.assertTrue('ds' in monthly.columns)
        self.assertTrue('y' in monthly.columns)
        
        # Check interpolation (simulate missing month)
        # Create gap
        df_gap = pd.DataFrame({
            'ds': [pd.Timestamp('2024-01-01'), pd.Timestamp('2024-03-01')],
            'y': [100.0, 300.0]
        })
        # Note: logic aggregates resample('MS'). 
        # If input has Jan and Mar, resample will create Feb with NaN.
        # Logic interpolates. Feb should be 200.
        
        mock_read_sql.return_value = df_gap
        monthly_gap = forecasting_module.get_monthly_data("GapTest")
        
        self.assertEqual(len(monthly_gap), 3) # Jan, Feb, Mar
        self.assertEqual(monthly_gap.iloc[1]['y'], 200.0) # Feb interpolated

    @patch('forecasting_module.train_arima')
    @patch('forecasting_module.train_prophet')
    @patch('forecasting_module.get_monthly_data')
    def test_model_selection(self, mock_get_data, mock_prophet, mock_arima):
        # Scenario: Prophet is better (Lower MAPE)
        
        # Mock data (24 months)
        mock_get_data.return_value = self.df.copy()
        
        # Mock Training Returns for EVALUATION step (test_size=3)
        # Train split is 21 months. Test is 3.
        # Test y values: 1210, 1220, 1230 (indices 21, 22, 23 => 1000 + 10*21=1210)
        
        # 1. ARIMA Forecast (Bad) - Predicts constant 1500
        # Returns: forecast, conf_int, model
        arima_forecast = np.array([1500, 1500, 1500])
        mock_arima.return_value = (arima_forecast, None, None)
        
        # 2. Prophet Forecast (Good) - Predicts close to actual
        # Returns: df, model
        # df needs 'yhat'
        prophet_df = pd.DataFrame({
            'ds': self.df.iloc[-3:]['ds'],
            'yhat': [1210, 1220, 1230], # Perfect
            'yhat_lower': [0]*3,
            'yhat_upper': [0]*3
        })
        mock_prophet.return_value = (prophet_df, None)
        
        # Run Generation
        # Note: generate_forecast is a Celery task. We call the underlying function if we mocked the decorator?
        # We imported forecasting_module. 
        # If we couldn't import celery, we mocked it.
        # If celery was mocked, app.task is a mock.
        # If generic mock, generate_forecast is the decorated object.
        # If we want the function, usually .run() logic or we assume we patched app.task to return func.
        
        # Let's try calling it. If it fails due to binding, we mock 'self'.
        mock_self = MagicMock()
        
        # We need to handle the RE-TRAINING step.
        # The function calls train_prophet AGAIN with full data.
        # We need side_effect to return different values? 
        # Or just return same structure.
        
        result = forecasting_module.generate_forecast(mock_self, state="TestSelection")
        
        # Prophet should be selected
        self.assertEqual(result['model_used'], 'Prophet')
        self.assertEqual(result['mape'], 0.0)
        
    @patch('forecasting_module.train_arima')
    @patch('forecasting_module.train_prophet')
    @patch('forecasting_module.get_monthly_data')
    def test_json_structure(self, mock_get_data, mock_prophet, mock_arima):
        mock_get_data.return_value = self.df.copy()
        
        # ARIMA wins
        # Evaluation step
        mock_arima.return_value = (np.array([10]*3), None, None) # returns array
        mock_prophet.return_value = (None, None) # Prophet fails
        
        # Retrain step
        # ARIMA returns forecast for 6 months
        arima_forecast = np.array([100]*6)
        conf_int = np.array([[90, 110]]*6)
        
        # We use side_effect to differentiate calls if needed, but here simple return works
        # First call (eval) gets array of 3. Second call (forecast) gets array of 6?
        # The code predicts n_periods=steps.
        # Eval: steps=3. Retrain: steps=6.
        # We can set side_effect = [ (arr3,), (arr6,) ]
        
        mock_arima.side_effect = [
            (np.array([1210, 1220, 1230]), None, None), # Eval (Perfect)
            (np.array([1240, 1250, 1260, 1270, 1280, 1290]), np.array([[1200,1300]]*6), None) # Future
        ]
        
        result = forecasting_module.generate_forecast(MagicMock(), state="Structure")
        
        self.assertEqual(result['model_used'], 'ARIMA')
        self.assertEqual(len(result['forecast']), 6)
        self.assertIn('lower', result['forecast'][0])
        self.assertIn('upper', result['forecast'][0])

if __name__ == '__main__':
    unittest.main()
