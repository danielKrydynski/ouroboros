# Ouroboros bootstrap — Windows PowerShell.
# Checks prerequisites, installs Python dependencies, prints next steps.
# Safe to re-run.
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Ouroboros setup" -ForegroundColor Cyan
Write-Host "---------------"

function Need($Name, $Hint) {
  Write-Host "  [missing] $Name" -ForegroundColor Red
  Write-Host "  -> $Hint"
  $script:failed = $true
}
$failed = $false

# --- Python ---
try {
  $pyv = (python --version 2>&1).ToString()
  if ($pyv -match "Python (\d+)\.(\d+)") {
    $major = [int]$Matches[1]; $minor = [int]$Matches[2]
    if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
      Write-Host "  [ok] $pyv" -ForegroundColor Green
    } else {
      Need "Python 3.10+" "Install from https://www.python.org/downloads/ (found: $pyv)"
    }
  } else { Need "Python 3.10+" "Install from https://www.python.org/downloads/" }
} catch { Need "Python 3.10+" "Install from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'" }

# --- git ---
try {
  $gv = (git --version 2>&1).ToString()
  Write-Host "  [ok] $gv" -ForegroundColor Green
} catch { Need "git" "Install from https://git-scm.com/download/win" }

# --- Ollama ---
try {
  $models = (ollama list 2>&1 | Out-String)
  if ($models -match "NAME") {
    Write-Host "  [ok] Ollama is reachable. Models:" -ForegroundColor Green
    Write-Host $models
  } else {
    Write-Host "  [warn] Ollama ran but no models are pulled." -ForegroundColor Yellow
    Write-Host "  -> Run: ollama pull qwen3:30b   (see INSTALL.md section 4 for sizing)"
  }
} catch {
  Write-Host "  [warn] Ollama not reachable." -ForegroundColor Yellow
  Write-Host "  -> Install from https://ollama.com and pull a model, e.g.: ollama pull qwen3:30b"
}

# --- Python deps ---
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
python -m pip install -r (Join-Path $PSScriptRoot ".." "requirements.txt")
python -c "import yaml, requests; print('  [ok] deps importable')" 2>$null
if ($LASTEXITCODE -ne 0) { Need "Python deps" "pip install failed — see output above" }

Write-Host ""
if ($failed) {
  Write-Host "Fix the missing items above, then re-run this script." -ForegroundColor Red
  exit 1
}

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit harness\config.yaml — project.name, product_repo, model names, test command"
Write-Host "  2. Smoke test: .\run_cycle.bat"
Write-Host "  3. Full guide: INSTALL.md   |   Agent-assisted setup: setup\agent-setup.md"
Write-Host ""
Write-Host "Done." -ForegroundColor Green
