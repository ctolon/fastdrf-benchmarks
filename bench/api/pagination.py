from rest_framework.pagination import PageNumberPagination


class ArticlePagination(PageNumberPagination):
    """Shared by both profiles, so that their pages are the same."""

    page_size = 20
