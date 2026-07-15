from django.utils import timezone

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken as SimpleJWTRefreshToken
from rest_framework_simplejwt.exceptions import TokenError

import uuid

from .models import AuthCredential, AuthHistory
from .serializers import LoginSerializer, LogoutSerializer
from .ldap_service import authenticate_against_ad, LDAPAuthenticationError, LDAPConnectionError


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    """
    POST /auth/login
    Vérifie l'identifiant/mot de passe directement auprès de l'Active
    Directory Ooredoo. Si valide, crée (première connexion) ou retrouve
    l'AuthCredential locale correspondante, puis émet les tokens JWT (RS256).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifiant = serializer.validated_data["identifiant"]
        password = serializer.validated_data["password"]
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        try:
            ad_user = authenticate_against_ad(identifiant, password)
        except LDAPAuthenticationError:
            AuthHistory.objects.create(action="login_failed", ip_adresse=ip, user_agent=user_agent)
            return Response(
                {"detail": "Identifiant ou mot de passe incorrect."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except LDAPConnectionError:
            return Response(
                {"detail": "Service d'authentification temporairement indisponible. Réessayez plus tard."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        credential, created = AuthCredential.objects.get_or_create(
            identifiant_ad=ad_user["identifiant"],
            defaults={
                "user_id": uuid.uuid4(),
                "email": ad_user["email"],
                "nom_complet": ad_user["nom_complet"],
            },
        )

        if not credential.actif:
            AuthHistory.objects.create(
                user_id=credential.user_id, action="login_failed", ip_adresse=ip, user_agent=user_agent,
            )
            return Response({"detail": "Ce compte est désactivé."}, status=status.HTTP_403_FORBIDDEN)

        credential.derniere_connexion = timezone.now()
        credential.email = ad_user["email"] or credential.email
        credential.nom_complet = ad_user["nom_complet"] or credential.nom_complet
        credential.save()

        refresh = SimpleJWTRefreshToken()
        refresh["user_id"] = str(credential.user_id)
        refresh["identifiant_ad"] = credential.identifiant_ad
        access = refresh.access_token

        AuthHistory.objects.create(
            user_id=credential.user_id, action="login_success", ip_adresse=ip, user_agent=user_agent,
        )

        if created:
            pass  # TODO: publier événement "UserFirstLogin" via RabbitMQ

        return Response({
            "access": str(access),
            "refresh": str(refresh),
            "user_id": str(credential.user_id),
            "nouveau_compte": created,
        }, status=status.HTTP_200_OK)


class CustomTokenRefreshView(TokenRefreshView):
    """POST /auth/refresh — inchangé, ne dépend pas de l'AD."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            AuthHistory.objects.create(
                action="token_refresh",
                ip_adresse=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        return response


class LogoutView(APIView):
    """POST /auth/logout — inchangé, blackliste juste le refresh token local."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = SimpleJWTRefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError:
            return Response({"detail": "Token invalide ou déjà révoqué."},
                             status=status.HTTP_400_BAD_REQUEST)

        AuthHistory.objects.create(
            action="logout",
            ip_adresse=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return Response({"detail": "Déconnexion réussie."}, status=status.HTTP_205_RESET_CONTENT)


class VerifyTokenView(APIView):
    """POST /auth/verify — inchangé."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({"valid": True}, status=status.HTTP_200_OK)
