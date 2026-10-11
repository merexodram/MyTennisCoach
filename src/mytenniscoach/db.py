"""Write pipeline results to the DuckDB database."""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_DB = ROOT / "data" / "tennis.duckdb"


def connect(path: str | Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA.read_text(encoding="utf-8"))
    return con


def _next_id(con, table: str, col: str) -> int:
    return con.execute(f"SELECT coalesce(max({col}), 0) + 1 FROM {table}").fetchone()[0]


def pipeline_version() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def save_session(con, info, shots, meta: dict) -> int:
    """Insert one processed video. Re-processing the same file replaces its rows."""
    old = con.execute("SELECT session_id FROM sessions WHERE video_file = ?", [str(info.path)]).fetchall()
    for (sid,) in old:
        con.execute("DELETE FROM pose_metrics WHERE shot_id IN (SELECT shot_id FROM shots WHERE session_id = ?)", [sid])
        for table in ("clips", "reviews", "shots", "points", "sessions"):
            con.execute(f"DELETE FROM {table} WHERE session_id = ?", [sid])

    sid = _next_id(con, "sessions", "session_id")
    con.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [sid, meta.get("played_on") or dt.date.today(), meta.get("kind", "reference"),
         meta.get("source", "broadcast"), meta.get("player"), meta.get("opponent"),
         meta.get("surface"), meta.get("location"), meta.get("camera_view", "broadcast"),
         info.fps, info.width, info.height, info.duration_s, str(info.path),
         pipeline_version(), meta.get("notes")],
    )
    me_default = meta.get("me_side", "near")
    me_by_rally = meta.get("me_by_rally", {})
    technique = meta.get("technique", {})

    def who(side, rally=None):
        return "me" if side == me_by_rally.get(rally, me_default) else "opponent"

    point_ids: dict[int, int] = {}
    for rally in sorted({s.rally for s in shots}):
        rs = [s for s in shots if s.rally == rally]
        pid = _next_id(con, "points", "point_id")
        point_ids[rally] = pid
        last = rs[-1]
        winner, reason = None, None
        if last.outcome == "winner":
            winner, reason = who(last.hitter, rally), "winner"
        elif last.outcome.startswith("error"):
            winner = "opponent" if who(last.hitter, rally) == "me" else "me"
            reason = "unforced_error"            # forced vs unforced needs Phase 4
        last_frame = last.bounce_frame or last.frame
        con.execute("INSERT INTO points VALUES (?,?,?,?,?,?,?,?,?)",
                    [pid, sid, rally, rs[0].frame, last_frame, who(rs[0].hitter, rally), len(rs), winner, reason])

    for s in shots:
        shid = _next_id(con, "shots", "shot_id")
        c, b = s.contact_xy_m or (None, None), s.bounce_xy_m or (None, None)
        con.execute(
            "INSERT INTO shots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [shid, sid, point_ids[s.rally], s.seq, s.frame, s.frame / info.fps, who(s.hitter, s.rally), s.stroke,
             c[0], c[1], b[0], b[1], s.in_court, s.speed_kmh, s.direction, s.depth, s.outcome, s.confidence],
        )
        t = technique.get(s.frame)
        if t is not None and t.pose_frames >= 5:
            con.execute(
                """INSERT INTO pose_metrics (shot_id, contact_height_m, contact_front_m, knee_flex_deg,
                       hip_shoulder_sep_deg, elbow_angle_deg, trunk_tilt_deg, stance, split_step, swing_duration_s,
                       contact_reach_m, shoulder_turn_deg, off_hand_on_racket, pose_frames)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [shid, t.contact_height_m, None, t.knee_flex_deg, t.hip_shoulder_sep_deg, t.elbow_angle_deg,
                 t.trunk_tilt_deg, t.stance, None, t.swing_duration_s, t.contact_reach_m, t.shoulder_turn_deg,
                 t.off_hand_on_racket, t.pose_frames],
            )
    return sid
