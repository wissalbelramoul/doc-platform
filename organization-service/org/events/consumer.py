import json
import logging
import os

import pika
from django.db import transaction

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = os.environ.get("RABBITMQ_EXCHANGE", "organisation_events")
QUEUE_NAME = os.environ.get("RABBITMQ_QUEUE", "organisation_service.inbox")

CONSUMED_ROUTING_KEYS = [
    "document.created",
    "document.deleted",
    "user.service_changed",
]


def _handle_document_created(payload: dict) -> None:
    from org.models import DocumentCountProjection

    service_id = payload["service_id"]
    with transaction.atomic():
        projection, _ = DocumentCountProjection.objects.select_for_update().get_or_create(
            service_id=service_id
        )
        projection.active_count += 1
        projection.save(update_fields=["active_count"])


def _handle_document_deleted(payload: dict) -> None:
    from org.models import DocumentCountProjection

    service_id = payload["service_id"]
    with transaction.atomic():
        projection, _ = DocumentCountProjection.objects.select_for_update().get_or_create(
            service_id=service_id
        )
        if projection.active_count > 0:
            projection.active_count -= 1
            projection.save(update_fields=["active_count"])


def _handle_user_service_changed(payload: dict) -> None:
    # Non spécifié par le document au-delà de la consommation de
    # l'événement. Journalisé pour l'instant ; à étendre si l'Organisation
    # doit réagir activement à un changement de service utilisateur.
    logger.info("user.service_changed reçu : %s", payload)


HANDLERS = {
    "document.created": _handle_document_created,
    "document.deleted": _handle_document_deleted,
    "user.service_changed": _handle_user_service_changed,
}


def _on_message(channel, method, properties, body):
    routing_key = method.routing_key
    handler = HANDLERS.get(routing_key)
    try:
        payload = json.loads(body)
        if handler:
            handler(payload)
        else:
            logger.warning("Aucun handler pour la routing key '%s'", routing_key)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        logger.exception("Erreur lors du traitement de l'événement '%s'", routing_key)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consuming() -> None:
    """
    Démarre la consommation bloquante des événements. À lancer dans un
    process dédié :

        python manage.py consume_events

    Jamais dans le cycle de requête HTTP (voir la management command
    associée dans org/management/commands/consume_events.py).
    """
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    for routing_key in CONSUMED_ROUTING_KEYS:
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=routing_key)

    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

    logger.info("En écoute sur la queue '%s'...", QUEUE_NAME)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()
