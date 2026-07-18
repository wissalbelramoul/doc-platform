#!/bin/bash
set -e

echo "Running database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting Document Service..."
exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class sync \
    --worker-connections 100 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    config.wsgi:application
