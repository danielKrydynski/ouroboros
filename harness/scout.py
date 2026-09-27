#!/usr/bin/env python3
"""
Scout: audit the product repo and propose new tickets.

Writes tickets/TICKET-*.md with status: open. Never touches code.
You curate the backlog afterwards: reprioritize, or drop won't-dos
by setting their status to `dropped`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import complete  # noqa: E402
from prompts import render  # noqa: E402
from tickets import load_tickets  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

TICKET_BLOCK = re.compile(r"### TICKET:\s*(\S+)\s*\n```markdown\n(.*?)```",
                          re.DOTALL)


def sh(args: list[str], cwd: Path) -> str:
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    return r.stdout


def main() -> int:
    cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    repo = Path(cfg["product_repo"]).expanduser()
    if not (repo / ".git").is_dir():
        print(f"product_repo is not a git repo: {repo}")
        return 2

    system = render("scout", cfg)
    files = sh(["git", "ls-files"], cwd=repo).splitlines()
    file_list = "\n".join(f for f in files if f.strip())[:12000]
    log = sh(["git", "log", "--oneline", "-15"], cwd=repo)
    existing = "\n".join(
        f"- {t.id}: {t.meta.get('title', '').strip()} [{t.status}]"
        for t in load_tickets(ROOT / "tickets")
    ) or "(no tickets yet)"

    user = (f"# Repository file list\n{file_list}\n\n"
            f"# Recent commits\n{log}\n\n"
            f"# Existing tickets (do not duplicate)\n{existing}\n\n"
            f"Propose new tickets now.")
    text, which = complete(cfg, "scout", system, user)

    made = 0
    for fname, body in TICKET_BLOCK.findall(text):
        fname = Path(fname).name
        if not fname.startswith("TICKET-"):
            fname = "TICKET-" + fname
        if not fname.endswith(".md"):
            fname += ".md"
        dest = ROOT / "tickets" / fname
        if dest.exists():
            print(f"skip {fname}: already exists")
            continue
        dest.write_text(body.strip() + "\n", encoding="utf-8")
        made += 1
        print(f"wrote {fname}")
    print(f"done [{which}]: {made} new ticket(s). Curate them in tickets/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
