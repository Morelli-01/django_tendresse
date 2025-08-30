from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a superuser from environment variables.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('MYSQL_USER')
        password = os.environ.get('MYSQL_ROOT_PASSWORD')
        email = 'admin@example.com'  # Or use another env var

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, password=password, email=email)
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser {username}'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser {username} already exists.'))
