#!/usr/bin/env python3
"""
Ouroboros — recursive dev loop harness. Runs ONE improvement cycle:

    pick ticket -> worktree + branch -> implementer loop -> reviewer gate -> merge

The harness owns every git operation and every test run. The LLM roles only
ever produce text: file contents (implementer), verdicts (reviewer), ticket
drafts (scout), plans (planner). Nothing they output is trusted — paths are
validated, tests must pass, and the merge gate defaults to requiring a human.
"""
from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import complete  # noqa: E402
from prompts import render  # noqa: E402
from tickets import load_tickets, next_open_ticket, set_ticket_status  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TICKETS_DIR = ROOT / "tickets"
WORKTREES = ROOT / "worktrees"

FILE_BLOCK = re.compile(r"### FILE:\s*(\S+)\s*\n```(?:\w+)?\n(.*?)```", re.DOTALL)
VERDICT = re.compile(r"VERDICT:\s*(APPROVE|REJECT)", re.IGNORECASE)

GIT_USER = "ouroboros-loop"


# ---------------- shell helpers ----------------

def sh(args: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"$ {' '.join(args)}\n{r.stderr[-3000:]}")
    return r


def sh_shell(cmd: str, cwd: Path, timeout: int) -> tuple[int, str]:
    """Run the test command. Returns (exit_code, tail_of_output)."""
    try:
        r = subprocess.run(cmd, cwd=str(cwd), shell=True, capture_output=True,
                           text=True, timeout=timeout)
        out = (r.stdout + "\n" + r.stderr)[-8000:]
        return r.returncode, f"exit={r.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return 124, f"exit=124\nTEST COMMAND TIMED OUT after {timeout}s"


def notify(cfg: dict, msg: str) -> None:
    url = cfg.get("notifications", {}).get("discord_webhook", "")
    if not url:
        return
    try:
        requests.post(url, json={"content": msg[:1900]}, timeout=15)
    except Exception:
        pass  # notifications must never break a cycle


# ---------------- repo helpers ----------------

def repo_file_list(repo: Path, limit: int = 400) -> str:
    r = sh(["git", "ls-files"], cwd=repo, check=True)
    files = [f for f in r.stdout.splitlines() if f.strip()]
    shown = files[:limit]
    extra = f"\n... and {len(files) - limit} more files" if len(files) > limit else ""
    return "\n".join(shown) + extra


def read_area_files(repo: Path, ticket, max_chars: int = 15000) -> str:
    area = ticket.meta.get("area", "").strip()
    if not area:
        return "(ticket lists no area files; work from the file list below)"
    chunks = []
    for name in [a.strip() for a in area.split(",") if a.strip()]:
        p = repo / name
        if not p.is_file():
            chunks.append(f"--- {name} ---\n(file not found in worktree)")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... truncated ({len(text)} chars total)"
        chunks.append(f"--- {name} ---\n{text}")
    return "\n\n".join(chunks)


def safe_relpath(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"blocked unsafe path: {raw}")
    return p


def is_protected(rel: Path, protected: list[str]) -> bool:
    s = rel.as_posix()
    return any(s == p or s.startswith(p.rstrip("/") + "/") for p in protected)


def apply_files(repo: Path, text: str, protected: list[str]) -> list[str]:
    """Apply the model's ### FILE: blocks. Returns list of written paths."""
    written = []
    for raw_path, content in FILE_BLOCK.findall(text):
        rel = safe_relpath(raw_path.strip())
        if is_protected(rel, protected):
            raise ValueError(f"blocked protected path: {raw_path}")
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(rel.as_posix())
    return written


def git_commit(repo: Path, message: str) -> bool:
    sh(["git", "add", "-A"], cwd=repo, check=True)
    if not sh(["git", "status", "--porcelain"], cwd=repo).stdout.strip():
        return False
    sh(["git", "-c", f"user.name={GIT_USER}", "-c",
        f"user.email={GIT_USER}@local", "commit", "-m", message],
       cwd=repo, check=True)
    return True


# ---------------- planner (optional) ----------------

def get_plan(cfg, ticket, file_list: str, area_src: str) -> str:
    """One planner pass for large feature tickets. Never fatal."""
    if ticket.meta.get("type", "").strip().lower() != "feature":
        return ""
    if not cfg.get("planner", {}).get("enabled_for_feature_tickets", True):
        return ""
    try:
        system = render("planner", cfg)
        user = (f"# Ticket {ticket.id}: {ticket.meta.get('title', '').strip()}\n\n"
                f"{ticket.body}\n\n"
                f"# Relevant file contents\n{area_src}\n\n"
                f"# Repository file list (abbreviated)\n{file_list}\n\n"
                f"Produce the plan.")
        text, which = complete(cfg, "planner", system, user)
        return f"\n\n## Planner's plan [{which}]\n{text}\n"
    except Exception as exc:  # planner is advisory; the cycle must survive it
        return f"\n\n## Planner's plan\n(planner unavailable: {exc})\n"


