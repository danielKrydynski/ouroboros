#!/usr/bin/env bash
# Ouroboros — audit the product repo and propose new tickets into tickets/.
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "[ouroboros] OPENROUTER_API_KEY not set - cloud fallback disabled, local only."
fi
python3 harness/scout.py "$@"
