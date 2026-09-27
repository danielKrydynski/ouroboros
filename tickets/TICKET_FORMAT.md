# Ticket format

Tickets live in `tickets/` as `TICKET-*.md`. The orchestrator picks the
highest-priority ticket with `status: open`. Statuses:

| status        | meaning                                              |
|---------------|------------------------------------------------------|
| `open`        | ready for the loop to pick up                        |
| `done`        | merged to main (set by the harness)                  |
| `blocked`     | implementer exhausted its budget (set by the harness)|
| `needs-human` | reviewer rejected, or merge declined (needs you)     |
| `dropped`     | you decided it's a won't-do (set by hand)            |

## Schema

```markdown
# <short title>
title: <short title>
status: open
priority: <1 highest … 5 lowest>
type: <bug|tech-debt|test|security|perf|docs|feature>
area: <comma-separated repo-relative files, best guess — may be empty>
created: <YYYY-MM-DD>
---
## Problem
<what is wrong or missing, with file/line references>

## Acceptance criteria
- [ ] <verifiable outcome>
- [ ] <existing test suite still passes>

## Constraints
<anything the implementer must not break>
```

- The header is `key: value` lines; the body starts after the first `---` line.
- `area` files get their full contents injected into the implementer's prompt —
  list the files the change will actually touch. Keep it to a handful.
- `priority` decides pickup order (lower number = sooner). Ties break by ticket id.
- Keep tickets small enough for one cycle (~30–45 min). Split big ideas;
  link follow-ups in the body.
- The harness appends a `## Cycle note` with the outcome, so the ticket file
  itself is the audit trail.
