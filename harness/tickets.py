"""Tiny ticket parser.

Tickets are markdown files with a `key: value` header, e.g.:

    # Short title
    title: Short title
    status: open
    priority: 2
    type: bug
    area: src/bot.py, src/router.py
    created: 2026-09-20
    ---
    ## Problem
    ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Ticket:
    id: str  # filename stem, e.g. TICKET-001
    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""

    @property
    def status(self) -> str:
        return self.meta.get("status", "open").strip().lower()


def _safe_priority(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 99


def load_tickets(tickets_dir: Path) -> list[Ticket]:
    out: list[Ticket] = []
    for path in sorted(tickets_dir.glob("TICKET-*.md")):
        text = path.read_text(encoding="utf-8")
        meta: dict[str, str] = {}
        body = text
        if "\n---\n" in text:
            head, body = text.split("\n---\n", 1)
            for line in head.splitlines():
                if ":" in line and not line.lstrip().startswith("#"):
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
        out.append(Ticket(id=path.stem, path=path, meta=meta,
                          body=body.strip()))
    return out


def next_open_ticket(tickets_dir: Path) -> Ticket | None:
    cands = [t for t in load_tickets(tickets_dir) if t.status == "open"]
    cands.sort(key=lambda t: (_safe_priority(t.meta.get("priority", "99")),
                              t.id))
    return cands[0] if cands else None


def set_ticket_status(ticket: Ticket, status: str, note: str = "") -> None:
    """Rewrite the ticket's status header and append a cycle note."""
    text = ticket.path.read_text(encoding="utf-8")
    if "\n---\n" in text:
        head, body = text.split("\n---\n", 1)
        lines, seen = [], False
        for line in head.splitlines():
            if line.lower().startswith("status:"):
                lines.append(f"status: {status}")
                seen = True
            else:
                lines.append(line)
        if not seen:
            lines.append(f"status: {status}")
        text = "\n".join(lines) + "\n---\n" + body
    else:
        text = f"status: {status}\n---\n" + text
    if note:
        text = text.rstrip() + f"\n\n## Cycle note\n{note}\n"
    ticket.path.write_text(text, encoding="utf-8")
    ticket.meta["status"] = status
