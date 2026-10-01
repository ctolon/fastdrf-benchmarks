"""
Plain DRF: generic views with DRF's default renderers, parsers and dispatch.

The database views spell out select_related and prefetch_related, as a
careful DRF project would, so that both profiles run the same SQL.
"""

from rest_framework import generics
from rest_framework.response import Response

from bench.api import models
from bench.api.drf import serializers
from bench.api.pagination import ArticlePagination

# Output of in-memory objects.


class ObjectView(generics.RetrieveAPIView):
    """One in-memory object; ``source`` returns it."""

    source = None

    def get_object(self):
        return self.source()


class ObjectListView(generics.ListAPIView):
    """A list of in-memory objects; ``source`` returns it."""

    source = None

    def get_queryset(self):
        return self.source()


# Input validation: the validated data, or DRF's 400 with the errors.


class ValidateView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


# PostgreSQL.


class ArticleList(generics.ListCreateAPIView):
    queryset = models.Article.objects.select_related("author").prefetch_related("tags")
    serializer_class = serializers.ArticleSerializer
    pagination_class = ArticlePagination


class ArticleDetail(generics.RetrieveUpdateAPIView):
    queryset = models.Article.objects.select_related("author").prefetch_related("tags")
    serializer_class = serializers.ArticleSerializer


class AuthorList(generics.ListAPIView):
    queryset = models.Author.objects.prefetch_related("articles__tags")
    serializer_class = serializers.AuthorWithArticlesSerializer
