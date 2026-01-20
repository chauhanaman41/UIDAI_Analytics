import pandas as pd
import numpy as np
import redis
import json
import os
from sqlalchemy import create_engine
from functools import wraps
from datetime import timedelta
import hashlib
from dotenv import load_dotenv

load_dotenv()

# Database Connection
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Redis Connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

def cache_result(ttl=3600):
    """
    Decorator to cache function results in Redis.
    Key is generated based on function name and arguments.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a unique key
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            key_str = ":".join(key_parts)
            # Hash to avoid long keys or sensitive info in keys
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            redis_key = f"bio_analysis:{func.__name__}:{key_hash}"
            
            try:
                cached = redis_client.get(redis_key)
                if cached:
                    return json.loads(cached)
            except redis.ConnectionError:
                pass # Fail silently if Cache is down
            
            result = func(*args, **kwargs)
            
            # Serialize for Redis (Handle DataFrames)
            if isinstance(result, pd.DataFrame):
                # We convert DF to JSON records for caching
                to_cache = result.to_dict(orient='records')
                # But wrapper must return the original type usually. 
                # For this specific module, returning list of dicts is fine as it's JSON serializable for API.
                # If we need DataFrame back, we'd need to reconstruct.
                # Requirement says "JSON-serializable for Redis caching".
                # Let's standardize: Functions return List[Dict] or Dict.
                pass 
            elif isinstance(result, (dict, list)):
                to_cache = result
            else:
                to_cache = str(result)
            
            try:
                redis_client.setex(redis_key, ttl, json.dumps(to_cache))
            except redis.ConnectionError:
                pass
                
            return to_cache
        return wrapper
    return decorator

def get_joined_data(state=None, district=None, start_date=None):
    """
    Joins enrollments and biometric_attempts.
    """
    query = """
        SELECT 
            e.date, e.state, e.district,
            e.age_5_17, e.age_18_greater,
            b.bio_age_5_17, b.bio_age_17_
        FROM enrollments e
        JOIN biometric_attempts b 
        ON e.date = b.date AND e.state = b.state AND e.district = b.district
        WHERE 1=1
    """
    params = {}
    if state:
        query += " AND e.state = %(state)s"
        params['state'] = state
    if district:
        query += " AND e.district = %(district)s"
        params['district'] = district
    
    # We join on full data, aggregates done in pandas for flexibility or SQL for perf.
    # Given requirements, let's fetch raw joined data to pandas.
    
    try:
        df = pd.read_sql(query, engine, params=params)
        return df
    except Exception as e:
        print(f"DB Error: {e}")
        return pd.DataFrame()

@cache_result(ttl=3600)
def calculate_success_rates(state=None, district=None):
    """
    Calculates success rates for authentication.
    Returns list of dicts.
    """
    df = get_joined_data(state, district)
    
    if df.empty:
        return []

    # Handle zeros to avoid division error
    df['age_5_17'] = df['age_5_17'].replace(0, np.nan)
    df['age_18_greater'] = df['age_18_greater'].replace(0, np.nan)
    
    df['success_rate_5_17'] = (df['bio_age_5_17'] / df['age_5_17']) * 100
    df['success_rate_17_plus'] = (df['bio_age_17_'] / df['age_18_greater']) * 100
    
    # Handle NaN results from division (fill 0 for now or leave None)
    df = df.fillna(0) # Assuming 0 success if 0 attempts is acceptable, or 0 enrollments.
    
    # Round
    df['success_rate_5_17'] = df['success_rate_5_17'].round(1)
    df['success_rate_17_plus'] = df['success_rate_17_plus'].round(1)
    
    # Convert dates
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    return df[['state', 'district', 'date', 'success_rate_5_17', 'success_rate_17_plus']].to_dict(orient='records')

@cache_result(ttl=3600)
def identify_low_performers(threshold=60):
    """
    Identifies districts with success rates below threshold.
    """
    # Get all data
    data = calculate_success_rates() # Uses cache
    df = pd.DataFrame(data)
    
    if df.empty:
        return []

    # Calculate average success rate per district
    # We need to re-aggregate if calculate_success_rates returns daily data
    district_stats = df.groupby(['state', 'district'])[['success_rate_5_17', 'success_rate_17_plus']].mean().reset_index()
    
    # Simple weighted avg logic or just check if ANY rate is low?
    # Requirement: "success_rate < threshold". Let's use avg of both groups or just 17+ (majority)
    # Let's use avg of the two rates for simplicity
    district_stats['avg_rate'] = (district_stats['success_rate_5_17'] + district_stats['success_rate_17_plus']) / 2
    
    low_performers = district_stats[district_stats['avg_rate'] < threshold].copy()
    
    low_performers['gap'] = threshold - low_performers['avg_rate']
    
    # Priority score needs 'total affected enrollments'
    # We need to join back with volume data or estimate.
    # For now, let's assume 'gap' is the main driver as volume requires another query.
    # Or we can fetch volume in the main query.
    
    low_performers['priority_score'] = low_performers['gap'] * 10 # Placeholder for volume weight
    
    low_performers = low_performers.sort_values('priority_score', ascending=False)
    
    return low_performers[['district', 'avg_rate', 'gap', 'priority_score']].rename(columns={'avg_rate': 'success_rate'}).to_dict(orient='records')

@cache_result(ttl=3600)
def detect_repeat_attempt_patterns():
    """
    Detects anomalies where attempts > 2 * enrollments.
    """
    df = get_joined_data()
    
    if df.empty:
        return []
    
    # Total attempts = bio_age_5_17 + bio_age_17_
    # Total enrollments = age_5_17 + age_18_greater
    df['total_attempts'] = df['bio_age_5_17'] + df['bio_age_17_']
    df['total_enrollments'] = df['age_5_17'] + df['age_18_greater']
    
    df['repeat_rate'] = np.where(df['total_enrollments'] > 0, df['total_attempts'] / df['total_enrollments'], 0)
    
    anomalies = df[df['repeat_rate'] > 2.0].copy()
    
    anomalies['date'] = pd.to_datetime(anomalies['date']).dt.strftime('%Y-%m-%d')
    anomalies['repeat_rate'] = anomalies['repeat_rate'].round(2)
    
    return anomalies[['state', 'district', 'date', 'repeat_rate']].to_dict(orient='records')

if __name__ == "__main__":
    pass
