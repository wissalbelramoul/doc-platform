from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken as SimpleJWTRefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import AuthCredential, AuthHistory
from .serializers import LoginSerializer, LogoutSerializer

MAX_TENTATIVES = 5
DUREE_VERROUILLAGE = timedelta(minutes=15)


def get_client_ip(request):
    return request.META.get("REMOTE_ADDR")


class LoginView(APIView):
    """
    POST /auth/login
    Vérifie email/mot de passe, gère le verrouillage après échecs répétés,
    retourne access + refresh token (RS256).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        try:
            credential = AuthCredential.objects.get(email=email)
        except AuthCredential.DoesNotExist:
            credential = None

        # Vérifier le verrouillage avant même de valider le mot de passe
        if credential and credential.verrouille_jusqu_a and credential.verrouille_jusqu_a > timezone.now():
            AuthHistory.objects.create(
                user_id=credential.user_id, action="login_failed",
                ip_adresse=ip, user_agent=user_agent,
            )
            return Response(
                {"detail": "Compte temporairement verrouillé suite à trop de tentatives."},
                status=status.HTTP_423_LOCKED,
            )

        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            if credential:
                credential.tentatives_echouees += 1
                if credential.tentatives_echouees >= MAX_TENTATIVES:
                    credential.verrouille_jusqu_a = timezone.now() + DUREE_VERROUILLAGE
                    AuthHistory.objects.create(
                        user_id=credential.user_id, action="account_locked",
                        ip_adresse=ip, user_agent=user_agent,
                    )
                credential.save()
                AuthHistory.objects.create(
                    user_id=credential.user_id, action="login_failed",
                    ip_adresse=ip, user_agent=user_agent,
                )
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        credential = serializer.validated_data["credential"]

        # Succès : réinitialiser les compteurs
        credential.tentatives_echouees = 0
        credential.verrouille_jusqu_a = None
        credential.derniere_connexion = timezone.now()
        credential.save()

        # Génération des tokens RS256 — le user_id custom est injecté dans les claims
        refresh = SimpleJWTRefreshToken()
        refresh["user_id"] = str(credential.user_id)
        refresh["email"] = credential.email
        access = refresh.access_token

        AuthHistory.objects.create(
            user_id=credential.user_id, action="login_success",
            ip_adresse=ip, user_agent=user_agent,
        )

        return Response({
            "access": str(access),
            "refresh": str(refresh),
            "user_id": str(credential.user_id),
        }, status=status.HTTP_200_OK)


class CustomTokenRefreshView(TokenRefreshView):
    """
    POST /auth/refresh
    Réutilise la vue standard de simplejwt (gère déjà la rotation
    et le blacklist grâce à ROTATE_REFRESH_TOKENS=True).
    Ajout d'une trace dans AuthHistory.
    """

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
    """
    POST /auth/logout
    Blackliste le refresh token fourni pour empêcher sa réutilisation.
    """
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
    """
    POST /auth/verify
    Endpoint interne : permet aux autres microservices ou à l'API Gateway
    de vérifier un token — utile si vous ne distribuez pas la clé publique
    partout, sinon la vérification RS256 peut se faire localement sans appel réseau.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({
            "valid": True,
            "user_id": str(request.user_id) if hasattr(request, "user_id") else None,
        }, status=status.HTTP_200_OK)