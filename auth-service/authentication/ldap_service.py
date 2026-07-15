"""
Service d'authentification contre Active Directory / LDAP.

Principe (bind authentication) :
1. On se connecte d'abord avec un compte de service pour RECHERCHER
   l'utilisateur dans l'annuaire (on ne connait que son identifiant, pas son DN complet).
2. Une fois son DN trouve, on tente une seconde connexion (bind) avec
   CE DN et le mot de passe fourni par l'employe.
3. Si ce second bind reussit -> les identifiants sont valides.
"""

from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError

from django.conf import settings


class LDAPAuthenticationError(Exception):
    """Levee quand l'authentification LDAP echoue (identifiants invalides)."""
    pass


class LDAPConnectionError(Exception):
    """Levee quand l'annuaire AD est injoignable (probleme reseau/serveur)."""
    pass


def authenticate_against_ad(identifiant: str, password: str) -> dict:
    """
    Verifie les identifiants aupres de l'Active Directory Ooredoo.

    Retourne un dictionnaire avec les infos de l'utilisateur si succes.
    Leve LDAPAuthenticationError si les identifiants sont invalides.
    Leve LDAPConnectionError si l'AD est injoignable.
    """
    server = Server(
        settings.LDAP_SERVER_URI,
        get_info=ALL,
        connect_timeout=settings.LDAP_CONNECT_TIMEOUT,
    )

    try:
        service_conn = Connection(
            server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_BIND_PASSWORD,
            auto_bind=True,
        )
    except LDAPException as e:
        raise LDAPConnectionError(f"Impossible de se connecter a l'annuaire AD : {e}")

    search_filter = f"({settings.LDAP_USER_ID_ATTRIBUTE}={identifiant})"
    service_conn.search(
        search_base=settings.LDAP_BASE_DN,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=[settings.LDAP_USER_ID_ATTRIBUTE, settings.LDAP_EMAIL_ATTRIBUTE, "cn"],
    )

    if not service_conn.entries:
        service_conn.unbind()
        raise LDAPAuthenticationError("Identifiant introuvable dans l'annuaire.")

    entry = service_conn.entries[0]
    user_dn = entry.entry_dn
    email = str(getattr(entry, settings.LDAP_EMAIL_ATTRIBUTE, "")) or None
    nom_complet = str(getattr(entry, "cn", "")) or identifiant

    service_conn.unbind()

    try:
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()
    except LDAPBindError:
        raise LDAPAuthenticationError("Identifiant ou mot de passe incorrect.")
    except LDAPException as e:
        raise LDAPConnectionError(f"Erreur lors de la verification : {e}")

    return {
        "identifiant": identifiant,
        "email": email,
        "nom_complet": nom_complet,
    }