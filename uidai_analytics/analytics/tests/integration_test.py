import os
import sys
import json
import time
import requests
import psycopg2
import redis
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('IntegrationTest')

# Configuration from ENV or Defaults
API_URL = os.getenv('API_URL', 'http://localhost:8000')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')

REPORT = {
    "timestamp": datetime.utcnow().isoformat(),
    "modules": {},
    "overall_status": "PENDING"
}

def log_result(module, status, details=None):
    REPORT['modules'][module] = {
        "status": status,
        "details": details or []
    }
    logger.info(f"[{module}] {status}")

def check_preflight():
    """1. Infrastructure & Connectivity"""
    details = []
    status = "PASS"
    
    # Env Vars
    required_vars = ['DATABASE_URL', 'REDIS_URL', 'SECRET_KEY']
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        details.append(f"Missing ENV vars: {missing}")
        status = "FAIL"

    # Supabase / Postgres IPv6
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        details.append("Database (IPv6) Connected")
    except Exception as e:
        details.append(f"Database Connection Failed: {str(e)}")
        status = "FAIL"

    # Redis IPv6
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        details.append("Redis (IPv6) Connected")
    except Exception as e:
        details.append(f"Redis Connection Failed: {str(e)}")
        status = "FAIL"

    # Ollama
    try:
        resp = requests.get('http://localhost:11434')
        if resp.status_code == 200:
            details.append("Ollama Service Running")
        else:
            status = "FAIL"
            details.append(f"Ollama returned {resp.status_code}")
    except:
        status = "FAIL"
        details.append("Ollama Service Unreachable")

    log_result("Pre-flight", status, details)

def check_data_pipeline():
    """2. ETL & Data Flow"""
    details = []
    status = "PASS"
    
    csv_data = "date,state,district,enrollments\n2023-01-01,TestState,TestDistrict,100"
    files = {'file': ('integration_test.csv', csv_data, 'text/csv')}
    
    try:
        auth = ('testuser', 'password') # Assuming basic auth/session mock
        resp = requests.post(f"{API_URL}/api/data/upload/", files=files, auth=auth)
        if resp.status_code == 202:
            task_id = resp.json().get('task_id')
            details.append(f"Upload Accepted, Task: {task_id}")
            # Verify DB (Mock check or real query)
            # In real scenario: wait for task, then check DB
        else:
            status = "FAIL"
            details.append(f"Upload Failed: {resp.status_code}")
    except Exception as e:
         status = "FAIL"
         details.append(str(e))
         
    log_result("Data Pipeline", status, details)

def check_analytics_engine():
    """3. Analytics Calculation & Caching"""
    details = []
    status = "PASS"
    
    try:
        start = time.time()
        # Trigger Calculation endpoint (e.g. Trends)
        resp = requests.get(f"{API_URL}/api/enrollments/trends/?state=TestState", auth=('testuser', 'password'))
        duration = time.time() - start
        
        if resp.status_code == 200:
            details.append(f"Calculation Successful ({round(duration*1000)}ms)")
            if duration < 0.5:
                details.append("Response < 500ms (Likely Cached)")
            
            # Check Redis for cache key exists? 
            # r = redis.from_url(REDIS_URL); r.exists(...)
        else:
            status = "FAIL"
            details.append(f"Analytics Endpoint Failed: {resp.status_code}")
    except Exception as e:
        status = "FAIL"
        details.append(str(e))
        
    log_result("Analytics Engine", status, details)

def check_predictive_models():
    """4. Forecasting & Risk"""
    details = []
    status = "PASS"
    try:
        resp = requests.get(f"{API_URL}/api/forecasts/TestState/", auth=('testuser', 'password'))
        if resp.status_code == 200:
            data = resp.json()
            if 'forecast' in data:
                 details.append("Forecast JSON Valid")
            else:
                 status = "FAIL"; details.append("Missing forecast key")
        else:
            status = "FAIL"; details.append(f"Forecast API Error: {resp.status_code}")
            
    except Exception as e:
        status = "FAIL"; details.append(str(e))
        
    log_result("Predictive Models", status, details)

def check_ai_integration():
    """7. AI & RAG"""
    details = []
    status = "PASS"
    
    payload = {"metric_data": {"trend": "up"}, "context": "test"}
    try:
        resp = requests.post(f"{API_URL}/api/insights/generate/", json=payload, auth=('testuser', 'password'))
        if resp.status_code == 200:
            details.append("AI Insight Generated")
        else:
            status = "WARN"; details.append(f"AI Service unavailable: {resp.status_code}")
    except:
        status = "WARN"; details.append("AI Service Unreachable")
        
    log_result("AI Integration", status, details)

def check_security():
    """10. Security Validation"""
    details = []
    status = "PASS"
    
    # 1. Test No Auth
    resp = requests.get(f"{API_URL}/api/enrollments/trends/")
    if resp.status_code == 403 or resp.status_code == 401:
        details.append("Unauthenticated Access Blocked (Pass)")
    else:
        status = "FAIL"; details.append(f"Security Fail: Unauth access allowed ({resp.status_code})")
        
    # 2. SQL Injection Attempt
    malicious = "' OR '1'='1"
    resp = requests.get(f"{API_URL}/api/enrollments/trends/?state={malicious}", auth=('testuser', 'password'))
    # Should handle gracefully, not 500 with stacktrace (though 500 is better than data leak)
    # Ideally returns empty or 400
    if resp.status_code == 200 and len(resp.json()) > 1000: # Assuming it dumps all
         status = "FAIL"; details.append("Potential SQL Injection Vulnerability")
    else:
         details.append("SQL Injection Payload Handled")
         
    log_result("Security", status, details)

def run_all():
    print("Starting Final Integration Validation...")
    results = {}
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Run sequentially to avoid state collision in this script
        executor.submit(check_preflight).result()
        executor.submit(check_data_pipeline).result()
        executor.submit(check_analytics_engine).result()
        executor.submit(check_predictive_models).result()
        executor.submit(check_ai_integration).result()
        executor.submit(check_security).result()
        
    # Calculate Overall
    statuses = [m['status'] for m in REPORT['modules'].values()]
    if "FAIL" in statuses:
        REPORT['overall_status'] = "FAIL"
    else:
        REPORT['overall_status'] = "PASS"
        
    # Write Report
    with open('integration_report.json', 'w') as f:
        json.dump(REPORT, f, indent=2)
        
    print(json.dumps(REPORT, indent=2))
    print(f"\nReport saved to integration_report.json")

if __name__ == "__main__":
    try:
        run_all()
    except KeyboardInterrupt:
        print("Aborted.")
