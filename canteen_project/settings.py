"""
Django settings for canteen_project.
"""

import os
from pathlib import Path
from decouple import config
import socket
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure logs folder exists
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

SECRET_KEY = config("SECRET_KEY", default="django-insecure-*nn=!r&0y_dr#*h)48s(fr$vc+8o28rrgm)=wxl*n-jq@km9km")
DEBUG = config("DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

LOCALE_PATHS = [
    BASE_DIR / 'locale',   # ✅ translations will be stored here
]

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', _('English')),
    ('fr', _('French')),
]

# --------------------
# Apps
# --------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "apps.authentication",
    "apps.menu",
    "apps.orders",
    "apps.payments",
    "apps.notifications",
    "apps.reports",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    'django.middleware.locale.LocaleMiddleware',
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "canteen_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "canteen_project.wsgi.application"
ASGI_APPLICATION = "canteen_project.asgi.application"

# --------------------
# Database
# --------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME", default="canteen_management"),
        "USER": config("DB_USER", default="codex"),
        "PASSWORD": config("DB_PASSWORD", default="codex"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# --------------------
# Authentication
# --------------------
AUTH_USER_MODEL = "authentication.User"

# --------------------
# Password validation
# --------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------
# Internationalization
# --------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --------------------
# Static & Media
# --------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------
# Django REST Framework
# --------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# --------------------
# Channels
# --------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    },
}

# --------------------
# Login URLs
# --------------------
LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/auth/login/"

# --------------------
# Email
# --------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@canteenoapi.com")

# --------------------
# Logging
# --------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["file", "console"], "level": "INFO", "propagate": True},
        "canteen": {"handlers": ["file", "console"], "level": "DEBUG", "propagate": True},
    },
}

# --------------------
# Security (production)
# --------------------
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"

# --------------------
# Canteen System Settings
# --------------------
CANTEEN_SETTINGS = {
    "MAX_DAILY_ORDER_AMOUNT": config("MAX_DAILY_ORDER_AMOUNT", default=50000, cast=int),
    "ORDER_CUTOFF_TIME": config("ORDER_CUTOFF_TIME", default="14:00"),
    "DELIVERY_TIMES": [
        ("12:00", "12:00 PM"),
        ("13:00", "1:00 PM"),
        ("14:00", "2:00 PM"),
    ],
    "PAYMENT_METHODS": [
        ("mtn", "MTN Mobile Money"),
        ("orange", "Orange Money"),
        ("wallet", "Wallet Balance"),
    ],
    "ORDER_STATUSES": [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ],
    "USER_ROLES": [
        ("employee", "Employee"),
        ("canteen_admin", "Canteen Admin"),
        ("system_admin", "System Admin"),
    ],
    "NOTIFICATION_TYPES": [
        ("order_status", "Order Status"),
        ("payment", "Payment"),
        ("system", "System"),
        ("announcement", "Announcement"),
    ],
}

# --------------------
# Mobile Money Configs
# --------------------
MTN_MOMO_CONFIG = {
    "API_URL": config("MTN_API_URL", default="https://sandbox.momodeveloper.mtn.com"),
    "API_KEY": config("MTN_API_KEY", default=""),
    "API_SECRET": config("MTN_API_SECRET", default=""),
    "SUBSCRIPTION_KEY": config("MTN_SUBSCRIPTION_KEY", default=""),
}

ORANGE_MONEY_CONFIG = {
    "API_URL": config("ORANGE_API_URL", default="https://api.orange.com/orange-money-webpay/dev/v1"),
    "CLIENT_ID": config("ORANGE_CLIENT_ID", default=""),
    "CLIENT_SECRET": config("ORANGE_CLIENT_SECRET", default=""),
    "MERCHANT_KEY": config("ORANGE_MERCHANT_KEY", default=""),
}

# Update settings.py to include CamPay config
CAMPAY_CONFIG = {
    "APP_USERNAME": config("CAMPAY_APP_USERNAME", default="cPe8puQuUfDJYZ7_SzAh4caSozD1tpd5Uf7H0BTqK1RovFJ_OtRKrIsfH-seXqdUIeVa6_5cW5mbyPTdHGw_BQ"),
    "APP_PASSWORD": config("CAMPAY_APP_PASSWORD", default="buTjmbRMb00xDK29FmHlax-10OdWJjRzT53max3P7Ih-aMoGXOjEFZqu2sv21hKuOJ3eh2HEOqEDfRwpSsZZVg"),
    "ENVIRONMENT": config("CAMPAY_ENVIRONMENT", default="DEV")  # or "PROD"
}

# --------------------
# Cache & Sessions
# --------------------
# Default: use DB sessions
SESSION_ENGINE = "django.contrib.sessions.backends.db"

def redis_running(host="127.0.0.1", port=6379):
    """Check if Redis server is running before using it."""
    try:
        s = socket.create_connection((host, port), timeout=1)
        s.close()
        return True
    except OSError:
        return False

if redis_running():
    # ✅ Use Redis if available
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
else:
    # 🚨 Fallback if Redis is not running
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
# ===============================
# Session and Security Settings
# ===============================

# Expire session when browser/app is closed
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Keep session alive max 24 hours if browser is not closed
SESSION_COOKIE_AGE = 86400  # 24 hours

# Refresh session expiry on every request
SESSION_SAVE_EVERY_REQUEST = True

# Extra security
SESSION_COOKIE_SECURE = True       # Use HTTPS only
SESSION_COOKIE_HTTPONLY = True     # Block JavaScript access
SESSION_COOKIE_SAMESITE = "Lax"    # Protect against CSRF (can be "Strict")


# --------------------
# CORS
# --------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True
