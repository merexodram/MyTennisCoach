"""Recompute the metrics of every session and rewrite the Obsidian notes and the dashboard.

    python scripts/update_stats.py [--compare A B]

coach.bat runs this last, so the notes always match the database.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import db, metrics  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--compare", nargs=2, type=int, metavar=("A", "B"))
    args = ap.parse_args()
    con = db.connect(args.db)
    sids = [r[0] for r in con.execute("SELECT session_id FROM sessions ORDER BY session_id").fetchall()]
    for sid in sids:
        try:
            metrics.store(con, sid)
        except Exception as e:
            print(f"Metrics of session {sid} skipped: {e}")
    con.close()
    print(f"Metrics updated for {len(sids)} sessions")
    py = sys.executable
    extra = ["--compare", *map(str, args.compare)] if args.compare else []
    subprocess.run([py, str(ROOT / "scripts" / "export_obsidian.py"), "--db", args.db, *extra], check=False)
    subprocess.run([py, str(ROOT / "scripts" / "dashboard.py"), "--db", args.db], check=False)


if __name__ == "__main__":
    main()
