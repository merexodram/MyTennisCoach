"""Serve, error and rally counting on a hand-made session.  python -m pytest tests"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mytenniscoach import db, metrics  # noqa: E402


def make(tmp_path):
    con = db.connect(tmp_path / "t.duckdb")
    con.execute("INSERT INTO sessions (session_id, played_on, kind, source, video_file, duration_s) "
                "VALUES (1, '2026-10-14', 'match', 'action_cam', 'x.mp4', 600)")
    # (point, [(t, hitter, stroke, in_court, bounce_y, outcome)], winner, end_reason)
    pts = [
        (1, [(10, "me", "serve", False, -8.0, "fault")], None, "fault"),                 # 1st serve fault
        (2, [(14, "me", "serve", False, -8.0, "fault")], None, "fault"),                 # 2nd serve fault: double fault
        (3, [(40, "me", "serve", True, -5.0, "winner")], "me", "winner"),                # unreturned 1st serve
        (4, [(70, "me", "serve", True, -5.0, "in_play"), (71, "opponent", "forehand", True, 10.0, "in_play"),
             (72, "me", "forehand", True, -11.0, "in_play"), (73, "opponent", "backhand", True, 9.0, "in_play"),
             (74, "me", "backhand", False, -13.5, "error_long")], "opponent", "unforced_error"),
        (5, [(100, "opponent", "serve", True, 5.0, "in_play"), (101, "me", "forehand", True, -10.0, "in_play"),
             (102, "opponent", "forehand", False, 13.0, "error_long")], "me", "unforced_error"),
    ]
    sid = 0
    for pid, shots, winner, reason in pts:
        con.execute("INSERT INTO points (point_id, session_id, seq, start_frame, end_frame, server, rally_length, winner, end_reason) "
                    "VALUES (?,1,?,0,0,?,?,?,?)", [pid, pid, shots[0][1], len(shots), winner, reason])
        for k, (t, who, stroke, inc, by, out) in enumerate(shots, 1):
            sid += 1
            con.execute("INSERT INTO shots (shot_id, session_id, point_id, seq, frame, t_s, hitter, stroke, contact_x_m, "
                        "contact_y_m, bounce_x_m, bounce_y_m, in_court, outcome) VALUES (?,1,?,?,?,?,?,?,1.0,?,1.0,?,?,?)",
                        [sid, pid, k, int(t * 30), float(t), who, stroke, 12.0 if who == "me" else -12.0, by, inc, out])
    return con


def test_counts(tmp_path):
    con = make(tmp_path)
    v = metrics.compute(con, 1)
    assert v["serves"][0] == 4
    assert v["double_faults"][0] == 1
    assert round(v["first_serve_in_pct"][0]) == 67          # 2 of 3 first serves in
    assert v["second_serve_in_pct"][0] == 0
    assert v["unreturned_serves"][0] == 1
    assert v["unforced_errors"][0] == 1 and v["errors_long"][0] == 1 and v["bh_errors"][0] == 1
    assert v["returns"][0] == 1 and v["return_in_pct"][0] == 100
    assert v["rally_max"][0] == 5
    metrics.store(con, 1)
    assert con.execute("SELECT count(*) FROM session_metrics WHERE session_id = 1").fetchone()[0] == len(v)


def test_coach_overrides(tmp_path):
    con = make(tmp_path)
    metrics.store(con, 1)
    f = tmp_path / "coach_input.json"
    f.write_text('{"session": {"opponent": "A"}, "metrics": {"double_faults": 3, "games_won": 6}}')
    metrics.apply_coach_input(con, 1, f)
    metrics.store(con, 1)                                   # recompute must keep what the coach was told
    got = dict(con.execute("SELECT metric, value FROM session_metrics WHERE source = 'coach'").fetchall())
    assert got == {"double_faults": 3.0, "games_won": 6.0}
    assert con.execute("SELECT opponent FROM sessions").fetchone()[0] == "A"
