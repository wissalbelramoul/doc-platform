import uuid
from django.db import models


class AuthCredential(models.Model):
    """
    Table de correspondance entre l'identité Active Directory (source de vérité
    pour le mot de passe) et notre identifiant interne user_id (UUID) utilisé
    dans tout le reste de l'architecture microservices.

    Le mot de passe n'est JAMAIS stocké ici : il est vérifié en direct auprès
    de l'AD à chaque connexion (voir ldap_service.py).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True, db_index=True)
    identifiant_ad = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True, null=True, blank=True)
    nom_complet = models.CharField(max_length=255, null=True, blank=True)
    actif = models.BooleanField(default=True)
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_credentials"

    def __str__(self):
        return self.identifiant_ad


class RefreshToken(models.Model):
    """
    Stocke les refresh tokens émis, sous forme hashée (jamais en clair),
    pour permettre la révocation et la rotation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    token_hash = models.CharField(max_length=255, unique=True)
    date_expiration = models.DateTimeField()
    revoque = models.BooleanField(default=False)
    ip_creation = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"

    def __str__(self):
        return f"RefreshToken({self.user_id})"


class AuthHistory(models.Model):
    """
    Journal des événements d'authentification, utile pour l'audit
    et la détection d'activité suspecte.
    """
    ACTION_CHOICES = [
        ("login_success", "Connexion réussie"),
        ("login_failed", "Échec de connexion"),
        ("logout", "Déconnexion"),
        ("token_refresh", "Rafraîchissement de token"),
        ("password_reset", "Réinitialisation de mot de passe"),
        ("account_locked", "Compte verrouillé"),
    ]

    id = models.BigAutoField(primary_key=True)
    user_id = models.UUIDField(db_index=True, null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    ip_adresse = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_history"
        ordering = ["-date_action"]

    def __str__(self):
        return f"{self.action} - {self.user_id} - {self.date_action}"
    