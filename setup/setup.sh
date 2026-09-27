#!/usr/bin/env bash
# Ouroboros bootstrap — macOS / Linux.
# Checks prerequisites, installs Python dependencies, prints next steps.
# Safe to re-run.
set -uo pipefail

cd "$(dirname "$0")/.."
FAILED=0

ok()   { echo "  [ok] $1"; }
warn() { echo "  [warn] $1"; echo "  -> $2"; }
need() { echo "  [missing] $1"; echo "  -> $2"; FAILED=1; }

echo ""
echo "Ouroboros setup"
echo "---------------"

# --- Python ---
if command -v python3 >/dev/null 2>&1; then
  PYV=$(python3 --version 2>&1)
  MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
  MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
  if [ "$MAJOR" -gt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; }; then
    ok "$PYV"
  else
    need "Python 3.10+" "Install a newer Python (found: $PYV)"
  fi
else
  need "Python 3.10+" "Install from https://www.python.org/downloads/"
fi

# --- git ---
if command -v git >/dev/null 2>&1; then
  ok "$(git --version)"
else
  need "git" "Install via your package manager (apt install git / brew install git)"
fi

# --- Ollama ---
if command -v ollama >/dev/null 2>&1 && ollama list 2>/dev/null | grep -q "NAME"; then
  ok "Ollama is reachable. Models:"
  ollama list
else
  warn "Ollama not reachable or no models pulled." \
       "Install from https://ollama.com then: ollama pull qwen3:30b (see INSTALL.md section 4)"
fi

# --- Python deps ---
echo ""
echo "Installing Python dependencies..."
if python3 -m pip install -r requirements.txt && python3 -c "import yaml, requests" 2>/dev/null; then
  ok "deps importable"
else
  need "Python deps" "pip install failed — see output above"
fi

echo ""
if [ "$FAILED" -ne 0 ]; then
  echo "Fix the missing items above, then re-run this script."
  exit 1
fi

echo "Next steps:"
echo "  1. Edit harness/config.yaml — project.name, product_repo, model names, test command"
echo "  2. Smoke test: ./run_cycle.sh"
echo "  3. Full guide: INSTALL.md   |   Agent-assisted setup: setup/agent-setup.md"
echo ""
echo "Done."
