FROM node:22.23.5-alpine AS builder

ARG VITE_COLLAB_WS_URL=ws://localhost:8084
ENV VITE_COLLAB_WS_URL=$VITE_COLLAB_WS_URL

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM ghcr.io/nginx/nginx-unprivileged:1.30.7-alpine
USER 0
RUN apk upgrade --no-cache
USER 101
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

# API_GATEWAY_URL default for runtime (can be overridden by Helm/docker-compose env);
# substituted into the nginx config template at container start.
ENV API_GATEWAY_URL=http://api-gateway:8080
