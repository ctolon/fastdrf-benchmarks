"""
The 50 fields of the ``validate-wide`` input serializer, shared by both
profiles.

fastdrf re-exports DRF's field classes, so the fields are DRF's in both
profiles; each profile declares the serializer on its own base.
"""

from rest_framework import serializers

COLOURS = ["red", "green", "blue"]


def wide_fields() -> dict[str, serializers.Field]:
    """New field instances; ``bench.api.payloads.wide_input()`` fills them."""
    fields: dict[str, serializers.Field] = {}
    for index in range(14):
        fields[f"text_{index:02d}"] = serializers.CharField(max_length=100)
    for index in range(12):
        fields[f"integer_{index:02d}"] = serializers.IntegerField(
            min_value=-(10**9), max_value=10**9
        )
    for index in range(8):
        fields[f"float_{index:02d}"] = serializers.FloatField()
    for index in range(6):
        fields[f"flag_{index:02d}"] = serializers.BooleanField()
    for index in range(4):
        fields[f"choice_{index:02d}"] = serializers.ChoiceField(choices=COLOURS)
    for index in range(2):
        fields[f"uuid_{index:02d}"] = serializers.UUIDField()
    for index in range(2):
        fields[f"date_{index:02d}"] = serializers.DateField()
    for index in range(2):
        fields[f"list_{index:02d}"] = serializers.ListField(
            child=serializers.IntegerField()
        )
    return fields
