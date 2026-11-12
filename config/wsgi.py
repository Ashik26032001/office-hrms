import os
from django.core.wsgi import get_wsgi_application

# Uses DJANGO_SETTINGS_MODULE env variable if set (Railway sets this)
# Falls back to development settings locally
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
