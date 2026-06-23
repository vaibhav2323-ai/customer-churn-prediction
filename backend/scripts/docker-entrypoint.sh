#!/bin/sh
# docker-entrypoint.sh
# Runs as root to fix volume permissions, then drops to appuser (uid 1001).
set -e

DATA_DIR="${DATA_DIR:-/app/data}"

# Ensure the data volume (SQLite) is writable by appuser
mkdir -p "$DATA_DIR"
chown -R 1001:1001 "$DATA_DIR"

# Seed demo data as the non-root user
gosu 1001 python -m scripts.seed

# Hand off to the main process as the non-root user
exec gosu 1001 "$@"
