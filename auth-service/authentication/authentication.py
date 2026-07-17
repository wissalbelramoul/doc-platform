from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTUser:
    """
    Objet utilisateur leger reconstruit a partir du contenu du token JWT,
    sans requete vers une table Django User (qui n'existe pas dans ce microservice).
    """
    def __init__(self, user_id, identifiant_ad=None):
        self.user_id = user_id
        self.identifiant_ad = identifiant_ad
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return str(self.user_id)


class CustomJWTAuthentication(JWTAuthentication):
    """
    Authentification JWT qui ne verifie PAS l'existence d'un utilisateur
    en base (pas de modele User classique ici). Le token signe RS256
    suffit a etablir la confiance.
    """
    def get_user(self, validated_token):
        user_id = validated_token.get("user_id")
        if user_id is None:
            return None
        identifiant_ad = validated_token.get("identifiant_ad")
        return JWTUser(user_id=user_id, identifiant_ad=identifiant_ad)
