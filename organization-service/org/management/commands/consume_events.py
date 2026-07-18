from django.core.management.base import BaseCommand

from org.events.consumer import start_consuming


class Command(BaseCommand):
    help = "Démarre le consommateur RabbitMQ du microservice Organisation."

    def handle(self, *args, **options):
        start_consuming()
