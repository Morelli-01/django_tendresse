from django.core.management.base import BaseCommand
import csv
from core.models import Retailer

class Command(BaseCommand):
    help = 'Import retailers from a CSV file'

    def handle(self, *args, **options):
        with open('Lista_Rivenditori.csv', 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header row

            for row in reader:
                self.stdout.write(self.style.SUCCESS(f'Importing {row[0]}'))
                Retailer.objects.get_or_create(
                    name=row[0],
                    defaults={
                        'street': row[1],
                        'postal_code': row[2],
                        'city': row[3],
                        'province': row[4],
                        'region': row[5],
                        'country': row[6],
                        'vat_number': row[7] if row[7] else None,
                        'fiscal_code': row[8] if row[8] else None,
                        'phone': row[9] if row[9] else None,
                    }
                )
            self.stdout.write(self.style.SUCCESS('Successfully imported retailers'))