"""Collect everything a coach needs to review one session.

    python scripts/coach_pack.py                # latest session
    python scripts/coach_pack.py --session 8

Writes outputs/coach/session_<id>/:
    pack.md       the facts: what was measured, how well, and how it compares with earlier sessions
    pack.json     the same as data
    stroke_*.jpg  picture strips of key strokes with the skeleton drawn

The pack contains facts only. The review itself (what they mean, what to work
on) is written by the coach from this pack and stored with save_review.py.
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from mytenniscoach import db, technique, video  # noqa: E402

OUT = ROOT / "outputs" / "coach"
CACHE = ROOT / "outputs" / "cache"


def rows(con, sql, params=()):
    cur = con.execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def md_table(items: list[dict]) -> str:
    if not items:
        return "_none_\n"
    cols = list(items[0])
    fmt = lambda v: "" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(r[c]) for c in cols) + " |" for r in items]
    return "\n".join(lines) + "\n"


STROKES_SQL = """
    SELECT stroke, count(*) AS strokes,
           count(in_court) AS with_bounce,
           round(100 * avg(CASE WHEN in_court THEN 1.0 WHEN in_court = false THEN 0.0 END)) AS in_pct,
           round(avg(speed_kmh)) AS avg_kmh,
           round(100 * avg(CASE WHEN depth = 'deep' THEN 1.0 WHEN depth IS NOT NULL THEN 0.0 END)) AS deep_pct,
           round(100 * avg(CASE WHEN depth = 'short' THEN 1.0 WHEN depth IS NOT NULL THEN 0.0 END)) AS short_pct,
           round(100 * avg(CASE WHEN direction = 'cross' THEN 1.0 WHEN direction IS NOT NULL THEN 0.0 END)) AS cross_pct,
           sum(CASE WHEN outcome LIKE 'error%' OR outcome = 'fault' THEN 1 ELSE 0 END) AS errors
    FROM shots WHERE session_id = ? AND hitter = ? GROUP BY ALL ORDER BY strokes DESC"""

TECH_SQL = """
    SELECT s.stroke, count(*) AS strokes,
           round(avg(p.contact_height_m), 2) AS contact_height_m, round(stddev_samp(p.contact_height_m), 2) AS height_spread,
           round(avg(p.contact_reach_m), 2) AS reach_m, round(stddev_samp(p.contact_reach_m), 2) AS reach_spread,
           round(avg(p.knee_flex_deg)) AS knee_deg, round(avg(p.elbow_angle_deg)) AS elbow_deg,
           round(avg(p.trunk_tilt_deg)) AS trunk_tilt_deg, round(avg(p.swing_duration_s), 2) AS swing_s,
           mode(p.stance) AS usual_stance,
           round(100 * avg(CASE WHEN p.off_hand_on_racket THEN 1.0 WHEN p.off_hand_on_racket = false THEN 0.0 END)) AS off_hand_on_racket_pct
    FROM pose_metrics p JOIN shots s USING (shot_id)
    WHERE s.session_id = ? GROUP BY ALL ORDER BY strokes DESC"""


def strip(session: dict, shot: dict, poses: dict, out: Path) -> bool:
    """Four moments of one stroke, cut around the player, skeleton drawn."""
    name = Path(session["video_file"]).stem
    source = next((p for p in (CACHE / f"{name}_work.mp4", Path(session["video_file"])) if p.exists()), None)
    if source is None:
        return False
    info = video.probe(source)
    reader = video.Reader(source)
    contact = int(round(shot["t_s"] * info.fps))
    tiles = []
    for dt in (-0.35, -0.15, 0.0, 0.2):
        f = contact + int(round(dt * info.fps))
        near = min(poses, key=lambda k: abs(k - f)) if poses else None
        got = reader.read(max(0, f), 1)
        if not got or near is None or abs(near - f) > 3:
            continue
        frame, kp = got[0], poses[near]
        technique.draw(frame, kp)
        ok = kp[:, 2] > 0.35
        if ok.sum() < 6:
            continue
        cx, cy = kp[ok, 0].mean(), kp[ok, 1].mean()
        half = int(max(80, 1.1 * (kp[ok, 1].max() - kp[ok, 1].min())))
        x0, y0 = int(max(0, cx - half)), int(max(0, cy - half))
        crop = frame[y0: y0 + 2 * half, x0: x0 + 2 * half]
        if crop.size == 0:
            continue
        crop = cv2.resize(crop, (320, 320))
        cv2.putText(crop, f"{dt:+.2f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
        tiles.append(crop)
    reader.close()
    if len(tiles) < 2:
        return False
    cv2.imwrite(str(out), np.hstack(tiles))
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--session", type=int)
    args = ap.parse_args()
    con = db.connect(args.db)
    sid = args.session or con.execute("SELECT max(session_id) FROM sessions").fetchone()[0]
    found = rows(con, "SELECT * FROM sessions WHERE session_id = ?", [sid])
    if not found:
        raise SystemExit(f"No session {sid}")
    session = found[0]
    try:
        notes = json.loads(session["notes"] or "{}")
    except Exception:
        notes = {"note": session["notes"]}

    pack = {
        "session": {k: (str(v) if k == "played_on" else v) for k, v in session.items() if k != "notes"},
        "quality": notes.get("quality", {}),
        "note": notes.get("note"),
        "rallies": rows(con, "SELECT seq AS rally, server, rally_length AS shots, winner, end_reason, "
                             "round((end_frame - start_frame) / ?, 1) AS seconds FROM points WHERE session_id = ? ORDER BY seq",
                        [session["fps"] or 30.0, sid]),
        "my_strokes": rows(con, STROKES_SQL, [sid, "me"]),
        "opponent_strokes": rows(con, STROKES_SQL, [sid, "opponent"]),
        "my_technique": rows(con, TECH_SQL, [sid]),
        "my_errors": rows(con, "SELECT round(t_s, 1) AS t_s, stroke, outcome, round(bounce_x_m, 1) AS bounce_x, "
                               "round(bounce_y_m, 1) AS bounce_y, confidence FROM shots WHERE session_id = ? AND hitter = 'me' "
                               "AND (outcome LIKE 'error%' OR outcome = 'fault') ORDER BY frame", [sid]),
        "my_contact_positions": rows(con, "SELECT stroke, round(avg(contact_x_m), 1) AS avg_x_m, round(avg(abs(contact_y_m)), 1) AS avg_depth_m, "
                                          "round(min(abs(contact_y_m)), 1) AS closest_to_net_m FROM shots WHERE session_id = ? AND hitter = 'me' "
                                          "AND contact_y_m IS NOT NULL GROUP BY ALL", [sid]),
        "clips": rows(con, "SELECT c.file, c.reason, s.stroke, round(s.t_s, 1) AS t_s FROM clips c JOIN shots s USING (shot_id) "
                           "WHERE c.session_id = ? ORDER BY s.frame", [sid]),
        # Earlier sessions of the same kind, for trends.
        "history": rows(con, """
            SELECT se.session_id, se.played_on, s.stroke, count(*) AS strokes,
                   round(100 * avg(CASE WHEN s.in_court THEN 1.0 WHEN s.in_court = false THEN 0.0 END)) AS in_pct,
                   round(avg(s.speed_kmh)) AS avg_kmh, round(avg(p.contact_height_m), 2) AS contact_height_m,
                   round(avg(p.knee_flex_deg)) AS knee_deg
            FROM sessions se JOIN shots s USING (session_id) LEFT JOIN pose_metrics p USING (shot_id)
            WHERE s.hitter = 'me' AND se.session_id < ? AND se.kind = ? AND se.source = ?
            GROUP BY ALL ORDER BY se.session_id DESC, strokes DESC LIMIT 40""", [sid, session["kind"], session["source"]]),
        "earlier_focus_points": rows(con, "SELECT created_on, focus_points FROM reviews WHERE session_id < ? "
                                          "ORDER BY review_id DESC LIMIT 3", [sid]),
    }
    for r in pack["history"]:
        r["played_on"] = str(r["played_on"])
    for r in pack["earlier_focus_points"]:
        r["created_on"] = str(r["created_on"])

    folder = OUT / f"session_{sid:04d}"
    folder.mkdir(parents=True, exist_ok=True)

    # Picture strips: every error, plus up to two of each stroke.
    strips = []
    name = Path(session["video_file"]).stem
    pose_file = CACHE / f"{name}_pose.pkl"
    if pose_file.exists():
        tech = pickle.loads(pose_file.read_bytes())["tech"]
        mine = rows(con, "SELECT shot_id, frame, t_s, stroke, outcome FROM shots WHERE session_id = ? AND hitter = 'me' ORDER BY frame", [sid])
        per_stroke: dict = {}
        for shot in mine:
            t = tech.get(shot["frame"])
            is_error = str(shot["outcome"]).startswith("error") or shot["outcome"] == "fault"
            if t is None or (not is_error and per_stroke.get(shot["stroke"], 0) >= 2) or len(strips) >= 12:
                continue
            f = folder / f"stroke_{shot['t_s']:07.2f}s_{shot['stroke']}{'_error' if is_error else ''}.jpg"
            if strip(session, shot, t.keypoints, f):
                per_stroke[shot["stroke"]] = per_stroke.get(shot["stroke"], 0) + 1
                strips.append({"file": f.name, "t_s": round(shot["t_s"], 2), "stroke": shot["stroke"], "outcome": shot["outcome"]})
    pack["picture_strips"] = strips
    con.close()

    (folder / "pack.json").write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    q = pack["quality"]
    md = [f"# Coach pack: session {sid}", "",
          f"- Played on {pack['session']['played_on']}, {session['kind']}, source {session['source']}, surface {session['surface'] or 'unknown'}",
          f"- Opponent: {session['opponent'] or 'not recorded'}",
          f"- Recording: {round(session['duration_s'] or 0)} s analysed, {session['width']}x{session['height']} at {round(session['fps'] or 0)} fps",
          "", "## How much the tracking saw", "",
          "Read every number below with this in mind.", ""]
    md += [f"- {k.replace('_', ' ')}: {v}" for k, v in q.items()] or ["- not recorded for this session"]
    for title, key in (("Rallies", "rallies"), ("My strokes", "my_strokes"), ("Opponent's strokes", "opponent_strokes"),
                       ("My technique by stroke (pose)", "my_technique"), ("Where I hit from", "my_contact_positions"),
                       ("My errors", "my_errors"), ("Clips kept", "clips"), ("Picture strips", "picture_strips"),
                       ("Earlier sessions (for trends)", "history"), ("Focus points from earlier reviews", "earlier_focus_points")):
        md += ["", f"## {title}", "", md_table(pack[key])]
    (folder / "pack.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Coach pack written: {folder}")


if __name__ == "__main__":
    main()
