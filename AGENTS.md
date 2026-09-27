# AGENTS.md — for AI agents working in the Ouroboros repo

> This file is for agents **contributing to Ouroboros itself**. If you're
> helping a *user* install or configure Ouroboros, read
> `setup/agent-setup.md` instead.

## What this is

Ouroboros is a harness that runs a recursive dev loop over a *separate*
product repo: ticket → isolated git worktree → implementer → tests →
reviewer → human-approved merge. Local Ollama models first, OpenRouter
fallback. See `README.md` for the architecture diagram.

## Repo map

- `harness/orchestrator.py` — one full cycle. Owns ALL git ops and test runs.
- `harness/scout.py` — repo audit → proposes `tickets/TICKET-*.md`.
- `harness/llm.py` — `complete(cfg, role, system, user)` → `(text, which_model)`.
- `harness/prompts.py` — `render(name, cfg)` fills `{{PROJECT_*}}` placeholders.
- `harness/tickets.py` — ticket parse / status updates. Don't reimplement.
- `harness/config.yaml` — the ONLY machine-specific file. Never commit real
  values (paths, keys) — placeholders only.
- `prompts/*.md` — role prompts. Keep them project-agnostic; use the
  `{{PROJECT_NAME}}` / `{{PROJECT_DESCRIPTION}}` placeholders.
- `tickets/` — the backlog. `TICKET_FORMAT.md` is the schema doc.
- `setup/` — installer scripts, `agent-setup.md`, `manifest.json`.

## Invariants (do not break)

1. **The harness owns git and tests.** Roles produce text only. Never give a
   role a shell, and never trust role output: paths go through `safe_relpath`
   + `is_protected`, merges require tests green + reviewer APPROVE.
2. **Secrets never enter prompts.** Workers see ticket + code + test output.
   Nothing else. Keep it that way.
3. **Worktree before branch deletion.** A `loop/*` branch is always checked
   out by its worktree — remove the worktree first, then `git branch -d`.
   (This was a real bug once; don't reintroduce it.)
4. **Merge target is explicit.** `git checkout main_branch` before merging —
   never assume the repo's current checkout.
5. **Planner is advisory.** `get_plan()` must never kill a cycle; it degrades
   to "no plan" on any failure.
6. **Notifications never break a cycle.** `notify()` swallows all exceptions.

## Conventions

- Python 3.10+, stdlib + `pyyaml` + `requests` only. No new dependencies
  without a strong reason (every dep is a install-friction tax).
- Commit messages from the loop use the `ouroboros(<ticket>): …` prefix and
  the `ouroboros-loop` git identity — keep both.
- Branches: `loop/<ticket-id-lowercase>`. Worktrees: `worktrees/<TICKET-ID>/`.
- Ticket statuses: `open → done | blocked | needs-human`, plus hand-set
  `dropped`. The harness appends `## Cycle note` — the ticket file is the
  audit trail.
- Keep prompts strict about output format (`### FILE:` / `### TICKET:` /
  `VERDICT:`) — the regexes in the harness depend on them.

## How to check your changes

```bash
python -m py_compile harness/*.py          # syntax
python - <<'EOF'                            # prompt rendering still substitutes
import sys; sys.path.insert(0, "harness")
import yaml; from prompts import render
cfg = yaml.safe_load(open("harness/config.yaml"))
for r in ("scout", "implementer", "reviewer", "planner"):
    t = render(r, cfg)
    assert "{{PROJECT_" not in t, r
print("prompts render OK")
EOF
```

For a full end-to-end test you need Ollama (or stub `llm.complete`):
point a test `config.yaml` at a scratch git repo, use `test_command: "true"`,
and drive `orchestrator.main()` with `--ticket`. Assert: ticket → `done`,
file merged to main, `loop/*` branch deleted, no worktrees left.

## Don't

- Don't add secrets handling, network calls, or new config keys without
  documenting them in `INSTALL.md` and `setup/manifest.json`.
- Don't make the implementer network-capable. The sandbox is the point.
- Don't "simplify" by merging the harness into the product repo. The
  separation (loop outside, workers in worktrees) is the safety model.
