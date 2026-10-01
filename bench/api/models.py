"""
The models of every case.

The output cases without a database (``small``, ``wide``, ``list-*``,
``nested``, ``deep``, ``types``, ``text-heavy``, ``method-field``) represent
model instances built in memory (``bench/api/payloads.py``). Their models
are unmanaged: no table exists and no query is ever made. They are models
because fastdrf's strict parity compiles ``ModelSerializer`` output only;
DRF's ``ModelSerializer`` represents them the same way it represents rows.

``Author``, ``Tag`` and ``Article`` are the PostgreSQL cases' tables.
"""

from decimal import Decimal

from django.db import models


class InMemory(models.Model):
    class Meta:
        abstract = True
        managed = False


class Small(InMemory):
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=254)
    active = models.BooleanField()
    score = models.FloatField()


def _wide_fields() -> dict[str, models.Field]:
    """49 columns of mixed types; with the id, 50 fields."""
    fields: dict[str, models.Field] = {}
    for index in range(13):
        fields[f"text_{index:02d}"] = models.CharField(max_length=64)
    for index in range(12):
        fields[f"integer_{index:02d}"] = models.IntegerField()
    for index in range(8):
        fields[f"float_{index:02d}"] = models.FloatField()
    for index in range(6):
        fields[f"flag_{index:02d}"] = models.BooleanField()
    for index in range(3):
        fields[f"date_{index:02d}"] = models.DateField()
    for index in range(3):
        fields[f"datetime_{index:02d}"] = models.DateTimeField()
    for index in range(3):
        fields[f"decimal_{index:02d}"] = models.DecimalField(
            max_digits=12, decimal_places=2
        )
    fields["uuid_00"] = models.UUIDField()
    return fields


# Declared with type() so that the 49 columns need not be spelled out.
Wide = type(
    "Wide",
    (InMemory,),
    {
        "__module__": __name__,
        "__qualname__": "Wide",
        "Meta": type("Meta", (), {"managed": False}),
        **_wide_fields(),
    },
)


class Item(InMemory):
    class Category(models.TextChoices):
        BOOKS = "books", "Books"
        GAMES = "games", "Games"
        MUSIC = "music", "Music"
        TOOLS = "tools", "Tools"

    sku = models.CharField(max_length=32)
    name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    in_stock = models.BooleanField()
    rating = models.FloatField()
    category = models.CharField(max_length=10, choices=Category)
    created_on = models.DateField()
    uuid = models.UUIDField()


class Typed(InMemory):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In review"
        PUBLISHED = "published", "Published"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"

    created_at = models.DateTimeField()
    day = models.DateField()
    at = models.TimeField()
    amount = models.DecimalField(max_digits=14, decimal_places=4)
    uuid = models.UUIDField()
    flag = models.BooleanField()
    note = models.CharField(max_length=100, null=True)
    count = models.IntegerField(null=True)
    status = models.CharField(max_length=10, choices=Status)
    priority = models.IntegerField(choices=Priority)
    quantity = models.IntegerField()
    ratio = models.FloatField()


class Document(InMemory):
    title = models.CharField(max_length=200)
    body_latin = models.TextField()
    body_greek = models.TextField()
    body_cjk = models.TextField()
    body_mixed = models.TextField()


class Customer(InMemory):
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=254)
    city = models.CharField(max_length=100)


class Order(InMemory):
    number = models.CharField(max_length=20)
    placed_at = models.DateTimeField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)


class OrderLine(InMemory):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.DO_NOTHING)
    sku = models.CharField(max_length=32)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    note = models.CharField(max_length=100)


class Node(InMemory):
    """A tree node; the ``deep`` case nests five levels of them."""

    parent = models.ForeignKey(
        "self", null=True, related_name="children", on_delete=models.DO_NOTHING
    )
    name = models.CharField(max_length=50)
    value = models.IntegerField()
    weight = models.FloatField()


class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=254)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.SlugField(max_length=30, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Article(models.Model):
    author = models.ForeignKey(
        Author, related_name="articles", on_delete=models.CASCADE
    )
    tags = models.ManyToManyField(Tag, related_name="articles", blank=True)
    title = models.CharField(max_length=200)
    body = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    published_at = models.DateTimeField()
    views = models.IntegerField(default=0)

    class Meta:
        ordering = ["-published_at", "id"]

    def __str__(self):
        return self.title
