#!/bin/bash
set -e

echo "==> Waiting for PostgreSQL..."
until python - <<'PYEOF'
import socket, os, sys
try:
    s = socket.create_connection(
        (os.environ.get('DB_HOST', 'db'), int(os.environ.get('DB_PORT', 5432))),
        timeout=1
    )
    s.close()
except Exception:
    sys.exit(1)
PYEOF
do
    echo "    still waiting..."
    sleep 2
done
echo "==> Database is ready."

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if env vars are set (first-time setup)
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "==> Creating superuser (if not exists)..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
email = '$DJANGO_SUPERUSER_EMAIL'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password='$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created: ' + email)
else:
    print('Superuser already exists: ' + email)
"
fi

echo "==> Starting application at http://localhost:8000"
exec "$@"
