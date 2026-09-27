@echo off
REM Ouroboros — audit the product repo and propose new tickets into tickets\.
setlocal
cd /d "%~dp0"
if not defined OPENROUTER_API_KEY (
  echo [ouroboros] OPENROUTER_API_KEY not set - cloud fallback disabled, local only.
)
python harness\scout.py %*
