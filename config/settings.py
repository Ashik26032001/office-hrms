from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-hrms-qr-attendance-secret-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom apps
    'accounts',
    'employees',
    'attendance',
    'dashboard',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.CustomUser'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ─── OFFICE GEOFENCE SETTINGS ─────────────────────────────────────────────────
# Set your office GPS coordinates here.
# Go to maps.google.com → right-click your office → copy coordinates
OFFICE_LATITUDE  = 10.0261    # <-- replace with your office lat
OFFICE_LONGITUDE = 76.3083    # <-- replace with your office lon
OFFICE_GEOFENCE_RADIUS_METRES = 200   # allowed radius from office centre

# ─── FACE RECOGNITION SETTINGS ────────────────────────────────────────────────
FACE_RECOGNITION_ENABLED = True
FACE_RECOGNITION_MODEL    = 'VGG-Face'   # DeepFace model: VGG-Face, Facenet, ArcFace
FACE_RECOGNITION_DISTANCE = 'cosine'     # cosine | euclidean
FACE_RECOGNITION_THRESHOLD = 0.40        # lower = stricter match

# ─── WEBAUTHN / FINGERPRINT SETTINGS ──────────────────────────────────────────
WEBAUTHN_RP_ID   = '127.0.0.1'          # domain (change to yourdomain.com in prod)
WEBAUTHN_RP_NAME = 'SmartHR Attendance'
WEBAUTHN_ORIGIN  = 'http://127.0.0.1:8000'  # change to https://yourdomain.com in prod
