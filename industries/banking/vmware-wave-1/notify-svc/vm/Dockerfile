# Stand-in for notify-01: Node 12 under PM2 with Redis on the same box.
FROM docker.io/library/node:12-bullseye
COPY --from=docker.io/library/redis:6.2-bullseye /usr/local/bin/redis-server /usr/local/bin/redis-server
RUN npm install -g pm2@4.5.6 && mkdir -p /var/log/notify
WORKDIR /opt/notify-svc
COPY package.json package-lock.json ./
RUN npm ci --only=production
COPY ecosystem.config.js ./
COPY src src
EXPOSE 3000
CMD ["sh", "-c", "redis-server --daemonize yes && pm2-runtime start ecosystem.config.js --env production"]
