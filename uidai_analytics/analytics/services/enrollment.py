import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from utils.db_connector import get_engine

def get_data(state=None, district=None, start_date=None, end_date=None):
    engine = get_engine()
    query = """
        SELECT date, age_0_5, age_5_17, age_18_greater
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
    if start_date:
        query += " AND date >= %(start_date)s"
        params['start_date'] = start_date
    if end_date:
        query += " AND date <= %(end_date)s"
        params['end_date'] = end_date
        
    query += " ORDER BY date"
    
    try:
        df = pd.read_sql(query, engine, params=params)
        df['date'] = pd.to_datetime(df['date'])
        df['total'] = df['age_0_5'] + df['age_5_17'] + df['age_18_greater']
        return df
    except Exception as e:
        print(f"Data fetch error: {e}")
        return pd.DataFrame()

def calculate_growth_rates(state=None, district=None, start_date=None, end_date=None):
    df = get_data(state, district, start_date, end_date)
    if df.empty: return {}
    
    results = {}
    period_map = {'Monthly_MoM': 'M', 'Quarterly_QoQ': 'Q', 'Yearly_YoY': 'A'}
    
    for label, rule in period_map.items():
        period_metrics = []
        try:
            resampled = df.set_index('date').resample(rule)[['age_0_5', 'age_5_17', 'age_18_greater']].sum()
            
            for col in ['age_0_5', 'age_5_17', 'age_18_greater']:
                resampled[f'{col}_pct'] = resampled[col].pct_change() * 100
                resampled[f'{col}_diff'] = resampled[col].diff()
                
                for date, row in resampled.iterrows():
                    if pd.notna(row[f'{col}_pct']):
                        period_metrics.append({
                            "date": date.strftime('%Y-%m-%d'),
                            "age_group": col,
                            "growth_rate_pct": int(round(row[f'{col}_pct'])),
                            "absolute_change": int(row[f'{col}_diff'] if pd.notna(row[f'{col}_diff']) else 0)
                        })
            results[label] = period_metrics
        except Exception:
            results[label] = [] # Handle cases with insufficient data for resampling
            
    return results

def logistic_model(t, L, k, t0):
    return L / (1 + np.exp(-k * (t - t0)))

def calculate_saturation_estimate(state, district):
    df = get_data(state=state, district=district)
    if df.empty: return {"error": "Insufficient data"}
    
    df_daily = df.set_index('date').resample('D')['total'].sum().fillna(0)
    cumulative_data = df_daily.cumsum()
    y_data = cumulative_data.values
    x_data = np.arange(len(y_data))
    
    try:
        p0 = [max(y_data) * 1.5, 0.01, len(x_data) / 2]
        popt, _ = curve_fit(logistic_model, x_data, y_data, p0=p0, bounds=([max(y_data), 0, -np.inf], [np.inf, 1, np.inf]), maxfev=5000)
        L, k, t0 = popt
        
        current_val = y_data[-1]
        penetration = (current_val / L) * 100 if L > 0 else 0
        
        target_time = t0 - (np.log(1/0.9 - 1) / k)
        remaining_days = target_time - len(x_data)
        months_to_90 = max(0, int(remaining_days / 30))
        
        return {
            "current_penetration": int(round(penetration)),
            "months_to_90_percent": months_to_90,
            "estimated_saturation_count": int(L)
        }
    except Exception as e:
        return {"error": "Cannot estimate saturation", "details": str(e)}
