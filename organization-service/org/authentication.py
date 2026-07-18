"""
Authentification JWT RS256 — délégation à l'auth-service.

L'organization-service ne possède pas sa propre table utilisateurs.
Il vérifie les tokens JWT émis et signés par l'auth-service via la
clé publique RS256 partagée (asymétrique, sans secret commun).

Le token doit contenir :
  - `user_id`         : identifiant unique de l'utilisateur (obligatoire) ;
  - `identifiant_ad`  : login Active Directory (optionnel) ;
  - `is_staff`        : booléen indiquant un accès administrateur (optionnel) ;
  - `is_superuser`    : booléen indiquant un accès superutilisateur (optionnel).
"""

import os
import uuid
from pathlib import Path

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed


class RemoteUser:
    """
    Représentation légère d'un utilisateur authentifié via l'auth-service.
    Compatible avec les permissions DRF (is_authenticated, is_staff, is_superuser).
    """

    def __init__(self, user_id, identifiant_ad=None, is_staff=False, is_superuser=False):
        self.id = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        self.identifiant_ad = identifiant_ad
        self.is_staff = bool(is_staff)
        self.is_superuser = bool(is_superuser)
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return str(self.id)


class ServiceJWTAuthentication(JWTAuthentication):
    """
    Authentifie les requêtes via un JWT RS256 émis par l'auth-service.

    Utilise la clé publique de l'auth-service pour vérifier la signature ;
    aucun secret partagé n'est nécessaire (asymétrique).
    La clé publique est lue depuis le chemin défini par JWT_PUBLIC_KEY_PATH
    (par défaut : keys/public.pem à la racine du projet).
    """

    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")
        if user_id is None:
            raise InvalidToken("Le claim 'user_id' est absent du token.")

        identifiant_ad = validated_token.get("identifiant_ad")
        is_staff = validated_token.get("is_staff", False)
        is_superuser = validated_token.get("is_superuser", False)

        try:
            return RemoteUser(
                user_id=user_id,
                identifiant_ad=identifiant_ad,
                is_staff=is_staff,
                is_superuser=is_superuser,
            )
        except (ValueError, AttributeError) as exc:
            raise AuthenticationFailed(f"user_id invalide dans le token : {exc}") from exc
