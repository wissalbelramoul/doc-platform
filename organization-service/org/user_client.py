from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class UserServiceClient:
    """Small HTTP client for reading user profile data from the user service.

    The organization service never creates, updates, or deletes users. It only
    consumes user identifiers and optional metadata through a dedicated client.
    """

    def __init__(self, base_url: str, timeout: int = 3, cache: Optional[Dict[str, Any]] = None):
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self._cache = cache if cache is not None else {}

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"user:{user_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = requests.get(
                urljoin(self.base_url, f"users/{user_id}/"),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Unable to fetch user %s from user service: %s", user_id, exc)
            return None

        payload = response.json()
        self._cache[cache_key] = payload
        return payload
