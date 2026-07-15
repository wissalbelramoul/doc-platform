from rest_framework import serializers
from .models import AuthCredential


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            credential = AuthCredential.objects.get(email=data["email"])
        except AuthCredential.DoesNotExist:
            raise serializers.ValidationError("Email ou mot de passe incorrect.")

        if not credential.actif:
            raise serializers.ValidationError("Ce compte est désactivé.")

        if not credential.check_password(data["password"]):
            raise serializers.ValidationError("Email ou mot de passe incorrect.")

        data["credential"] = credential
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()