# ---------------- implementer ----------------

def implementer_turn(cfg, ticket, wt, file_list, area_src,
                     feedback: str, iteration, plan: str = "") -> tuple[str, str]:
    system = render("implementer", cfg)
    user = f"""# Ticket {ticket.id}: {ticket.meta.get('title', '').strip()}

{ticket.body}{plan}

# Relevant file contents
{area_src}

# Repository file list (abbreviated)
{file_list}

# Iteration {iteration} — harness feedback
{feedback}

Propose file changes now, as ### FILE: blocks."""
    return complete(cfg, "implementer", system, user)


def run_implementer(cfg, ticket, wt) -> tuple[bool, str]:
    max_iter = int(cfg["budgets"]["max_iterations_per_ticket"])
    test_cmd = cfg["gates"]["test_command"]
    test_timeout = int(cfg["budgets"]["test_timeout_seconds"])
    protected = cfg["gates"]["protected_paths"]

    file_list = repo_file_list(wt)
    area_src = read_area_files(wt, ticket)
    plan = get_plan(cfg, ticket, file_list, area_src)
    feedback = "No tests have run yet. Make your first implementation attempt."
    log: list[str] = []
    if plan:
        log.append("planner: plan generated for feature ticket")

    for i in range(1, max_iter + 1):
        text, which = implementer_turn(cfg, ticket, wt, file_list, area_src,
                                       feedback, i, plan)
        written = apply_files(wt, text, protected)
        if not written:
            feedback = ("You proposed no file changes. If the ticket truly needs "
                        "no code change, explain why in plain text and propose a "
                        "test or doc change instead. Otherwise propose the code "
                        "changes now.")
            log.append(f"iter {i} [{which}]: no files proposed")
            continue
        git_commit(wt, f"ouroboros({ticket.id}): implementer iter {i} [{which}]")
        code, out = sh_shell(test_cmd, wt, test_timeout)
        log.append(f"iter {i} [{which}]: wrote {len(written)} file(s), "
                   f"tests exit={code}")
        if code == 0:
            return True, "\n".join(log)
        feedback = (f"Tests FAILED (exit {code}). Fix the failures — the output "
                    f"below is ground truth.\n{out}\n\n"
                    f"Reply with corrected ### FILE: blocks (complete contents).")
    return False, "\n".join(log)


# ---------------- reviewer ----------------

def run_reviewer(cfg, ticket, wt, branch: str, main_branch: str) -> tuple[bool, str]:
    system = render("reviewer", cfg)
    rounds = int(cfg["budgets"]["max_review_rounds"])
    fix_iters = int(cfg["budgets"]["max_fix_iters_per_round"])
    max_diff = int(cfg["budgets"]["max_diff_chars"])
    test_cmd = cfg["gates"]["test_command"]
    test_timeout = int(cfg["budgets"]["test_timeout_seconds"])
    protected = cfg["gates"]["protected_paths"]

    file_list = repo_file_list(wt)
    area_src = read_area_files(wt, ticket)
    last_text = ""

    for rnd in range(1, rounds + 1):
        diff = sh(["git", "diff", f"{main_branch}...{branch}"], cwd=wt).stdout
        if not diff.strip():
            return False, "empty diff — nothing to review"
        if len(diff) > max_diff:
            diff = diff[:max_diff] + "\n... diff truncated"
        user = (f"# Ticket {ticket.id}\n{ticket.body}\n\n"
                f"# Diff under review ({main_branch}...{branch})\n"
                f"```diff\n{diff}\n```\n\nGive your verdict.")
        text, which = complete(cfg, "reviewer", system, user)
        last_text = text
        m = VERDICT.search(text)
        if m and m.group(1).upper() == "APPROVE":
            return True, f"round {rnd} [{which}]: APPROVE"

        # REJECT (or no parseable verdict): send the critique back to implementer
        feedback = (f"REVIEWER REJECTED the change (round {rnd}). Address every "
                    f"point below, then re-propose files.\n\n{text}")
        fixed = False
        for i in range(1, fix_iters + 1):
            t2, w2 = implementer_turn(cfg, ticket, wt, file_list, area_src,
                                      feedback, f"fix-{rnd}.{i}")
            written = apply_files(wt, t2, protected)
            if not written:
                feedback = "You proposed no file changes. Propose the fixes now."
                continue
            git_commit(wt, f"ouroboros({ticket.id}): review-fix r{rnd}.{i} [{w2}]")
            code, out = sh_shell(test_cmd, wt, test_timeout)
            if code == 0:
                fixed = True
                break
            feedback = (f"Tests FAILED after review fixes (exit {code}):\n{out}\n\n"
                        f"Original reviewer critique:\n{text}")
        if not fixed:
            return False, f"round {rnd}: review fixes did not get tests green"
        # tests green again -> next review round re-examines the new diff
    return False, last_text[-2000:]


