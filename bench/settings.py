"""
Django settings of both profiles; ``BENCH_PROFILE`` selects one.

``drf`` is Django REST framework with its default configuration: no
``REST_FRAMEWORK`` setting at all. ``fastdrf`` adds the ``FASTDRF`` setting,
which only fastdrf's serializer bases read, and the ``fastdrf`` app for its
system checks. The renderers and parsers of the fastdrf profile are set on
its views (``bench/api/fast/views.py``), so that both profiles can also be
served side by side in one test process.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES = ("drf", "fastdrf")
PROFILE = os.environ.get("BENCH_PROFILE", "fastdrf")
if PROFILE not in PROFILES:
    raise ValueError(f"Unknown benchmark profile: {PROFILE}")

SECRET_KEY = "benchmark-only-not-for-deployment"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
# No middleware: the measurement is the framework, not a production stack.
MIDDLEWARE = []
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "bench.api",
]
if PROFILE == "fastdrf":
    INSTALLED_APPS.append("fastdrf")
ROOT_URLCONF = "bench.urls"
WSGI_APPLICATION = "bench.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
]
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING"},
        # The invalid case answers 400 thousands of times per second; Django
        # would log a warning for each.
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

USE_TZ = True
# Not UTC, so that every datetime is converted to the current time zone.
TIME_ZONE = "Europe/Istanbul"
LANGUAGE_CODE = "en-us"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"

if os.environ.get("BENCH_DATABASE", "postgres") == "sqlite":
    # Tests and CI only; measurements refuse it (bench/runner.py).
    (BASE_DIR / ".state").mkdir(exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ".state" / "bench.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("BENCH_PG_DB", "fastdrf_benchmarks"),
            "USER": os.environ.get("BENCH_PG_USER", "bench"),
            "PASSWORD": os.environ.get("BENCH_PG_PASSWORD", "benchmark-local-only"),
            "HOST": os.environ.get("BENCH_PG_HOST", "127.0.0.1"),
            "PORT": os.environ.get("BENCH_PG_PORT", "55451"),
            # Persistent connections, one per Gunicorn thread, as a
            # production deployment would keep them.
            "CONN_MAX_AGE": None,
            "CONN_HEALTH_CHECKS": False,
        }
    }

if PROFILE == "fastdrf":
    FASTDRF = {
        # Output of fastdrf serializers from a compiled msgspec class; input
        # that DRF would accept unchanged recognized by a compiled class.
        "SERIALIZER_BACKEND": "msgspec",
        # Only output proven equal to DRF's is compiled; everything else,
        # including every serializer the compiler declines, is DRF's.
        "SERIALIZER_BACKEND_PARITY": "strict",
        "SERIALIZER_BACKEND_FALLBACK": "drf",
        # Build each serializer class's fields once, copy them per request
        # with a generated plan instead of deepcopy.
        "CACHE_SERIALIZER_FIELDS": True,
        "FIELD_COPY_MODE": "compiled",
        # Left off: it would make db-create run fewer queries than DRF, and
        # the benchmark compares the same SQL (docs/methodology.md).
        "BATCH_RELATED_LOOKUPS": False,
        # A relation the serializers do not declare would be loaded for the
        # whole page at once; none of the cases needs it.
        "FETCH_MODE": "peers",
    }
