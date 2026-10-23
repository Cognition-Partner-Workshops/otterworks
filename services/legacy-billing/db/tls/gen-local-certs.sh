#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tls
if [[ ! -s /tls/ca.crt || ! -s /tls/server.crt || ! -s /tls/server.key ]]; then
  work_dir="$(mktemp -d)"
  trap 'rm -rf "$work_dir"' EXIT
  umask 077

  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$work_dir/ca.key" \
    -out /tls/ca.crt \
    -days 3650 \
    -sha256 \
    -subj "/CN=legacy-billing local throwaway CA"
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout /tls/server.key \
    -out "$work_dir/server.csr" \
    -subj "/CN=legacy-billing-db"
  printf '%s\n' \
    '[server_ext]' \
    'subjectAltName=DNS:legacy-billing-db,DNS:localhost,IP:127.0.0.1' \
    'extendedKeyUsage=serverAuth' > "$work_dir/server.ext"
  openssl x509 -req \
    -in "$work_dir/server.csr" \
    -CA /tls/ca.crt \
    -CAkey "$work_dir/ca.key" \
    -CAcreateserial \
    -out /tls/server.crt \
    -days 3650 \
    -sha256 \
    -extfile "$work_dir/server.ext" \
    -extensions server_ext
fi

chmod 0644 /tls/ca.crt /tls/server.crt
chown 999:999 /tls/server.key
chmod 0600 /tls/server.key
