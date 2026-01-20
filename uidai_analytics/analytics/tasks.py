from celery import shared_task
from celery.utils.log import get_task_logger
import time
from .services import risk, forecasting, anomaly, enrollment
try:
    from .services import insights
except Exception:
    insights = None
from .services import policy
from .models import PolicyRecommendation
from django.core.cache import cache

logger = get_task_logger(__name__)

# Base Task Configuration
# Max retries: 3
# Delay between retries: 60s (default, can be exponential)

@shared_task(bind=True, max_retries=3)
def calculate_trends_task(self, state=None, district=None, date_range=None):
    """
    Calculates trends with progress updates.
    """
    logger.info(f"Starting trends calculation for {state}/{district}")
    try:
        # Simulate long running steps or hook into service if it supported callbacks
        # For now, we wrap the service call and simulate progress for the API requirements
        
        self.update_state(state='STARTED', meta={'current': 0, 'total': 100, 'status': 'Initializing'})
        
        # In a real heavy calculation, we'd chunk this. 
        # Since our service is pandas ops (fast for moderate data), we simulate stages.
        
        self.update_state(state='PROGRESS', meta={'current': 20, 'total': 100, 'status': 'Fetching Data'})
        # Start/End date handling (pass to service if it accepted them)
        # Using default service for now which accepts optional dates
        start_date = date_range[0] if date_range else None
        end_date = date_range[1] if date_range else None
        
        self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100, 'status': 'Processing Growth Rates'})
        results = enrollment.calculate_growth_rates(state, district, start_date, end_date)
        
        self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100, 'status': 'Finalizing'})
        
        logger.info("Trends calculation completed successfully")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating trends: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def generate_anomaly_report_task(self, params):
    """
    Generates anomaly report and stores in DB.
    """
    state = params.get('state')
    district = params.get('district')
    logger.info(f"Generating anomaly report for {state}")
    
    try:
        # Calls sync service which handles DB insertion internally
        anomaly.detect_anomalies_daily_sync() 
        logger.info("Anomaly report generated")
        return {"status": "success", "message": "Anomaly scan completed"}
        
    except Exception as e:
        logger.error(f"Anomaly generation failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def train_forecast_model_task(self, state):
    """
    Trains forecast model (retrains on full data) and returns results.
    """
    logger.info(f"Training forecast model for {state}")
    try:
        # Service logic trains and returns forecast
        result = forecasting.generate_forecast_sync(state)
        
        if "error" in result:
             raise ValueError(result['error'])
             
        logger.info("Forecasting completed")
        return result
        
    except Exception as e:
        logger.error(f"Forecasting failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task
def daily_anomaly_scan():
    """
    Scheduled task. Triggers anomaly report for all contexts (simplified).
    """
    logger.info("Starting daily anomaly scan")
    # Trigger the worker task
    generate_anomaly_report_task.delay({})
    
    # Also trigger risk model retraining
    train_risk_model_task.delay()

@shared_task(bind=True, max_retries=3)
def train_risk_model_task(self):
    """
    Retrains the risk prediction model.
    """
    logger.info("Retraining risk model")
    try:
        risk.train_model_logic()
        return {"status": "success", "message": "Risk model retrained"}
    except Exception as e:
        logger.error(f"Risk model training failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def generate_insights_task(self, metrics_data: dict):
    """
    Generates AI insights and caches them.
    """
    logger.info("Starting AI insights generation")
    try:
        if not insights:
            return {"error": "Insights module not available"}
        result = insights.generate_insights(metrics_data)
        
        # Cache for 24 hours
        cache.set("latest_insights", result, timeout=86400)
        
        return result
    except Exception as e:
        logger.error(f"Insights generation failed: {e}")
        self.retry(exc=e, countdown=60)


# Legacy aliases if needed
@shared_task(bind=True, max_retries=3)
def generate_weekly_policy_report(self):
    """
    Generates policy recommendations for problem districts.
    """
    logger.info("Generating weekly policy recommendations")
    try:
        # 1. Identify problem districts (Mock logic for MVP)
        # In production: Query Enrollment/Biometric models for low metrics
        problem_districts = [
            {
                "district": "Mewat",
                "state": "Haryana",
                "issues": ["Low biometric success (45%)", "High drop in enrollments"],
                "context": {"literacy": "Low", "infrastructure": "Rural"}
            },
            {
                "district": "Kopaganj",
                "state": "Uttar Pradesh", 
                "issues": ["Unusual spike in anomalies", "Delayed sync"],
                "context": {"literacy": "Medium", "infrastructure": "Semi-urban"}
            }
        ]
        
        # 2. Generate recommendations
        recommendations = policy.generate_policy_recommendations(problem_districts)
        
        # 3. Save to DB
        saved_count = 0
        for rec in recommendations:
            PolicyRecommendation.objects.create(
                district=rec['district'],
                state="Unknown", # API response might not have state if not asked, mimicking MVP
                issue_type="Combined Issues",
                recommendation=rec['recommendation'],
                rationale=rec['rationale'],
                impact_estimate=rec['impact_estimate'],
                priority=rec['priority']
            )
            saved_count += 1
            
        logger.info(f"Saved {saved_count} policy recommendations")
        return {"status": "success", "count": saved_count}
        
    except Exception as e:
        logger.error(f"Policy report generation failed: {e}")
        self.retry(exc=e, countdown=60)

