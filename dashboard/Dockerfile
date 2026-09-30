# Home hub web app plus the old kiosk carousel, served by Caddy on :8083.
# Build context is the repo root (see the CI workflow).

FROM node:26-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM caddy:2-alpine

COPY caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /web/dist/ /srv/web/
COPY dashboard/ /srv/kiosk/

# Development-only files that should not be served.
RUN rm -f /srv/kiosk/Dockerfile /srv/kiosk/serve.py

EXPOSE 8083
