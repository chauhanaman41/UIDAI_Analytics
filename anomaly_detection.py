import pandas as pd
import numpy as np
from celery import Celery
import os
from sqlalchemy import create_engine
from scipy import stats
from dotenv import load_dotenv
import json

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for testing/imports
    DATABASE_URL = "postgresql://user:pass@localhost/db"
    
engine = create_engine(DATABASE_URL)

app = Celery('anomaly_detection', broker=os.getenv("REDIS_URL", 'redis://localhost:6379/0'))

def get_time_series_data(state=None, district=None, days=90):
    """Fetches last N days of data for analysis."""
    query = """
        SELECT date, 
               (age_0_5 + age_5_17 + age_18_greater) as daily_enrollments
        FROM enrollments
        WHERE 1=1
    """
    params = {}
    if state:
        query += " AND state = %(state)s"
        params['state'] = state
    if district:
        query += " AND district = %(district)s"
        params['district'] = district
        
    query += " ORDER BY date DESC LIMIT %(limit)s"
    params['limit'] = days + 60 # Fetch extra for rolling window context
    
    try:
        df = pd.read_sql(query, engine, params=params)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date') # Sort ASC for time series
        return df.set_index('date')
    except Exception as e:
        print(f"Data fetch error: {e}")
        return pd.DataFrame()

def z_score_anomalies(data_series, threshold=3):
    """
    Detects anomalies using Z-score.
    Returns list of dicts: {date, value, z_score}
    """
    if len(data_series) < 3:
        return []
    
    # Calculate Z-scores
    z_scores = np.abs(stats.zscore(data_series))
    
    anomalies = []
    for date, value, z in zip(data_series.index, data_series.values, z_scores):
        if z > threshold:
            anomalies.append({
                "date": date,
                "value": float(value),
                "z_score": float(z),
                "method": "z_score"
            })
    return anomalies

def iqr_outliers(data_series):
    """
    Detects outliers using IQR method.
    """
    if len(data_series) < 5:
        return []
        
    Q1 = data_series.quantile(0.25)
    Q3 = data_series.quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    anomalies = []
    for date, value in data_series.items():
        if value < lower_bound or value > upper_bound:
            anomalies.append({
                "date": date,
                "value": float(value),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "method": "iqr"
            })
    return anomalies

def rolling_average_deviation(data_series, window=30):
    """
    Detects deviation from rolling mean.
    """
    if len(data_series) < window:
        return []
        
    rolling_mean = data_series.rolling(window=window).mean()
    
    # We look at the deviation of current value vs rolling mean of previous window (excluding current usually, but here comprehensive)
    # Let's take difference pct
    deviation_pct = np.abs((data_series - rolling_mean) / rolling_mean)
    
    anomalies = []
    # Only check checks where we have full window
    valid_indices = deviation_pct.index[window:] # Skip first 'window' NaNs
    
    for date in valid_indices:
        dev = deviation_pct.loc[date]
        if dev > 0.5: # 50% deviation
            anomalies.append({
                "date": date,
                "value": float(data_series.loc[date]),
                "rolling_mean": float(rolling_mean.loc[date]),
                "deviation_pct": float(dev),
                "method": "rolling_deviation"
            })
    return anomalies

def comprehensive_anomaly_report(state=None, district=None, days=90):
    """
    Combines methods and validates anomalies.
    """
    df = get_time_series_data(state, district, days)
    if df.empty or 'daily_enrollments' not in df.columns:
        return []
    
    series = df['daily_enrollments']
    
    # Run all methods
    z_anomalies = z_score_anomalies(series)
    iqr_anoms = iqr_outliers(series)
    roll_anoms = rolling_average_deviation(series)
    
    # Aggregate by date
    findings = {}
    
    def add_finding(date_key, entry):
        if date_key not in findings:
            findings[date_key] = {
                "date": entry['date'],
                "value": entry['value'],
                "methods": [],
                "details": {}
            }
        findings[date_key]['methods'].append(entry['method'])
        findings[date_key]['details'][entry['method']] = entry
        
    for a in z_anomalies: add_finding(a['date'], a)
    for a in iqr_anoms: add_finding(a['date'], a)
    for a in roll_anoms: add_finding(a['date'], a)
    
    # Cross-validate
    validated_anomalies = []
    for date_key, f in findings.items():
        if len(f['methods']) >= 2: # Must be flagged by at least 2 methods
            # Categorize
            val = f['value']
            # Determine if high or low
            # Use rolling mean from rolling method if avail, else mean
            is_spike = True
            if 'rolling_deviation' in f['details']:
                roll_mean = f['details']['rolling_deviation']['rolling_mean']
                if val < roll_mean: is_spike = False
            else:
                # Use simple mean
                if val < series.mean(): is_spike = False
            
            anom_type = 'spike' if is_spike else 'drop'
            
            # Severity score (1-10)
            # Use Z-score if available as base
            severity = 5.0
            if 'z_score' in f['details']:
                z = f['details']['z_score']['z_score']
                severity = min(10.0, z) # Z-score 3 -> 3, 10 -> 10
            
            validated_anomalies.append({
                "date": f['date'].strftime('%Y-%m-%d'),
                "metric_name": "daily_enrollments",
                "anomaly_value": val,
                "severity_score": round(severity, 2),
                "anomaly_type": anom_type,
                "detection_methods": f['methods'],
                "district": district,
                "state": state
            })
            
    return validated_anomalies

@app.task
def detect_anomalies_daily():
    """
    Celery task to run for all active contexts.
    In real app, we might iterate all districts.
    """
    # Example: Run for a few key districts or fetch distinct districts from DB
    # For MVP, let's run for "State wide" or similar.
    # Fetch distinct districts
    # districts = pd.read_sql("SELECT DISTINCT district, state FROM enrollments", engine) ...
    # For now, just a placeholder run on null (aggregate) or one sample
    
    print("Starting Anomaly Detection...")
    # Mock iteration
    # results = comprehensive_anomaly_report(state="S1", district="D1")
    # Store in DB...
    
    # To implementation:
    # 1. Get districts
    try:
        districts_df = pd.read_sql("SELECT DISTINCT state, district FROM enrollments LIMIT 10", engine)
        
        all_alerts = []
        for _, row in districts_df.iterrows():
            alerts = comprehensive_anomaly_report(state=row['state'], district=row['district'])
            all_alerts.extend(alerts)
            
        if all_alerts:
            # Bulk insert alerts
            alerts_df = pd.DataFrame(all_alerts)
            # Need to map columns to DB schema
            # DB: date, state, district, metric_name, anomaly_value, severity_score, anomaly_type, detection_methods
            # DF has detection_methods as list, sqlalchemy/psycopg2 should handle array mapping if configured, 
            # or we cast to list/string. Postgres array works with list in psycopg2.
            
            alerts_df.to_sql('anomaly_alerts', engine, if_exists='append', index=False, method='multi')
            print(f"Inserted {len(alerts_df)} alerts.")
            
    except Exception as e:
        print(f"Error in daily detection: {e}")

if __name__ == "__main__":
    pass
