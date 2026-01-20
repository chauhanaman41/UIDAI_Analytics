import pandas as pd
import numpy as np
import os
import json
from celery import Celery
from sqlalchemy import create_engine
from dotenv import load_dotenv

from dateutil.relativedelta import relativedelta
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

load_dotenv()

# Database Connection
DATABASE_URL = os.getenv("DATABASE_URL")
# Fallback for testing
if not DATABASE_URL:
    DATABASE_URL = "postgresql://user:pass@localhost/db"
    
engine = create_engine(DATABASE_URL)

# Celery Setup
app = Celery('forecasting', broker=os.getenv("REDIS_URL", 'redis://localhost:6379/0'))

def get_monthly_data(state=None):
    """Fetches and aggregates data to monthly level."""
    query = """
        SELECT date as ds, 
               (age_0_5 + age_5_17 + age_18_greater) as y
        FROM enrollments
        WHERE 1=1
    """
    params = {}
    if state:
        query += " AND state = %(state)s"
        params['state'] = state
        
    query += " ORDER BY ds"
    
    try:
        df = pd.read_sql(query, engine, params=params)
        df['ds'] = pd.to_datetime(df['ds'])
        
        # Aggregate to monthly (Group by first, to avoid filling 0s via resample)
        df['month_start'] = df['ds'].dt.to_period('M').dt.to_timestamp()
        df_monthly = df.groupby('month_start')['y'].sum().reset_index().rename(columns={'month_start': 'ds'})
        
        # Interpolate missing months
        # Create full range
        if df_monthly.empty:
            return pd.DataFrame()
            
        min_date = df_monthly['ds'].min()
        max_date = df_monthly['ds'].max()
        idx = pd.date_range(min_date, max_date, freq='MS')
        
        # Merge with full range to introduce NaNs
        full_df = pd.DataFrame({'ds': idx})
        df_monthly = pd.merge(full_df, df_monthly, on='ds', how='left')
        
        df_monthly['y'] = df_monthly['y'].interpolate(method='linear')
        
        # Ensure 'y' is not negative and fills NaNs at edges
        df_monthly['y'] = df_monthly['y'].fillna(0)
        
        return df_monthly
        
    except Exception as e:
        print(f"Data fetch error: {e}")
        return pd.DataFrame()

def train_arima(train_series, steps=6):
    """
    Trains ARIMA and forecasts.
    """
    try:
        from pmdarima import auto_arima
        
        # Fit auto_arima
        model = auto_arima(train_series, seasonal=False, trace=False, error_action='ignore', suppress_warnings=True)
        
        # Forecast
        forecast, conf_int = model.predict(n_periods=steps, return_conf_int=True)
        
        return forecast, conf_int, model
    except Exception as e:
        print(f"ARIMA error: {e}")
        return None, None, None

def train_prophet(train_df, steps=6):
    """
    Trains Prophet and forecasts.
    train_df must have 'ds', 'y'.
    """
    try:
        from prophet import Prophet
        
        # Initialize
        m = Prophet(yearly_seasonality=True, daily_seasonality=False, weekly_seasonality=False)
        m.add_country_holidays(country_name='IN') # Indian holidays
        
        m.fit(train_df)
        
        future = m.make_future_dataframe(periods=steps, freq='MS')
        forecast = m.predict(future)
        
        # Return only future part
        return forecast.tail(steps)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']], m
        
    except Exception as e:
        print(f"Prophet error: {e}")
        return None, None

@app.task(bind=True)
def generate_forecast(self, state=None):
    """
    Generates forecast for a state.
    """
    df = get_monthly_data(state)
    
    if len(df) < 12:
        return {"error": "Insufficient data (need at least 12 months)"}
    
    # Split Train/Test (Last 3 months for validation)
    test_size = 3
    train = df.iloc[:-test_size]
    test = df.iloc[-test_size:]
    
    # --- Evaluation ---
    
    # 1. ARIMA Eval
    arima_mape = float('inf')
    try:
        f_arima, _, _ = train_arima(train['y'], steps=test_size)
        if f_arima is not None:
             # Manual MAPE: mean(|(y_true - y_pred) / y_true|)
             y_true = test['y'].values
             y_pred = f_arima
             arima_mape = np.mean(np.abs((y_true - y_pred) / y_true))
    except: pass
    
    # 2. Prophet Eval
    prophet_mape = float('inf')
    try:
        f_prophet_df, _ = train_prophet(train, steps=test_size)
        if f_prophet_df is not None:
            y_true = test['y'].values
            y_pred = f_prophet_df['yhat'].values
            prophet_mape = np.mean(np.abs((y_true - y_pred) / y_true))
    except: pass
    
    # --- Selection & Final Forecast ---
    steps = 6
    best_model = "Prophet" if prophet_mape < arima_mape else "ARIMA"
    final_mape = min(prophet_mape, arima_mape)
    
    forecast_results = []
    
    if best_model == "Prophet":
        # Retrain on full data
        preds, _ = train_prophet(df, steps=steps)
        if preds is not None:
            for _, row in preds.iterrows():
                forecast_results.append({
                    "month": row['ds'].strftime('%Y-%m'),
                    "predicted": int(row['yhat']),
                    "lower": int(row['yhat_lower']),
                    "upper": int(row['yhat_upper'])
                })
    else:
        # ARIMA Retrain
        f_arima, conf, _ = train_arima(df['y'], steps=steps)
        if f_arima is not None:
             # Create dates
            last_date = df['ds'].max()
            future_dates = [last_date + relativedelta(months=i+1) for i in range(steps)]
            
            for i, date in enumerate(future_dates):
                forecast_results.append({
                    "month": date.strftime('%Y-%m'),
                    "predicted": int(f_arima[i]),
                    "lower": int(conf[i][0]),
                    "upper": int(conf[i][1])
                })
    
    # If both failed
    if not forecast_results:
        return {"error": "Model training failed"}
        
    return {
        "state": state if state else "All India",
        "forecast": forecast_results,
        "model_used": best_model,
        "mape": round(final_mape * 100, 2) # Percent
    }

if __name__ == "__main__":
    pass
