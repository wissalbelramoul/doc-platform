"""
Management command pour traiter la queue d'outbox.

Lance un process qui consomme les événements en attente de publication
et les envoie à RabbitMQ avec retry et backoff exponentiel.

Lancement :
    python manage.py process_outbox

Ce process doit tourner continuellement en production (systemd, Docker, etc.)
en parallèle de runserver (ou gunicorn).
"""

import logging
import time
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from org.models import OutboxEvent
from org.events.publisher import _publish_to_rabbitmq

logger = logging.getLogger(__name__)

# Configuration du retry
MAX_ATTEMPTS = 5
INITIAL_DELAY = 1  # secondes
MAX_DELAY = 60  # secondes


def _backoff_delay(attempt: int) -> float:
    """
    Calcule le délai d'attente avec backoff exponentiel.
    Évite une charge trop importante sur RabbitMQ en cas de panne prolongée.
    """
    delay = min(INITIAL_DELAY * (2 ** attempt), MAX_DELAY)
    # Jitter aléatoire ±20% pour décorréler les tentatives
    import random
    jitter = delay * random.uniform(-0.2, 0.2)
    return delay + jitter


def _process_event(event: OutboxEvent) -> bool:
    """
    Tente de publier un événement sur RabbitMQ.
    Retourne True si succès, False si échec.
    """
    try:
        _publish_to_rabbitmq(event.routing_key, event.payload)
        event.mark_as_published()
        logger.info(
            "✓ Événement '%s' publié avec succès (tentative %d)",
            event.routing_key,
            event.attempt_count + 1
        )
        return True
    except Exception as exc:
        event.attempt_count += 1
        event.last_error = str(exc)
        event.save(update_fields=["attempt_count", "last_error"])

        if event.attempt_count >= MAX_ATTEMPTS:
            logger.error(
                "✗ Événement '%s' abandonné après %d tentatives : %s",
                event.routing_key,
                event.attempt_count,
                exc
            )
        else:
            logger.warning(
                "⚠ Tentative %d/%d pour '%s' échouée : %s",
                event.attempt_count,
                MAX_ATTEMPTS,
                event.routing_key,
                exc
            )
        return False


class Command(BaseCommand):
    help = "Traite la queue d'outbox : publie les événements en attente sur RabbitMQ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Nombre d'événements à traiter par itération (défaut: 10)"
        )
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=5,
            help="Intervalle d'interrogation de la base en secondes (défaut: 5)"
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        poll_interval = options["poll_interval"]

        self.stdout.write(
            self.style.SUCCESS(
                f"🚀 Démarrage du consumer outbox (batch={batch_size}, interval={poll_interval}s)"
            )
        )

        try:
            self._loop(batch_size, poll_interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n⏹ Arrêt demandé par l'utilisateur"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"✗ Erreur fatale : {exc}"))
            raise

    def _loop(self, batch_size: int, poll_interval: int) -> None:
        """Boucle principale du consumer."""
        while True:
            events = list(
                OutboxEvent.objects
                .filter(is_published=False, attempt_count__lt=MAX_ATTEMPTS)
                .order_by("created_at")[:batch_size]
            )

            if not events:
                # Pas d'événements à traiter : attendre avant de réinterroger
                time.sleep(poll_interval)
                continue

            self.stdout.write(
                f"📨 Traitement de {len(events)} événement(s)..."
            )

            for event in events:
                success = _process_event(event)
                if success:
                    # Succès : court délai avant le suivant
                    time.sleep(0.1)
                else:
                    # Échec : utiliser le backoff exponentiel
                    delay = _backoff_delay(event.attempt_count)
                    self.stdout.write(
                        f"   ⏳ Attente {delay:.1f}s avant nouvelle tentative..."
                    )
                    time.sleep(delay)

            # Petit repos entre les batches
            time.sleep(0.5)