# ---------------- main cycle ----------------

def append_log(ticket, outcome: str, notes: list[str]) -> None:
    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (f"\n## {started} — {ticket.id} "
             f"({ticket.meta.get('title', '').strip()}) — {outcome}\n"
             + "\n".join(notes) + "\n")
    with (ROOT / "CYCLE_LOG.md").open("a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ouroboros recursive dev loop — one cycle")
    ap.add_argument("--config", default=str(HERE / "config.yaml"))
    ap.add_argument("--ticket", default=None, help="specific ticket id, e.g. TICKET-003")
    ap.add_argument("--yes", action="store_true", help="skip the human merge prompt")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    repo = Path(cfg["product_repo"]).expanduser()
    main_branch = cfg.get("main_branch", "main")
    if not (repo / ".git").is_dir():
        print(f"product_repo is not a git repo: {repo}")
        return 2

    if args.ticket:
        found = [t for t in load_tickets(TICKETS_DIR) if t.id == args.ticket]
        ticket = found[0] if found else None
    else:
        ticket = next_open_ticket(TICKETS_DIR)
    if ticket is None:
        print("No open tickets. Run the scout (run_scout.*) or add one to tickets/.")
        return 0
    if ticket.status != "open":
        print(f"{ticket.id} is not open (status={ticket.status}).")
        return 0

    branch = f"loop/{ticket.id.lower()}"
    wt = WORKTREES / ticket.id

    # fresh worktree; clear stale state from a crashed run
    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
    if sh(["git", "branch", "--list", branch], cwd=repo).stdout.strip():
        sh(["git", "branch", "-D", branch], cwd=repo)
    WORKTREES.mkdir(parents=True, exist_ok=True)
    sh(["git", "worktree", "add", str(wt), "-b", branch, main_branch],
       cwd=repo, check=True)

    notes: list[str] = []
    try:
        ok, impl_log = run_implementer(cfg, ticket, wt)
        notes.append("## Implementer\n" + impl_log)
        if not ok:
            set_ticket_status(ticket, "blocked", "\n".join(notes))
            append_log(ticket, "blocked", notes)
            notify(cfg, f"🔴 ouroboros {ticket.id}: implementer exhausted its budget — marked blocked.")
            print(f"{ticket.id}: implementer failed -> blocked")
            return 1

        ok, rev_log = run_reviewer(cfg, ticket, wt, branch, main_branch)
        notes.append("## Reviewer\n" + rev_log)
        if not ok:
            set_ticket_status(ticket, "needs-human", "\n".join(notes))
            append_log(ticket, "needs-human", notes)
            notify(cfg, f"🟡 ouroboros {ticket.id}: reviewer rejected — branch kept: {branch}")
            print(f"{ticket.id}: reviewer rejected -> needs-human (branch kept: {branch})")
            return 1

        stat = sh(["git", "diff", "--stat", f"{main_branch}...{branch}"],
                  cwd=repo).stdout
        print(f"--- {ticket.id} ready to merge ---\n{stat}")
        if cfg["gates"]["require_human_approval_for_merge"] and not args.yes:
            ans = input(f"Merge {branch} into {main_branch}? [y/N] ").strip().lower()
            if ans != "y":
                note = "\n".join(notes) + "\n\nMerge declined by human."
                set_ticket_status(ticket, "needs-human", note)
                append_log(ticket, "merge-declined", notes)
                notify(cfg, f"🟡 ouroboros {ticket.id}: merge declined by human — branch kept: {branch}")
                print("Merge declined. Branch kept for manual inspection.")
                return 0

        # Merge into main explicitly — never assume the repo is on main_branch.
        sh(["git", "checkout", main_branch], cwd=repo, check=True)
        sh(["git", "merge", "--no-ff", branch, "-m",
            f"ouroboros: {ticket.id} {ticket.meta.get('title', '').strip()}".strip()],
           cwd=repo, check=True)
        # The worktree still has `branch` checked out: remove the worktree
        # BEFORE deleting the branch, otherwise `git branch -d` refuses.
        sh(["git", "worktree", "remove", "--force", str(wt)], cwd=repo,
           check=True)
        sh(["git", "branch", "-d", branch], cwd=repo, check=True)
        done_note = "\n".join(notes) + f"\n\nMerged {branch} into {main_branch}."
        set_ticket_status(ticket, "done", done_note)
        append_log(ticket, "done", notes)
        notify(cfg, f"🟢 ouroboros {ticket.id}: merged to {main_branch}.")
        print(f"{ticket.id}: merged.")
        return 0
    finally:
        if wt.exists():
            sh(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
        sh(["git", "worktree", "prune"], cwd=repo)


if __name__ == "__main__":
    raise SystemExit(main())
