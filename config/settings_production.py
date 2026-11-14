"""
Production settings for Railway deployment.
"""
from .settings import *
import os
import dj_database_url

# ─── SECURITY ─────────────────────────────────────────────────────────────────
SECRET_KEY    = os.environ.get('SECRET_KEY', 'smarthr-fallback-secret-key-2026')
DEBUG         = False
ALLOWED_HOSTS = ['*']

# ─── DATABASE ─────────────────────────────────────────────────────────────────
database_url = os.environ.get('DATABASE_URL')
if database_url:
    DATABASES = {
        'default': dj_database_url.parse(database_url, conn_max_age=600)
    }

# ─── STATIC FILES ─────────────────────────────────────────────────────────────
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─── MEDIA ────────────────────────────────────────────────────────────────────
MEDIA_ROOT = BASE_DIR / 'media'

# ─── CSRF — allow Railway domain ──────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    'https://office-hrms-production.up.railway.app',
    'https://*.up.railway.app',
    'https://*.railway.app',
]

# ─── WEBAUTHN ─────────────────────────────────────────────────────────────────
WEBAUTHN_RP_ID   = os.environ.get('APP_DOMAIN', 'office-hrms-production.up.railway.app')
WEBAUTHN_RP_NAME = 'SmartHR Attendance'
WEBAUTHN_ORIGIN  = os.environ.get('APP_ORIGIN', 'https://office-hrms-production.up.railway.app')

# ─── GEOFENCE ─────────────────────────────────────────────────────────────────
OFFICE_LATITUDE               = float(os.environ.get('OFFICE_LAT', '10.0629'))
OFFICE_LONGITUDE              = float(os.environ.get('OFFICE_LON', '76.3479'))
OFFICE_GEOFENCE_RADIUS_METRES = int(os.environ.get('GEO_RADIUS', '300'))

# ─── LOGGING ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
