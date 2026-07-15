from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    # "identifiant" = le nom d'utilisateur Windows/AD de l'employé
    # (ex: "j.dupont" ou "jdupont", selon la convention Ooredoo)
    identifiant = serializers.CharField()
    password = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
