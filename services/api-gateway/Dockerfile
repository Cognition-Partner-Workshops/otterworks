FROM golang:1.26-alpine@sha256:30b1e546a9c7fa3b747c2bdba3a0c7bdf3a02ebb4c5b8405d2f948d7e8aac4ec AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /bin/server ./cmd/server

FROM alpine:3.18.0
RUN apk --no-cache add ca-certificates wget
WORKDIR /app
COPY --from=builder /bin/server /app/server

RUN adduser -D -u 1001 appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD wget --spider -q http://localhost:8080/health || exit 1
ENTRYPOINT ["/app/server"]
