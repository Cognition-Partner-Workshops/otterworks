#!/usr/bin/env bash
docker rm -f auth-char-svc auth-char-pg >/dev/null 2>&1 || true
docker network rm auth-char-net >/dev/null 2>&1 || true
