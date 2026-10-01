"""The URLs of both profiles: the same paths, each profile's views."""

from functools import partial

from django.http import HttpResponse
from django.urls import path

from bench.api import payloads


def health(request):
    """Answers once the server is up, without running DRF."""
    return HttpResponse(b"ok", content_type="text/plain")


def routes(views, serializers) -> list:
    one = views.ObjectView.as_view
    many = views.ObjectListView.as_view
    validate = views.ValidateView.as_view
    return [
        path("health/", health),
        path(
            "out/small/",
            one(serializer_class=serializers.SmallSerializer, source=payloads.small),
        ),
        path(
            "out/wide/",
            one(serializer_class=serializers.WideSerializer, source=payloads.wide),
        ),
        *(
            path(
                f"out/list-{count}/",
                many(
                    serializer_class=serializers.ItemSerializer,
                    source=partial(payloads.items, count),
                ),
            )
            for count in (100, 1000, 10_000)
        ),
        path(
            "out/nested/",
            one(serializer_class=serializers.OrderSerializer, source=payloads.order),
        ),
        path(
            "out/deep/",
            one(serializer_class=serializers.TreeSerializer, source=payloads.tree),
        ),
        path(
            "out/types/",
            many(serializer_class=serializers.TypedSerializer, source=payloads.typed),
        ),
        path(
            "out/text-heavy/",
            one(
                serializer_class=serializers.DocumentSerializer,
                source=payloads.document,
            ),
        ),
        path(
            "out/method-field/",
            many(
                serializer_class=serializers.LabelledItemSerializer,
                source=partial(payloads.items, 100),
            ),
        ),
        path(
            "out/plain-serializer/",
            many(
                serializer_class=serializers.PlainItemSerializer,
                source=payloads.plain,
            ),
        ),
        path("in/small/", validate(serializer_class=serializers.SmallInputSerializer)),
        path("in/wide/", validate(serializer_class=serializers.WideInputSerializer)),
        path("in/nested/", validate(serializer_class=serializers.BatchSerializer)),
        path("db/articles/", views.ArticleList.as_view()),
        path("db/articles/<int:pk>/", views.ArticleDetail.as_view()),
        path("db/authors/", views.AuthorList.as_view()),
    ]
