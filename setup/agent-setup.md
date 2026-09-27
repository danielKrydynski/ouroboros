# Agent Setup Procedure — Ouroboros

> You are an AI assistant helping a human install and configure **Ouroboros**,
> a recursive dev-loop harness. Follow this procedure top to bottom. Each
> phase ends with a **verification gate** — do not proceed past a failed gate;
> fix it or ask the human.
>
> Conventions: exact commands are in `code blocks`. "Expect" lines describe
> the output that means success. Anything else means stop and diagnose.

## Phase 0 — Orientation (read-only)

Read these files, in order, before touching anything:

1. `README.md` — what Ouroboros is and how the loop works.
2. `INSTALL.md` — the full human guide (your reference for every step below).
3. `setup/manifest.json` — machine-readable metadata (entry points, config
   schema, prerequisites). Trust it over your assumptions.
4. `harness/config.yaml` — the current configuration, placeholders and all.

Do not edit code or prompts during setup. Configuration only.

## Phase 1 — Environment verification

Run each check. All must pass before Phase 2.

```bash
python --version
```
Expect: `Python 3.10` or higher (3.10.x, 3.11.x, …).

```bash
git --version
```
Expect: `git version 2.30` or higher.

```bash
ollama list
```
Expect: a table listing at least one pulled model. If the command is not
found or the list is empty, **stop** and tell the human: install Ollama
from https://ollama.com and run `ollama pull <model>` (see INSTALL.md §4
for sizing guidance). Record the exact model names — config must match
them character-for-character.

```bash
pip install -r requirements.txt
python -c "import yaml, requests; print('deps OK')"
```
Expect: `deps OK`.

**Gate 1:** Python ≥3.10, git ≥2.30, Ollama serving with ≥1 model, Python
deps importable. If any fail, resolve with the human before continuing.

## Phase 2 — Configuration

You need four facts. Some you can detect, some only the human knows:

| # | Fact | How to get it |
|---|---|---|
| 1 | Path to the **product repo** (the codebase the loop improves) | Ask the human. Must be a git repo: verify with `git -C <path> rev-parse --is-inside-work-tree` → expect `true`. |
| 2 | The repo's **test command** | Ask, or detect: `pytest -q` if `pytest.ini`/`pyproject.toml` with pytest exists; `npm test` if `package.json` has a test script. **Verify by running it** in the product repo and confirming exit 0 on a clean tree. Never guess — a wrong test command makes every cycle fail. |
| 3 | **Ollama model names** per role | From `ollama list` in Phase 1. Suggest: strongest coder model for `implementer`, mid-size for `scout`/`reviewer`/`planner`. Keep defaults if unsure. |
| 4 | Project **name + 1–2 sentence description** | Ask the human, or draft from the repo's README and confirm. |

Write them into `harness/config.yaml`:

- `project.name`, `project.description`
- `product_repo` (full path; forward slashes are fine on Windows)
- `models.local.default/scout/implementer/reviewer/planner`
- `gates.test_command`

Leave unchanged unless the human asks: `main_branch` (confirm it matches
the repo's default branch — check `git -C <path> branch --show-current` or
the remote's HEAD), all `budgets`, `require_human_approval_for_merge: true`
(never turn this off during setup), `protected_paths` (add obvious secrets
paths for their stack if any), `notifications` (only if they give a webhook).

Optional — ask, don't assume:

- OpenRouter fallback: only if the human provides `OPENROUTER_API_KEY`.
  They set it in their shell profile; you never handle the raw key.
- Discord webhook: only if they provide the URL.

Then validate:

```bash
python - <<'EOF'
import yaml
from pathlib import Path
c = yaml.safe_load(open("harness/config.yaml"))
assert Path(c["product_repo"]).joinpath(".git").is_dir(), "product_repo is not a git repo"
assert c["gates"]["test_command"].strip(), "test_command is empty"
assert c["project"]["name"] not in ("my-project", ""), "project.name still a placeholder"
print("config OK:", c["product_repo"], "|", c["gates"]["test_command"])
EOF
```

**Gate 2:** the validation prints `config OK`. If it asserts, fix the named
field and re-run.

## Phase 3 — Smoke test

`tickets/TICKET-001.md` is a docs-only ticket — safe by design. Run one
cycle:

- Windows: `.\run_cycle.bat`
- macOS/Linux: `./run_cycle.sh`

Narrate what's happening as it goes (implementer → tests → reviewer →
merge prompt). Expected:

1. Implementer writes `docs/ARCHITECTURE.md` into a `loop/ticket-001`
   worktree; test command exits 0.
2. Reviewer ends with `VERDICT: APPROVE`.
3. The human is prompted `Merge loop/ticket-001 into main? [y/N]` —
   **let the human answer.** Do not pass `--yes` yourself.
4. `tickets/TICKET-001.md` → `status: done`; `CYCLE_LOG.md` gains an entry;
   `git -C <product_repo> branch --list "loop/*"` → empty (branch cleaned up).

**Gate 3:** ticket is `done` and the loop branch is gone. If the ticket lands
in `blocked` or `needs-human`, read the `## Cycle note` in the ticket file
and the `CYCLE_LOG.md` entry, diagnose (INSTALL.md §7), fix, and re-run —
do not silently move on.

After a green smoke test, tell the human to delete or supersede TICKET-001,
then offer to run the Scout (`run_scout.*`) to draft the real backlog —
reminding them to curate (reprioritize / drop) before scheduling anything.

## Phase 4 — Scheduling (only if the human asks)

Do not schedule unattended runs unprompted. If asked, follow INSTALL.md §6
(Task Scheduler / cron / systemd / launchd), keep
`require_human_approval_for_merge: true` unless the human explicitly accepts
`--yes` merges, and insist on a notification channel (Discord webhook or
log file they will actually read).

## Rules

- **Never** turn off `require_human_approval_for_merge` without the human
  explicitly asking for unattended merges.
- **Never** put secrets (API keys, tokens, webhook URLs with tokens) into
  `config.yaml`, tickets, logs, or chat. Env vars only.
- **Never** edit `prompts/` or `harness/*.py` during setup. If something
  looks like a code bug, report it — don't patch it silently.
- **Never** run with `--yes` on the human's behalf.
- Ask the human for facts only they know (repo path, test command,
  project description). Detect everything else yourself.
- When you finish, summarize: what you verified, the config values you set,
  the smoke-test outcome, and what remains (real backlog, scheduling).
