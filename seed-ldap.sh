#!/bin/sh
# Script à lancer UNE FOIS après "docker compose up", pour peupler
# l'annuaire LDAP de test avec un utilisateur fictif.
set -e

echo "Copie du fichier LDIF dans le conteneur test-ldap..."
docker cp auth-service/test_user.ldif test-ldap:/tmp/test_user.ldif

echo "Ajout de l'utilisateur de test dans l'annuaire..."
docker exec test-ldap ldapadd -x -D "cn=admin,dc=ooredoo-test,dc=local" -w admin123 -f /tmp/test_user.ldif

echo "Termine. Utilisateur de test : s.testeur / motdepasse123"
