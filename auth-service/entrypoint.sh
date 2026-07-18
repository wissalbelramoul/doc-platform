#!/bin/sh
set -e

echo "Attente de la base de donnees..."
until python manage.py migrate --check > /dev/null 2>&1 || python manage.py migrate; do
  echo "En attente de auth-db..."
  sleep 2
done

echo "Migrations appliquees avec succes."

echo "Demarrage du serveur Django..."
exec python manage.py runserver 0.0.0.0:8001
