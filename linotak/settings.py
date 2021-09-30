"""
Django settings for linotak project.

Generated by 'django-admin startproject' using Django 2.1.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

I’m using environment variables for config: see
https://alleged.org.uk/pdc/2018/07/07.html

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import sys

import environ


env = environ.Env(
    DEBUG=(bool, False),
    STATIC_ROOT=(str, None),
    STATIC_URL=(str, None),
    CELERY_BROKER_URL=(str, 'pyamqp://localhost/'),
    NOTES_FETCH_LOCATORS=(bool, False),
    NOTES_DOMAIN=(str, None),
    NOTES_DOMAIN_INSECURE=(bool, False),
    IMAGES_FETCH_DATA=(bool, False),
    MENTIONS_POST_NOTIFICATIONS=(bool, False),
    MASTODON_POST_STATUSES=(bool, False),
    LOGGING=(str, None),
    LOG_LEVEL=(str, 'WARNING'),
)
environ.Env.read_env()


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# Used to avoid making network requests from tests.
TEST = 'test' in sys.argv

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'secret-key-value' if DEBUG else env('SECRET_KEY')

ALLOWED_HOSTS = [
    'localhost',
    'mustardseed.local',
    'ooble.uk',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'customuser.apps.CustomuserConfig',
    'linotak.notes.apps.NotesConfig',
    'linotak.images.apps.ImagesConfig',
    'linotak.about.apps.AboutConfig',
    'linotak.mentions.apps.MentionsConfig',
    'linotak.mastodon.apps.MastodonConfig',
]

MIDDLEWARE = [
    'linotak.notes.middleware.SubdomainSeriesMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'linotak.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'linotak.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': env.db(default='sqlite:///%s' % os.path.join(BASE_DIR, 'db.sqlite3')),
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

AUTH_USER_MODEL = 'customuser.Login'

LOGOUT_REDIRECT_URL = '/'


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-GB'

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

TIME_ZONE = 'Europe/London'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

if env('STATIC_ROOT'):
    STATIC_URL = env('STATIC_URL', default='https//static.linotak.org.uk/')
    STATIC_ROOT = env('STATIC_ROOT')  # e.g., '/home/linotak/static')
    if not DEBUG:
        STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
else:
    STATIC_URL = '/static/'


if env('MEDIA_ROOT'):
    # Uploaded and generated files are saved to local disk.
    MEDIA_ROOT = env('MEDIA_ROOT')

if DEBUG and env('MEDIA_ROOT'):
    # Uploaded files are served from local disk.
    MEDIA_URL = '/media/'
else:
    MEDIA_URL = env('MEDIA_URL')

# Suppress Celery dispatch during tests.
CELERY_BROKER_URL = not TEST and env('CELERY_BROKER_URL')


# Whether we fetch pages for subjects when they are added to the database.
# Suppressed during most tests to avoid network traffic during testing.
NOTES_FETCH_LOCATORS = not TEST and env('NOTES_FETCH_LOCATORS')

# Whether we downloaad images to ascertain their dimensions and create thumbnails.
IMAGES_FETCH_DATA = not TEST and env('IMAGES_FETCH_DATA')

# Whether we contact WebMention endpoints of pages we mention in notes.
MENTIONS_POST_NOTIFICATIONS = not TEST and env('MENTIONS_POST_NOTIFICATIONS')

# Common parent domain to all series. Series domain is $SERIES_NAMAE.$NOTES_DOMAIN.
NOTES_DOMAIN = env('NOTES_DOMAIN')
if NOTES_DOMAIN:
    ALLOWED_HOSTS.append('.' + NOTES_DOMAIN.split(':', 1)[0])

# Whether to use `http` instead of `https` in series & note URLs.
# NOT used in production: only used for the development web site.
NOTES_DOMAIN_INSECURE = not TEST and env('NOTES_DOMAIN_INSECURE')

# Whether to post statuses to Mastodon.
MASTODON_POST_STATUSES = not TEST and env('MASTODON_POST_STATUSES')


# LOGGING if defined contains JSON-encoded logging configuration
# LOG_LEVEL if defined specifies a logging level (WARNMING,. IONFO< DENUIG)
LOGGING = env('LOGGING')
if LOGGING:
    import json

    LOGGING = json.loads(LOGGING)
else:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': env('LOG_LEVEL'),
        },
    }
