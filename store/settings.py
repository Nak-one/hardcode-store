"""
Django settings for store project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

AUTH_USER_MODEL = "users.User"
LOGIN_URL = "/account/login/"
LOGIN_REDIRECT_URL = "/catalog/"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

_allowed = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]
if not any('hardcode' in h for h in ALLOWED_HOSTS):
    ALLOWED_HOSTS.extend(['hardcode-it.store', 'www.hardcode-it.store', 'hardcode-it.ru', 'www.hardcode-it.ru'])

CSRF_TRUSTED_ORIGINS = [
    'https://hardcode-it.store',
    'https://www.hardcode-it.store',
    'https://hardcode-it.ru',
    'https://www.hardcode-it.ru',
]

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "mptt",
    "django.contrib.admin",
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'catalog',
    'users',
    'orders',
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

ROOT_URLCONF = 'store.urls'

# Сессия — принудительное сохранение при изменении (для корзины)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1209600

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'catalog.context_processors.cart_count',
                'catalog.context_processors.favorites_count',
                'catalog.context_processors.nav_categories',
                'catalog.context_processors.hide_hero_nav',
            ],
        },
    },
]

WSGI_APPLICATION = 'store.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'hardcode_store'),
        'USER': os.environ.get('DB_USER', 'hardcode_store_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# API ключ для эндпоинтов /api/order-sync/ и /api/orders/<uuid>/
# Если задан — запросы без заголовка X-API-Key с этим значением получат 401
ORDER_SYNC_API_KEY = os.environ.get('ORDER_SYNC_API_KEY', '').strip() or None

# API ключ для эндпоинтов /api/user-sync/ и /api/users/<uuid>/
USER_SYNC_API_KEY = os.environ.get('USER_SYNC_API_KEY', '').strip() or None

# СДЭК API v2 (доставка): учётные данные запросить у integrator@cdek.ru
CDEK_ACCOUNT = os.environ.get('CDEK_ACCOUNT', '').strip() or None
CDEK_SECURE = os.environ.get('CDEK_SECURE', '').strip() or None
CDEK_TEST = os.environ.get('CDEK_TEST', 'False').lower() in ('true', '1', 'yes')
CDEK_BASE_URL = os.environ.get('CDEK_BASE_URL', '').strip() or None  # пусто = авто (тест/прод)
# Код города отправителя для калькулятора СДЭК (например Москва = 44)
CDEK_SENDER_CITY_CODE = os.environ.get('CDEK_SENDER_CITY_CODE', '').strip() or None
# Только локальный список городов (без API СДЭК) — при таймаутах API
CDEK_CITIES_FALLBACK_ONLY = os.environ.get('CDEK_CITIES_FALLBACK_ONLY', 'True').lower() in ('true', '1', 'yes')
if CDEK_SENDER_CITY_CODE is not None:
    try:
        CDEK_SENDER_CITY_CODE = int(CDEK_SENDER_CITY_CODE)
    except ValueError:
        CDEK_SENDER_CITY_CODE = None

# 5post API (доставка X5): api-key → JWT, тариф по зонам, ПВЗ через /api/v1/pickuppoints/query
FIVEPOST_API_KEY = os.environ.get('FIVEPOST_API_KEY', '').strip() or None
FIVEPOST_API_URL = os.environ.get('FIVEPOST_API_URL', '').strip() or None  # пусто = авто (test/prod)
FIVEPOST_TEST = os.environ.get('FIVEPOST_TEST', 'False').lower() in ('true', '1', 'yes')
# Маппинг город → тарифная зона. Из .env: FIVEPOST_CITY_ZONE='{"Москва":1,"Санкт-Петербург":2,"__default__":1}'
_FIVEPOST_ZONE_RAW = os.environ.get('FIVEPOST_CITY_ZONE', '').strip()
FIVEPOST_CITY_ZONE = {}
if _FIVEPOST_ZONE_RAW:
    try:
        import json as _json
        FIVEPOST_CITY_ZONE = _json.loads(_FIVEPOST_ZONE_RAW)
    except Exception:
        pass

# Почта России (tariff.pochta.ru): индекс отправителя для расчёта тарифа
RUSSIANPOST_SENDER_INDEX = os.environ.get('RUSSIANPOST_SENDER_INDEX', '').strip() or None
if RUSSIANPOST_SENDER_INDEX is not None:
    try:
        RUSSIANPOST_SENDER_INDEX = int(RUSSIANPOST_SENDER_INDEX)
        if not (100000 <= RUSSIANPOST_SENDER_INDEX <= 999999):
            RUSSIANPOST_SENDER_INDEX = None
    except ValueError:
        RUSSIANPOST_SENDER_INDEX = None
RUSSIANPOST_OBJECT = int(os.environ.get('RUSSIANPOST_OBJECT', '4040'))  # 4040 = посылка с ОЦ и наложенным
RUSSIANPOST_TARIFF_URL = os.environ.get('RUSSIANPOST_TARIFF_URL', '').strip() or None

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images) — с / для абсолютных путей (иначе 404 на /backend/)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media (uploaded files, e.g. product images)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Логирование корзины — файл для отладки товаров с вариантами
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "cart": {
            "format": "%(asctime)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "cart_file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "logs" / "cart.log"),
            "formatter": "cart",
        },
    },
    "loggers": {
        "catalog.cart": {
            "handlers": ["cart_file"],
            "level": "INFO",
        },
    },
}

# Unfold Admin — тёмная тема, sidebar (по ADMIN_DESIGN.md)
UNFOLD = {
    "SITE_TITLE": "Hardcode Store",
    "SITE_HEADER": "Админка",
    "THEME": "dark",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Основное",
                "separator": True,
                "items": [
                    {"title": "Обзор", "link": "/backend/", "icon": "dashboard"},
                    {"title": "Товары", "link": "/backend/catalog/product/", "icon": "inventory_2"},
                ],
            },
            {
                "title": "Пользователи",
                "separator": True,
                "items": [
                    {"title": "Пользователи", "link": "/backend/users/user/", "icon": "person"},
                    {"title": "Очередь выгрузки", "link": "/backend/users/usersyncqueue/", "icon": "sync"},
                ],
            },
            {
                "title": "Заказы",
                "separator": True,
                "items": [
                    {"title": "Заказы покупателей", "link": "/backend/orders/order/", "icon": "shopping_cart"},
                    {"title": "Очередь выгрузки заказов", "link": "/backend/orders/ordersyncqueue/", "icon": "sync"},
                    {"title": "Способы доставки", "link": "/backend/orders/deliverymethod/", "icon": "local_shipping"},
                ],
            },
            {
                "title": "Справочники",
                "collapsible": True,
                "items": [
                    {"title": "Категории", "link": "/backend/catalog/category/", "icon": "category"},
                    {"title": "Бренды", "link": "/backend/catalog/brand/", "icon": "label"},
                    {"title": "Атрибуты", "link": "/backend/catalog/productattribute/", "icon": "tune"},
                ],
            },
            {
                "title": "Команды",
                "separator": True,
                "items": [
                    {"title": "Добавить товар", "link": "/backend/catalog/product/add/", "icon": "add_circle"},
                    {"title": "Добавить категорию", "link": "/backend/catalog/category/add/", "icon": "add"},
                    {"title": "Добавить бренд", "link": "/backend/catalog/brand/add/", "icon": "add"},
                ],
            },
        ],
    },
}
