import pandas as pd
import numpy as np
import os
import joblib
from sqlalchemy import create_engine
from celery import Celery
from dotenv import load_dotenv

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://user:pass@localhost/db"
    
engine = create_engine(DATABASE_URL)
app = Celery('risk_prediction', broker=os.getenv("REDIS_URL", 'redis://localhost:6379/0'))

MODEL_PATH = "c:/Users/Amandeep/uidai20th/risk_model.pkl"
FEATURE_NAMES_PATH = "c:/Users/Amandeep/uidai20th/model_features.json"

def fetch_training_data():
    """
    Joins Enrollment, Biometric, and Demographic tables aggregated by Month/District.
    """
    query = """
    SELECT 
        DATE_TRUNC('month', e.date) as month,
        e.state,
        e.district,
        SUM(e.age_5_17 + e.age_18_greater) as enrollments,
        SUM(b.bio_age_5_17 + b.bio_age_17_) as biometric_attempts,
        SUM(d.demo_age_5_17 + d.demo_age_17_) as demo_updates
    FROM enrollments e
    LEFT JOIN biometric_attempts b 
        ON e.date = b.date AND e.state = b.state AND e.district = b.district
    LEFT JOIN demographic_updates d
        ON e.date = d.date AND e.state = d.state AND e.district = d.district
    GROUP BY 1, 2, 3
    ORDER BY 1
    """
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        print(f"Data fetch error: {e}")
        return pd.DataFrame()

def engineer_features(df):
    """
    Creates rolling window features and targets.
    """
    if df.empty: return df
    
    # 1. Base Rates
    # Success Rate (Biometric / Enrollment). Avoid div by zero.
    df['success_rate'] = np.where(df['enrollments'] > 0, 
                                 (df['biometric_attempts'] / df['enrollments']) * 100, 0)
    
    # Demo Update Freq
    df['update_freq'] = np.where(df['enrollments'] > 0,
                                (df['demo_updates'] / df['enrollments']), 0)
                                
    # Enrollment Density (Proxy: Count)
    df['density'] = df['enrollments']
    
    # 2. Rolling Features (Sort first)
    df = df.sort_values(['state', 'district', 'month'])
    
    # Group by district for windows
    g = df.groupby(['state', 'district'])
    
    for win in [3, 6, 12]:
        # Rolling Success Rate
        df[f'roll_success_{win}m'] = g['success_rate'].transform(lambda x: x.rolling(win, min_periods=1).mean())
        # Rolling Update Freq
        df[f'roll_update_{win}m'] = g['update_freq'].transform(lambda x: x.rolling(win, min_periods=1).mean())
    
    # Growth Rate (Monthly)
    df['growth_rate'] = g['enrollments'].transform(lambda x: x.pct_change().fillna(0))
    
    # 3. Target Variable
    # Predict if success_rate < 60% in Next Quarter (3 months later)
    # We shift 'success_rate' backwards by 3.
    df['target_rate'] = g['success_rate'].shift(-3)
    df['is_high_risk'] = (df['target_rate'] < 60).astype(int)
    
    # Drop rows where target is NaN (last 3 months)
    df_model = df.dropna(subset=['target_rate']).copy()
    
    return df_model

