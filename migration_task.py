from celery import Celery
import pandas as pd
import psycopg2
import psycopg2.extras
import os
import json
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Celery
# celery -A migration_task worker --loglevel=info
app = Celery('migration_task', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# Database Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Establishes a connection to the Supabase database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def migrate_to_supabase(self, file_path, table_name):
    """
    Migrates data from a Parquet file to a Supabase PostgreSQL table.
    
    Args:
        file_path (str): Path to the parquet file.
        table_name (str): Destination table name.
    
    Returns:
        dict: Summary of the migration.
    """
    TOTAL_BATCH_SIZE = 10000  # Rows per DB insert
    PROGRESS_UPDATE_FREQ = 50000 # Update UI/Celery state every N rows

    summary = {
        "file": file_path,
        "total_rows": 0,
        "inserted": 0,
        "errors": 0,
        "status": "Started"
    }
    
    conn = None
    try:
        # Read the parquet file
        # Parquet files are typically small enough to load into memory for this use case (<50MB)
        # If huge, we would use pyarrow to stream.
        df = pd.read_parquet(file_path)
        total_rows = len(df)
        summary["total_rows"] = total_rows
        
        # Connect to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare columns
        columns = list(df.columns)
        columns_str = ', '.join(columns)
        
        # Generate the SQL for bulk insert
        # ON CONFLICT DO NOTHING to handle restarts/duplicates
        sql = f"INSERT INTO {table_name} ({columns_str}) VALUES %s ON CONFLICT DO NOTHING"
        
        rows_processed = 0
        
        # Iterate in batches
        num_batches = math.ceil(total_rows / TOTAL_BATCH_SIZE)
        
        for i in range(num_batches):
            start_idx = i * TOTAL_BATCH_SIZE
            end_idx = start_idx + TOTAL_BATCH_SIZE
            batch_df = df.iloc[start_idx:end_idx]
            
            # Convert to list of tuples for psycopg2
            # Handle NaN values for SQL (convert to None)
            values = list(batch_df.where(pd.notnull(batch_df), None).itertuples(index=False, name=None))
            
            try:
                psycopg2.extras.execute_values(
                    cursor, sql, values, template=None, page_size=TOTAL_BATCH_SIZE
                )
                conn.commit()
                
                rows_processed += len(values)
                summary["inserted"] += len(values) # In DO NOTHING case, rowcount might be different but we count processed.
                
                # Update progress
                if rows_processed % PROGRESS_UPDATE_FREQ == 0 or rows_processed == total_rows:
                    self.update_state(
                        state='PROGRESS',
                        meta={'current': rows_processed, 'total': total_rows}
                    )
                    print(f"Progress: {rows_processed}/{total_rows}")
                    
            except Exception as e:
                conn.rollback()
                print(f"Batch failed: {e}")
                summary["errors"] += len(values)
                # In a real scenario, you might want to retry the batch or log specific rows.
                # For now, we count as errors and continue to next batch or fail depending on strictness.
                # If connection lost, it will raise and trigger task retry.
                if isinstance(e, psycopg2.OperationalError):
                    raise e
        
        summary["status"] = "Completed"
        return summary

    except Exception as e:
        summary["status"] = f"Failed: {str(e)}"
        print(f"Migration failed: {e}")
        # Retry logic handled by Celery decorator
        raise self.retry(exc=e)
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # For manual testing without worker
    # Ensure DATABASE_URL is set in .env
    pass
