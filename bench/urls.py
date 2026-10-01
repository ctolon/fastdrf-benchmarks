"""The URLconf of the profile ``BENCH_PROFILE`` selects."""

from django.conf import settings
from django.urls import include, path

URLCONFS = {"drf": "bench.api.drf.urls", "fastdrf": "bench.api.fast.urls"}

urlpatterns = [path("", include(URLCONFS[settings.PROFILE]))]
