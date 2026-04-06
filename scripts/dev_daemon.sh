#!/usr/bin/env bash
# Dev loop: run the NIO dashboard in foreground for development
set -euo pipefail

cd "$(dirname "$0")/.."
echo "Starting NIO dashboard on http://localhost:4242"
python -m nio.dash.server
