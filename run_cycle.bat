@echo off
REM Ouroboros — run one recursive-dev-loop cycle.
REM Usage: run_cycle.bat [--ticket TICKET-003] [--yes]
setlocal
cd /d "%~dp0"
if not defined OPENROUTER_API_KEY (
  echo [ouroboros] OPENROUTER_API_KEY not set - cloud fallback disabled, local only.
)
python harness\orchestrator.py %*
