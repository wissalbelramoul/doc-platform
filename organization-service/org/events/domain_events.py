from __future__ import annotations

import logging
from typing import Any, Dict

from django.db import transaction

logger = logging.getLogger(__name__)


def emit_domain_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Emit a business event only after the current database transaction commits.

    This keeps the domain state and the outbox records consistent even when a
    later step fails or the request is rolled back.
    """
    from org.events.publisher import publish_event

    def _publish() -> None:
        publish_event(event_type, payload)
        logger.info("domain event emitted: %s %s", event_type, payload)

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_publish)
        return

    _publish()
