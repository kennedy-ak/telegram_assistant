#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! python manage.py check --database default; do
  echo "Database is unavailable - sleeping"
  sleep 2
done
echo "Database is ready!"

# Run migrations
echo "Running database migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Collect static files (if needed)
echo "Collecting static files..."
python manage.py collectstatic --noinput || true

# Create logs directory
mkdir -p /app/logs

# Start the appropriate service based on the command
case "$1" in
    "bot")
        echo "Starting Telegram Bot..."
        python manage.py start_bot
        ;;
    "celery")
        echo "Starting Celery Worker..."
        celery -A telegram_assistant worker -l info
        ;;
    "celery-beat")
        echo "Starting Celery Beat..."
        celery -A telegram_assistant beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    "web")
        echo "Starting Django Web Server..."
        python manage.py runserver 0.0.0.0:8000
        ;;
    *)
        echo "Unknown command: $1"
        echo "Available commands: bot, celery, celery-beat, web"
        exit 1
        ;;
esac