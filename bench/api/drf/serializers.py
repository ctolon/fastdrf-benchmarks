"""Plain Django REST framework serializers."""

from rest_framework import serializers

from bench.api import inputs, models

# Output of in-memory model instances.


class SmallSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Small
        fields = "__all__"


class WideSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Wide
        fields = "__all__"


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Item
        fields = "__all__"


class TypedSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Typed
        fields = "__all__"


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Document
        fields = "__all__"


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Customer
        fields = ["id", "name", "email", "city"]


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OrderLine
        fields = ["id", "sku", "quantity", "unit_price", "note"]


class OrderSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer()
    lines = OrderLineSerializer(many=True)

    class Meta:
        model = models.Order
        fields = ["id", "number", "placed_at", "total", "customer", "lines"]


class Level5Serializer(serializers.ModelSerializer):
    class Meta:
        model = models.Node
        fields = ["id", "name", "value", "weight"]


class Level4Serializer(serializers.ModelSerializer):
    children = Level5Serializer(many=True)

    class Meta:
        model = models.Node
        fields = ["id", "name", "value", "weight", "children"]


class Level3Serializer(serializers.ModelSerializer):
    children = Level4Serializer(many=True)

    class Meta:
        model = models.Node
        fields = ["id", "name", "value", "weight", "children"]


class Level2Serializer(serializers.ModelSerializer):
    children = Level3Serializer(many=True)

    class Meta:
        model = models.Node
        fields = ["id", "name", "value", "weight", "children"]


class TreeSerializer(serializers.ModelSerializer):
    children = Level2Serializer(many=True)

    class Meta:
        model = models.Node
        fields = ["id", "name", "value", "weight", "children"]


class LabelledItemSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = models.Item
        fields = "__all__"

    def get_label(self, item):
        return f"{item.sku}: {item.name} ({item.category})"


class PlainItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sku = serializers.CharField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    in_stock = serializers.BooleanField()
    rating = serializers.FloatField()
    category = serializers.ChoiceField(choices=models.Item.Category.choices)
    created_on = serializers.DateField()
    uuid = serializers.UUIDField()


# Input validation.


class SmallInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    age = serializers.IntegerField(min_value=0, max_value=150)
    active = serializers.BooleanField()
    score = serializers.FloatField()
    role = serializers.ChoiceField(choices=["admin", "editor", "viewer"])


WideInputSerializer = type(
    "WideInputSerializer",
    (serializers.Serializer,),
    {"__module__": __name__, **inputs.wide_fields()},
)


class DimensionsSerializer(serializers.Serializer):
    width = serializers.FloatField(min_value=0)
    height = serializers.FloatField(min_value=0)
    depth = serializers.FloatField(min_value=0)
    unit = serializers.ChoiceField(choices=["cm", "in"])


class LineSerializer(serializers.Serializer):
    line = serializers.IntegerField(min_value=1)
    sku = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=100)
    quantity = serializers.IntegerField(min_value=1)
    weight = serializers.FloatField(min_value=0)
    fragile = serializers.BooleanField()
    tags = serializers.ListField(child=serializers.CharField(max_length=20))
    dimensions = DimensionsSerializer()


class BatchSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=40)
    warehouse = serializers.CharField(max_length=10)
    items = LineSerializer(many=True)


# PostgreSQL.


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Author
        fields = ["id", "name"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tag
        fields = ["id", "name"]


class ArticleSerializer(serializers.ModelSerializer):
    """Nested author and tags on output; their primary keys on input."""

    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        source="author", queryset=models.Author.objects.all(), write_only=True
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        source="tags", queryset=models.Tag.objects.all(), many=True, write_only=True
    )

    class Meta:
        model = models.Article
        fields = [
            "id",
            "title",
            "body",
            "price",
            "published_at",
            "views",
            "author",
            "tags",
            "author_id",
            "tag_ids",
        ]


class ArticleSummarySerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = models.Article
        fields = ["id", "title", "price", "published_at", "tags"]


class AuthorWithArticlesSerializer(serializers.ModelSerializer):
    articles = ArticleSummarySerializer(many=True, read_only=True)

    class Meta:
        model = models.Author
        fields = ["id", "name", "email", "articles"]
