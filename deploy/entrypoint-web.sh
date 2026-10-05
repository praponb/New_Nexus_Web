#!/usr/bin/env bash
# Nexus `web` container: apply migrations, collect static files, then serve REST + WebSockets.
set -euo pipefail
cd /app/backend
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
exec python -m daphne --proxy-headers -b 0.0.0.0 -p 8000 nexus_backend.asgi:application
