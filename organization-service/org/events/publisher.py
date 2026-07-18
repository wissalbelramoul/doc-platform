import json
import logging
import os

import pika

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = os.environ.get("RABBITMQ_EXCHANGE", "organisation_events")


def _get_connection():
    return pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))


def publish_event(routing_key: str, payload: dict) -> None:
    """
    Publie un événement en l'enregistrant d'abord dans l'outbox.

    L'outbox pattern garantit qu'aucun événement n'est perdu en cas
    d'indisponibilité RabbitMQ. Un process dédié traite la queue de
    publication avec retry et backoff exponentiel :

        python manage.py process_outbox

    Cette approche remplace la publication synchrone best-effort qui
    perdait les événements en cas d'erreur (voir commit précédent).
    """
    from org.models import OutboxEvent

    # Enregistrer l'événement dans l'outbox (garantie transactionnelle)
    OutboxEvent.objects.create(
        routing_key=routing_key,
        payload=payload,
    )
    logger.info(
        "Événement '%s' enregistré dans l'outbox (sera publié asynchrone)",
        routing_key
    )


def _publish_to_rabbitmq(routing_key: str, payload: dict) -> None:
    """
    Publie un événement sur RabbitMQ (interne : appelé par process_outbox).

    Cette fonction est séparée pour permettre le retry indépendamment
    de la logique métier (qui ne doit jamais échouer en cas d'erreur RabbitMQ).
    """
    body = json.dumps(payload, default=str).encode("utf-8")
    try:
        connection = _get_connection()
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # persistant
            ),
        )
        connection.close()
    except Exception as exc:
        logger.exception("Échec de publication de l'événement '%s'", routing_key)
        raise