@app.task
def train_model():
    """
    Retrains the risk model.
    """
    print("Starting Model Training...")
    raw = fetch_training_data()
    if raw.empty or len(raw) < 50:
        print("Insufficient data for training.")
        return
        
    df = engineer_features(raw)
    
    # Features
    feature_cols = [
        'success_rate', 'update_freq', 'density', 'growth_rate',
        'roll_success_3m', 'roll_success_6m', 'roll_success_12m',
        'roll_update_3m', 'roll_update_6m', 'roll_update_12m'
    ]
    
    X = df[feature_cols]
    y = df['is_high_risk']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    
    # Models to Try
    models = {
        'RF': RandomForestClassifier(random_state=42),
        'GBM': GradientBoostingClassifier(random_state=42)
    }
    
    best_score = 0
    best_model = None
    
    for name, model in models.items():
        pipeline = Pipeline([
            ('imputer', SimpleImputer(strategy='mean')),
            ('scaler', StandardScaler()),
            ('clf', model)
        ])
        
        # Simple Grid Search
        param_grid = {}
        if name == 'RF':
            param_grid = {'clf__n_estimators': [50, 100], 'clf__max_depth': [5, 10]}
        else:
            param_grid = {'clf__n_estimators': [50, 100], 'clf__learning_rate': [0.05, 0.1]}
            
        cv = GridSearchCV(pipeline, param_grid, cv=3, scoring='f1')
        cv.fit(X_train, y_train)
        
        score = cv.best_score_
        print(f"{name} F1 Score: {score:.4f}")
        
        if score >= best_score:
            best_score = score
            best_model = cv.best_estimator_
            
    # Save Feature Names (hacky but useful for consistency)
    import json
    with open(FEATURE_NAMES_PATH, 'w') as f:
        json.dump(feature_cols, f)
        
    # Save Model
    joblib.dump(best_model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH} with F1: {best_score:.4f}")

def predict_risk(state, district):
    """
    Predicts risk for a specific district based on latest data.
    """
    if not os.path.exists(MODEL_PATH):
        return {"error": "Model not trained yet."}
        
    # Load Model & Features
    model = joblib.load(MODEL_PATH)
    import json
    with open(FEATURE_NAMES_PATH, 'r') as f:
        feature_cols = json.load(f)
    
    # Get Data
    df = fetch_training_data()
    # Filter for district history
    district_df = df[(df['state'] == state) & (df['district'] == district)].copy()
    
    if district_df.empty:
        return {"error": "No data for district"}
        
    # Engineer (This will create features for the last row)
    # Note: engineer_features drops last 3 months usually for training TARGET.
    # But here we want features for the LATEST month to predict FUTURE risk.
    # So we need a version of engineering that DOES NOT drop NaN targets.
    
    # Re-use logic but don't drop target
    df_feat = engineer_features_inference(district_df)
    
    # Get latest row
    latest = df_feat.iloc[[-1]][feature_cols]
    
    # Impute missing if any (using pipeline inside model handles, but need DataFrame match)
    # The pipeline has Imputer.
    
    # Predict
    prob = model.predict_proba(latest)[0][1] # Prob of Class 1 (High Risk)
    
    # Category
    if prob > 0.7: category = "High"
    elif prob > 0.4: category = "Medium"
    else: category = "Low"
    
    # Explanation (Feature Importances)
    # Get feature importances from the classifier step
    clf = model.named_steps['clf']
    importances = clf.feature_importances_
    
    # Map features to importance
    imp_dict = dict(zip(feature_cols, importances))
    top_3 = sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        "district": district,
        "risk_score": round(prob, 2),
        "risk_category": category,
        "top_factors": [f[0] for f in top_3]
    }

def engineer_features_inference(df):
    """Helper to generate features without dropping target-less rows."""
    # ... Copy paste feature logic or refactor. 
    # For conciseness, let's copy the Transformation logic.
    if df.empty: return df
    
    df['success_rate'] = np.where(df['enrollments'] > 0, (df['biometric_attempts'] / df['enrollments']) * 100, 0)
    df['update_freq'] = np.where(df['enrollments'] > 0, (df['demo_updates'] / df['enrollments']), 0)
    df['density'] = df['enrollments']
    
    # Rolling (Must serve single district generally, so no groupBy needed if caller filters, but let's keep it safe)
    # But rolling requires history.
    df = df.sort_values('month')
    
    for win in [3, 6, 12]:
        df[f'roll_success_{win}m'] = df['success_rate'].rolling(win, min_periods=1).mean()
        df[f'roll_update_{win}m'] = df['update_freq'].rolling(win, min_periods=1).mean()
        
    df['growth_rate'] = df['enrollments'].pct_change().fillna(0)
    
    return df

if __name__ == "__main__":
    pass
