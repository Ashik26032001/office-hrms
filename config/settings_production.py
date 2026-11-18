"""
Production settings for Railway deployment.
Extends base settings.py — only overrides what needs to change for production.
"""
from .settings import *
import os
import dj_database_url

# ─── SECURITY ─────────────────────────────────────────────────────────────────
SECRET_KEY    = os.environ.get('SECRET_KEY', 'smarthr-fallback-secret-key-change-me')
DEBUG         = False
ALLOWED_HOSTS = ['*']

# ─── DATABASE — PostgreSQL on Railway, SQLite fallback locally ────────────────
database_url = os.environ.get('DATABASE_URL')
if database_url:
    DATABASES = {
        'default': dj_database_url.parse(
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

# ─── STATIC FILES — WhiteNoise serves them directly ──────────────────────────
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─── CLOUDINARY — permanent storage for QR codes, photos, face images ─────────
# Set CLOUDINARY_URL in Railway environment variables:
#   cloudinary://API_KEY:API_SECRET@CLOUD_NAME
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')

if CLOUDINARY_URL:
    import cloudinary
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)

    # Add to installed apps if not already there
    if 'cloudinary_storage' not in INSTALLED_APPS:
        INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']

    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    MEDIA_URL = '/media/'
else:
    # Fallback — files stored locally (OK for local dev, lost on Railway redeploy)
    MEDIA_ROOT = BASE_DIR / 'media'
    MEDIA_URL  = '/media/'

# ─── CSRF TRUSTED ORIGINS ────────────────────────────────────────────────────
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
