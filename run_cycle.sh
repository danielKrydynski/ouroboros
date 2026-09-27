#!/usr/bin/env bash
# Ouroboros — run one recursive-dev-loop cycle.
# Usage: ./run_cycle.sh [--ticket TICKET-003] [--yes]
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "[ouroboros] OPENROUTER_API_KEY not set - cloud fallback disabled, local only."
fi
python3 harness/orchestrator.py "$@"
