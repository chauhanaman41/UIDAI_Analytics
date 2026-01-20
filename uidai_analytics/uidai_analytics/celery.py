import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uidai_analytics.settings')

app = Celery('uidai_analytics')

# Configuration
app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'), # Use Redis for results too
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True, # Recommended
    worker_concurrency=4, # As requested
    task_track_started=True,
    task_time_limit=3600, # 1 hour max per task
)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Periodic Tasks Schedule
app.conf.beat_schedule = {
    'daily-anomaly-scan': {
        'task': 'analytics.tasks.daily_anomaly_scan',
        'schedule': crontab(hour=2, minute=0), # 2:00 AM IST
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
