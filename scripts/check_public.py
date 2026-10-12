"""Check that nothing personal or secret is about to be published.

This repository is public. Run before every push:

    python scripts/check_public.py              # files in git + staged changes + unpushed commit messages
    python scripts/check_public.py --history    # every file in every commit, every commit message

It fails (exit code 1) on:
  * files that must stay local: footage, pictures, databases, caches, weights,
    calibration clicks, player settings, reviews, logs, anything under data/,
    outputs/ or models/
  * files larger than 1 MB
  * credentials: API keys, tokens, private keys
  * personal paths (C:\\Users\\<name>, /Users/<name>, /home/<name>) and e-mail addresses
  * Google Drive file and folder links with their ids
  * the private terms listed in data/private_terms.txt, one per line (your name,
    e-mail, vault and folder names...). That file is local only: it is in data/,
    which is never committed, so the list itself is never published.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS = ROOT / "data" / "private_terms.txt"

LOCAL_ONLY = re.compile(
    r"(^|/)(data|outputs|models|_to_delete)/"
    r"|\.(mp4|mov|avi|mkv|m4v|webm|lrv|thm|insv|insp|360|jpe?g|png|heic|gif|duckdb|wal|pkl|pt|pth|onnx|bundle"
    r"|pem|key|p12|env)$"
    r"|(^|/)(player\.json|coach_input\.json|review\.md|pack\.md|pack\.json|links\.txt|\.env)$"
    r"|\.court\.json$|_log\.txt$|(^|/)(cookies|client_secret|credentials|token|service_account)[^/]*$",
    re.IGNORECASE)
ALLOWED_PICTURES = re.compile(r"^docs/img/")

SECRETS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Google OAuth secret", re.compile(r"\bGOCSPX-[0-9A-Za-z_\-]{20,}")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}")),
    ("API key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_\-]{20,}")),
    ("password assignment", re.compile(r"(?i)\b(password|passwd|pwd|secret|api_key|apikey|access_token)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]")),
]
PERSONAL = [
    ("personal path", re.compile(r"(?i)\b[A-Z]:\\{1,2}Users\\{1,2}(?!<|%|\{|Public\b|Default\b)[^\\\s\"'`]+")),
    ("personal path", re.compile(r"/(Users|home)/(?!claude\b|runner\b|user\b|<)[a-z][a-z0-9._-]+/", re.IGNORECASE)),
    ("e-mail address", re.compile(r"\b[A-Za-z0-9._%+-]+@(?!anthropic\.com\b|example\.(com|org)\b|users\.noreply\.github\.com\b)"
                                  r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("Google Drive id", re.compile(r"drive\.google\.com/(drive/folders|file/d|open\?id=)/?[A-Za-z0-9_-]{20,}")),
]
MAX_BYTES = 1_000_000


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def private_terms() -> list[str]:
    if not TERMS.exists():
        return []
    return [t.strip() for t in TERMS.read_text(encoding="utf-8").splitlines()
            if t.strip() and not t.strip().startswith("#")]


def scan_text(where: str, text: str, terms: list[str], problems: list[str]) -> None:
    for name, rx in SECRETS + PERSONAL:
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            problems.append(f"{where}:{line}: {name}")
    low = text.lower()
    for t in terms:
        i = low.find(t.lower())
        if i >= 0:
            problems.append(f"{where}:{low.count(chr(10), 0, i) + 1}: private term #{terms.index(t) + 1}")


def scan_tree(rev: str | None, terms: list[str], problems: list[str], seen: set) -> None:
    """rev None = the index (what the next commit will contain)."""
    if rev is None:
        listing = git("ls-files", "-s").splitlines()            # mode sha stage\tpath
        entries = [(l.split()[0], l.split()[1], l.split("\t", 1)[1]) for l in listing if "\t" in l]
    else:
        listing = git("ls-tree", "-r", "-l", rev).splitlines()  # mode type sha size\tpath
        entries = [(l.split()[0], l.split()[2], l.split("\t", 1)[1]) for l in listing if "\t" in l]
    for mode, sha, path in entries:
        if mode == "160000" or (path, sha) in seen:              # submodule pointer, or checked already
            continue
        seen.add((path, sha))
        where = f"{rev[:8] + ':' if rev else ''}{path}"
        if LOCAL_ONLY.search(path) and not ALLOWED_PICTURES.search(path):
            problems.append(f"{where}: this kind of file must stay local")
            continue
        size = int(git("cat-file", "-s", sha).strip() or 0)
        if size > MAX_BYTES:
            problems.append(f"{where}: {size / 1e6:.1f} MB, too large for this repository")
            continue
        if ALLOWED_PICTURES.search(path):
            continue
        scan_text(where, git("cat-file", "-p", sha), terms, problems)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", action="store_true", help="check every commit, not only what is about to be pushed")
    ap.add_argument("--rev", default=None, help="with --history: only commits reachable from this revision (default: all refs)")
    args = ap.parse_args()
    terms = private_terms()
    problems: list[str] = []
    seen: set = set()
    scan_tree(None, terms, problems, seen)
    if args.history:
        revs = git("rev-list", args.rev or "--all").split()
        log_range = [args.rev or "--all"]
    else:
        revs = []
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
        log_range = [f"{upstream}..HEAD"] if upstream else ["-20"]
    for r in revs:
        scan_tree(r, terms, problems, seen)
    for line in git("log", *log_range, "--format=%H%x00%an <%ae>%x00%cn <%ce>%x00%B%x1e").split("\x1e"):
        if not line.strip():
            continue
        sha, author, committer, body = (line.strip("\n").split("\x00") + ["", "", ""])[:4]
        scan_text(f"commit {sha[:8]} message", body, terms, problems)
        scan_text(f"commit {sha[:8]} author", f"{author}\n{committer}", terms, problems)
    if not terms:
        print("Note: no data/private_terms.txt, so names and other private words were not checked.")
    if problems:
        print("NOT safe to publish:")
        for p in sorted(set(problems)):
            print("  " + p)
        sys.exit(1)
    print("OK: nothing personal or secret found" + (" in the whole history." if args.history else "."))


if __name__ == "__main__":
    main()
