import redis
from django.conf import settings

def get_redis_client():
    """
    Returns a redis client configured from settings.
    """
    return redis.StrictRedis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
