"""Store a coaching review.

    python scripts/save_review.py --session 8 --file outputs/coach/session_0008/review.md \
        --focus "Meet the backhand earlier" "Recover to the centre after wide forehands" \
        --drills "Cross-court backhand, 3 x 20 balls" [--scope session|monthly]

Saves the review in the database, keeps a dated copy in data/reviews/, and,
if data/player.json names an "obsidian_file", appends it there.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import db  # noqa: E402


def section(text: str, title: str) -> list[str]:
    """The list items under a '## <title>' heading of the review."""
    items, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith(title.lower())
            continue
        stripped = line.strip()
        if inside and stripped[:2] in ("- ", "* "):
            items.append(stripped[2:].strip())
        elif inside and stripped[:1].isdigit() and ". " in stripped[:4]:
            items.append(stripped.split(". ", 1)[1].strip())
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--session", type=int)
    ap.add_argument("--file", help="the review, Markdown")
    ap.add_argument("--focus", nargs="*", default=[], help="2-3 priorities (default: the '## Priorities' list in the file)")
    ap.add_argument("--drills", nargs="*", default=[], help="default: the '## Drills' list in the file")
    ap.add_argument("--scope", default="session", choices=["session", "monthly"])
    ap.add_argument("--auto", action="store_true",
                    help="save outputs/coach/session_<latest>/review.md if it is there and not saved yet")
    args = ap.parse_args()

    con = db.connect(args.db)
    if args.auto:
        args.session = args.session or con.execute("SELECT max(session_id) FROM sessions").fetchone()[0]
        if args.session is None:
            print("No sessions yet.")
            return
        args.file = str(ROOT / "outputs" / "coach" / f"session_{args.session:04d}" / "review.md")
        if not Path(args.file).exists():
            print(f"No review written yet for session {args.session} (expected {args.file}).")
            return
        saved = con.execute("SELECT summary_md FROM reviews WHERE session_id = ? AND scope = ?",
                            [args.session, args.scope]).fetchone()
        if saved and saved[0] == Path(args.file).read_text(encoding="utf-8"):
            print(f"Review for session {args.session} is already saved.")
            return
    if args.session is None or not args.file:
        raise SystemExit("Give --session and --file, or use --auto")
    text = Path(args.file).read_text(encoding="utf-8")
    args.focus = args.focus or section(text, "Priorities")
    args.drills = args.drills or section(text, "Drills")
    played = con.execute("SELECT played_on FROM sessions WHERE session_id = ?", [args.session]).fetchone()
    if played is None:
        raise SystemExit(f"No session {args.session}")
    con.execute("DELETE FROM reviews WHERE session_id = ? AND scope = ?", [args.session, args.scope])
    rid = con.execute("SELECT coalesce(max(review_id), 0) + 1 FROM reviews").fetchone()[0]
    con.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?)",
                [rid, args.session, dt.date.today(), args.scope, text, "\n".join(args.focus), "\n".join(args.drills)])
    con.close()

    keep = ROOT / "data" / "reviews"
    keep.mkdir(parents=True, exist_ok=True)
    copy = keep / f"{played[0]}_session_{args.session:04d}_{args.scope}.md"
    copy.write_text(text, encoding="utf-8")
    print(f"Review {rid} saved for session {args.session}; copy: {copy}")

    cfg = ROOT / "data" / "player.json"
    target = json.loads(cfg.read_text(encoding="utf-8")).get("obsidian_file") if cfg.exists() else None
    if target:
        t = Path(target)
        if t.exists():
            with t.open("a", encoding="utf-8") as fh:
                fh.write(f"\n\n---\n\n{text}\n")
            print(f"Appended to {t}")
        else:
            print(f"Obsidian file not found, skipped: {t}")


if __name__ == "__main__":
    main()
