import unittest
from unittest.mock import MagicMock, patch
import sys
import pandas as pd
import os

# 1. Patch Celery BEFORE importing migration_task
mock_celery_module = MagicMock()
sys.modules['celery'] = mock_celery_module

# Mock the Celery app instance and its task decorator
mock_app = MagicMock()
mock_celery_module.Celery.return_value = mock_app

def task_decorator(*args, **kwargs):
    def wrapper(func):
        # We attach the 'retry' method to the function to mock self.retry
        func.retry = MagicMock() 
        func.update_state = MagicMock() # Ensure update_state exists on the wrapper
        return func
    return wrapper

mock_app.task.side_effect = task_decorator

# 2. Import module under test
import migration_task

class TestMigrationTask(unittest.TestCase):
    def setUp(self):
        self.test_file = 'test_data.parquet'
        df = pd.DataFrame({
            'id': range(100),
            'data': ['test'] * 100
        })
        df.to_parquet(self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @patch('migration_task.get_db_connection')
    @patch('migration_task.psycopg2.extras.execute_values') # Patch here too!
    def test_migrate_logic(self, mock_execute_values, mock_get_db):
        # Setup DB mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Run the function 
        # Since we are using the 'self' argument in the function logic, we pass a mock.
        mock_self = MagicMock()
        
        summary = migration_task.migrate_to_supabase(mock_self, self.test_file, 'test_table')
        
        # Check that errors is 0
        if summary['errors'] > 0:
            print(f"\nMigration failed with status: {summary['status']}")
            
        self.assertEqual(summary['total_rows'], 100)
        self.assertEqual(summary['inserted'], 100)
        self.assertEqual(summary['errors'], 0)
        
    @patch('migration_task.get_db_connection')
    @patch('migration_task.psycopg2.extras.execute_values')
    def test_batching(self, mock_execute_values, mock_get_db):
        # Large file
        df = pd.DataFrame({'id': range(25000)})
        df.to_parquet(self.test_file)
        
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = MagicMock()
        
        mock_self = MagicMock()
        
        summary = migration_task.migrate_to_supabase(mock_self, self.test_file, 'test_table')
        
        self.assertEqual(summary['total_rows'], 25000)
        # 10000, 10000, 5000 => 3 calls
        self.assertEqual(mock_execute_values.call_count, 3)

if __name__ == '__main__':
    unittest.main()
