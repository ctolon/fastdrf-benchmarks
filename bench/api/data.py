"""The PostgreSQL cases' rows: written once, and again after every write."""

from django.core.management.color import no_style
from django.db import connection, transaction

from bench.api import models, payloads


@transaction.atomic
def seed() -> None:
    """
    Replace every row with the fixed rows of ``payloads.rows()`` and restart
    the key sequences after them, so that the next created article has the
    same primary key in every sample.
    """
    rows = payloads.rows()
    models.Article.tags.through.objects.all().delete()
    models.Article.objects.all().delete()
    models.Tag.objects.all().delete()
    models.Author.objects.all().delete()
    models.Author.objects.bulk_create(models.Author(**row) for row in rows["authors"])
    models.Tag.objects.bulk_create(models.Tag(**row) for row in rows["tags"])
    models.Article.objects.bulk_create(
        models.Article(**row) for row in rows["articles"]
    )
    through = models.Article.tags.through
    through.objects.bulk_create(
        through(article_id=article, tag_id=tag) for article, tag in rows["links"]
    )
    statements = connection.ops.sequence_reset_sql(
        no_style(), [models.Author, models.Tag, models.Article, through]
    )
    if connection.vendor == "sqlite":
        # SQLite's AUTOINCREMENT counters would continue after deleted rows;
        # without them the next key follows the highest one.
        statements.append("DELETE FROM sqlite_sequence")
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def counts() -> dict[str, int]:
    return {
        "authors": models.Author.objects.count(),
        "tags": models.Tag.objects.count(),
        "articles": models.Article.objects.count(),
        "links": models.Article.tags.through.objects.count(),
    }
