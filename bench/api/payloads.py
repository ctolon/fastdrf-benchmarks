"""
The deterministic data of every case: the in-memory objects the output
cases represent, the request bodies of the input cases and the rows of the
PostgreSQL cases.

Everything derives from fixed seeds, so every process, profile and run
builds the same values. The objects are built once per process and only
read afterwards; serializers do not change them.
"""

import datetime
import random
import uuid
from decimal import Decimal
from functools import cache
from zoneinfo import ZoneInfo

from bench.api import models

UTC = datetime.UTC
ISTANBUL = ZoneInfo("Europe/Istanbul")
BERLIN = ZoneInfo("Europe/Berlin")
EPOCH = datetime.datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
WORDS = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
]


def _rng(name: str) -> random.Random:
    return random.Random(f"fastdrf-benchmarks:{name}")


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _words(rng: random.Random, count: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(count))


def _money(rng: random.Random, high: int) -> Decimal:
    return Decimal(rng.randrange(100, high * 100)) / 100


def _float(rng: random.Random) -> float:
    # Three decimals in a range both JSON encoders write without an
    # exponent: the bytes compare equal, and any float would round-trip.
    return round(rng.uniform(0.001, 99_999), 3)


def _prefetched(instance, name: str, items: list) -> None:
    """
    Attach ``items`` as the prefetched objects of the to-many relation
    ``name``, as ``prefetch_related`` stores them: the related manager's
    ``all()`` then returns them without a query.
    """
    queryset = getattr(instance, name).model._default_manager.none()
    queryset._result_cache = items
    queryset._prefetch_done = True
    cache_name = instance._meta.get_field(name).cache_name
    instance.__dict__.setdefault("_prefetched_objects_cache", {})[cache_name] = queryset


@cache
def small() -> models.Small:
    return models.Small(
        id=1, name="Ada Lovelace", email="ada@example.com", active=True, score=97.25
    )


@cache
def wide() -> models.Wide:
    rng = _rng("wide")
    values = {"id": 1}
    for field in models.Wide._meta.concrete_fields:
        name = field.name
        if name.startswith("text_"):
            values[name] = _words(rng, 4)
        elif name.startswith("integer_"):
            values[name] = rng.randrange(-1_000_000, 1_000_000)
        elif name.startswith("float_"):
            values[name] = _float(rng)
        elif name.startswith("flag_"):
            values[name] = rng.random() < 0.5
        elif name.startswith("datetime_"):
            values[name] = EPOCH + datetime.timedelta(
                seconds=rng.randrange(0, 86_400 * 365),
                microseconds=rng.randrange(10**6),
            )
        elif name.startswith("date_"):
            values[name] = datetime.date(2026, 1, 1) + datetime.timedelta(
                days=rng.randrange(365)
            )
        elif name.startswith("decimal_"):
            values[name] = _money(rng, 100_000)
        elif name.startswith("uuid_"):
            values[name] = _uuid(rng)
    return models.Wide(**values)


@cache
def items(count: int) -> list[models.Item]:
    rng = _rng(f"items-{count}")
    categories = list(models.Item.Category)
    return [
        models.Item(
            id=index,
            sku=f"SKU-{index:06d}",
            name=_words(rng, 3).title(),
            quantity=rng.randrange(0, 500),
            price=_money(rng, 1000),
            in_stock=rng.random() < 0.8,
            rating=round(rng.uniform(0, 5), 2),
            # Plain strings, as the database returns them; the choices
            # enumeration members are str subclasses.
            category=str(rng.choice(categories).value),
            created_on=datetime.date(2025, 1, 1)
            + datetime.timedelta(days=rng.randrange(600)),
            uuid=_uuid(rng),
        )
        for index in range(1, count + 1)
    ]


