"""
Configuration Active Directory / LDAP pour l'authentification des employes Ooredoo.
"""

from decouple import config

LDAP_SERVER_URI = config("LDAP_SERVER_URI", default="ldap://REMPLACER_ADRESSE_AD:389")
LDAP_BASE_DN = config("LDAP_BASE_DN", default="DC=REMPLACER,DC=dz")
LDAP_BIND_DN = config("LDAP_BIND_DN", default="CN=svc-doc-platform,OU=Services,DC=ooredoo,DC=dz")
LDAP_BIND_PASSWORD = config("LDAP_BIND_PASSWORD", default="REMPLACER_MOT_DE_PASSE")
LDAP_USER_ID_ATTRIBUTE = config("LDAP_USER_ID_ATTRIBUTE", default="sAMAccountName")
LDAP_EMAIL_ATTRIBUTE = config("LDAP_EMAIL_ATTRIBUTE", default="mail")
LDAP_CONNECT_TIMEOUT = 5