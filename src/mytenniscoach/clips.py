"""Keep a few seconds of video for the strokes worth looking at again.

The numbers in the database are enough for statistics, but a coach needs to
show a stroke now and then. After a session is analysed, short clips of the
flagged strokes are cut from the original recording; the recording itself can
then be deleted.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from . import render

ROOT = Path(__file__).resolve().parents[2]
CLIPS = ROOT / "data" / "clips"
BEFORE_S, AFTER_S = 1.5, 1.5


def choose(rows: list[dict], max_errors: int = 12, max_best: int = 3) -> list[tuple[dict, str]]:
    """Which of my shots to keep, and why. rows: dicts with shot_id, stroke, outcome, speed_kmh, in_court."""
    picked: dict[int, tuple[dict, str]] = {}
    errors = [r for r in rows if str(r["outcome"]).startswith("error") or r["outcome"] == "fault"]
    for r in errors[:max_errors]:
        picked[r["shot_id"]] = (r, "error_example")
    good = sorted((r for r in rows if r["in_court"] and r["speed_kmh"]), key=lambda r: -r["speed_kmh"])
    for r in good[:max_best]:
        picked.setdefault(r["shot_id"], (r, "best_example"))
    seen = set()
    for r in rows:                                        # one of each stroke as this session's reference
        if r["stroke"] not in seen and r["stroke"] != "unknown":
            seen.add(r["stroke"])
            picked.setdefault(r["shot_id"], (r, "monthly_reference"))
    return list(picked.values())


def cut(con, session_id: int, original: Path, log=print) -> int:
    """Cut and register clips for one session. Returns how many were written."""
    ffmpeg = render.find_ffmpeg()
    if ffmpeg is None:
        log("  no clips: ffmpeg not found")
        return 0
    cur = con.execute(
        "SELECT shot_id, t_s, stroke, outcome, speed_kmh, in_court FROM shots "
        "WHERE session_id = ? AND hitter = 'me' ORDER BY frame", [session_id])
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    folder = CLIPS / f"session_{session_id:04d}"
    folder.mkdir(parents=True, exist_ok=True)
    con.execute("DELETE FROM clips WHERE session_id = ?", [session_id])
    n = 0
    next_id = con.execute("SELECT coalesce(max(clip_id), 0) + 1 FROM clips").fetchone()[0]
    for row, reason in choose(rows):
        out = folder / f"shot_{row['shot_id']:06d}_{row['stroke']}_{reason}.mp4"
        start = max(0.0, row["t_s"] - BEFORE_S)
        cmd = [ffmpeg, "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", str(original), "-t", f"{BEFORE_S + AFTER_S:.2f}",
               "-an", "-vf", "scale=-2:'min(1080,ih)'", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", str(out)]
        if subprocess.call(cmd) != 0 or not out.exists():
            continue
        keep = None if reason == "monthly_reference" else dt.date.today() + dt.timedelta(days=180)
        con.execute("INSERT INTO clips VALUES (?,?,?,?,?,?)",
                    [next_id, session_id, row["shot_id"], str(out.relative_to(ROOT)), reason, keep])
        next_id += 1
        n += 1
    return n
