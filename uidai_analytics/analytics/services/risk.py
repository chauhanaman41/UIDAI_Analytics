import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from utils.db_connector import get_engine

MODEL_PATH = "c:/Users/Amandeep/uidai20th/risk_model.pkl"
FEATURE_NAMES_PATH = "c:/Users/Amandeep/uidai20th/model_features.json"

def fetch_training_data():
    engine = get_engine()
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
    if df.empty: return df
    
    df['success_rate'] = np.where(df['enrollments'] > 0, 
                                 (df['biometric_attempts'] / df['enrollments']) * 100, 0)
    df['update_freq'] = np.where(df['enrollments'] > 0,
                                (df['demo_updates'] / df['enrollments']), 0)
    df['density'] = df['enrollments']
    
    df = df.sort_values(['state', 'district', 'month'])
    g = df.groupby(['state', 'district'])
    
    for win in [3, 6, 12]:
        df[f'roll_success_{win}m'] = g['success_rate'].transform(lambda x: x.rolling(win, min_periods=1).mean())
        df[f'roll_update_{win}m'] = g['update_freq'].transform(lambda x: x.rolling(win, min_periods=1).mean())
    
    df['growth_rate'] = g['enrollments'].transform(lambda x: x.pct_change().fillna(0))
    
    df['target_rate'] = g['success_rate'].shift(-3)
    df['is_high_risk'] = (df['target_rate'] < 60).astype(int)
    
    df_model = df.dropna(subset=['target_rate']).copy()
    return df_model

def train_model_logic(): # Renamed to avoid confusion with task
    print("Starting Model Training...")
    raw = fetch_training_data()
    if raw.empty or len(raw) < 50:
        print("Insufficient data for training.")
        return
        
    df = engineer_features(raw)
    
    feature_cols = [
        'success_rate', 'update_freq', 'density', 'growth_rate',
        'roll_success_3m', 'roll_success_6m', 'roll_success_12m',
        'roll_update_3m', 'roll_update_6m', 'roll_update_12m'
    ]
    
    X = df[feature_cols]
    y = df['is_high_risk']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    
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
            
    import json
    with open(FEATURE_NAMES_PATH, 'w') as f:
        json.dump(feature_cols, f)
        
    joblib.dump(best_model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH} with F1: {best_score:.4f}")

def engineer_features_inference(df):
    if df.empty: return df
    df['success_rate'] = np.where(df['enrollments'] > 0, (df['biometric_attempts'] / df['enrollments']) * 100, 0)
    df['update_freq'] = np.where(df['enrollments'] > 0, (df['demo_updates'] / df['enrollments']), 0)
    df['density'] = df['enrollments']
    df = df.sort_values('month')
    for win in [3, 6, 12]:
        df[f'roll_success_{win}m'] = df['success_rate'].rolling(win, min_periods=1).mean()
        df[f'roll_update_{win}m'] = df['update_freq'].rolling(win, min_periods=1).mean()
    df['growth_rate'] = df['enrollments'].pct_change().fillna(0)
    return df

def predict_risk_sync(state, district):
    if not os.path.exists(MODEL_PATH):
        return {"error": "Model not trained yet."}
        
    model = joblib.load(MODEL_PATH)
    import json
    with open(FEATURE_NAMES_PATH, 'r') as f:
        feature_cols = json.load(f)
    
    df = fetch_training_data()
    district_df = df[(df['state'] == state) & (df['district'] == district)].copy()
    
    if district_df.empty:
        return {"error": "No data for district"}
        
    df_feat = engineer_features_inference(district_df)
    latest = df_feat.iloc[[-1]][feature_cols]
    
    prob = model.predict_proba(latest)[0][1]
    
    if prob > 0.7: category = "High"
    elif prob > 0.4: category = "Medium"
    else: category = "Low"
    
    clf = model.named_steps['clf']
    importances = clf.feature_importances_
    imp_dict = dict(zip(feature_cols, importances))
    top_3 = sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)[:3]
    
    return {
        "district": district,
        "risk_score": round(prob, 2),
        "risk_category": category,
        "top_factors": [f[0] for f in top_3]
    }
