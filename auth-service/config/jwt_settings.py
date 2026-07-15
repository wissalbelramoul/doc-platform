"""
Configuration JWT en RS256 pour djangorestframework-simplejwt.
À importer/coller dans settings.py
"""

from datetime import timedelta
import os

BASE_DIR_KEYS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keys")

with open(os.path.join(BASE_DIR_KEYS, "private.pem"), "r") as f:
    JWT_PRIVATE_KEY = f.read()

with open(os.path.join(BASE_DIR_KEYS, "public.pem"), "r") as f:
    JWT_PUBLIC_KEY = f.read()

SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": JWT_PRIVATE_KEY,
    "VERIFYING_KEY": JWT_PUBLIC_KEY,

    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}