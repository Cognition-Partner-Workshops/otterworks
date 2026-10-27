ARG BUILD_IMAGE=public.ecr.aws/docker/library/node:22-alpine
ARG RUN_IMAGE=public.ecr.aws/nginx/nginx-unprivileged:1.27-alpine
FROM ${BUILD_IMAGE} AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_BASE=
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM ${RUN_IMAGE}
COPY <<'CONF' /etc/nginx/conf.d/default.conf
server {
    listen 8080;
    root /usr/share/nginx/html;
    location / {
        try_files $uri $uri/ /index.html;
    }
    location = /index.html {
        add_header Cache-Control "no-store";
    }
}
CONF
COPY --from=build /src/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
