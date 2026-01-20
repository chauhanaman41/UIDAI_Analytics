import os
from sqlalchemy import create_engine
from django.conf import settings

def get_engine():
    """
    Returns SQL Alchemy engine using Django settings.
    Useful for existing pandas scripts.
    """
    db_config = settings.DATABASES['default']
    
    # Construct URL manually or use env if direct
    # dj-database-url already verified it
    url = os.environ.get('DATABASE_URL')
    return create_engine(url)
