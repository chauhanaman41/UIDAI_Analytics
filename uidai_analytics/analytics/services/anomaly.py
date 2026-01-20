import pandas as pd
import numpy as np
from scipy import stats
from utils.db_connector import get_engine

def get_time_series_data(state=None, district=None, days=90):
    engine = get_engine()
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
    params['limit'] = days + 60
    
    try:
        df = pd.read_sql(query, engine, params=params)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        return df.set_index('date')
    except Exception as e:
        print(f"Data fetch error: {e}")
        return pd.DataFrame()

def z_score_anomalies(data_series, threshold=3):
    if len(data_series) < 3: return []
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
    if len(data_series) < 5: return []
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
    if len(data_series) < window: return []
    rolling_mean = data_series.rolling(window=window).mean()
    deviation_pct = np.abs((data_series - rolling_mean) / rolling_mean)
    anomalies = []
    valid_indices = deviation_pct.index[window:]
    for date in valid_indices:
        dev = deviation_pct.loc[date]
        if dev > 0.5:
            anomalies.append({
                "date": date,
                "value": float(data_series.loc[date]),
                "rolling_mean": float(rolling_mean.loc[date]),
                "deviation_pct": float(dev),
                "method": "rolling_deviation"
            })
    return anomalies

def comprehensive_anomaly_report(state=None, district=None, days=90):
    df = get_time_series_data(state, district, days)
    if df.empty or 'daily_enrollments' not in df.columns:
        return []
    series = df['daily_enrollments']
    
    z_anomalies = z_score_anomalies(series)
    iqr_anoms = iqr_outliers(series)
    roll_anoms = rolling_average_deviation(series)
    
    findings = {}
    def add_finding(date_key, entry):
        if date_key not in findings:
            findings[date_key] = {"date": entry['date'], "value": entry['value'], "methods": [], "details": {}}
        findings[date_key]['methods'].append(entry['method'])
        findings[date_key]['details'][entry['method']] = entry
        
    for a in z_anomalies: add_finding(a['date'], a)
    for a in iqr_anoms: add_finding(a['date'], a)
    for a in roll_anoms: add_finding(a['date'], a)
    
    validated_anomalies = []
    for date_key, f in findings.items():
        if len(f['methods']) >= 2:
            val = f['value']
            is_spike = True
            if 'rolling_deviation' in f['details']:
                if val < f['details']['rolling_deviation']['rolling_mean']: is_spike = False
            else:
                if val < series.mean(): is_spike = False
            anom_type = 'spike' if is_spike else 'drop'
            severity = 5.0
            if 'z_score' in f['details']:
                z = f['details']['z_score']['z_score']
                severity = min(10.0, z)
            
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

def detect_anomalies_daily_sync():
    engine = get_engine()
    try:
        districts_df = pd.read_sql("SELECT DISTINCT state, district FROM enrollments LIMIT 10", engine)
        all_alerts = []
        for _, row in districts_df.iterrows():
            alerts = comprehensive_anomaly_report(state=row['state'], district=row['district'])
            all_alerts.extend(alerts)
        if all_alerts:
            alerts_df = pd.DataFrame(all_alerts)
            alerts_df.to_sql('anomaly_alerts', engine, if_exists='append', index=False, method='multi')
            print(f"Inserted {len(alerts_df)} alerts.")
    except Exception as e:
        print(f"Error in detection: {e}")
