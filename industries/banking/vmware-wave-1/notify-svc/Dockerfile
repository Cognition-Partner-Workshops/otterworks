FROM docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS test
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY src src
COPY test test
RUN npm test

FROM docker.io/library/node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS runtime
RUN apt-get update && apt-get install -y --only-upgrade libgnutls30 perl-base \
    && rm -rf /var/lib/apt/lists/* \
        /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
        /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack
WORKDIR /app
COPY --from=test /app/node_modules node_modules
COPY package.json ./
COPY src src
USER 10001:10001
EXPOSE 3000
CMD ["node","src/server.js"]
