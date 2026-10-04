"""
The views of bench/api/drf/views.py with fastdrf's opt-ins.

Every view answers what its DRF pair answers, byte for byte; the tests and
the runner check it for every case.
"""

from django.conf import settings
from django.utils.module_loading import import_string
from fastdrf.mixins import CreateModelMixin, UpdateModelMixin
from fastdrf.response import DataResponse
from fastdrf.views import DispatchOptimizationMixin, QueryOptimizationMixin
from rest_framework import generics
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.renderers import BrowsableAPIRenderer

from bench.api import models
from bench.api.fast import serializers
from bench.api.pagination import ArticlePagination

JSON_TRANSPORTS = {
    "msgspec": (
        "fastdrf.msgspec.parsers.MsgspecJSONParser",
        "fastdrf.msgspec.renderers.MsgspecJSONRenderer",
    ),
    "pydantic": (
        "fastdrf.pydantic.parsers.PydanticJSONParser",
        "fastdrf.pydantic.renderers.PydanticJSONRenderer",
    ),
    "orjson": (
        "fastdrf.orjson.parsers.ORJSONParser",
        "fastdrf.orjson.renderers.ORJSONRenderer",
    ),
    "drf": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.renderers.JSONRenderer",
    ),
}
_json_parser, _json_renderer = map(import_string, JSON_TRANSPORTS[settings.BENCH_JSON])


class Optimized(DispatchOptimizationMixin):
    """
    DispatchOptimizationMixin keeps the content negotiation and request
    set-up that DRF repeats on every request, resolves DataResponse, and
    answers with a Response that releases the request when it is closed.
    """

    # Keep the browsable API and form/upload parsers, including DRF's Vary
    # header. Every selected transport must pass the same byte comparison.
    renderer_classes = [_json_renderer, BrowsableAPIRenderer]
    parser_classes = [_json_parser, FormParser, MultiPartParser]


# Output of in-memory objects.


class ObjectView(Optimized, generics.RetrieveAPIView):
    source = None

    def get_object(self):
        return self.source()

    def retrieve(self, request, *args, **kwargs):
        # Rendered straight into an HttpResponse, without DRF's template
        # response; status, headers and bytes are DRF's.
        return DataResponse(self.get_serializer(self.get_object()).data)


class ObjectListView(Optimized, generics.ListAPIView):
    source = None

    def get_queryset(self):
        return self.source()

    def list(self, request, *args, **kwargs):
        return DataResponse(self.get_serializer(self.get_queryset(), many=True).data)


# Input validation.


class ValidateView(Optimized, generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return DataResponse(serializer.validated_data)


# PostgreSQL. QueryOptimizationMixin derives the lookups from the
# serializers' Meta.auto_prefetch; fastdrf's CreateModelMixin and
# UpdateModelMixin produce the saved object with the compiled encoder of the
# serializer's class.


class ArticleList(
    Optimized, QueryOptimizationMixin, CreateModelMixin, generics.ListCreateAPIView
):
    queryset = models.Article.objects.all()
    serializer_class = serializers.ArticleSerializer
    pagination_class = ArticlePagination


class ArticleDetail(
    Optimized, QueryOptimizationMixin, UpdateModelMixin, generics.RetrieveUpdateAPIView
):
    queryset = models.Article.objects.all()
    serializer_class = serializers.ArticleSerializer

    def retrieve(self, request, *args, **kwargs):
        return DataResponse(self.get_serializer(self.get_object()).data)


class AuthorList(Optimized, QueryOptimizationMixin, generics.ListAPIView):
    queryset = models.Author.objects.all()
    serializer_class = serializers.AuthorWithArticlesSerializer

    def list(self, request, *args, **kwargs):
        authors = self.filter_queryset(self.get_queryset())
        return DataResponse(self.get_serializer(authors, many=True).data)
