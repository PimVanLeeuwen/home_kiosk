# Static dashboard served by Caddy, which also proxies /api to the collector.
# Build context is the repo root, so the Caddyfile comes along.

FROM caddy:2-alpine

COPY caddy/Caddyfile /etc/caddy/Caddyfile
COPY dashboard/ /srv/

# Not needed at runtime and only confuses things once the collector is live.
RUN rm -f /srv/Dockerfile

EXPOSE 8083
