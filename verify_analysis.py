import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
import os
import sys

# Mock create_engine BEFORE import
mock_sqlalchemy = MagicMock()
sys.modules['sqlalchemy'] = mock_sqlalchemy

# Mock os.getenv to avoid NoneType error if logic relies on it before engine creation
with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}):
    import enrollment_analysis

class TestEnrollmentAnalysis(unittest.TestCase):
    def setUp(self):
        # Create synthetic daily data for 2 years
        dates = pd.date_range(start='2024-01-01', periods=730, freq='D')
        
        # Linear growth with some noise
        values = np.linspace(10, 100, 730) + np.random.normal(0, 5, 730)
        # Add seasonality: Higher in June (Month 6)
        seasonality = np.where(dates.month == 6, 20, 0)
        values += seasonality
        # Ensure positive
        values = np.maximum(values, 0)
        
        self.df = pd.DataFrame({
            'date': dates,
            'age_0_5': values.astype(int),
            'age_5_17': (values * 0.5).astype(int),
            'age_18_greater': (values * 0.2).astype(int)
        })
        self.df['total'] = self.df['age_0_5'] + self.df['age_5_17'] + self.df['age_18_greater']

    @patch('enrollment_analysis.pd.read_sql')
    @patch('enrollment_analysis.check_dpdp_compliance') # Patch compliance helper to avoid issues with mock engine
    def test_growth_rates(self, mock_check, mock_read_sql):
        mock_read_sql.return_value = self.df.copy()
        mock_check.return_value = True # compliant
        
        result = enrollment_analysis.calculate_growth_rates(state="TestState")
        
        self.assertIn('Monthly_MoM', result)
        self.assertTrue(len(result['Monthly_MoM']) > 0)
        # Check first record structure
        first = result['Monthly_MoM'][0]
        self.assertIn('growth_rate_pct', first)
        self.assertIn('absolute_change', first)
        
    @patch('enrollment_analysis.pd.read_sql')
    @patch('enrollment_analysis.check_dpdp_compliance')
    def test_seasonality(self, mock_check, mock_read_sql):
        mock_read_sql.return_value = self.df.copy()
        mock_check.return_value = True 
        
        result = enrollment_analysis.detect_seasonality(state="TestState")
        
        self.assertIn(6, result) # June exists
        self.assertIsInstance(result[1], float)

    @patch('enrollment_analysis.pd.read_sql')
    @patch('enrollment_analysis.check_dpdp_compliance')
    def test_saturation_logistic(self, mock_check, mock_read_sql):
        mock_check.return_value = True
        
        # Create perfect logistic curve data
        x = np.linspace(-6, 6, 100)
        L = 1000
        k = 1
        t0 = 0
        y = L / (1 + np.exp(-k * x))
        
        dates = pd.date_range(start='2024-01-01', periods=100)
        df_log = pd.DataFrame({
            'date': dates,
        })
        
        # We need to simulate the return of get_data which calculates 'total'
        # The logic in calculate_saturation_estimate calls get_data().
        # get_data() calls read_sql and adds total.
        # But we mock read_sql.
        # So inside get_data:
        # df = read_sql(...) -> returns our df_log
        # df['total'] = sum(cols)
        # So our df_log must have the columns age_0_5 etc.
        
        y_int = (y/3).astype(int)
        df_log['age_0_5'] = y_int
        df_log['age_5_17'] = y_int
        df_log['age_18_greater'] = y_int
        
        # To make cumsum match logistic curve, the daily values must be the increments of logistic curve
        # Curve_fit fits the CUMULATIVE sum of the data.
        # So input data (enrollments per day) should be the derivative of logistic curve.
        y_diff = np.diff(y, prepend=0)
        y_diff_int = (y_diff/3).astype(int)
        
        df_log['age_0_5'] = y_diff_int
        df_log['age_5_17'] = y_diff_int
        df_log['age_18_greater'] = y_diff_int
        
        mock_read_sql.return_value = df_log
        
        # We need to ensure check_dpdp_compliance passes or is mocked
        # It is mocked above.
        
        result = enrollment_analysis.calculate_saturation_estimate("Test", "District")
        
        self.assertIn('current_penetration', result)
        self.assertIn('months_to_90_percent', result)
        
    @patch('enrollment_analysis.pd.read_sql')
    def test_dpdp_suppression(self, mock_read_sql):
        # Small dataframe
        small_df = pd.DataFrame({
            'date': [pd.Timestamp('2024-01-01')],
            'age_0_5': [10],
            'age_5_17': [10],
            'age_18_greater': [10]
        }) # Total 30 < 100
        
        mock_read_sql.return_value = small_df
        
        # We test the real check_dpdp_compliance by NOT mocking it here?
        # But verify_analysis imports 'enrollment_analysis' which has 'check_dpdp_compliance'
        # In this test method, we call calculate_growth_rates.
        # We want IT to call the REAL check_dpdp_compliance.
        # But I patched imported module's dependencies? No, I patched 'enrollment_analysis.pd.read_sql'.
        # I did not patch check_dpdp_compliance in this specific test method decoration.
        # So it uses real one.
        
        result = enrollment_analysis.calculate_growth_rates("SmallData")
        self.assertIn("error", result)

if __name__ == '__main__':
    unittest.main()
