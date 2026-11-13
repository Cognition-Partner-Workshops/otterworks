FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5 AS builder

WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci
COPY src ./src
RUN npm run build

FROM node:24-alpine@sha256:116b800c3754b440ee0aa3ed2f20f5bf3d99a554bfd9adeea09ea8017f6e85f5
RUN apk --no-cache upgrade && apk --no-cache add curl
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./

RUN adduser -D -u 1001 appuser
USER appuser

EXPOSE 8084
HEALTHCHECK --interval=10s --timeout=3s CMD curl -f http://localhost:8084/health || exit 1
CMD ["node", "dist/index.js"]
