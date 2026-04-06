#!/usr/bin/env bash
# Import existing Hermes SOUL.md into a NIO soul
set -euo pipefail

echo "Migrating Hermes SOUL.md to NIO..."
nio install --migrate-hermes
echo "Done. Run: nio soul list"
