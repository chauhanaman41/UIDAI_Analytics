import pandas as pd
import numpy as np
from utils.db_connector import get_engine

def get_joined_data(state=None, district=None, start_date=None):
    engine = get_engine()
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
        
    try:
        df = pd.read_sql(query, engine, params=params)
        return df
    except Exception as e:
        print(f"DB Error: {e}")
        return pd.DataFrame()

def calculate_success_rates(state=None, district=None):
    df = get_joined_data(state, district)
    if df.empty: return []
    
    df['age_5_17'] = df['age_5_17'].replace(0, np.nan)
    df['age_18_greater'] = df['age_18_greater'].replace(0, np.nan)
    
    df['success_rate_5_17'] = (df['bio_age_5_17'] / df['age_5_17']) * 100
    df['success_rate_17_plus'] = (df['bio_age_17_'] / df['age_18_greater']) * 100
    df = df.fillna(0)
    
    df['success_rate_5_17'] = df['success_rate_5_17'].round(1)
    df['success_rate_17_plus'] = df['success_rate_17_plus'].round(1)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    return df[['state', 'district', 'date', 'success_rate_5_17', 'success_rate_17_plus']].to_dict(orient='records')

def identify_low_performers(threshold=60, state=None):
    data = calculate_success_rates(state=state)
    df = pd.DataFrame(data)
    if df.empty: return []
    
    district_stats = df.groupby(['state', 'district'])[['success_rate_5_17', 'success_rate_17_plus']].mean().reset_index()
    district_stats['avg_rate'] = (district_stats['success_rate_5_17'] + district_stats['success_rate_17_plus']) / 2
    
    low_performers = district_stats[district_stats['avg_rate'] < threshold].copy()
    low_performers['gap'] = threshold - low_performers['avg_rate']
    low_performers['priority_score'] = low_performers['gap'] * 10
    low_performers = low_performers.sort_values('priority_score', ascending=False)
    
    return low_performers[['district', 'avg_rate', 'gap', 'priority_score']].rename(columns={'avg_rate': 'success_rate'}).to_dict(orient='records')
