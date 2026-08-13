# KUDOS ↔ opencode bridge sidecar
# Exposes a tiny HTTP API that runs `opencode run --agent …` on request, so the
# backend can delegate research of any subject to an opencode subagent.
FROM node:22-slim

# opencode-ai pins the native opencode binary — keep in sync with the CLI the
# campus host runs (opencode --version).
RUN npm install -g opencode-ai@1.18.16 --no-audit --no-fund

WORKDIR /app
COPY server.js /app/server.js

# The sidecar runs as its own user so a mounted auth.json can be read-only.
RUN useradd -m opencode && mkdir -p /home/opencode/.local/share/opencode/log \
    && chown -R opencode:opencode /home/opencode/.local/share/opencode
USER opencode
ENV HOME=/home/opencode

EXPOSE 8090
CMD ["node", "/app/server.js"]
