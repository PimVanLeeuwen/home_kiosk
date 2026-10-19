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
# The desk panels' firmware for updates over Wi-Fi, when CI has built it
# (panels/dist holds only placeholders in a local build).
COPY panels/dist/ /srv/panels/

# Development-only files that should not be served.
RUN rm -f /srv/kiosk/Dockerfile /srv/kiosk/serve.py /srv/panels/.gitignore /srv/panels/.gitkeep

EXPOSE 8083
