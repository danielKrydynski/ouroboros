# Backlog

Tickets live in `tickets/` as `TICKET-*.md`. The orchestrator always picks the
highest-priority `open` ticket. The Scout (`run_scout.*`) proposes new ones
from a repo audit — you curate: adjust priorities, close won't-dos by setting
`status: dropped`.

## Seed ideas (for your product repo)

Convert the ones you want into tickets (see `tickets/TICKET_FORMAT.md`).
Delete this section once the Scout takes over.

- [ ] Health-check: a single command that verifies the loop's own
      dependencies — Ollama reachable, fallback chain configured,
      test command runnable — and reports which leg failed.
- [ ] Startup config validation: fail fast with a clear message when
      `product_repo`, model names, or the test command are wrong,
      instead of dying mid-cycle.
- [ ] Structured logging (JSON lines) for every model call: role, model,
      latency, provider — the raw material for measuring the loop's cost.
- [ ] Test coverage for the model router: local-only, fallback-triggered,
      all-providers-down.
- [ ] Docs: an ARCHITECTURE.md for the product repo (this is also the
      loop's smoke test — see `tickets/TICKET-001.md`).
- [ ] Dependency audit: outdated / vulnerable packages in the product repo.

## Seed ideas (for the loop itself)

Ouroboros can improve its own harness — point `product_repo` at a checkout
of this repo and let it file tickets against itself. Candidates:

- [ ] Retry with backoff on the OpenRouter fallback leg; log which provider
      served each request.
- [ ] Token/cost accounting per cycle, with a per-day budget cap.
- [ ] Parallel ticket lanes: run independent tickets in separate worktrees.
- [ ] ACP/tool-driven implementer: let the implementer edit via tools
      instead of whole-file blocks.
