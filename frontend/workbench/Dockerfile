FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts
COPY . .
ENV VITE_WORKBENCH_MODE=hosted
RUN npm run build && npm run build:server

FROM node:20-alpine

ENV NODE_ENV=production PORT=3002
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --omit=dev --ignore-scripts \
  && addgroup -S workbench \
  && adduser -S -G workbench workbench
COPY --from=build --chown=workbench:workbench /app/dist ./dist
COPY --from=build --chown=workbench:workbench /app/server/dist ./server/dist

USER workbench
EXPOSE 3002
HEALTHCHECK --interval=10s --timeout=3s CMD node -e "fetch('http://127.0.0.1:3002/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server/dist/index.js"]