@cache
def typed(count: int = 100) -> list[models.Typed]:
    rng = _rng("typed")
    zones = (UTC, ISTANBUL, BERLIN)
    result = []
    for index in range(1, count + 1):
        moment = EPOCH + datetime.timedelta(
            seconds=rng.randrange(0, 86_400 * 365), microseconds=rng.randrange(10**6)
        )
        result.append(
            models.Typed(
                id=index,
                # Aware datetimes in several zones; DRF and fastdrf both
                # convert them to the current time zone.
                created_at=moment.astimezone(zones[index % 3]),
                day=moment.date(),
                at=datetime.time(
                    rng.randrange(24),
                    rng.randrange(60),
                    rng.randrange(60),
                    rng.randrange(10**6) if index % 2 else 0,
                ),
                amount=Decimal(rng.randrange(-(10**9), 10**9)) / 10_000,
                uuid=_uuid(rng),
                flag=index % 3 == 0,
                note=None if index % 4 == 0 else _words(rng, 2),
                count=None if index % 5 == 0 else rng.randrange(1000),
                status=str(rng.choice(list(models.Typed.Status)).value),
                priority=int(rng.choice(list(models.Typed.Priority)).value),
                quantity=rng.randrange(-(2**40), 2**40),
                ratio=_float(rng),
            )
        )
    return result


def _unicode_text(rng: random.Random, alphabet: str, size: int) -> str:
    """About ``size`` characters of words drawn from ``alphabet``."""
    words = []
    length = 0
    while length < size:
        word = "".join(rng.choice(alphabet) for _ in range(rng.randrange(2, 9)))
        words.append(word)
        length += len(word) + 1
    return " ".join(words)[:size]


@cache
def document() -> models.Document:
    rng = _rng("document")
    latin = "abcçdefgğhıijklmnoöprsştuüvyzâêîôûéèàñß"
    greek = "αβγδεζηθικλμνξοπρστυφχψωάέήίόύώ"
    cjk = "的一是不了人我在有他这中大来上国个到说们为子和你地出道也时年得就那要下以生会自着去之过家学对可"
    mixed = (
        latin
        + "😀🚀🎉🌍"
        + 'éß"\\/'
        + "\n\t\r\x08\x0c"
        + "\u2028\u2029\u00a0\u200b"
        + "𝔘𝔫𝔦𝔠𝔬𝔡𝔢"
    )
    return models.Document(
        id=1,
        title="Unicode text, about 10,000 characters per field",
        body_latin=_unicode_text(rng, latin, 10_000),
        body_greek=_unicode_text(rng, greek, 10_000),
        body_cjk=_unicode_text(rng, cjk, 10_000),
        body_mixed=_unicode_text(rng, mixed, 10_000),
    )


@cache
def order() -> models.Order:
    rng = _rng("order")
    customer = models.Customer(
        id=7, name="Grace Hopper", email="grace@example.com", city="Arlington"
    )
    result = models.Order(
        id=1001,
        number="ORD-2026-001001",
        placed_at=datetime.datetime(2026, 9, 30, 14, 5, 9, 123456, tzinfo=UTC),
        total=Decimal("0"),
        customer=customer,
    )
    lines = [
        models.OrderLine(
            id=index,
            order=result,
            sku=f"SKU-{rng.randrange(10**6):06d}",
            quantity=rng.randrange(1, 20),
            unit_price=_money(rng, 500),
            note=_words(rng, 3),
        )
        for index in range(1, 11)
    ]
    result.total = sum((line.unit_price * line.quantity for line in lines), Decimal())
    _prefetched(result, "lines", lines)
    return result


@cache
def tree(depth: int = 5, branching: int = 3) -> models.Node:
    """A root with ``branching`` children per node, ``depth`` levels in all."""
    rng = _rng("tree")
    counter = iter(range(1, 10**6))

    def node(level: int, parent):
        current = models.Node(
            id=next(counter),
            parent=parent,
            name=f"level-{level}-{_words(rng, 1)}",
            value=rng.randrange(10_000),
            weight=_float(rng),
        )
        children = (
            [node(level + 1, current) for _ in range(branching)]
            if level < depth
            else []
        )
        _prefetched(current, "children", children)
        return current

    return node(1, None)


@cache
def plain(count: int = 100) -> list[dict]:
    """Dictionaries for the plain ``Serializer`` of the ``plain-serializer`` case."""
    return [
        {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "quantity": item.quantity,
            "in_stock": item.in_stock,
            "rating": item.rating,
            "category": item.category,
            "created_on": item.created_on,
            "uuid": item.uuid,
        }
        for item in items(count)
    ]


# Request bodies of the input cases, as JSON-ready values.


