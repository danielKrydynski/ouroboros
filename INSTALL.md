# Ouroboros — Install & Operations Guide

This is the complete guide: prerequisites, installation on Windows / macOS /
Linux, model selection, configuration, your first cycle, scheduling,
troubleshooting, and security. If an AI agent is helping you, have it read
`setup/agent-setup.md` alongside this file.

---

## 1. What you need

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.10+ | `python --version` |
| git | 2.30+ | `git --version` |
| Ollama | running | `ollama list` — see §4 |
| A product repo | git, with tests | the codebase the loop improves |
| Disk | ~1 GB + models | models live in Ollama, not here |

Optional:

- **OpenRouter API key** — cloud fallback when a local model call fails.
  The loop runs fine without it (local-only), it just can't fall back.
- **Discord webhook URL** — cycle results posted to a channel.

Ouroboros itself needs almost nothing: `pip install -r requirements.txt`
installs `pyyaml` and `requests`.

---

## 2. Install

### Layout

The loop lives **next to** your product repo, never inside it:

```
C:\dev\                      ~/dev/
├── my-project\              ├── my-project/      ← product repo (has .git)
└── ouroboros\               └── ouroboros/        ← this repo
```

### Windows (PowerShell)

```powershell
git clone https://github.com/danielKrydynski/ouroboros.git
cd ouroboros
.\setup\setup.ps1
```

The bootstrap script checks Python, git, and Ollama, installs Python
dependencies, and prints what to do next. If you'd rather do it by hand:

```powershell
pip install -r requirements.txt
```

### macOS / Linux (bash)

```bash
git clone https://github.com/danielKrydynski/ouroboros.git
cd ouroboros
./setup/setup.sh
# or by hand:
pip install -r requirements.txt
chmod +x run_cycle.sh run_scout.sh
```

---

## 3. Get Ollama ready

Ouroboros talks to Ollama at `http://localhost:11434` (configurable in
`harness/config.yaml`). Make sure the Ollama app/service is running, then
pull the models you want:

```bash
ollama list          # what you already have
ollama pull qwen3:30b
ollama pull qwen3-coder:30b
```

### How big a model can you run?

At Q4 quantization, a model needs roughly **0.55–0.65 GB per billion
parameters** of VRAM for full GPU offload. Ollama will spill overflow into
system RAM — it still works, just slower.

| Model size | VRAM (Q4) | Fits comfortably |
|---|---|---|
| 7–8B | ~5 GB | any gaming GPU |
| 14B | ~9 GB | 12 GB+ VRAM |
| 30–32B | ~19–21 GB | 16 GB VRAM + RAM offload, or 24 GB VRAM |

On a 16 GB VRAM card (e.g. RTX 5070 Ti): a 14B model flies fully on-GPU;
a 30B model runs with partial RAM offload — usable, noticeably slower.
A practical starting split: **14B-class for scout/reviewer** (judgment is
cheap) and the **largest coder model that fits for the implementer**.

The defaults in `config.yaml` assume ~30B models; if that's too heavy,
point every role at a 14B model to start and scale up later.

### Optional: OpenRouter fallback

```powershell
# Windows (PowerShell) — persists for your user
setx OPENROUTER_API_KEY "sk-or-..."
# macOS/Linux — add to ~/.bashrc or ~/.zshrc
export OPENROUTER_API_KEY="sk-or-..."
```

Then set `models.cloud_fallback.model` in `config.yaml` to the model you
want (the default is a strong generalist). Without the key, the loop is
local-only and says so at startup.

---

## 4. Configure

Everything machine-specific lives in **`harness/config.yaml`**. Open it and
set these five things:

| Key | What to put |
|---|---|
| `project.name` | Short name of your product repo, e.g. `my-project`. Agents see this in prompts. |
| `project.description` | 1–2 sentences: what it does, its stack, who it's for. |
| `product_repo` | **Full path** to your product repo, e.g. `C:/dev/my-project` or `/home/you/dev/my-project`. Forward slashes work on Windows too. |
| `models.local.*` | Model names **exactly as `ollama list` shows them** (`qwen3:30b`, not `qwen3`). Each role can use a different model. |
| `gates.test_command` | The command that runs your product repo's test suite, e.g. `pytest -q`, `npm test`, `go test ./...`, `dotnet test`. It must exit 0 on success. |

The rest of the knobs:

- **`planner.enabled_for_feature_tickets`** — runs a planning pass before
  the implementer on `type: feature` tickets. Leave on.
- **`budgets`** — `max_iterations_per_ticket` (12): implementer turns before
  the ticket is marked blocked. `max_review_rounds` (2) / `max_fix_iters_per_round`
  (3): reviewer strictness. `test_timeout_seconds` (600): kill runaway tests.
- **`gates.require_human_approval_for_merge`** — **leave `true`** until
  several manual cycles succeed. `--yes` skips the prompt per-run.
