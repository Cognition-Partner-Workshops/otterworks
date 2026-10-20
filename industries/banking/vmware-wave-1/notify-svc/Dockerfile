# notify-svc on the platform Node base. The test stage installs the locked
# dependencies and runs the unit tests; the runtime stage carries only the
# production dependencies and src/. One process per container, logs on stdout.
FROM docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS test
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY src src
COPY test test
RUN npm test

FROM docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0
ENV NODE_ENV=production PORT=8080
WORKDIR /app
# Pick up Debian security fixes newer than the pinned base, install the
# production dependencies, then drop npm/yarn: the runtime only needs node.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
       /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /opt/yarn-* \
       /usr/local/bin/yarn /usr/local/bin/yarnpkg /root/.npm
COPY src src
USER 10001
EXPOSE 8080
CMD ["node", "src/server.js"]
