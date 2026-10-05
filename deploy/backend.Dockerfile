# ---------------------------------------------------------------------------
# Nexus backend image, shared by the `web` (Daphne) and `worker` (Celery) services.
# The worker runs the QA tooling for generated apps (python -m venv, npm install, npx nuxi build,
# npx @playwright/mcp), so the image carries Python 3.12, Node 20 and Playwright Chromium.
# Build context: the repository root (see docker-compose.prod.yml).
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NUXT_TELEMETRY_DISABLED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 nexus

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Chromium + its system libraries for the QA agent's @playwright/mcp.
RUN npx -y playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/* /root/.npm

COPY backend /app/backend
COPY deploy/entrypoint-web.sh /app/deploy/entrypoint-web.sh
RUN mkdir -p /app/media/workspaces /app/static /app/logs \
    && chown -R nexus:nexus /app/media /app/static /app/logs

USER nexus
# Pre-fetch the MCP servers into the nexus user's npm cache (as setup_environment.sh step 6 does).
RUN npx -y @playwright/mcp@latest --version >/dev/null 2>&1 || true; \
    for pkg in @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-sequential-thinking; do \
      npm cache add "$pkg" >/dev/null 2>&1 || true; \
    done

WORKDIR /app/backend
EXPOSE 8000
CMD ["/app/deploy/entrypoint-web.sh"]
