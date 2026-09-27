# Ouroboros 🐍

A recursive development loop: AI agents that continuously improve your
codebase — with tests and review as the fitness function.

Ouroboros is named for the serpent eating its own tail, the ancient symbol
of cyclical self-renewal. The loop picks up a ticket, implements it in an
isolated git worktree, runs your test suite, puts the diff through a
reviewer agent, and merges — or stops and asks a human. No measurement,
no merge.

## How it works

```
tickets/ ── open ticket ──▶ orchestrator
                               │
                 ┌─────────────┴──────────────┐
                 ▼                            ▼
        git worktree + branch            (isolated copy)
                 │
        implementer loop (Ollama → OpenRouter fallback)
          propose files → harness applies → run tests → feed back failures
                 │ pass
        reviewer gate (APPROVE / REJECT)
                 │ approve
        human merge approval (on by default, configurable)
                 │
        merge to main, ticket → done, cycle logged
```

Three things stay deliberately separate:

1. **Harness** (`harness/`, `prompts/`) — the loop controller. Agents never
   edit this. It lives in its own folder, *outside* the product repo.
2. **Backlog** (`tickets/`) — the task queue. The Scout proposes tickets, you curate them.
3. **Workers** — LLM roles (scout, implementer, reviewer, planner) that only
   ever touch a throwaway `git worktree` on a `loop/*` branch.

Local-first: every role runs on Ollama by default. OpenRouter is a fallback
for hard tasks, not the default — most cycles cost nothing and never leave
your machine.

## Quickstart

**Full guide: [INSTALL.md](INSTALL.md)** — prerequisites, model sizing,
config walkthrough, scheduling, troubleshooting.

The 60-second version (Windows):

1. Clone this repo **next to** your product repo (not inside it):
   ```
   C:\dev\
   ├── my-project\   ← the repo the loop improves
   └── ouroboros\    ← this repo
   ```
2. `.\setup\setup.ps1` — checks Python, git, Ollama; installs dependencies.
3. Edit `harness\config.yaml`: `project.name`, `product_repo`, your Ollama
   model names, and `gates.test_command`.
4. Smoke test: `.\run_cycle.bat` — processes `tickets\TICKET-001.md`, a
   docs-only ticket that can't break anything.

macOS/Linux: use `setup/setup.sh`, `./run_cycle.sh`, `./run_scout.sh`.

## Daily use

- **Add work**: write tickets by hand in `tickets/` (see
  `tickets/TICKET_FORMAT.md`), or generate candidates with the Scout:
  `run_scout.*`
- **Run a cycle**: `run_cycle.*` — add `--yes` to skip the merge prompt once
  the loop has earned your trust
- **Run one ticket**: `python harness/orchestrator.py --ticket TICKET-003`
- **Review**: `CYCLE_LOG.md` gets an entry per cycle; each ticket file keeps
  its own audit trail
- **Schedule it**: Task Scheduler / cron / systemd — see INSTALL.md.
  Start manual, automate once the gates prove out.

## Safety rules (enforced by the harness, not by hope)

- Agents work in a disposable worktree on a `loop/*` branch. `main` is only
  ever touched by a `--no-ff` merge after all gates pass.
- Protected paths (`.env`, `secrets/`, …) can never be written by the
  implementer; unsafe paths (`..`, absolute) are rejected outright.
- Secrets never enter prompts. Workers see the ticket and the code, nothing else.
- Budgets: max implementer iterations per ticket, test timeout, max review rounds.
- The harness directory itself is never within the implementer's reach.

## Having an AI agent help you set up

Point your assistant at **`setup/agent-setup.md`** — a deterministic,
checkable procedure written for AI agents: exact commands, expected
outputs, and verification gates. `setup/manifest.json` carries the same
information machine-readable. If you're an agent reading this: start there.

## Files

```
ouroboros/
├── README.md                 ← you are here
├── INSTALL.md                ← full install & operations guide
├── AGENTS.md                 ← instructions for AI agents working in this repo
├── LICENSE
├── requirements.txt
├── run_cycle.* / run_scout.* ← .bat (Windows), .sh (macOS/Linux)
├── harness/
│   ├── config.yaml           ← ALL machine-specific settings live here
│   ├── orchestrator.py       ← one full cycle: ticket → merge
│   ├── scout.py              ← propose new tickets from a repo audit
│   ├── llm.py                ← Ollama-first, OpenRouter fallback
│   ├── tickets.py            ← tiny ticket parser
│   └── prompts.py            ← project-aware prompt rendering
├── prompts/
│   ├── scout.md / implementer.md / reviewer.md / planner.md
├── tickets/
│   ├── TICKET_FORMAT.md      ← the ticket schema, annotated
│   └── TICKET-001.md         ← smoke-test ticket (docs only)
├── setup/
│   ├── agent-setup.md        ← step-by-step for an assisting AI agent
│   ├── manifest.json         ← machine-readable setup metadata
│   ├── setup.ps1 / setup.sh  ← bootstrap: checks + dependency install
├── BACKLOG.md                ← how the backlog works + seed ideas
├── CYCLE_LOG.md              ← every cycle gets logged here
└── worktrees/                ← throwaway git worktrees (gitignored)
```

## Customizing

- `prompts/*.md` — tune the roles. Use `{{PROJECT_NAME}}` and
  `{{PROJECT_DESCRIPTION}}` placeholders; they're filled from config.
- `harness/config.yaml` — models, budgets, gates, optional Discord webhook.
- **Upgrade path**: swap the file-block implementer for ACP calls into your
  editor, or point the roles at your own agent once it can use tools. The
  harness (tickets → worktree → tests → review → merge) stays the same.