- **`gates.protected_paths`** — files the implementer can never write
  (`.env`, `secrets/` by default). Add your own.
- **`notifications.discord_webhook`** — optional Discord channel posts.

> Validate your config any time with:
> `python -c "import yaml; c=yaml.safe_load(open('harness/config.yaml')); print(c['product_repo'], c['gates']['test_command'])"`

---

## 5. First cycle (smoke test)

`tickets/TICKET-001.md` is a docs-only ticket: it asks the loop to write a
`docs/ARCHITECTURE.md` stub in your product repo. It exercises the entire
pipeline (worktree → implement → test → review → merge) without touching
code behavior.

```powershell
.\run_cycle.bat
# macOS/Linux:
./run_cycle.sh
```

What a healthy run looks like:

1. The implementer proposes `docs/ARCHITECTURE.md`; tests run green.
2. The reviewer prints analysis ending in `VERDICT: APPROVE`.
3. You're asked `Merge loop/ticket-001 into main? [y/N]` — say `y`.
4. `tickets/TICKET-001.md` flips to `status: done`; `CYCLE_LOG.md` gains an entry.

Then **delete or supersede TICKET-001** and let the Scout build the real
backlog:

```powershell
.\run_scout.bat
```

Curate what it proposes in `tickets/` — reprioritize, or set `status: dropped`
on won't-dos. The orchestrator always picks the highest-priority `open` ticket.

---

## 6. Scheduling

Start manual. Automate only after several successful attended cycles.

**Windows — Task Scheduler**

1. Task Scheduler → Create Task → run whether user is logged on or not.
2. Trigger: Daily, e.g. 2:00 AM.
3. Action: Start a program → `C:\dev\ouroboros\run_cycle.bat`
   with "Start in" = `C:\dev\ouroboros`.
4. Keep `require_human_approval_for_merge: true` — the task will wait at the
   prompt; use `--yes` in the action arguments only once you trust it, and
   add a Discord webhook so you see results in the morning.

**Linux — cron**

```bash
crontab -e
# 2 AM daily, logs to a file:
0 2 * * * cd /home/you/dev/ouroboros && ./run_cycle.sh >> cycle-cron.log 2>&1
```

**Linux — systemd timer** or **macOS — launchd**: same idea — run
`run_cycle.sh` on a schedule, capture stdout to a log.

> ⚠️ Unattended `--yes` merges are the "let go" phase. Earn it: watch at
> least 3–5 clean manual cycles first, keep the Discord webhook on, and
> review `CYCLE_LOG.md` weekly.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `product_repo is not a git repo` | Path wrong in config | Check `product_repo` — full path, forward slashes OK on Windows |
| `Local model '…' failed … no OPENROUTER_API_KEY` | Ollama not running, or model name wrong | Start Ollama; `ollama list` and copy names exactly |
| Implementer loops proposing nothing | Ticket too vague, or model too small | Tighten acceptance criteria; try a bigger model for `implementer` |
| `Tests FAILED` every iteration | Test command wrong for the repo | Run `gates.test_command` by hand in the product repo first |
| `git checkout main` fails at merge | Dirty working tree in product repo | Commit/stash your own changes; the loop needs a clean checkout |
| Merge conflict at `--no-ff` | `main` moved during the cycle | Resolve manually, or re-run the cycle (fresh worktree) |
| Reviewer rejects everything | Diff too large / prompt mismatch | Shrink ticket scope; check `budgets.max_diff_chars` |
| `VERDICT` never parsed | Reviewer model ignoring format | Try a stronger `reviewer` model; unparseable verdicts count as REJECT |
| Stale `worktrees/` entries | Crashed run | Next cycle cleans them automatically (`worktree prune`) |

---

## 8. Security model

- Workers only ever see: the ticket, repo file list, `area` file contents,
  test output, diffs. **Never** your env, your other files, or your secrets.
- `protected_paths` + `..`/absolute-path rejection are enforced in code
  (`apply_files`), not in prompts.
- The loop never commits secrets: prompts forbid it, and `protected_paths`
  blocks the usual suspects. Still, **review diffs before merging** —
  that's what the human gate is for.
- `config.yaml` holds no secrets (the OpenRouter key lives in an env var).
  Don't put tokens in it.

## 9. Upgrading & uninstall

- **Upgrade**: `git pull` in the ouroboros repo. Your `config.yaml`,
  `tickets/`, and `CYCLE_LOG.md` are yours — back them up before pulling
  if you've customized prompts.
- **Uninstall**: delete the ouroboros folder. Your product repo keeps every
  merged change (normal git history); just delete any leftover `loop/*`
  branches you don't want.

---

## 10. Getting help

- `setup/agent-setup.md` — the same setup, written as a checkable procedure
  for an AI assistant.
- `AGENTS.md` — how the repo is organized, for agents contributing to it.
- Open an issue on GitHub with your `CYCLE_LOG.md` entry and the ticket file.