def small_input() -> dict:
    return {
        "name": "Ada Lovelace",
        "age": 36,
        "active": True,
        "score": 97.25,
        "role": "admin",
    }


def wide_input() -> dict:
    rng = _rng("wide-input")
    body = {}
    for index in range(14):
        body[f"text_{index:02d}"] = _words(rng, 4)
    for index in range(12):
        body[f"integer_{index:02d}"] = rng.randrange(-1_000_000, 1_000_000)
    for index in range(8):
        body[f"float_{index:02d}"] = _float(rng)
    for index in range(6):
        body[f"flag_{index:02d}"] = rng.random() < 0.5
    for index in range(4):
        body[f"choice_{index:02d}"] = rng.choice(["red", "green", "blue"])
    for index in range(2):
        body[f"uuid_{index:02d}"] = str(_uuid(rng))
    for index in range(2):
        body[f"date_{index:02d}"] = (
            datetime.date(2026, 1, 1) + datetime.timedelta(days=rng.randrange(365))
        ).isoformat()
    for index in range(2):
        body[f"list_{index:02d}"] = [rng.randrange(1000) for _ in range(5)]
    return body


def invalid_input() -> dict:
    """The wide body with ten kinds of error, and three fields missing."""
    body = wide_input()
    body |= {
        "text_00": "",
        "text_01": "x" * 101,
        "integer_00": "twelve",
        "integer_01": 10**12,
        "float_00": "NaN-ish",
        "flag_00": "perhaps",
        "choice_00": "purple",
        "uuid_00": "not-a-uuid",
        "date_00": "2026-02-30",
        "list_00": ["a", 1],
    }
    for key in ("text_13", "integer_11", "float_07"):
        del body[key]
    return body


def nested_input(count: int = 100) -> dict:
    rng = _rng("nested-input")
    return {
        "reference": "BATCH-2026-0042",
        "warehouse": "IST-1",
        "items": [
            {
                "line": index,
                "sku": f"SKU-{rng.randrange(10**6):06d}",
                "name": _words(rng, 3),
                "quantity": rng.randrange(1, 100),
                "weight": _float(rng),
                "fragile": rng.random() < 0.2,
                "tags": [rng.choice(WORDS) for _ in range(3)],
                "dimensions": {
                    "width": _float(rng),
                    "height": _float(rng),
                    "depth": _float(rng),
                    "unit": rng.choice(["cm", "in"]),
                },
            }
            for index in range(1, count + 1)
        ],
    }


# The PostgreSQL cases' rows.

AUTHORS = 10
ARTICLES_PER_AUTHOR = 10
TAGS = 12
TAGS_PER_ARTICLE = 3
ARTICLES = AUTHORS * ARTICLES_PER_AUTHOR
DETAIL_ARTICLE = 1
UPDATED_ARTICLE = 2


def rows() -> dict[str, list]:
    """Authors, tags, articles and article-tag links, with fixed keys."""
    rng = _rng("rows")
    authors = [
        {
            "id": index,
            "name": f"Author {index:02d}",
            "email": f"author{index}@example.com",
        }
        for index in range(1, AUTHORS + 1)
    ]
    tags = [{"id": index, "name": f"tag-{index:02d}"} for index in range(1, TAGS + 1)]
    articles = []
    links = []
    for index in range(1, ARTICLES + 1):
        articles.append(
            {
                "id": index,
                "author_id": (index - 1) % AUTHORS + 1,
                "title": _words(rng, 6).capitalize(),
                "body": _words(rng, 60).capitalize() + ".",
                "price": _money(rng, 100),
                "published_at": EPOCH + datetime.timedelta(hours=7 * index),
                "views": rng.randrange(100_000),
            }
        )
        links += [
            (index, tag)
            for tag in sorted(rng.sample(range(1, TAGS + 1), TAGS_PER_ARTICLE))
        ]
    return {"authors": authors, "tags": tags, "articles": articles, "links": links}


def create_input() -> dict:
    return {
        "title": "Measure before you optimize",
        "body": "Count the queries first, then the serializer work.",
        "price": "12.50",
        "published_at": "2026-09-30T10:00:00+03:00",
        "author_id": 3,
        "tag_ids": [2, 5, 7],
    }


def update_input() -> dict:
    return {"title": "Updated title", "price": "7.25", "views": 12345}
