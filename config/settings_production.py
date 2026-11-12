"""
Production settings — used when deployed on Railway / Render / any server.
Inherits from base settings.py and overrides for production.
"""
from .settings import *
import os
import dj_database_url

# ─── SECURITY ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
DEBUG      = False
ALLOWED_HOSTS = ['*']  # Railway provides domain — tighten to your domain in prod

# ─── DATABASE ─────────────────────────────────────────────────────────────────
# Railway provides DATABASE_URL env variable automatically
database_url = os.environ.get('DATABASE_URL')
if database_url:
    DATABASES = {
        'default': dj_database_url.parse(database_url, conn_max_age=600)
    }

# ─── STATIC FILES (WhiteNoise serves them without a CDN) ──────────────────────
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─── MEDIA FILES ──────────────────────────────────────────────────────────────
# For production, ideally use Cloudinary or AWS S3.
# For free tier, media files stay on local disk (they reset on redeploy).
MEDIA_ROOT = BASE_DIR / 'media'

# ─── WEBAUTHN ─────────────────────────────────────────────────────────────────
WEBAUTHN_RP_ID     = os.environ.get('APP_DOMAIN', 'localhost')
WEBAUTHN_RP_NAME   = 'SmartHR Attendance'
WEBAUTHN_ORIGIN    = os.environ.get('APP_ORIGIN', 'https://localhost')

# ─── OFFICE GEOFENCE ──────────────────────────────────────────────────────────
# These are overridden by DB settings — kept as fallback
OFFICE_LATITUDE  = float(os.environ.get('OFFICE_LAT', '10.0629'))
OFFICE_LONGITUDE = float(os.environ.get('OFFICE_LON', '76.3479'))
OFFICE_GEOFENCE_RADIUS_METRES = int(os.environ.get('GEO_RADIUS', '300'))

# ─── CSRF ─────────────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
    'https://*.onrender.com',
]

# ─── LOGGING ──────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': { 'console': { 'class': 'logging.StreamHandler' } },
    'root': { 'handlers': ['console'], 'level': 'WARNING' },
}
