# ---------------------------------------------------------------------------
# Nexus frontend: the Nuxt SPA (ssr: false) is generated to static files and served by nginx,
# which also proxies /api/, /admin/, /ws/ and /static/ to the backend.
# NUXT_PUBLIC_* are baked into the generated pages, so they are build args.
# Build context: the repository root (see docker-compose.prod.yml).
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS build
ARG NUXT_PUBLIC_API_BASE
ARG NUXT_PUBLIC_WS_BASE
ENV NUXT_PUBLIC_API_BASE=${NUXT_PUBLIC_API_BASE} \
    NUXT_PUBLIC_WS_BASE=${NUXT_PUBLIC_WS_BASE} \
    NUXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npx nuxt generate

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/.output/public /usr/share/nginx/html
