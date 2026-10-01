from django.core.management.base import BaseCommand

from bench.api import data


class Command(BaseCommand):
    help = "Replace the PostgreSQL cases' rows with the fixed benchmark rows."

    def handle(self, *args, **options):
        data.seed()
        self.stdout.write(f"Seeded: {data.counts()}")
