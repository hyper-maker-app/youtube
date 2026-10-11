"""Automated Git audit, stage, commit, and push utility.

Enforces the non-negotiable project rule:
All modifications must pass scripts/audit_and_sync.py and be automatically
committed and pushed to origin/main before the developer or LLM concludes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout + "\n" + proc.stderr).strip()


def sync(commit_msg: str | None = None) -> None:
    print("[1/4] Running audit_and_sync.py...")
    audit_cmd = [sys.executable, str(ROOT / "scripts" / "audit_and_sync.py")]
    code, out = run_cmd(audit_cmd)
    if code != 0:
        print(f"[FAIL] Audit failed:\n{out}")
        sys.exit(code)
    print("      Audit passed (0 failures).")

    print("[2/4] Checking git status...")
    code, status_out = run_cmd(["git", "status", "--porcelain"])
    if not status_out.strip():
        print("      Working tree is clean. Nothing to commit or push.")
        return

    print("[3/4] Staging files...")
    code, out = run_cmd(["git", "add", "."])
    if code != 0:
        print(f"[FAIL] git add failed:\n{out}")
        sys.exit(code)

    msg = commit_msg or "chore: automatic sync after code/doc updates"
    print(f"[4/4] Committing & pushing to origin/main ('{msg}')...")
    code, out = run_cmd(["git", "commit", "-m", msg])
    if code != 0:
        print(f"[FAIL] git commit failed:\n{out}")
        sys.exit(code)

    code, out = run_cmd(["git", "push", "origin", "main"])
    if code != 0:
        print(f"[FAIL] git push failed:\n{out}")
        sys.exit(code)

    print("[SUCCESS] All changes successfully verified, committed, and pushed to origin/main!")


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    sync(message)
